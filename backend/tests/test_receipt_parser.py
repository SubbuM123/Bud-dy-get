# """Unit tests for the pure text-heuristic functions in app/services/receipt_parser.py.

# These test identify_merchant/identify_total/identify_date/identify_tax/
# should_flag_for_review directly against fixed sample OCR-shaped text, with no database,
# FastAPI app, or real image/PDF file involved - the OCR and PDF-extraction *paths*
# (extract_from_image/extract_from_pdf) that produce this text in production aren't
# exercised here since they require a real Tesseract binary and sample files; those are
# covered by the "Manual verification" checklist in docs/phase3-plan.md instead, run once a
# real Docker environment is available (same standing limitation as the rest of this
# project's OCR/PDF-touching code - see docs/progress.md).
# """

# from datetime import date
# from decimal import Decimal

# from app.models.enums import ExtractionMethod
# from app.services import receipt_parser as parser


# SAMPLE_GROCERY_RECEIPT = """
# TRADER JOE'S #123
# 123 MAIN ST
# ANYTOWN, CA 90210
# (555) 123-4567

# BANANAS               1.99
# ALMOND MILK            3.49
# SOURDOUGH BREAD         4.29

# SUBTOTAL                9.77
# TAX                      0.83
# TOTAL                   10.60

# VISA ****1234
# DATE: 03/15/2026
# THANK YOU FOR SHOPPING
# """

# SAMPLE_INVOICE_PDF_TEXT = """
# Invoice #INV-88213
# Sold By: Acme Cloud Services LLC
# Bill To: Jane Doe

# Item                Qty   Price
# Cloud Hosting         1   49.00
# Support Plan          1   10.00

# Subtotal                  59.00
# Amount Due                59.00

# Invoice Date: 2026-02-01
# """

# SAMPLE_LOW_CONFIDENCE_RECEIPT = """
# xkq3910 !! z
# $1.00
# $45.02
# """


# class TestIdentifyMerchant:
#     def test_uses_keyword_anchor_when_present(self):
#         merchant, confidence = parser.identify_merchant(SAMPLE_INVOICE_PDF_TEXT)
#         assert merchant == "Acme Cloud Services LLC"
#         assert confidence == 0.85

#     def test_falls_back_to_first_plausible_line(self):
#         merchant, confidence = parser.identify_merchant(SAMPLE_GROCERY_RECEIPT)
#         assert merchant == "TRADER JOE'S #123"
#         assert confidence == 0.55

#     def test_returns_none_for_empty_text(self):
#         merchant, confidence = parser.identify_merchant("")
#         assert merchant is None
#         assert confidence == 0.0

#     def test_skips_address_and_phone_lines(self):
#         # Every candidate line before "TRADER JOE'S #123" itself would be skipped by the
#         # address/phone filters, so the store name line is still what's picked.
#         text = "123 MAIN ST\n(555) 123-4567\nTRADER JOE'S #123\nTOTAL 5.00"
#         merchant, _ = parser.identify_merchant(text)
#         assert merchant == "TRADER JOE'S #123"


# class TestIdentifyTotal:
#     def test_prefers_keyword_anchored_total_over_bare_amounts(self):
#         total, confidence = parser.identify_total(SAMPLE_GROCERY_RECEIPT)
#         assert total == Decimal("10.60")
#         assert confidence == 0.85

#     def test_bare_total_does_not_match_inside_subtotal(self):
#         # "SUBTOTAL" appears before "TOTAL" in the sample text - if \btotal\b matched
#         # inside "SUBTOTAL" this would incorrectly return 9.77 instead of 10.60.
#         total, _ = parser.identify_total(SAMPLE_GROCERY_RECEIPT)
#         assert total != Decimal("9.77")

#     def test_amount_due_keyword(self):
#         total, confidence = parser.identify_total(SAMPLE_INVOICE_PDF_TEXT)
#         assert total == Decimal("59.00")
#         assert confidence == 0.9

