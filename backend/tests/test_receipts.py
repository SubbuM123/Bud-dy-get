"""API-level coverage for the Receipts endpoints: batch upload with synchronous OCR,
ownership scoping, manual correction during review, and creating an Expense from a
reviewed receipt.

Runs against SQLite (see conftest.py), with receipt_parser's OCR functions monkeypatched
to return fixed test data - this suite never needs real Tesseract or PDF processing.
"""

from decimal import Decimal
from datetime import date

from app.services import receipt_parser
from app.services.receipt_parser import ExtractionResult
from app.models.enums import ExtractionMethod


def _stub_out_ocr(monkeypatch, extraction_result=None):
    """Replace OCR calls with a stub that returns fixed test data."""
    if extraction_result is None:
        extraction_result = ExtractionResult(
            raw_text="Test receipt text",
            extraction_method=ExtractionMethod.TESSERACT_IMAGE,
            merchant_name="Test Store",
            merchant_name_confidence=Decimal("0.85"),
            total_amount=Decimal("42.50"),
            total_amount_confidence=Decimal("0.90"),
            transaction_date=date(2026, 3, 15),
            transaction_date_confidence=Decimal("0.80"),
            tax_amount=Decimal("3.50"),
        )
    monkeypatch.setattr(receipt_parser, "extract_from_image", lambda file_bytes: extraction_result)
    monkeypatch.setattr(receipt_parser, "extract_from_pdf", lambda file_bytes: extraction_result)


async def test_upload_requires_authentication(client):
    response = await client.post(
        "/api/v1/receipts/upload",
        files=[("files", ("receipt.jpg", b"fake-bytes", "image/jpeg"))],
    )

    assert response.status_code == 401


async def test_upload_processes_receipt_synchronously(client, auth_headers, monkeypatch):
    _stub_out_ocr(monkeypatch)

    response = await client.post(
        "/api/v1/receipts/upload",
        files=[("files", ("receipt.jpg", b"fake-bytes", "image/jpeg"))],
        headers=auth_headers,
    )

    assert response.status_code == 201
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["filename"] == "receipt.jpg"
    assert results[0]["status"] == "completed"
    assert results[0]["receipt_id"]
    assert results[0]["error"] is None


async def test_upload_marks_low_confidence_as_needs_review(client, auth_headers, monkeypatch):
    low_confidence_result = ExtractionResult(
        raw_text="Test receipt text",
        extraction_method=ExtractionMethod.TESSERACT_IMAGE,
        merchant_name="Maybe Store",
        merchant_name_confidence=Decimal("0.40"),
        total_amount=Decimal("10.00"),
        total_amount_confidence=Decimal("0.90"),
        transaction_date=date(2026, 3, 15),
        transaction_date_confidence=Decimal("0.80"),
        tax_amount=None,
    )
    _stub_out_ocr(monkeypatch, low_confidence_result)

    response = await client.post(
        "/api/v1/receipts/upload",
        files=[("files", ("receipt.jpg", b"fake-bytes", "image/jpeg"))],
        headers=auth_headers,
    )

    assert response.status_code == 201
    results = response.json()["results"]
    assert results[0]["status"] == "needs_review"


async def test_upload_batch_rejects_unsupported_type_without_failing_the_whole_batch(
    client, auth_headers, monkeypatch
):
    _stub_out_ocr(monkeypatch)

    response = await client.post(
        "/api/v1/receipts/upload",
        files=[
            ("files", ("receipt.jpg", b"fake-bytes", "image/jpeg")),
            ("files", ("malware.exe", b"not-a-receipt", "application/x-msdownload")),
        ],
        headers=auth_headers,
    )

    assert response.status_code == 201
    results = response.json()["results"]
    assert len(results) == 2
    good, bad = results
    assert good["filename"] == "receipt.jpg"
    assert good["receipt_id"]
    assert bad["filename"] == "malware.exe"
    assert bad["receipt_id"] is None
    assert "Unsupported file type" in bad["error"]


async def test_upload_rejects_file_over_size_limit(client, auth_headers, monkeypatch):
    _stub_out_ocr(monkeypatch)
    oversized = b"x" * (10 * 1024 * 1024 + 1)

    response = await client.post(
        "/api/v1/receipts/upload",
        files=[("files", ("big.jpg", oversized, "image/jpeg"))],
        headers=auth_headers,
    )

    assert response.status_code == 201
    result = response.json()["results"][0]
    assert result["receipt_id"] is None
    assert "10MB" in result["error"]


