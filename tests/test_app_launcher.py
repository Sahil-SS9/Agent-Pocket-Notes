"""Desktop-menu entry is a manual launcher, NEVER login/terminal startup."""
from pathlib import Path
import configparser
import os
import shutil
import subprocess
import sys
import pytest
from sticky_intent.store import Store


def launcher():
    import sticky_intent.app_launcher as module
    return module


@pytest.fixture
def executable(tmp_path):
    exe = tmp_path / 'a tool with spaces %' / 'sticky'
    exe.parent.mkdir(); exe.write_text('#!/bin/sh\nexit 0\n'); exe.chmod(0o755)
    return exe


def test_manual_app_launcher_install_and_remove(executable):
    module = launcher(); store = Store(); store.add('Keep my real notes')
    result = module.install_launcher(executable=executable)
    target = Path(os.environ['XDG_DATA_HOME'])/'applications/sticky-intent.desktop'
    assert target.exists() and str(target) in result
    cfg = configparser.ConfigParser(interpolation=None); cfg.read(target)
    entry = cfg['Desktop Entry']
    assert entry['Type']=='Application' and entry['Name']=='Sticky Intent'
    assert entry['Terminal']=='false' and 'widget' in entry['Exec']
    assert '%%' in entry['Exec'] and 'X-GNOME-Autostart-enabled' not in entry
    assert Path(entry['Icon']).is_file()
    assert Path(os.environ['XDG_STATE_HOME']).is_relative_to(Path.home()), 'Launcher receipts must stay in this test home'
    assert not (Path.home()/'.config/autostart/sticky-intent.desktop').exists()
    original = target.read_bytes()
    module.install_launcher(executable=executable); assert target.read_bytes()==original
    module.uninstall_launcher(); assert not target.exists()
    assert store.get(1).body=='Keep my real notes'


def test_launcher_refuses_to_overwrite_an_unmanaged_entry(executable):
    module=launcher(); target=Path(os.environ['XDG_DATA_HOME'])/'applications/sticky-intent.desktop'
    target.parent.mkdir(parents=True); target.write_text('USER CONTENT')
    with pytest.raises(ValueError,match='unmanaged'):
        module.install_launcher(executable=executable)
    assert target.read_text()=='USER CONTENT'


def test_launcher_uninstall_preserves_user_edits(executable):
    module=launcher(); module.install_launcher(executable=executable)
    target=Path(os.environ['XDG_DATA_HOME'])/'applications/sticky-intent.desktop'
    target.write_text(target.read_text()+'\n# User change\n')
    with pytest.raises(ValueError,match='edited'):
        module.uninstall_launcher()
    assert target.exists()


def test_launcher_cli_works_without_gui_import(executable):
    argv=[sys.executable,'-m','sticky_intent','install-launcher','--executable',str(executable)]
    result=subprocess.run(argv,capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stdout+result.stderr
    result=subprocess.run([sys.executable,'-m','sticky_intent','uninstall-launcher'],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr


def test_actual_linux_desktop_file_validator(executable):
    tool=shutil.which('desktop-file-validate')
    if not tool: pytest.skip('Native desktop validator unavailable')
    launcher().install_launcher(executable=executable)
    target=Path(os.environ['XDG_DATA_HOME'])/'applications/sticky-intent.desktop'
    result=subprocess.run([tool,str(target)],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    assert not (result.stdout + result.stderr).strip(), 'The app-menu entry should validate without warnings or duplicate-category hints'
