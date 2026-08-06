"""Registration, login, refresh, and logout endpoints.

This router handles the unauthenticated part of the auth flow: creating a
new account, exchanging credentials for a JWT access token, exchanging the
httpOnly refresh-token cookie (set on login) for a new access token, and
clearing that cookie on logout.
"""

from jose import JWTError, jwt
from fastapi import APIRouter, HTTPException, Request, status, Response
from sqlalchemy import select

from app.config import get_settings
from app.core.dependencies import DBSession
from app.core.rate_limit import rate_limit
from app.core.auth import (
    get_password_hash,
    create_access_token,
    create_refresh_token,
    authenticate_user,
)
from app.models.user import User
from app.models.expense_categories import seed_default_categories
from app.schemas.user import UserCreate, UserResponse, Token, LoginRequest

router = APIRouter()
settings = get_settings()


# Create a new user account after checking the email isn't already registered.
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@rate_limit("10/minute")
async def register(request: Request, user_data: UserCreate, db: DBSession):
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Give every new user the same starter category set the Expense Tracker module
    # (Phase 3) expects to already exist - see models/expense_categories.py's docstring
    # for why this happens here instead of at migration time.
    await seed_default_categories(db, user.id)

    return user


# Verify credentials, issue an access token, and set the refresh token as an httpOnly cookie.
@router.post("/login", response_model=Token)
@rate_limit("10/minute")
async def login(request: Request, login_data: LoginRequest, response: Response, db: DBSession):
    user = await authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=60 * 60 * 24 * 7,
    )

    return Token(access_token=access_token)


# Exchange the httpOnly refresh-token cookie (set on login) for a new access token, so a
# session can outlive the 15-minute access token without forcing a fresh login every time.
@router.post("/refresh", response_model=Token)
async def refresh_token(request: Request, db: DBSession):
    invalid_token_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )

    token = request.cookies.get("refresh_token")
    if not token:
        raise invalid_token_exception

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        raise invalid_token_exception

    user_id = payload.get("sub")
    if user_id is None or payload.get("type") != "refresh":
        raise invalid_token_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise invalid_token_exception

    return Token(access_token=create_access_token(data={"sub": user.id}))


# Clear the refresh-token cookie; the client is responsible for discarding its access token.
@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully"}
