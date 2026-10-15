import io
import sys
import pytest
from sticky_intent.cli import main
from sticky_intent.store import Store


def test_help(capsys):
    with pytest.raises(SystemExit) as e:
        main(['--help'])
    assert e.value.code == 0
    assert 'sticky' in capsys.readouterr().out


def test_add_text_and_show(capsys):
    assert main(['add','hello\nworld']) == 0
    assert '#1' in capsys.readouterr().out
    assert main(['show','1']) == 0
    assert 'hello\nworld' in capsys.readouterr().out


def test_add_stdin_exact(monkeypatch):
    monkeypatch.setattr(sys, 'stdin', io.StringIO(' first\n\nlast '))
    assert main(['add']) == 0
    assert Store().get(1).body == ' first\n\nlast '


def test_add_pinned():
    assert main(['add','pin me','--pin']) == 0
    assert Store().get(1).status == 'pinned'


@pytest.mark.parametrize('command,status', [('pin','pinned'),('unpin','inbox'),('done','done')])
def test_status_command(command,status):
    Store().add('note')
    assert main([command,'1']) == 0
    assert Store().get(1).status == status


@pytest.mark.parametrize('flag,expected', [([], 'INBOX'),(['--pinned'],'PIN'),(['--done'],'DONE'),(['--all'],'INBOX')])
def test_list_filters(capsys,flag,expected):
    s=Store()
    s.add('INBOX'); s.add('PIN',pin=True); s.update(s.add('DONE').id,status='done')
    assert main(['list',*flag]) == 0
    output=capsys.readouterr().out
    assert expected in output
    if flag != ['--all']:
        for title in {'INBOX','PIN','DONE'}-{expected}:
            assert title not in output


def test_rm_moves_to_trash():
    s=Store(); s.add('trash')
    assert main(['rm','1']) == 0
    assert (s.trash/'1.md').exists() and not (s.notes/'1.md').exists()


def test_missing_note_clear_error(capsys):
    assert main(['show','999']) == 1
    assert 'Note #999' in capsys.readouterr().err


def test_oversize_refused_without_note(monkeypatch,capsys):
    monkeypatch.setattr(sys,'stdin',io.StringIO('x'*(1024*1024+1)))
    assert main(['add']) == 1
    assert '1 MB' in capsys.readouterr().err
    assert Store().list('all') == []


def test_empty_board(capsys):
    assert main(['list']) == 0
    assert 'No notes' in capsys.readouterr().out


def test_clipboard_add(monkeypatch):
    from sticky_intent import clipboard
    monkeypatch.setattr(clipboard,'read_clipboard',lambda:'paste exactly')
    assert main(['add','--clipboard']) == 0
    assert Store().get(1).body == 'paste exactly'


def test_send_and_sessions_cli(capsys):
    from sticky_intent.targets import Registry, claim_messages
    store=Store(); store.add('CLI send')
    Registry(store.home).register('claude','chosen',cwd='/repo')
    assert main(['sessions']) == 0
    assert 'chosen' in capsys.readouterr().out
    assert main(['send','1','--to','claude','--session','chosen']) == 0
    assert 'next message' in capsys.readouterr().out
    assert len(list(claim_messages(store.home,'claude-chosen'))) == 1


def test_install_claude_cli(sandbox):
    assert main(['install-claude','--autostart']) == 0
    assert (sandbox/'.claude/commands/sticky.md').exists()
    assert main(['uninstall-claude']) == 0
    assert not (sandbox/'.claude/commands/sticky.md').exists()


def test_claude_hook_cli_json_only(monkeypatch,capsys):
    import json
    monkeypatch.setattr(sys,'stdin',io.StringIO(json.dumps({'hook_event_name':'SessionStart','session_id':'cli','cwd':'/project'})))
    assert main(['claude-hook']) == 0
    assert json.loads(capsys.readouterr().out) == {}
