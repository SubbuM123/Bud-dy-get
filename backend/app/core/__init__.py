"""Namespace package for cross-cutting backend infrastructure.

This package holds code that many feature modules depend on but that isn't
itself a feature: authentication (auth.py), FastAPI dependency wiring
(dependencies.py), and shared financial math (calculations/). Nothing
feature-specific (e.g. bank accounts, expenses) should live here.
"""
