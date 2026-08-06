"""Upload, review, and lifecycle endpoints for the Receipts resource (Expense Tracker module).

Every route scopes its query to the authenticated user via `_get_owned_receipt`, matching
every other module's ownership-scoping pattern in this app. OCR extraction runs synchronously
during upload - no file is persisted to storage, only the extracted fields are saved.
"""

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.dependencies import DBSession, CurrentUser
from app.models.enums import ReceiptProcessingStatus
from app.models.receipts import Receipt
from app.models.expenses import Expense
from app.schemas.receipts import (
    ReceiptResponse,
    ReceiptDetailResponse,
    ReceiptLineItemResponse,
    ReceiptUpdate,
    ReceiptUploadResponse,
    ReceiptUploadResultItem,
    CreateExpenseFromReceiptRequest,
)
from app.schemas.expenses import ExpenseResponse
from app.services.receipt_parser import (
    extract_from_image,
    extract_from_pdf,
    should_flag_for_review,
    ExtractionResult,
)

router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/heic",
    "image/heif",
    "application/pdf",
}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
_PDF_CONTENT_TYPES = {"application/pdf"}


def _apply_extraction(receipt: Receipt, extraction: ExtractionResult) -> None:
    """Copy an ExtractionResult's fields onto the Receipt row."""
    receipt.raw_extracted_text = extraction.raw_text
    receipt.extraction_method = extraction.extraction_method
    receipt.merchant_name = extraction.merchant_name
    receipt.merchant_name_confidence = extraction.merchant_name_confidence
    receipt.total_amount = extraction.total_amount
    receipt.total_amount_confidence = extraction.total_amount_confidence
    receipt.transaction_date = extraction.transaction_date
    receipt.transaction_date_confidence = extraction.transaction_date_confidence
    receipt.tax_amount = extraction.tax_amount


async def _get_owned_receipt(db: DBSession, receipt_id: str, user_id: str) -> Receipt:
    """Fetch a receipt by id, scoped to `user_id`; raise 404 if missing or not owned."""
    result = await db.execute(
        select(Receipt)
        .options(selectinload(Receipt.line_items))
        .where(Receipt.id == receipt_id, Receipt.user_id == user_id)
    )
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


def _receipt_to_response(receipt: Receipt) -> ReceiptResponse:
    """Build a ReceiptResponse from a Receipt row."""
    response = ReceiptResponse.model_validate(receipt)
    response.file_url = None
    return response


def _receipt_to_detail_response(receipt: Receipt) -> ReceiptDetailResponse:
    data = ReceiptResponse.model_validate(receipt).model_dump()
    data["file_url"] = None
    data["line_items"] = [
        ReceiptLineItemResponse.model_validate(item) for item in receipt.line_items
    ]
    return ReceiptDetailResponse(**data)


