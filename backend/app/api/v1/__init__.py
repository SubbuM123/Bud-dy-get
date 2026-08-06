"""Version 1 of the HTTP API.

Each sibling module (auth.py, users.py, bank_accounts.py, dashboard.py, and
future feature modules) defines one `APIRouter` for its resource; router.py
in this package combines them all under the shared `/api/v1` prefix that
main.py mounts.
"""