async def test_receipts_are_scoped_to_their_owner(client, monkeypatch):
    _stub_out_ocr(monkeypatch)

    await client.post("/api/v1/auth/register", json={"email": "a@example.com", "password": "pw123456"})
    a_login = await client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "pw123456"})
    a_headers = {"Authorization": f"Bearer {a_login.json()['access_token']}"}

    await client.post("/api/v1/auth/register", json={"email": "b@example.com", "password": "pw123456"})
    b_login = await client.post("/api/v1/auth/login", json={"email": "b@example.com", "password": "pw123456"})
    b_headers = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    await client.post(
        "/api/v1/receipts/upload",
        files=[("files", ("receipt.jpg", b"fake-bytes", "image/jpeg"))],
        headers=a_headers,
    )

    response = await client.get("/api/v1/receipts", headers=b_headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_update_receipt_corrects_fields_and_stamps_full_confidence(
    client, auth_headers, monkeypatch
):
    _stub_out_ocr(monkeypatch)
    upload_response = await client.post(
        "/api/v1/receipts/upload",
        files=[("files", ("receipt.jpg", b"fake-bytes", "image/jpeg"))],
        headers=auth_headers,
    )
    receipt_id = upload_response.json()["results"][0]["receipt_id"]

    response = await client.put(
        f"/api/v1/receipts/{receipt_id}",
        json={
            "merchant_name": "Corrected Store Name",
            "total_amount": "12.34",
            "transaction_date": "2026-03-01",
            "user_verified": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["merchant_name"] == "Corrected Store Name"
    assert float(body["total_amount"]) == 12.34
    assert body["transaction_date"] == "2026-03-01"
    assert body["user_verified"] is True
    assert body["verified_at"] is not None


async def test_create_expense_from_receipt_requires_core_fields(client, auth_headers, monkeypatch):
    missing_fields_result = ExtractionResult(
        raw_text="Unreadable receipt",
        extraction_method=ExtractionMethod.TESSERACT_IMAGE,
        merchant_name=None,
        merchant_name_confidence=None,
        total_amount=None,
        total_amount_confidence=None,
        transaction_date=None,
        transaction_date_confidence=None,
        tax_amount=None,
    )
    _stub_out_ocr(monkeypatch, missing_fields_result)

    upload_response = await client.post(
        "/api/v1/receipts/upload",
        files=[("files", ("receipt.jpg", b"fake-bytes", "image/jpeg"))],
        headers=auth_headers,
    )
    receipt_id = upload_response.json()["results"][0]["receipt_id"]

    response = await client.post(
        f"/api/v1/receipts/{receipt_id}/create-expense", json={}, headers=auth_headers
    )

    assert response.status_code == 400


async def test_create_expense_from_receipt_succeeds_once_fields_are_present(
    client, auth_headers, monkeypatch
):
    _stub_out_ocr(monkeypatch)
    upload_response = await client.post(
        "/api/v1/receipts/upload",
        files=[("files", ("receipt.jpg", b"fake-bytes", "image/jpeg"))],
        headers=auth_headers,
    )
    receipt_id = upload_response.json()["results"][0]["receipt_id"]

    response = await client.post(
        f"/api/v1/receipts/{receipt_id}/create-expense", json={}, headers=auth_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["merchant_name"] == "Test Store"
    assert float(body["amount"]) == 42.50
    assert body["expense_date"] == "2026-03-15"
    assert body["receipt_id"] == receipt_id


async def test_delete_receipt_removes_it(client, auth_headers, monkeypatch):
    _stub_out_ocr(monkeypatch)

    upload_response = await client.post(
        "/api/v1/receipts/upload",
        files=[("files", ("receipt.jpg", b"fake-bytes", "image/jpeg"))],
        headers=auth_headers,
    )
    receipt_id = upload_response.json()["results"][0]["receipt_id"]

    response = await client.delete(f"/api/v1/receipts/{receipt_id}", headers=auth_headers)

    assert response.status_code == 204

    get_response = await client.get(f"/api/v1/receipts/{receipt_id}", headers=auth_headers)
    assert get_response.status_code == 404


async def test_reprocess_returns_400(client, auth_headers, monkeypatch):
    _stub_out_ocr(monkeypatch)

    upload_response = await client.post(
        "/api/v1/receipts/upload",
        files=[("files", ("receipt.jpg", b"fake-bytes", "image/jpeg"))],
        headers=auth_headers,
    )
    receipt_id = upload_response.json()["results"][0]["receipt_id"]

    response = await client.post(f"/api/v1/receipts/{receipt_id}/reprocess", headers=auth_headers)

    assert response.status_code == 400
    assert "Re-upload" in response.json()["detail"]
