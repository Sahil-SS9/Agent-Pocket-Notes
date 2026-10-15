"""Cheap, GUI-free platform store-location resolution."""
import os
from pathlib import Path
import sys

def default_home(*, platform=None, env=None, home=None):
    env = os.environ if env is None else env
    home = Path.home() if home is None else Path(home)
    platform = sys.platform if platform is None else platform
    if env.get('STICKY_INTENT_HOME'):
        return Path(env['STICKY_INTENT_HOME']).expanduser()
    if platform == 'darwin':
        return home / 'Library/Application Support/sticky-intent'
    if platform == 'win32':
        return Path(env.get('APPDATA') or home/'AppData/Roaming') / 'sticky-intent'
    return Path(env.get('XDG_DATA_HOME') or home/'.local/share') / 'sticky-intent'
