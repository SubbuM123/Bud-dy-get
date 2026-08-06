"""SQLAlchemy ORM model for user-defined expense categories (Expense Tracker module).

Categories are per-user rows (not a global enum, unlike e.g. RetirementAccountType) since
users can rename, recolor, or add their own - only the *starter set* seeded for every new
user is fixed, via DEFAULT_CATEGORIES/seed_default_categories below, called once from
api/v1/auth.py's register endpoint right after a User row is created. is_system marks
those starter rows so the UI can (optionally) treat them differently from a user's custom
ones, but nothing in the backend actually prevents editing or deleting a system category -
"system" here just means "how it got there," not a protected/immutable flag.
"""

from datetime import datetime
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, Numeric, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base


class ExpenseCategory(Base):
    """A spending category (e.g. "Groceries") a user can assign expenses to."""

    __tablename__ = "expense_categories"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_expense_category_user_name"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Hex color (e.g. "#22c55e") used for chart series/badges, and a lucide-react icon name
    # (e.g. "shopping-cart") used by the frontend's CategoryPicker - both purely cosmetic,
    # validated only for shape (schemas/expense_categories.py), never for a specific palette.
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    monthly_budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # True for the starter categories created by seed_default_categories at registration -
    # see this module's docstring for what that flag does and doesn't mean.
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="expense_categories")
    expenses = relationship("Expense", back_populates="category")


# (name, color, icon) for every category a new user starts with - a smaller, simpler
# 6-category set requested directly over the original 10 (Groceries/Restaurants/
# Transportation/Entertainment/Shopping/Utilities/Healthcare/Travel/Subscriptions/Other).
# Colors are the first 5 slots of the app's validated categorical palette (same fixed hue
# order already used by frontend/src/components/charts/RetirementGrowthChart.tsx - blue/
# orange/aqua/yellow/magenta/green/violet/red - run through the data-viz skill's
# validate_palette.js; see docs/progress.md for the validation run), reused in the same
# sequence the original 10-category list already used them in, so no re-validation is
# needed. "Other" keeps the same muted neutral tone the miscellaneous bucket always had -
# it falls outside the validated hue set on purpose, same reasoning as before. icon values
# are lucide-react component names in kebab-case, matching how frontend/src/components/
# layout/Sidebar.tsx already names its own icons for consistency across the app. Since
# categories are per-user and freely editable (see this module's docstring), this list
# only affects what a *newly registered* user starts with - existing users' categories
# are unaffected by changing it.
DEFAULT_CATEGORIES: list[tuple[str, str, str]] = [
    ("Food", "#2a78d6", "shopping-cart"),
    ("Travel", "#eb6834", "plane"),
    ("Entertainment", "#1baf7a", "film"),
    ("Lifestyle/Fitness", "#eda100", "dumbbell"),
    ("Restaurants/Family", "#e87ba4", "utensils"),
    ("Other", "#64748b", "more-horizontal"),
]


# Create the starter category set for a newly registered user. Called once, right after
# the User row is committed in api/v1/auth.py's register endpoint - not a migration-time
# seed, since categories are per-user and the user doesn't exist yet at migration time.
async def seed_default_categories(db: AsyncSession, user_id: str) -> None:
    for name, color, icon in DEFAULT_CATEGORIES:
        db.add(
            ExpenseCategory(
                user_id=user_id, name=name, color=color, icon=icon, is_system=True
            )
        )
    await db.commit()