#     def test_falls_back_to_largest_amount_with_low_confidence(self):
#         total, confidence = parser.identify_total(SAMPLE_LOW_CONFIDENCE_RECEIPT)
#         assert total == Decimal("45.02")
#         assert confidence == 0.4

#     def test_returns_none_when_no_amounts_present(self):
#         total, confidence = parser.identify_total("no numbers here at all")
#         assert total is None
#         assert confidence == 0.0

#     def test_handles_thousands_separator(self):
#         total, confidence = parser.identify_total("GRAND TOTAL $1,234.56")
#         assert total == Decimal("1234.56")
#         assert confidence == 0.95


# class TestIdentifyDate:
#     def test_keyword_anchored_date_wins(self):
#         parsed, confidence = parser.identify_date(
#             SAMPLE_GROCERY_RECEIPT, today=date(2026, 3, 20)
#         )
#         assert parsed == date(2026, 3, 15)
#         assert confidence == 0.9

#     def test_iso_format_date(self):
#         parsed, confidence = parser.identify_date(
#             SAMPLE_INVOICE_PDF_TEXT, today=date(2026, 2, 5)
#         )
#         assert parsed == date(2026, 2, 1)
#         assert confidence == 0.9

#     def test_rejects_implausibly_old_or_future_dates(self):
#         # A stray "01/01/1900"-shaped token more than 5 years in the past should be
#         # rejected rather than accepted as the transaction date.
#         parsed, confidence = parser.identify_date(
#             "SERIAL 01/01/1900 TOTAL 5.00", today=date(2026, 3, 20)
#         )
#         assert parsed is None
#         assert confidence == 0.0

#     def test_returns_none_when_no_date_shaped_text(self):
#         parsed, confidence = parser.identify_date("no dates here")
#         assert parsed is None
#         assert confidence == 0.0


# class TestIdentifyTax:
#     def test_finds_tax_amount(self):
#         tax, confidence = parser.identify_tax(SAMPLE_GROCERY_RECEIPT)
#         assert tax == Decimal("0.83")
#         assert confidence == 0.8

#     def test_returns_none_when_no_tax_line(self):
#         tax, confidence = parser.identify_tax("TOTAL 10.00")
#         assert tax is None
#         assert confidence == 0.0


# class TestShouldFlagForReview:
#     def test_high_confidence_extraction_does_not_need_review(self):
#         result = parser.ExtractionResult(
#             merchant_name="Trader Joe's",
#             merchant_name_confidence=0.85,
#             total_amount=Decimal("10.60"),
#             total_amount_confidence=0.85,
#             transaction_date=date(2026, 3, 15),
#             transaction_date_confidence=0.9,
#             tax_amount=Decimal("0.83"),
#             raw_text=SAMPLE_GROCERY_RECEIPT,
#             extraction_method=ExtractionMethod.TESSERACT,
#         )
#         assert parser.should_flag_for_review(result) is False

#     def test_low_confidence_field_triggers_review(self):
#         result = parser.ExtractionResult(
#             merchant_name="xkq3910",
#             merchant_name_confidence=0.25,
#             total_amount=Decimal("45.02"),
#             total_amount_confidence=0.4,
#             transaction_date=None,
#             transaction_date_confidence=0.0,
#             tax_amount=None,
#             raw_text=SAMPLE_LOW_CONFIDENCE_RECEIPT,
#             extraction_method=ExtractionMethod.TESSERACT,
#         )
#         assert parser.should_flag_for_review(result) is True

#     def test_missing_core_field_triggers_review_even_with_high_confidence_elsewhere(self):
#         result = parser.ExtractionResult(
#             merchant_name="Trader Joe's",
#             merchant_name_confidence=0.85,
#             total_amount=Decimal("10.60"),
#             total_amount_confidence=0.85,
#             transaction_date=None,
#             transaction_date_confidence=0.0,
#             tax_amount=None,
#             raw_text=SAMPLE_GROCERY_RECEIPT,
#             extraction_method=ExtractionMethod.TESSERACT,
#         )
#         assert parser.should_flag_for_review(result) is True
