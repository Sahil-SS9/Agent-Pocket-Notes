"""Desktop native-library preparation; no GUI imports or host installations."""
import ctypes
import os
from pathlib import Path
import sys


def prepare_qt():
    if sys.platform.startswith('linux'):
        # Optional account-local XCB cursor runtime, prepared by the pinned installer.
        base = Path(os.getenv('STICKY_INTENT_QT_RUNTIME') or Path.home()/'.local/share/sticky-intent/runtime')
        library = base/'libxcb-cursor.so.0'
        if library.is_file():
            ctypes.CDLL(str(library.resolve()),mode=ctypes.RTLD_GLOBAL)
    # Software rendering avoids dependence on GPU drivers for this small utility.
    os.environ.setdefault('QT_QUICK_BACKEND','software')
    os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
