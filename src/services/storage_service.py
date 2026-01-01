"""File storage service with S3/GCS support."""

import os
import uuid
from typing import Optional, BinaryIO, Union
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import timedelta

import structlog

from src.config import settings

logger = structlog.get_logger()


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    async def upload(
        self,
        file_data: Union[bytes, BinaryIO],
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file and return its path/URL."""
        pass
    
    @abstractmethod
    async def download(self, file_path: str) -> bytes:
        """Download a file and return its contents."""
        pass
    
    @abstractmethod
    async def delete(self, file_path: str) -> bool:
        """Delete a file."""
        pass
    
    @abstractmethod
    async def exists(self, file_path: str) -> bool:
        """Check if a file exists."""
        pass
    
    @abstractmethod
    async def get_url(self, file_path: str, expires_in: int = 3600) -> str:
        """Get a (possibly signed) URL for the file."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""
    
    def __init__(self, base_dir: str = "./uploads"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    async def upload(
        self,
        file_data: Union[bytes, BinaryIO],
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file to local storage."""
        # Generate unique filename
        file_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        unique_filename = f"{uuid.uuid4()}.{file_ext}" if file_ext else str(uuid.uuid4())
        
        file_path = self.base_dir / unique_filename
        
        if isinstance(file_data, bytes):
            file_path.write_bytes(file_data)
        else:
            file_path.write_bytes(file_data.read())
        
        logger.info("File uploaded to local storage", path=str(file_path))
        return str(file_path)
    
    async def download(self, file_path: str) -> bytes:
        """Download a file from local storage."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        return path.read_bytes()
    
    async def delete(self, file_path: str) -> bool:
        """Delete a file from local storage."""
        path = Path(file_path)
        if path.exists():
            path.unlink()
            logger.info("File deleted from local storage", path=str(path))
            return True
        return False
    
    async def exists(self, file_path: str) -> bool:
        """Check if a file exists in local storage."""
        return Path(file_path).exists()
    
    async def get_url(self, file_path: str, expires_in: int = 3600) -> str:
        """Get a file URL (just returns the path for local storage)."""
        return file_path


class S3StorageBackend(StorageBackend):
    """AWS S3 storage backend."""
    
    def __init__(
        self,
        bucket_name: str,
        region: str = "us-east-1",
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ):
        self.bucket_name = bucket_name
        self.region = region
        self.endpoint_url = endpoint_url
        self._client = None
        self._access_key = access_key
        self._secret_key = secret_key
    
    async def _get_client(self):
        """Get or create S3 client."""
        if self._client is None:
            try:
                import aioboto3
                
                session = aioboto3.Session()
                self._client = await session.client(
                    "s3",
                    region_name=self.region,
                    aws_access_key_id=self._access_key,
                    aws_secret_access_key=self._secret_key,
                    endpoint_url=self.endpoint_url,
                ).__aenter__()
            except ImportError:
                raise ImportError("aioboto3 required for S3 storage. Install with: pip install aioboto3")
        return self._client
    
    async def upload(
        self,
        file_data: Union[bytes, BinaryIO],
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file to S3."""
        client = await self._get_client()
        
        # Generate unique key
        file_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        key = f"{uuid.uuid4()}.{file_ext}" if file_ext else str(uuid.uuid4())
        
        if isinstance(file_data, bytes):
            from io import BytesIO
            file_data = BytesIO(file_data)
        
        await client.upload_fileobj(
            file_data,
            self.bucket_name,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        
        logger.info("File uploaded to S3", bucket=self.bucket_name, key=key)
        return f"s3://{self.bucket_name}/{key}"
    
    async def download(self, file_path: str) -> bytes:
        """Download a file from S3."""
        client = await self._get_client()
        
        # Parse s3:// URL or use as key
        if file_path.startswith("s3://"):
            parts = file_path[5:].split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
        else:
            bucket = self.bucket_name
            key = file_path
        
        from io import BytesIO
        buffer = BytesIO()
        await client.download_fileobj(bucket, key, buffer)
        return buffer.getvalue()
    
    async def delete(self, file_path: str) -> bool:
        """Delete a file from S3."""
        client = await self._get_client()
        
        if file_path.startswith("s3://"):
            parts = file_path[5:].split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
        else:
            bucket = self.bucket_name
            key = file_path
        
        try:
            await client.delete_object(Bucket=bucket, Key=key)
            logger.info("File deleted from S3", bucket=bucket, key=key)
            return True
        except Exception as e:
            logger.error("Failed to delete from S3", error=str(e))
            return False
    
    async def exists(self, file_path: str) -> bool:
        """Check if a file exists in S3."""
        client = await self._get_client()
        
        if file_path.startswith("s3://"):
            parts = file_path[5:].split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
        else:
            bucket = self.bucket_name
            key = file_path
        
        try:
            await client.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False
    
    async def get_url(self, file_path: str, expires_in: int = 3600) -> str:
        """Get a pre-signed URL for the file."""
        client = await self._get_client()
        
        if file_path.startswith("s3://"):
            parts = file_path[5:].split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
        else:
            bucket = self.bucket_name
            key = file_path
        
        url = await client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return url


class GCSStorageBackend(StorageBackend):
    """Google Cloud Storage backend."""
    
    def __init__(
        self,
        bucket_name: str,
        credentials_path: Optional[str] = None,
    ):
        self.bucket_name = bucket_name
        self.credentials_path = credentials_path
        self._client = None
        self._bucket = None
    
    async def _get_bucket(self):
        """Get or create GCS bucket."""
        if self._bucket is None:
            try:
                from google.cloud import storage

                if self.credentials_path:
                    self._client = storage.Client.from_service_account_json(
                        self.credentials_path
                    )
                else:
                    self._client = storage.Client()

                if self._client is not None:
                    self._bucket = self._client.bucket(self.bucket_name)
            except ImportError:
                raise ImportError(
                    "google-cloud-storage required for GCS storage. "
                    "Install with: pip install google-cloud-storage"
                )
        return self._bucket
    
    async def upload(
        self,
        file_data: Union[bytes, BinaryIO],
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file to GCS."""
        import asyncio
        
        bucket = await self._get_bucket()
        
        # Generate unique blob name
        file_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        blob_name = f"{uuid.uuid4()}.{file_ext}" if file_ext else str(uuid.uuid4())
        
        blob = bucket.blob(blob_name)
        
        if isinstance(file_data, bytes):
            # Run synchronous upload in executor
            await asyncio.to_thread(
                blob.upload_from_string, file_data, content_type=content_type
            )
        else:
            await asyncio.to_thread(
                blob.upload_from_file, file_data, content_type=content_type
            )
        
        logger.info("File uploaded to GCS", bucket=self.bucket_name, blob=blob_name)
        return f"gs://{self.bucket_name}/{blob_name}"
    
    async def download(self, file_path: str) -> bytes:
        """Download a file from GCS."""
        import asyncio
        
        bucket = await self._get_bucket()
        
        if file_path.startswith("gs://"):
            parts = file_path[5:].split("/", 1)
            blob_name = parts[1] if len(parts) > 1 else ""
        else:
            blob_name = file_path
        
        blob = bucket.blob(blob_name)
        return await asyncio.to_thread(blob.download_as_bytes)
    
    async def delete(self, file_path: str) -> bool:
        """Delete a file from GCS."""
        import asyncio
        
        bucket = await self._get_bucket()
        
        if file_path.startswith("gs://"):
            parts = file_path[5:].split("/", 1)
            blob_name = parts[1] if len(parts) > 1 else ""
        else:
            blob_name = file_path
        
        try:
            blob = bucket.blob(blob_name)
            await asyncio.to_thread(blob.delete)
            logger.info("File deleted from GCS", bucket=self.bucket_name, blob=blob_name)
            return True
        except Exception as e:
            logger.error("Failed to delete from GCS", error=str(e))
            return False
    
    async def exists(self, file_path: str) -> bool:
        """Check if a file exists in GCS."""
        import asyncio
        
        bucket = await self._get_bucket()
        
        if file_path.startswith("gs://"):
            parts = file_path[5:].split("/", 1)
            blob_name = parts[1] if len(parts) > 1 else ""
        else:
            blob_name = file_path
        
        blob = bucket.blob(blob_name)
        return await asyncio.to_thread(blob.exists)
    
    async def get_url(self, file_path: str, expires_in: int = 3600) -> str:
        """Get a signed URL for the file."""
        import asyncio
        
        bucket = await self._get_bucket()
        
        if file_path.startswith("gs://"):
            parts = file_path[5:].split("/", 1)
            blob_name = parts[1] if len(parts) > 1 else ""
        else:
            blob_name = file_path
        
        blob = bucket.blob(blob_name)
        url = await asyncio.to_thread(
            blob.generate_signed_url,
            expiration=timedelta(seconds=expires_in),
        )
        return url


class StorageService:
    """Unified storage service that supports multiple backends."""
    
    _instance: Optional["StorageService"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self._backend: Optional[StorageBackend] = None
    
    def configure(
        self,
        backend: str = "local",
        **kwargs,
    ):
        """Configure the storage backend.
        
        Args:
            backend: Storage backend type ("local", "s3", "gcs")
            **kwargs: Backend-specific configuration
        """
        if backend == "local":
            base_dir = kwargs.get("base_dir", settings.UPLOAD_DIR)
            self._backend = LocalStorageBackend(base_dir)
        elif backend == "s3":
            bucket_name = kwargs.get("bucket_name")
            if not bucket_name:
                raise ValueError("bucket_name is required for S3 storage backend")
            self._backend = S3StorageBackend(
                bucket_name=bucket_name,
                region=kwargs.get("region", "us-east-1"),
                access_key=kwargs.get("access_key"),
                secret_key=kwargs.get("secret_key"),
                endpoint_url=kwargs.get("endpoint_url"),
            )
        elif backend == "gcs":
            bucket_name = kwargs.get("bucket_name")
            if not bucket_name:
                raise ValueError("bucket_name is required for GCS storage backend")
            self._backend = GCSStorageBackend(
                bucket_name=bucket_name,
                credentials_path=kwargs.get("credentials_path"),
            )
        else:
            raise ValueError(f"Unknown storage backend: {backend}")
        
        logger.info("Storage service configured", backend=backend)
    
    def _ensure_configured(self):
        """Ensure the storage backend is configured."""
        if self._backend is None:
            # Default to local storage
            self._backend = LocalStorageBackend(settings.UPLOAD_DIR)
    
    async def upload(
        self,
        file_data: Union[bytes, BinaryIO],
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file."""
        self._ensure_configured()
        assert self._backend is not None
        return await self._backend.upload(file_data, filename, content_type)

    async def download(self, file_path: str) -> bytes:
        """Download a file."""
        self._ensure_configured()
        assert self._backend is not None
        return await self._backend.download(file_path)

    async def delete(self, file_path: str) -> bool:
        """Delete a file."""
        self._ensure_configured()
        assert self._backend is not None
        return await self._backend.delete(file_path)

    async def exists(self, file_path: str) -> bool:
        """Check if a file exists."""
        self._ensure_configured()
        assert self._backend is not None
        return await self._backend.exists(file_path)

    async def get_url(self, file_path: str, expires_in: int = 3600) -> str:
        """Get a URL for the file."""
        self._ensure_configured()
        assert self._backend is not None
        return await self._backend.get_url(file_path, expires_in)


# Singleton instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get the storage service singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service