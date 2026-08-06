"""Receipt parsing: OCR/text extraction plus regex-and-heuristic field identification.

Handles both image files (via Tesseract, through pytesseract) and PDF files (via
pdfplumber for text-based PDFs, with a Tesseract-on-rasterized-pages fallback for
scanned/image-only PDFs - see extract_from_pdf). The three fields
docs/phase3-plan.md prioritizes - merchant name, total amount, transaction date - are each
identified independently and paired with a 0.0-1.0 confidence score, so
workers/receipt_processing.py can decide whether a receipt is good enough to mark
`completed` outright or needs a human to look at it (`needs_review`) before it becomes an
Expense. Every identify_* function is a pure function of the extracted text - no
database/FastAPI/Celery dependency - so this module is directly unit-testable against
fixed sample text without a real image or a running worker (see tests/test_receipt_parser.py).

This is heuristic, not ML-based: keyword-anchored regex matches (e.g. "TOTAL:" directly
before a dollar amount) get high confidence, format-only matches (a dollar-looking number
with no anchoring keyword) get medium confidence, and best-effort fallbacks (e.g. "the
largest dollar amount on the receipt is probably the total") get low confidence. See
"OCR Accuracy Considerations" in docs/phase3-plan.md for the target accuracy per field and
the future ML-based improvement path this is deliberately not attempting in v1.
"""

import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image, ImageFilter, ImageOps
from dateutil import parser as dateutil_parser

from app.models.enums import ExtractionMethod

# Below this confidence, a core field (merchant/total/date) is considered untrustworthy
# enough that the receipt as a whole should be flagged 'needs_review' rather than
# 'completed' - see should_flag_for_review and workers/receipt_processing.py.
REVIEW_CONFIDENCE_THRESHOLD = 0.6

# Matches a dollar amount like "1,234.56" or "$12.00" (the "$" and thousands separators
# are optional; the two decimal digits are not - receipts don't print fractional cents).
_AMOUNT_PATTERN = r'\$?\s*(\d{1,3}(?:,\d{3})*\.\d{2})'

_TOTAL_KEYWORD_PATTERNS = [
    (re.compile(r'(?i)grand\s*total' + r'.{0,40}?' + _AMOUNT_PATTERN), 0.95),
    (re.compile(r'(?i)total\s*due' + r'.{0,40}?' + _AMOUNT_PATTERN), 0.95),
    (re.compile(r'(?i)amount\s*due' + r'.{0,40}?' + _AMOUNT_PATTERN), 0.9),
    (re.compile(r'(?i)balance\s*due' + r'.{0,40}?' + _AMOUNT_PATTERN), 0.9),
    # \btotal\b deliberately doesn't match inside "subtotal" - no word boundary between
    # "sub" and "total" since both sides are word characters.
    (re.compile(r'(?i)\btotal\b' + r'.{0,40}?' + _AMOUNT_PATTERN), 0.85),
]

_ANY_AMOUNT_PATTERN = re.compile(_AMOUNT_PATTERN)

_TAX_PATTERN = re.compile(r'(?i)\btax\b' + r'.{0,40}?' + _AMOUNT_PATTERN)

_MERCHANT_KEYWORD_PATTERN = re.compile(
    r'(?im)^\s*(?:sold\s*by|merchant|store|vendor|from)\s*[:\-]\s*(.+)$'
)

# Candidate date-shaped substrings: MM/DD/YYYY-ish, YYYY-MM-DD, or "Month DD, YYYY".
_DATE_CANDIDATE_PATTERN = re.compile(
    r'(?i)(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}'
    r'|\d{4}-\d{1,2}-\d{1,2}'
    r'|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{2,4})'
)


@dataclass
class ExtractionResult:
    merchant_name: str | None
    merchant_name_confidence: float
    total_amount: Decimal | None
    total_amount_confidence: float
    transaction_date: date | None
    transaction_date_confidence: float
    tax_amount: Decimal | None
    raw_text: str
    extraction_method: ExtractionMethod


def _parse_amount(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(",", ""))
    except InvalidOperation:
        return None


# Prepare a receipt photo for OCR: grayscale + autocontrast improve Tesseract's accuracy
# on low-contrast thermal receipts, and a small median filter removes speckle noise from
# phone-camera photos without blurring text edges enough to hurt recognition.
def preprocess_receipt_image(image: Image.Image) -> Image.Image:
    img = ImageOps.grayscale(image)
    img = ImageOps.autocontrast(img, cutoff=2)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    return img


# Extract merchant name from receipt text. Keyword-anchored labels ("Sold By:", "Merchant:")
# are rare on printed receipts but common on emailed/PDF invoices, so they're checked
# first at high confidence; otherwise fall back to "probably one of the first few lines,"
# skipping lines that look like a street address or phone number.
def identify_merchant(text: str) -> tuple[str | None, float]:
    keyword_match = _MERCHANT_KEYWORD_PATTERN.search(text)
    if keyword_match:
        candidate = keyword_match.group(1).strip()
        if candidate:
            return candidate[:255], 0.85

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None, 0.0

    for line in lines[:5]:
        if not (3 <= len(line) <= 60):
            continue
        if re.match(r'^\$?\d', line):  # starts with a digit/amount -> address or price line
            continue
        if re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', line):  # looks like a phone number
            continue
        return line[:255], 0.55

    # Nothing passed the filters above - just take the very first line as a low-confidence guess.
    return lines[0][:255], 0.25


