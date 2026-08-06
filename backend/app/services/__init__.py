"""Namespace package for business-logic services.

Services in this package (e.g. bank_simulator.py) sit between the API layer
and the database models: they accept plain model objects and primitives, run
domain calculations, and return plain results with no FastAPI or HTTP
concepts involved. This separation keeps the calculation logic reusable from
background workers (see app/workers) as well as from HTTP request handlers.
"""
