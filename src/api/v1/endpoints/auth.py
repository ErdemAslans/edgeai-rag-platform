"""Authentication endpoints."""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, CurrentUser
from src.api.v1.schemas.auth import (
    UserCreate,
    UserResponse,
    Token,
    TokenRefresh,
    ProfileUpdate,
    PasswordChange,
    EmailVerificationConfirm,
    TwoFactorSetupResponse,
    TwoFactorEnableRequest,
    TwoFactorVerifyRequest,
    TwoFactorDisableRequest,
)
from src.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    get_password_hash,
    verify_token,
    blacklist_token,
    create_email_verification_token,
    TOTP,
)
from src.config import settings
from src.db.repositories.user import UserRepository
from src.api.rate_limiter import brute_force_protection

import structlog

logger = structlog.get_logger()

router = APIRouter()
security = HTTPBearer()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Register a new user and return login token."""
    user_repo = UserRepository(db)
    
    existing_user = await user_repo.get_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    hashed_password = get_password_hash(user_data.password)
    verification_token = create_email_verification_token()
    
    user = await user_repo.create({
        "email": user_data.email,
        "hashed_password": hashed_password,
        "full_name": user_data.full_name,
        "email_verification_token": verification_token,
        "email_verification_sent_at": datetime.utcnow(),
    })
    await db.commit()
    
    logger.info(
        "User registered",
        user_id=str(user.id),
        email=user.email,
    )
    
    # Create tokens for auto-login
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(
        subject=str(user.id),
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    
    user_response = UserResponse.model_validate(user)
    user_response.permissions = user.get_permissions()
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        requires_2fa=False,
        user=user_response,
    )


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Login and get access token."""
    client_ip = _get_client_ip(request)
    identifier = f"{client_ip}:{form_data.username}"
    
    is_blocked, retry_after = await brute_force_protection.is_blocked(identifier)
    if is_blocked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )
    
    user_repo = UserRepository(db)
    
    user = await user_repo.get_by_email(form_data.username)
    if not user:
        await brute_force_protection.record_failed_attempt(identifier)
        remaining = await brute_force_protection.get_remaining_attempts(identifier)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Incorrect email or password. {remaining} attempts remaining.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not verify_password(form_data.password, user.hashed_password):
        await brute_force_protection.record_failed_attempt(identifier)
        remaining = await brute_force_protection.get_remaining_attempts(identifier)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Incorrect email or password. {remaining} attempts remaining.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
    
    await brute_force_protection.record_successful_attempt(identifier)
    
    if user.two_factor_enabled:
        return Token(
            access_token="",
            refresh_token="",
            token_type="bearer",
            requires_2fa=True,
        )
    
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(
        subject=str(user.id),
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    
    logger.info("User logged in", user_id=str(user.id))
    
    user_response = UserResponse.model_validate(user)
    user_response.permissions = user.get_permissions()
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        requires_2fa=False,
        user=user_response,
    )


@router.post("/verify-2fa", response_model=Token)
async def verify_2fa(
    request: Request,
    data: TwoFactorVerifyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Verify 2FA code and get access token."""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(str(data.user_id))
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    if not user.two_factor_enabled or not user.two_factor_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA not enabled for this user",
        )
    
    if data.is_backup_code:
        if not user.two_factor_backup_codes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No backup codes available",
            )
        
        code = data.code.upper().replace("-", "")
        backup_codes = [c.replace("-", "") for c in user.two_factor_backup_codes]
        
        if code not in backup_codes:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid backup code",
            )
        
        remaining_codes = [c for c in user.two_factor_backup_codes if c.replace("-", "") != code]
        await user_repo.update(user.id, {"two_factor_backup_codes": remaining_codes})
        await db.commit()
    else:
        if not TOTP.verify(user.two_factor_secret, data.code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2FA code",
            )
    
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(
        subject=str(user.id),
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    
    logger.info("User verified 2FA", user_id=str(user.id))
    
    user_response = UserResponse.model_validate(user)
    user_response.permissions = user.get_permissions()
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        requires_2fa=False,
        user=user_response,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: TokenRefresh,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Refresh access token using refresh token."""
    payload = verify_token(token_data.refresh_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    token_type = payload.get("type")
    
    if token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    blacklist_token(token_data.refresh_token)
    
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    new_refresh_token = create_refresh_token(
        subject=str(user.id),
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    
    user_response = UserResponse.model_validate(user)
    user_response.permissions = user.get_permissions()
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        user=user_response,
    )


@router.post("/logout")
async def logout(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    current_user: CurrentUser,
) -> dict:
    """Logout and blacklist the current token."""
    token = credentials.credentials
    blacklist_token(token)
    
    logger.info("User logged out", user_id=str(current_user.id))
    
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUser,
) -> UserResponse:
    """Get current user information."""
    response = UserResponse.model_validate(current_user)
    response.permissions = current_user.get_permissions()
    return response


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    profile_data: ProfileUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Update current user profile."""
    user_repo = UserRepository(db)
    
    update_data = {}
    if profile_data.full_name is not None:
        update_data["full_name"] = profile_data.full_name
    
    if update_data:
        updated_user = await user_repo.update(current_user.id, update_data)
        await db.commit()
        return UserResponse.model_validate(updated_user)
    
    return UserResponse.model_validate(current_user)


@router.post("/change-password")
async def change_password(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    password_data: PasswordChange,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Change current user password."""
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    
    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )
    
    user_repo = UserRepository(db)
    hashed_password = get_password_hash(password_data.new_password)
    await user_repo.update(current_user.id, {"hashed_password": hashed_password})
    await db.commit()
    
    blacklist_token(credentials.credentials)
    
    logger.info("User changed password", user_id=str(current_user.id))
    
    return {"message": "Password changed successfully. Please login again."}


