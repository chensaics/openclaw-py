"""Flet application entry point for native builds.

Supports two execution modes:

1. Development:  ``flet run flet_app.py`` or ``python flet_app.py``
2. Production:   ``flet build web/macos/windows/linux/apk/ipa``
   — ``flet build`` detects the top-level ``main(page)`` function
     automatically and uses it as the application entry point.
"""

import flet as ft

from pyclaw.ui.app import PyClawApp


async def main(page: ft.Page) -> None:
    """Entry point for both ``flet run`` and ``flet build``."""
    app = PyClawApp()
    await app.main(page)


if __name__ == "__main__":
    ft.run(main)