# Extract the total amount. Tries each keyword-anchored pattern in priority order (grand
# total > total due > amount due > balance due > bare "total"); if none match, falls back
# to "the largest dollar amount anywhere on the receipt is probably the total," which is
# usually true since tax/subtotal/line-items are each smaller than the final total.
def identify_total(text: str) -> tuple[Decimal | None, float]:
    for pattern, confidence in _TOTAL_KEYWORD_PATTERNS:
        match = pattern.search(text)
        if match:
            amount = _parse_amount(match.group(1))
            if amount is not None:
                return amount, confidence

    all_amounts = [_parse_amount(m.group(1)) for m in _ANY_AMOUNT_PATTERN.finditer(text)]
    all_amounts = [a for a in all_amounts if a is not None]
    if all_amounts:
        return max(all_amounts), 0.4

    return None, 0.0


# Extract the transaction date. A candidate is only accepted if it parses to a plausible
# date (not more than 5 years in the past, not more than a day in the future) - this
# filters out phone numbers, receipt/order numbers, or OCR noise that happens to look
# date-shaped but parses to something absurd (e.g. year 0091). A candidate preceded by
# the word "date" within a few characters is treated as keyword-anchored and preferred
# over an unanchored one, mirroring identify_merchant/identify_total's anchored-vs-guessed
# confidence split.
def identify_date(text: str, today: date | None = None) -> tuple[date | None, float]:
    today = today or date.today()
    earliest_plausible = today - timedelta(days=5 * 365)
    latest_plausible = today + timedelta(days=1)

    best_unanchored: date | None = None

    for match in _DATE_CANDIDATE_PATTERN.finditer(text):
        candidate_str = match.group(0)
        try:
            parsed = dateutil_parser.parse(
                candidate_str, default=datetime(today.year, 1, 1)
            ).date()
        except (ValueError, OverflowError):
            continue

        if not (earliest_plausible <= parsed <= latest_plausible):
            continue

        prefix = text[max(0, match.start() - 15):match.start()].lower()
        if "date" in prefix:
            return parsed, 0.9

        if best_unanchored is None:
            best_unanchored = parsed

    if best_unanchored is not None:
        return best_unanchored, 0.7

    return None, 0.0


# Extract the tax amount, if printed - secondary field, never blocks a receipt from
# being usable even if this returns (None, 0.0).
def identify_tax(text: str) -> tuple[Decimal | None, float]:
    match = _TAX_PATTERN.search(text)
    if match:
        amount = _parse_amount(match.group(1))
        if amount is not None:
            return amount, 0.8
    return None, 0.0


def _build_extraction_result(text: str, method: ExtractionMethod) -> ExtractionResult:
    merchant, merchant_confidence = identify_merchant(text)
    total, total_confidence = identify_total(text)
    transaction_date, date_confidence = identify_date(text)
    tax, _ = identify_tax(text)

    return ExtractionResult(
        merchant_name=merchant,
        merchant_name_confidence=merchant_confidence,
        total_amount=total,
        total_amount_confidence=total_confidence,
        transaction_date=transaction_date,
        transaction_date_confidence=date_confidence,
        tax_amount=tax,
        raw_text=text,
        extraction_method=method,
    )


# Run Tesseract OCR on an image (JPEG/PNG/etc.) and extract receipt fields. --psm 4
# ("assume a single column of text of variable sizes") fits a typical narrow receipt
# strip better than Tesseract's default full-page-layout assumption.
def extract_from_image(image_bytes: bytes) -> ExtractionResult:
    image = Image.open(io.BytesIO(image_bytes))
    processed = preprocess_receipt_image(image)
    text = pytesseract.image_to_string(processed, config="--psm 4")
    return _build_extraction_result(text, ExtractionMethod.TESSERACT)


# Read a PDF's embedded text layer directly. Returns (text, is_text_based) - is_text_based
# is False when there's suspiciously little text (<50 chars), the signal that this is a
# scanned/image-only PDF with no real text layer and needs the OCR fallback instead.
def _extract_pdf_text(pdf_bytes: bytes) -> tuple[str, bool]:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return text, len(text.strip()) > 50


# Rasterize every page of a scanned PDF to an image and run the same OCR pipeline used
# for photos, concatenating each page's text - the fallback path for PDFs with no
# extractable text layer (e.g. a phone-scanned paper receipt saved as PDF).
def _ocr_pdf_pages(pdf_bytes: bytes) -> str:
    pages = convert_from_bytes(pdf_bytes)
    page_texts = []
    for page_image in pages:
        processed = preprocess_receipt_image(page_image)
        page_texts.append(pytesseract.image_to_string(processed, config="--psm 4"))
    return "\n".join(page_texts)


# Extract fields from a PDF receipt (online order confirmation, emailed invoice, or a
# scanned paper receipt saved as PDF). Tries the fast, accurate text-layer path first and
# only falls back to OCR when the PDF turns out to have no usable embedded text.
def extract_from_pdf(pdf_bytes: bytes) -> ExtractionResult:
    text, is_text_based = _extract_pdf_text(pdf_bytes)
    if is_text_based:
        return _build_extraction_result(text, ExtractionMethod.PDF_TEXT)

    ocr_text = _ocr_pdf_pages(pdf_bytes)
    return _build_extraction_result(ocr_text, ExtractionMethod.PDF_OCR)


# Decide whether a completed extraction needs a human to review it before becoming an
# Expense - true if any of the three core fields is missing or below the confidence
# threshold. Secondary fields (tax, line items) never trigger review on their own.
def should_flag_for_review(result: ExtractionResult) -> bool:
    core_confidences = [
        result.merchant_name_confidence,
        result.total_amount_confidence,
        result.transaction_date_confidence,
    ]
    core_values = [result.merchant_name, result.total_amount, result.transaction_date]
    return any(v is None for v in core_values) or any(
        c < REVIEW_CONFIDENCE_THRESHOLD for c in core_confidences
    )