@router.post("/verify-email")
async def verify_email(
    data: EmailVerificationConfirm,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Verify email with token."""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_verification_token(data.token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )
    
    if user.email_verification_sent_at:
        token_age = datetime.utcnow() - user.email_verification_sent_at
        if token_age > timedelta(hours=24):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification token has expired",
            )
    
    await user_repo.update(user.id, {
        "is_email_verified": True,
        "email_verification_token": None,
        "email_verification_sent_at": None,
    })
    await db.commit()
    
    logger.info("User verified email", user_id=str(user.id))
    
    return {"message": "Email verified successfully"}


@router.post("/resend-verification")
async def resend_verification_email(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Resend email verification token."""
    if current_user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified",
        )
    
    user_repo = UserRepository(db)
    verification_token = create_email_verification_token()
    
    await user_repo.update(current_user.id, {
        "email_verification_token": verification_token,
        "email_verification_sent_at": datetime.utcnow(),
    })
    await db.commit()
    
    logger.info("Resent verification email", user_id=str(current_user.id))
    
    return {"message": "Verification email sent"}


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_2fa(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TwoFactorSetupResponse:
    """Initialize 2FA setup."""
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is already enabled",
        )
    
    secret = TOTP.generate_secret()
    backup_codes = TOTP.generate_backup_codes()
    uri = TOTP.get_totp_uri(secret, current_user.email)
    
    user_repo = UserRepository(db)
    await user_repo.update(current_user.id, {
        "two_factor_secret": secret,
        "two_factor_backup_codes": backup_codes,
    })
    await db.commit()
    
    return TwoFactorSetupResponse(
        secret=secret,
        uri=uri,
        backup_codes=backup_codes,
    )


@router.post("/2fa/enable")
async def enable_2fa(
    data: TwoFactorEnableRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Enable 2FA after verifying code."""
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is already enabled",
        )
    
    if not current_user.two_factor_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA setup not initiated. Call /2fa/setup first.",
        )
    
    if not TOTP.verify(current_user.two_factor_secret, data.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code",
        )
    
    user_repo = UserRepository(db)
    await user_repo.update(current_user.id, {"two_factor_enabled": True})
    await db.commit()
    
    logger.info("User enabled 2FA", user_id=str(current_user.id))
    
    return {"message": "2FA enabled successfully"}


@router.post("/2fa/disable")
async def disable_2fa(
    data: TwoFactorDisableRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Disable 2FA."""
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled",
        )
    
    if not verify_password(data.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password",
        )
    
    if not TOTP.verify(current_user.two_factor_secret, data.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 2FA code",
        )
    
    user_repo = UserRepository(db)
    await user_repo.update(current_user.id, {
        "two_factor_enabled": False,
        "two_factor_secret": None,
        "two_factor_backup_codes": None,
    })
    await db.commit()
    
    logger.info("User disabled 2FA", user_id=str(current_user.id))
    
    return {"message": "2FA disabled successfully"}