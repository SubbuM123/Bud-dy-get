"""Namespace package for Pydantic schemas.

Each sibling module here (user.py, bank_accounts.py, and future modules like
expenses.py or retirement.py) defines the request/response contracts for one
feature area of the API. Nothing is re-exported at this level; call sites
import directly from the specific schema module they need, e.g.
`from app.schemas.bank_accounts import BankAccountResponse`.
"""
