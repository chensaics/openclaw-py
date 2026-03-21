"""Shim for ``flet build``: Flet CLI looks for main.py in the app root by default.

Real entry point is flet_app.main; this module re-exports it so both
``flet build web/linux/...`` and ``--module-name flet_app`` work.
"""

from flet_app import main

__all__ = ["main"]
