import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from unittest.mock import Mock
import pytest
from sticky_intent import install,doctor
from sticky_intent.cli import main
from sticky_intent.store import Store
from sticky_intent.instance import WidgetInstance


@pytest.mark.parametrize('shell',['bash','zsh','fish','pwsh'])
@pytest.mark.parametrize('original',[b'# my rc\r\nexport KEEP=yes\r\n',b'# no trailing newline'])
def test_shell_install_uninstall_byte_exact(sandbox,shell,original,monkeypatch):
    monkeypatch.setenv('STICKY_PWSH_PROFILE',str(sandbox/'Documents/PowerShell/profile.ps1'))
    rc=install.shell_path(shell); rc.parent.mkdir(parents=True,exist_ok=True); rc.write_bytes(original)
    install.install_autostart(shell=shell)
    first=rc.read_bytes(); assert first.startswith(original)
    assert first.count(b'# >>> sticky-intent >>>')==1
    assert b'widget' in first and b'--if-not-running' in first
    install.install_autostart(shell=shell); assert rc.read_bytes()==first
    install.uninstall_autostart(); assert rc.read_bytes()==original


def test_uninstall_preserves_user_append(sandbox):
    rc=sandbox/'.bashrc'; original=b'no-newline'; rc.write_bytes(original)
    install.install_autostart(shell='bash')
    rc.write_bytes(rc.read_bytes()+b'\n# appended by user\n')
    install.uninstall_autostart()
    assert rc.read_bytes()==original+b'\n# appended by user\n'


def test_uninstall_refuses_modified_owned_block(sandbox):
    install.install_autostart(shell='bash'); rc=sandbox/'.bashrc'
    rc.write_bytes(rc.read_bytes().replace(b'--if-not-running',b'--changed'))
    with pytest.raises(ValueError,match='edited'): install.uninstall_autostart()
    assert b'--changed' in rc.read_bytes()


@pytest.mark.parametrize('platform',['linux','darwin','win32'])
def test_login_variants_and_restore(sandbox,platform):
    target=install.login_path(platform)
    target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(b'original login file')
    install.install_autostart(login=True,platform=platform)
    content=target.read_bytes()
    assert b'sticky' in content and b'--if-not-running' in content
    if platform=='darwin':
        import plistlib
        assert plistlib.loads(content)['RunAtLoad'] is True
    elif platform=='linux':
        assert b'Terminal=false' in content
    else:
        assert b'start' in content.lower()
    install.uninstall_autostart(); assert target.read_bytes()==b'original login file'


@pytest.mark.parametrize('shell',['bash','zsh','fish','pwsh'])
def test_shell_block_interactive_and_display_guard(shell):
    block=install.shell_block(shell,platform='linux')
    assert 'DISPLAY' in block and 'WAYLAND_DISPLAY' in block
    assert 'interactive' in block.lower() or '$-' in block or 'IsInputRedirected' in block
    assert '--background' in block


@pytest.mark.parametrize('shell',['bash','zsh'])
def test_real_shell_rc_added_prompt_cost_under_50ms(sandbox,shell,monkeypatch):
    exe=shutil.which(shell); assert exe is not None
    install.install_autostart(shell=shell)
    rc=install.shell_path(shell)
    instance=WidgetInstance(Store().home); assert instance.acquire(); instance.ready()
    env=os.environ.copy(); env['DISPLAY']=':fake-not-used'; env.pop('WAYLAND_DISPLAY',None)
    def sample(file):
        times=[]
        for _ in range(5):
            start=time.perf_counter()
            p=subprocess.run([exe,'--norc','-i','-c',f'. "{file}"; exit'] if shell=='bash' else [exe,'-f','-i','-c',f'. "{file}"; exit'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3)
            assert p.returncode==0
            times.append(time.perf_counter()-start)
        return sorted(times)[len(times)//2]
    baseline=sandbox/'empty-rc'; baseline.write_bytes(b'')
    try:
        cost=sample(rc)-sample(baseline)
        print(f'{shell} rc median added cost: {cost*1000:.3f} ms')
        assert cost<.05,cost
    finally: instance.close()


def test_doctor_headless_warning_only(monkeypatch):
    monkeypatch.delenv('DISPLAY',raising=False); monkeypatch.delenv('WAYLAND_DISPLAY',raising=False)
    info=doctor.inspect()
    assert info['ok'] is True and info['display'] is False
    # Supported native Tk 8.6 and managed Tk 9 both satisfy the doctor contract.
    assert tuple(map(int, info['tk'].split('.')[:2])) >= (8, 6)
    assert info['store_writable'] is True


def test_doctor_missing_tk_is_error(monkeypatch):
    monkeypatch.setenv('STICKY_INTENT_RENDERER','tk')
    monkeypatch.setattr(doctor.subprocess,'run',Mock(return_value=Mock(returncode=1,stdout='',stderr='missing tkinter')))
    info=doctor.inspect()
    assert info['ok'] is False and info['tk']=='unavailable'


def test_doctor_bad_adapter_config_is_warning_only(sandbox):
    path=sandbox/'.claude/settings.json'; path.parent.mkdir(); path.write_text('{"hooks": null}')
    assert doctor.inspect()['ok'] is True


def test_shared_board_explicit_group_mode(monkeypatch):
    from sticky_intent.io import FileLock
    monkeypatch.setenv('STICKY_INTENT_SHARED','1')
    store=Store(); store.add('shared')
    with FileLock(store.home/'shared.lock'):
        pass
    if os.name!='nt':
        assert (store.notes.stat().st_mode & 0o777)==0o770
        assert ((store.notes/'1.md').stat().st_mode & 0o777)==0o660
        assert ((store.home/'shared.lock').stat().st_mode & 0o777)==0o660


def test_doctor_unusable_store_is_error(monkeypatch,tmp_path):
    bad=tmp_path/'file'; bad.write_text('not directory'); monkeypatch.setenv('STICKY_INTENT_HOME',str(bad))
    assert doctor.inspect()['ok'] is False


def test_autostart_and_doctor_cli(sandbox,capsys):
    assert main(['install-autostart','--shell','bash'])==0
    assert (sandbox/'.bashrc').exists()
    assert main(['doctor'])==0
    output=capsys.readouterr().out
    for name in ['Python','Tk','Display','Store','Clipboard','Hermes','Claude','Autostart']: assert name in output
    assert main(['uninstall-autostart'])==0
    assert not (sandbox/'.bashrc').exists()
