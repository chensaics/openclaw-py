"""Flet application entry point for native builds.

Supports two execution modes:

1. Development:  ``flet run flet_app.py`` or ``python flet_app.py``
2. Production:   ``flet build web/macos/windows/linux/apk/ipa``
   — ``flet build`` detects the top-level ``main(page)`` function
     automatically and uses it as the application entry point.

PWA assets (manifest.json, service-worker.js, icons/) live in ``web/``
and are included automatically by ``flet build web``.
"""

import flet as ft

from pyclaw.ui.app import PyClawApp

_SW_REGISTER_JS = """
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/service-worker.js')
    .then(function(reg) { console.log('SW registered:', reg.scope); })
    .catch(function(err) { console.warn('SW registration failed:', err); });
}
"""


async def main(page: ft.Page) -> None:
    """Entry point for both ``flet run`` and ``flet build``."""
    if page.web:
        page.run_javascript(_SW_REGISTER_JS)

    app = PyClawApp()
    await app.main(page)


if __name__ == "__main__":
    ft.run(main, assets_dir="web")