@router.post("/upload", response_model=ReceiptUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_receipts(
    current_user: CurrentUser,
    db: DBSession,
    files: list[UploadFile] = File(...),
):
    """Upload and process receipt files. OCR runs synchronously; no files are stored."""
    results: list[ReceiptUploadResultItem] = []

    for upload in files:
        content_type = upload.content_type or "application/octet-stream"
        if content_type not in ALLOWED_CONTENT_TYPES:
            results.append(
                ReceiptUploadResultItem(
                    filename=upload.filename or "unknown",
                    error=f"Unsupported file type: {content_type}",
                )
            )
            continue

        file_bytes = await upload.read()
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            results.append(
                ReceiptUploadResultItem(
                    filename=upload.filename or "unknown",
                    error="File exceeds the 10MB upload limit",
                )
            )
            continue
        if len(file_bytes) == 0:
            results.append(
                ReceiptUploadResultItem(filename=upload.filename or "unknown", error="Empty file")
            )
            continue

        filename = upload.filename or "receipt"

        receipt = Receipt(
            user_id=current_user.id,
            original_filename=filename,
            file_key=None,
            file_type=content_type,
            file_size_bytes=len(file_bytes),
            processing_status=ReceiptProcessingStatus.PROCESSING,
        )
        db.add(receipt)
        await db.commit()
        await db.refresh(receipt)

        try:
            if content_type in _PDF_CONTENT_TYPES:
                extraction = extract_from_pdf(file_bytes)
            else:
                extraction = extract_from_image(file_bytes)

            _apply_extraction(receipt, extraction)
            receipt.processed_at = datetime.utcnow()
            receipt.processing_status = (
                ReceiptProcessingStatus.NEEDS_REVIEW
                if should_flag_for_review(extraction)
                else ReceiptProcessingStatus.COMPLETED
            )
        except Exception as exc:
            receipt.processing_status = ReceiptProcessingStatus.FAILED
            receipt.processing_error = str(exc)
            receipt.processed_at = datetime.utcnow()

        await db.commit()
        await db.refresh(receipt)

        results.append(
            ReceiptUploadResultItem(
                filename=filename, receipt_id=receipt.id, status=receipt.processing_status
            )
        )

    return ReceiptUploadResponse(results=results)


@router.get("", response_model=list[ReceiptResponse])
async def list_receipts(
    current_user: CurrentUser,
    db: DBSession,
    processing_status: ReceiptProcessingStatus | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    """List the authenticated user's receipts, optionally filtered."""
    query = select(Receipt).where(Receipt.user_id == current_user.id)
    if processing_status is not None:
        query = query.where(Receipt.processing_status == processing_status)
    if start_date is not None:
        query = query.where(Receipt.created_at >= start_date)
    if end_date is not None:
        query = query.where(Receipt.created_at <= end_date)
    query = query.order_by(Receipt.created_at.desc())

    result = await db.execute(query)
    receipts = result.scalars().all()
    return [_receipt_to_response(r) for r in receipts]


@router.get("/{receipt_id}", response_model=ReceiptDetailResponse)
async def get_receipt(receipt_id: str, current_user: CurrentUser, db: DBSession):
    """Fetch a single receipt with its line items."""
    receipt = await _get_owned_receipt(db, receipt_id, current_user.id)
    return _receipt_to_detail_response(receipt)


@router.put("/{receipt_id}", response_model=ReceiptResponse)
async def update_receipt(
    receipt_id: str,
    receipt_data: ReceiptUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    """Correct extracted fields or mark a receipt verified during human review."""
    receipt = await _get_owned_receipt(db, receipt_id, current_user.id)

    update_data = receipt_data.model_dump(exclude_unset=True, exclude={"user_verified"})
    for field, value in update_data.items():
        setattr(receipt, field, value)
        confidence_field = f"{field}_confidence"
        if hasattr(receipt, confidence_field):
            setattr(receipt, confidence_field, Decimal("1.00"))

    if receipt_data.user_verified is True and not receipt.user_verified:
        receipt.user_verified = True
        receipt.verified_at = datetime.utcnow()
        if receipt.processing_status in (
            ReceiptProcessingStatus.NEEDS_REVIEW,
            ReceiptProcessingStatus.FAILED,
        ):
            receipt.processing_status = ReceiptProcessingStatus.COMPLETED
    elif receipt_data.user_verified is False:
        receipt.user_verified = False
        receipt.verified_at = None

    await db.commit()
    await db.refresh(receipt)
    return _receipt_to_response(receipt)


@router.delete("/{receipt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_receipt(receipt_id: str, current_user: CurrentUser, db: DBSession):
    """Delete a receipt. Any Expense created from this receipt is kept."""
    receipt = await _get_owned_receipt(db, receipt_id, current_user.id)
    await db.delete(receipt)
    await db.commit()


@router.post("/{receipt_id}/reprocess", response_model=ReceiptResponse)
async def reprocess_receipt(receipt_id: str, current_user: CurrentUser, db: DBSession):
    """Reprocessing is not supported - the original file is not stored. Re-upload instead."""
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Reprocessing is not available - files are not stored. Please re-upload the receipt.",
    )


@router.post(
    "/{receipt_id}/create-expense",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_expense_from_receipt(
    receipt_id: str,
    payload: CreateExpenseFromReceiptRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Turn a receipt's fields into an Expense."""
    receipt = await _get_owned_receipt(db, receipt_id, current_user.id)

    if receipt.merchant_name is None or receipt.total_amount is None or receipt.transaction_date is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Receipt is missing merchant name, total, or date - correct it via "
            "PUT /receipts/{id} before creating an expense from it",
        )

    expense = Expense(
        user_id=current_user.id,
        receipt_id=receipt.id,
        merchant_name=receipt.merchant_name,
        amount=receipt.total_amount,
        expense_date=receipt.transaction_date,
        category_id=payload.category_id,
        bank_account_id=payload.bank_account_id,
        description=payload.description,
    )
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return expense
