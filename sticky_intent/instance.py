"""Cross-platform single-instance ownership, raise requests and GUI-free fast path."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from .io import FileLock, atomic_write, private_dir


class WidgetInstance:
    def __init__(self,home):
        self.home=private_dir(Path(home))
        self.lock=FileLock(self.home/'widget.lock')
        self.owned=False
        self.token=uuid.uuid4().hex
        self.raises=0

    def acquire(self):
        self.owned=self.lock.acquire(blocking=False)
        if not self.owned:
            atomic_write(self.home/'widget-raise',uuid.uuid4().hex.encode())
        return self.owned

    def ready(self):
        if not self.owned:
            raise RuntimeError('Cannot announce widget readiness without ownership')
        atomic_write(self.home/'widget-ready.json',json.dumps({'pid':os.getpid(),'token':self.token,'raises':self.raises}).encode())

    def poll_raise(self):
        path=self.home/'widget-raise'
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        self.raises+=1
        self.ready()
        return True

    def close(self):
        if self.owned:
            path=self.home/'widget-ready.json'
            try:
                info=json.loads(path.read_bytes())
                if info.get('token')==self.token:
                    path.unlink(missing_ok=True)
            except (OSError,ValueError):
                pass
            self.lock.release()
            self.owned=False


def renderer_choice(renderer=None):
    selected = renderer or os.getenv('STICKY_INTENT_RENDERER','auto')
    if selected not in {'auto','qt','tk'}: raise ValueError('Renderer must be auto, qt or tk')
    if selected=='auto':
        from importlib.util import find_spec
        return 'qt' if find_spec('PySide6') is not None else 'tk'
    return selected


def run_widget(store,*,background=False,if_not_running=False,renderer=None):
    from .clipboard import has_display
    instance=WidgetInstance(store.home)
    if not instance.acquire():
        return 0  # no Tk import: the already-running path stays under 100ms
    if not has_display():
        instance.close()
        raise RuntimeError('No display available; use sticky list instead')
    try: chosen = renderer_choice(renderer)
    except (ValueError, ImportError):
        instance.close()
        raise
    if background:
        instance.close()
        log=store.home/'widget-launch.log'
        with log.open('ab') as output:
            if os.name!='nt':
                os.chmod(log,0o600)
            subprocess.Popen([sys.executable,'-m','sticky_intent','widget','--renderer',chosen],stdin=subprocess.DEVNULL,stdout=output,stderr=output,
                             start_new_session=os.name!='nt',creationflags=(subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name=='nt' else 0)
        return 0
    try:
        if chosen=='qt':
            from .qt_runtime import prepare_qt
            prepare_qt()
            try:
                from .qt_widget import run
            except ImportError as exc:
                raise RuntimeError('Qt desktop extra is missing; install sticky-intent[desktop] or use --renderer tk') from exc
            return run(store,instance)
        from .widget import Widget, tk
        root=tk.Tk(className='StickyIntent')
        Widget(root,store,instance=instance)
        instance.ready()
        root.mainloop()
        return 0
    except Exception as exc:
        raise RuntimeError(f'Widget could not open: {exc}') from exc
    finally:
        instance.close()
