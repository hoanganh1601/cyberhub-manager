"""Compatibility module: retain one desktop module identity for callers/patches."""
import sys
from cyberhub_manager.presentation import desktop_app

if __name__ == "__main__":
    desktop_app.main()
else:
    sys.modules[__name__] = desktop_app
