"""Authentication primitives: password hashing and JWT issuance/verification.

Everything in this module is stateless with respect to HTTP - it wraps
bcrypt directly for password hashing and python-jose for JWT encode/decode -
except for `get_current_user`, which is a FastAPI dependency that resolves
the bearer token on an incoming request into a database-backed User. That
dependency is re-exported as `CurrentUser` in core/dependencies.py for use
across the API routers.

Password hashing uses the `bcrypt` library directly rather than passlib:
passlib 1.7.4 is unmaintained and probes bcrypt's internals to detect its
version, which broke against bcrypt>=4.1 (hence this app's earlier
bcrypt<4.1 pin). Calling bcrypt directly removes that indirection entirely.
"""

from datetime import datetime, timedelta
import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.core.request_context import current_user_id
from app.database import get_db
from app.models.user import User
from app.schemas.user import TokenData

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# Check a plaintext password against a stored bcrypt hash.
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


# Hash a plaintext password for storage on the User model. bcrypt truncates input at 72
# bytes internally; passwords are also capped at 72 chars by UserCreate's schema validator
# so that limit is never silently hit here.
def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# Issue a short-lived JWT used to authenticate individual API requests.
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


# Issue a long-lived JWT (stored as an httpOnly cookie) used to mint new access tokens.
def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


# FastAPI dependency: decode the request's bearer token and load the matching active User.
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        if user_id is None or token_type != "access":
            raise credentials_exception
        token_data = TokenData(user_id=user_id)
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Drives the Postgres row-level-security policies set up in migration 015 - see
    # app/database.py's `begin` event listener for how this reaches the DB connection.
    current_user_id.set(user.id)
    return user


# Look up a user by email and verify their password; returns None on any mismatch.
async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
