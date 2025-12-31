"""Security utilities for JWT, password hashing, 2FA, and token blacklist."""

import secrets
import hashlib
import time
import base64
import hmac
import struct
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from collections import OrderedDict

from jose import jwt, JWTError
import bcrypt

from src.config import settings


class TokenBlacklist:
    """In-memory token blacklist with automatic cleanup."""
    
    MAX_ENTRIES = 10000
    
    def __init__(self):
        self._blacklist: OrderedDict[str, float] = OrderedDict()
    
    def _get_token_hash(self, token: str) -> str:
        """Get hash of token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()[:32]
    
    def add(self, token: str, expires_at: float) -> None:
        """Add token to blacklist."""
        token_hash = self._get_token_hash(token)
        self._blacklist[token_hash] = expires_at
        
        if len(self._blacklist) > self.MAX_ENTRIES:
            oldest_key = next(iter(self._blacklist))
            del self._blacklist[oldest_key]
    
    def is_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted."""
        token_hash = self._get_token_hash(token)
        
        if token_hash not in self._blacklist:
            return False
        
        expires_at = self._blacklist[token_hash]
        if time.time() > expires_at:
            del self._blacklist[token_hash]
            return False
        
        return True
    
    def cleanup(self) -> int:
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, exp in self._blacklist.items() if now > exp]
        for k in expired:
            del self._blacklist[k]
        return len(expired)


token_blacklist = TokenBlacklist()


class TOTP:
    """Time-based One-Time Password generator and validator."""
    
    DIGITS = 6
    PERIOD = 30
    ALGORITHM = "sha1"
    
    @classmethod
    def generate_secret(cls) -> str:
        """Generate a new TOTP secret."""
        secret_bytes = secrets.token_bytes(20)
        return base64.b32encode(secret_bytes).decode("utf-8").rstrip("=")
    
    @classmethod
    def generate_backup_codes(cls, count: int = 10) -> List[str]:
        """Generate backup codes for 2FA recovery."""
        codes = []
        for _ in range(count):
            code = secrets.token_hex(4).upper()
            codes.append(f"{code[:4]}-{code[4:]}")
        return codes
    
    @classmethod
    def get_totp_uri(cls, secret: str, email: str, issuer: str = "EdgeAI") -> str:
        """Generate TOTP URI for QR code."""
        import urllib.parse
        params = {
            "secret": secret,
            "issuer": issuer,
            "algorithm": cls.ALGORITHM.upper(),
            "digits": cls.DIGITS,
            "period": cls.PERIOD,
        }
        query = urllib.parse.urlencode(params)
        return f"otpauth://totp/{issuer}:{email}?{query}"
    
    @classmethod
    def _decode_secret(cls, secret: str) -> bytes:
        """Decode base32 secret."""
        padding = 8 - (len(secret) % 8)
        if padding != 8:
            secret += "=" * padding
        return base64.b32decode(secret.upper())
    
    @classmethod
    def _generate_hotp(cls, secret: bytes, counter: int) -> str:
        """Generate HOTP value."""
        counter_bytes = struct.pack(">Q", counter)
        
        if cls.ALGORITHM == "sha1":
            import hashlib
            hmac_hash = hmac.new(secret, counter_bytes, hashlib.sha1).digest()
        else:
            raise ValueError(f"Unsupported algorithm: {cls.ALGORITHM}")
        
        offset = hmac_hash[-1] & 0x0F
        binary = struct.unpack(">I", hmac_hash[offset:offset + 4])[0]
        binary &= 0x7FFFFFFF
        
        otp = binary % (10 ** cls.DIGITS)
        return str(otp).zfill(cls.DIGITS)
    
    @classmethod
    def generate(cls, secret: str, timestamp: Optional[float] = None) -> str:
        """Generate TOTP code for current time."""
        if timestamp is None:
            timestamp = time.time()
        counter = int(timestamp) // cls.PERIOD
        secret_bytes = cls._decode_secret(secret)
        return cls._generate_hotp(secret_bytes, counter)
    
    @classmethod
    def verify(cls, secret: str, code: str, window: int = 1) -> bool:
        """Verify TOTP code with time window tolerance."""
        if len(code) != cls.DIGITS:
            return False
        
        timestamp = time.time()
        secret_bytes = cls._decode_secret(secret)
        current_counter = int(timestamp) // cls.PERIOD
        
        for offset in range(-window, window + 1):
            counter = current_counter + offset
            expected = cls._generate_hotp(secret_bytes, counter)
            if hmac.compare_digest(code, expected):
                return True
        
        return False


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    password_bytes = plain_password.encode('utf-8')[:72]
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    """Hash a plain password."""
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "sub": subject,
        "exp": expire,
        "type": "access",
        "jti": secrets.token_hex(16),
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    
    return encoded_jwt


def create_refresh_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT refresh token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    to_encode = {
        "sub": subject,
        "exp": expire,
        "type": "refresh",
        "jti": secrets.token_hex(16),
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    
    return encoded_jwt


def verify_token(token: str, check_blacklist: bool = True) -> Optional[Dict[str, Any]]:
    """Verify a JWT token and return the payload."""
    try:
        if check_blacklist and token_blacklist.is_blacklisted(token):
            return None
        
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None


def blacklist_token(token: str) -> bool:
    """Add a token to the blacklist."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": False},
        )
        exp = payload.get("exp", 0)
        token_blacklist.add(token, exp)
        return True
    except JWTError:
        return False


def create_email_verification_token() -> str:
    """Create a secure email verification token."""
    return secrets.token_urlsafe(32)


def create_password_reset_token() -> str:
    """Create a secure password reset token."""
    return secrets.token_urlsafe(32)