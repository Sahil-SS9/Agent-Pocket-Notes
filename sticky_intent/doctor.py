"""Diagnostics are local only; missing display/harnesses are warnings, not errors."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from .clipboard import has_display, backend_name
from .io import atomic_write
from .locations import default_home
from .store import Store


def inspect():
    info={'python':sys.version.split()[0],'tk':'unavailable','display':has_display(),'store':str(default_home()),
          'store_writable':False,'clipboard':backend_name(),'hermes':shutil.which('hermes'),'claude':shutil.which('claude'),
          'plugin':False,'claude_hooks':False,'autostart':False,'errors':[]}
    from importlib import metadata
    from .instance import renderer_choice
    try: info['qt']=metadata.version('PySide6-Essentials')
    except metadata.PackageNotFoundError: info['qt']='unavailable'
    info['renderer']=renderer_choice()
    try:
        result=subprocess.run([sys.executable,'-m','sticky_intent.widget','--tk-version'],capture_output=True,text=True,timeout=5)
        if result.returncode==0 and result.stdout.strip(): info['tk']=result.stdout.strip()
        else: info['errors'].append('Tk is missing; install Python with tkinter support')
    except (OSError,subprocess.SubprocessError):
        info['errors'].append('Could not load tkinter in the CLI Python environment')
    try:
        store=Store()
        probe=store.home/f'.doctor-{uuid.uuid4().hex}'
        try:
            atomic_write(probe,b'probe')
            info['store_writable']=probe.read_bytes()==b'probe'
        finally: probe.unlink(missing_ok=True)
        receipts=store.home/'installs'
        if (receipts/'autostart.json').exists():
            records=json.loads((receipts/'autostart.json').read_bytes())
            info['autostart']=any(Path(p).exists() for p in records)
        settings=Path.home()/'.claude/settings.json'
        if settings.exists():
            value=json.loads(settings.read_bytes())
            info['claude_hooks']=all(any(any(h.get('command','').startswith('sticky claude-hook') for h in entry.get('hooks',[]))
                                                for entry in value.get('hooks',{}).get(event,[])) for event in ('SessionStart','UserPromptSubmit'))
    except (OSError,ValueError,TypeError,AttributeError) as exc:
        if not info['store_writable']: info['errors'].append(f'Store unusable: {exc}')
    home=Path(os.getenv('HERMES_HOME') or Path.home()/'.hermes')
    info['plugin']=(home/'plugins/sticky-intent/plugin.yaml').is_file()
    info['ok']=info['store_writable'] and (info['qt']!='unavailable' if info['renderer']=='qt' else info['tk']!='unavailable')
    if info['renderer']=='qt' and info['qt']!='unavailable':
        info['errors']=[e for e in info['errors'] if 'Tk' not in e and 'tkinter' not in e]
    return info


def format_report(info):
    yn=lambda value:'yes' if value else 'no'
    lines=[f'Python: {info["python"]}',f'Tk: {info["tk"]}',f'Qt: {info.get("qt","unavailable")} · selected renderer: {info.get("renderer","tk")}',
           f'Display: {yn(info["display"])}'+(' (warning only; CLI/text board works)' if not info['display'] else ''),
           f'Store: {info["store"]} (writable: {yn(info["store_writable"])})',f'Clipboard: {info["clipboard"]}',
           f'Hermes on PATH: {info["hermes"] or "not found (warning)"}',f'Claude on PATH: {info["claude"] or "not found (warning)"}',
           f'Hermes plugin directory: {"installed" if info["plugin"] else "not installed here; check Hermes own environment for wheel entry point"}',
           f'Claude hooks: {"installed" if info["claude_hooks"] else "not installed"}',f'Autostart: {"installed" if info["autostart"] else "not installed"}']
    lines.extend('ERROR: '+error for error in info['errors'])
    return '\n'.join(lines)
