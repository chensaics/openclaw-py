"""Flet application entry point for native builds.

Used by ``flet build`` to create standalone desktop and mobile apps.
Run directly with ``flet run flet_app.py`` for development.
"""

from pyclaw.ui.app import run_app

if __name__ == "__main__":
    run_app()
