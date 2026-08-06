"""Pydantic request/response schemas for the Receipts API.

These classes define the exact shape of JSON accepted and returned by the
/receipts endpoints in api/v1/receipts.py, independent of the SQLAlchemy
models in models/receipts.py - the same separation used by every other
module's schemas. `ReceiptUpdate` is deliberately narrow: it only exposes
the fields a human reviewing a low-confidence extraction would actually
correct (the three core fields plus the secondary ones), not processing-
pipeline internals like `processing_status` or `raw_extracted_text`, which
only the Celery task (services/receipt_parser.py via
workers/receipt_processing.py) is allowed to set.
"""

from pydantic import BaseModel, Field
from datetime import datetime, date
from decimal import Decimal

from app.models.enums import ReceiptProcessingStatus, ExtractionMethod


# One line item parsed off a receipt - see models/receipts.py:ReceiptLineItem.
class ReceiptLineItemResponse(BaseModel):
    id: str
    description: str | None
    quantity: Decimal | None
    unit_price: Decimal | None
    total_price: Decimal | None
    line_order: int | None

    class Config:
        from_attributes = True


# Shape returned for a single receipt, including whatever extraction produced. file_url is
# NOT read directly off the Receipt model - receipt files are never persisted to storage
# (OCR runs synchronously on the raw upload and only the extracted fields are kept), so
# file_url is always None; the field is kept for API-shape stability rather than removed.
class ReceiptResponse(BaseModel):
    id: str
    user_id: str
    original_filename: str
    file_url: str | None = None
    file_type: str
    file_size_bytes: int | None

    processing_status: ReceiptProcessingStatus
    processing_error: str | None
    processed_at: datetime | None
    extraction_method: ExtractionMethod | None

    merchant_name: str | None
    merchant_name_confidence: Decimal | None
    total_amount: Decimal | None
    total_amount_confidence: Decimal | None
    transaction_date: date | None
    transaction_date_confidence: Decimal | None

    tax_amount: Decimal | None
    subtotal_amount: Decimal | None
    payment_method: str | None
    receipt_number: str | None

    user_verified: bool
    verified_at: datetime | None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Same as ReceiptResponse but with line items attached - used by GET /receipts/{id}
# (the detail/review view) while the list endpoint returns the lighter ReceiptResponse.
class ReceiptDetailResponse(ReceiptResponse):
    line_items: list[ReceiptLineItemResponse] = []


# Payload for PUT /receipts/{id} - a human correcting extracted fields during review.
# Setting user_verified=True stamps verified_at server-side (see api/v1/receipts.py);
# it isn't a client-supplied timestamp so the record can't be backdated.
class ReceiptUpdate(BaseModel):
    merchant_name: str | None = Field(None, max_length=255)
    total_amount: Decimal | None = Field(None, ge=0)
    transaction_date: date | None = None
    tax_amount: Decimal | None = Field(None, ge=0)
    subtotal_amount: Decimal | None = Field(None, ge=0)
    payment_method: str | None = Field(None, max_length=50)
    receipt_number: str | None = Field(None, max_length=100)
    user_verified: bool | None = None


# One row of the response to POST /receipts/upload - one per uploaded file, since a batch
# upload (multiple files, e.g. a whole folder selected at once) creates a Receipt row and
# enqueues a Celery task per file rather than a single combined job. receipt_id/status are
# None and `error` is set when a file is rejected before a Receipt row is even created
# (unsupported type, over the size limit) - that failure is per-file, not a reason to
# reject the rest of the batch.
class ReceiptUploadResultItem(BaseModel):
    filename: str
    receipt_id: str | None = None
    status: ReceiptProcessingStatus | None = None
    error: str | None = None


class ReceiptUploadResponse(BaseModel):
    results: list[ReceiptUploadResultItem]


# Payload for POST /receipts/{id}/create-expense - turns a (usually just-reviewed) receipt
# into an Expense. category_id/bank_account_id are optional at this step since a receipt's
# extraction never determines a category on its own; merchant_name/amount/date always come
# from the receipt's own (possibly just-corrected) fields, not from this payload.
class CreateExpenseFromReceiptRequest(BaseModel):
    category_id: str | None = None
    bank_account_id: str | None = None
    description: str | None = None
