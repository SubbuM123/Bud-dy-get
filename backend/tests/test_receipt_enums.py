# """Regression-style check for the enum-binding bug documented in docs/progress.md
# (session 2026-07-31/08-01, #8): SQLAlchemy's `Enum(SomeEnum)` binds using the Python enum
# member's *name* by default, not its *value* - `values_callable` is required, or every
# insert fails against a real Postgres database once the column's bound values
# ("PENDING") don't match the Postgres enum type's actual labels (lowercase, per
# alembic/versions/007_add_expense_tracker.py). Checked directly against each column's
# compiled `.enums` list - no database needed - same approach as
# test_education_account_enums.py.
# """

# from decimal import Decimal

# from app.models.receipts import Receipt

# # Must match the literal enum labels in alembic/versions/007_add_expense_tracker.py.
# EXPECTED_PROCESSING_STATUS_VALUES = ["pending", "processing", "completed", "needs_review", "failed"]
# EXPECTED_EXTRACTION_METHOD_VALUES = ["tesseract", "pdf_text", "pdf_ocr", "manual"]


# def test_receipt_processing_status_binds_lowercase_values_matching_the_migration():
#     assert Receipt.__table__.c.processing_status.type.enums == EXPECTED_PROCESSING_STATUS_VALUES


# def test_receipt_extraction_method_binds_lowercase_values_matching_the_migration():
#     assert Receipt.__table__.c.extraction_method.type.enums == EXPECTED_EXTRACTION_METHOD_VALUES


# def test_receipt_confidence_columns_are_numeric():
#     assert Receipt.__table__.c.merchant_name_confidence.type.python_type is Decimal
#     assert Receipt.__table__.c.total_amount_confidence.type.python_type is Decimal
#     assert Receipt.__table__.c.transaction_date_confidence.type.python_type is Decimal
