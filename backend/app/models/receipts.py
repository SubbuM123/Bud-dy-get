"""SQLAlchemy ORM models for receipt upload and extraction (Expense Tracker module).

This file defines two tables: Receipt (one row per uploaded photo or PDF - the file's
storage location, its processing lifecycle, and the three core fields this app actually
cares about extracting: merchant name, total amount, and transaction date, each paired
with a confidence score so the frontend can flag low-confidence fields for user review)
and ReceiptLineItem (best-effort per-item extraction, not required for a receipt to be
usable - Expense records only ever need the three core fields off the parent Receipt).
Confidence scores and the raw OCR/extracted text are kept on the row itself rather than a
separate audit table since there's exactly one extraction attempt's worth of data to keep
per receipt in v1 (reprocessing overwrites rather than versions - see
api/v1/receipts.py's /reprocess endpoint). See docs/phase3-plan.md for the full data model
and the OCR/PDF extraction pipeline this feeds.
"""

from datetime import datetime, date
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, Date, Numeric, Integer, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ReceiptProcessingStatus, ExtractionMethod


# SQLAlchemy's Enum(SomeEnum) binds using the Python enum member's *name* by default, not
# its *value* - see models/bank_accounts.py's _enum_values for the full explanation.
def _enum_values(enum_cls):
    return [member.value for member in enum_cls]


class Receipt(Base):
    """An uploaded receipt photo or PDF, plus whatever fields extraction produced from it."""

    __tablename__ = "receipts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Upload info - file_key was the S3/MinIO object key from when receipt files were
    # persisted to storage; OCR now runs synchronously on the raw upload and no file is
    # kept (see api/v1/receipts.py), so this is always null on new rows. Kept for schema
    # stability rather than dropped.
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Processing lifecycle - see enums.ReceiptProcessingStatus for what each state means.
    processing_status: Mapped[ReceiptProcessingStatus] = mapped_column(
        SQLEnum(ReceiptProcessingStatus, values_callable=_enum_values),
        default=ReceiptProcessingStatus.PENDING,
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Raw extraction output, kept for debugging a bad extraction and for /reprocess to
    # re-run field identification without re-downloading/re-OCRing the source file.
    raw_extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[ExtractionMethod | None] = mapped_column(
        SQLEnum(ExtractionMethod, values_callable=_enum_values), nullable=True
    )

    # Core extracted fields - the three things docs/phase3-plan.md prioritizes: who was
    # paid, how much, and when. Each has a paired 0.00-1.00 confidence score (see
    # services/receipt_parser.py) so the frontend can badge low-confidence fields instead
    # of silently trusting a bad OCR read.
    merchant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    merchant_name_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_amount_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    transaction_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    transaction_date_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)

    # Secondary fields - best-effort, never block a receipt from being usable.
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    subtotal_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    receipt_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Whether a human has looked at and confirmed/corrected the extracted fields. An
    # expense can be created from an unverified receipt (nothing here blocks that, unlike
    # e.g. retirement's contribution limits), but the UI leads with unverified low-
    # confidence receipts to encourage a quick review first.
    user_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="receipts")
    line_items = relationship(
        "ReceiptLineItem", back_populates="receipt", cascade="all, delete-orphan"
    )
    # A receipt can produce at most one Expense (see models/expenses.py); nulled out (not
    # cascade-deleted) if the receipt is removed, since the expense record itself - the
    # user's categorized spending history - should outlive its source document.
    expenses = relationship("Expense", back_populates="receipt")


class ReceiptLineItem(Base):
    """One product/service line parsed off a receipt - best-effort, not required for use.

    Nothing else in the app reads this table yet in v1 (Expense only stores the receipt's
    total, not a per-item breakdown) - it exists so line-item text isn't thrown away during
    extraction, ready for a future per-item categorization feature without a schema change.
    """

    __tablename__ = "receipt_line_items"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    receipt_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    line_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    receipt = relationship("Receipt", back_populates="line_items")
