"""Namespace package for all HTTP API route modules.

Route handlers live under api/v1 (see that package for the actual routers);
this top-level package exists so future breaking API changes can be shipped
as a parallel api/v2 package without touching v1 clients.
"""
