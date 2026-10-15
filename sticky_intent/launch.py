"""GUI launch boundary: plugin-side callers never import Tk or the widget."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from .clipboard import has_display
from .store import default_home
from .targets import pid_alive


def widget_ready(home=None):
    try:
        info=json.loads((Path(home or default_home())/'widget-ready.json').read_text('utf-8'))
        return pid_alive(info['pid'])
    except (OSError,ValueError,KeyError,TypeError):
        return False


def launch_widget(*,wait=False):
    if not has_display():
        return False,'No display available'
    command=shutil.which('sticky')
    if not command:
        return False,'sticky is not on PATH; install its Tk-enabled CLI environment'
    try:
        process=subprocess.Popen([command,'widget','--if-not-running'],stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                 start_new_session=os.name!='nt',creationflags=(subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name=='nt' else 0)
        if not wait:
            return True,'Widget launch requested'
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            if widget_ready():
                return True,'Sticky Intent is open'
            if process.poll() not in (None,0):
                return False,'Widget failed to open; check Tk and display access'
            time.sleep(0.05)
        return False,'Widget not ready within 3 seconds; check Tk and display access'
    except OSError as exc:
        return False,str(exc)
