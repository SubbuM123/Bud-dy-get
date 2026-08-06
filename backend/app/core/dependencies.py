"""Reusable FastAPI dependency type aliases for route handlers.

Every authenticated endpoint across the API routers needs both a database
session and the current user, so this module wraps the underlying
`Depends(get_db)` / `Depends(get_current_user)` calls in `Annotated` aliases.
Route handlers then declare parameters as `db: DBSession` or
`current_user: CurrentUser` instead of repeating the Depends() boilerplate
in every function signature.
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.auth import get_current_user
from app.models.user import User

# An injected async database session, scoped to a single request.
DBSession = Annotated[AsyncSession, Depends(get_db)]

# The authenticated User resolved from the request's bearer token.
CurrentUser = Annotated[User, Depends(get_current_user)]
