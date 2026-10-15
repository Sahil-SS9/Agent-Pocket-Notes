"""The sticky console script. Optional front-ends are imported only on demand."""
from __future__ import annotations
import argparse
import sys
from .store import Store, BODY_LIMIT


def board_text(store, status='inbox'):
    notes = store.list(status)
    return '\n'.join(f'#{n.id}  {n.status}  [{n.research}]  {n.title}' for n in notes) or 'No notes.'


def parser():
    p = argparse.ArgumentParser(prog='sticky', description='Private sticky notes for your agent.')
    sub = p.add_subparsers(dest='command', required=True)
    add = sub.add_parser('add', help='Save text or stdin')
    add.add_argument('text', nargs='?')
    add.add_argument('--clipboard', action='store_true')
    add.add_argument('--pin', action='store_true')
    listing = sub.add_parser('list', help='List the board')
    group = listing.add_mutually_exclusive_group()
    for flag in ('pinned','done','all'):
        group.add_argument('--'+flag, action='store_true')
    for name in ('show','pin','unpin','done','rm'):
        command = sub.add_parser(name)
        command.add_argument('id', type=int)
    send = sub.add_parser('send', help='Queue a note for a live session, or copy it')
    send.add_argument('id', type=int)
    send.add_argument('--to', required=True, choices=('hermes','claude','clipboard'))
    send.add_argument('--session')
    sub.add_parser('sessions', help='List live send targets')
    install = sub.add_parser('install-claude')
    install.add_argument('--autostart', action='store_true')
    sub.add_parser('uninstall-claude')
    hook = sub.add_parser('claude-hook', help=argparse.SUPPRESS)
    hook.add_argument('--autostart', action='store_true')
    research = sub.add_parser('research', help='Start background one-shot research')
    research.add_argument('id', type=int)
    research.add_argument('--with', dest='runner', choices=('hermes','claude'), default='hermes')
    widget = sub.add_parser('widget', help='Open or raise Pocket Notes (Qt desktop extra, Tk fallback)')
    widget.add_argument('--renderer', choices=('auto','qt','tk'), default=None)
    widget.add_argument('--background', action='store_true')
    widget.add_argument('--if-not-running', action='store_true')
    autostart = sub.add_parser('install-autostart', help='Explicitly install shell or OS-login startup')
    auto_group = autostart.add_mutually_exclusive_group(required=True)
    auto_group.add_argument('--shell', choices=('bash','zsh','fish','pwsh'))
    auto_group.add_argument('--login', action='store_true')
    sub.add_parser('uninstall-autostart')
    app = sub.add_parser('install-launcher', help='Add Sticky Intent to the Linux application menu (not autostart)')
    app.add_argument('--executable', help='Absolute sticky executable path; defaults to PATH discovery')
    sub.add_parser('uninstall-launcher', help='Remove the app-menu launcher without deleting notes')
    sub.add_parser('doctor', help='Check Tk, store, clipboard and adapter installation')
    return p


def main(argv=None):
    effective=sys.argv[1:] if argv is None else argv
    args = parser().parse_args(effective or ['widget'])
    try:
        store = Store()
        if args.command == 'add':
            if args.clipboard:
                from .clipboard import read_clipboard
                body = read_clipboard()
            else:
                body = args.text if args.text is not None else sys.stdin.read(BODY_LIMIT+1)
            note = store.add(body, source='clipboard' if args.clipboard else 'cli', pin=args.pin)
            print(f'Added #{note.id}: {note.title}')
        elif args.command == 'list':
            status = next((s for s in ('pinned','done','all') if getattr(args,s)), 'inbox')
            print(board_text(store,status))
        elif args.command == 'show':
            note = store.get(args.id)
            print(f'#{note.id}: {note.title} ({note.status}, research: {note.research})')
            sys.stdout.write(note.body)
            if not note.body.endswith('\n'):
                print()
        elif args.command in ('pin','unpin','done'):
            state = {'pin':'pinned','unpin':'inbox','done':'done'}[args.command]
            store.update(args.id,status=state)
            print(f'#{args.id}: {state}')
        elif args.command == 'rm':
            store.delete(args.id)
            print(f'#{args.id} moved to trash')
        elif args.command == 'send':
            from .targets import send_note
            print(send_note(store,args.id,args.to,session=args.session))
        elif args.command == 'sessions':
            from .targets import Registry
            sessions=Registry(store.home).list()
            for session in sessions:
                print(f'{session["kind"]}  {session["session_id"]}  {session["cwd"]}')
            if not sessions:
                print('No live sessions.')
        elif args.command in ('install-claude','uninstall-claude','claude-hook'):
            from . import claude_adapter
            if args.command == 'install-claude':
                print(claude_adapter.install(autostart=args.autostart))
            elif args.command == 'uninstall-claude':
                print(claude_adapter.uninstall())
            else:
                import json
                try:
                    payload=json.loads(sys.stdin.read(BODY_LIMIT+1))
                except ValueError:
                    payload={}
                print(json.dumps(claude_adapter.hook(payload,autostart=args.autostart),ensure_ascii=False))
        elif args.command == 'research':
            from .research import start_research
            job=start_research(store,args.id,args.runner)
            print(f'Research started for #{args.id} with {args.runner}; log: {job["log"]}')
        elif args.command == 'widget':
            from .instance import run_widget
            return run_widget(store,background=args.background,if_not_running=args.if_not_running,renderer=args.renderer)
        elif args.command in ('install-autostart','uninstall-autostart'):
            from .install import install_autostart, uninstall_autostart
            print(install_autostart(shell=args.shell,login=args.login) if args.command=='install-autostart' else uninstall_autostart())
        elif args.command in ('install-launcher', 'uninstall-launcher'):
            from .app_launcher import install_launcher, uninstall_launcher
            print(install_launcher(executable=args.executable) if args.command == 'install-launcher' else uninstall_launcher())
        elif args.command == 'doctor':
            from .doctor import inspect, format_report
            info=inspect(); print(format_report(info)); return 0 if info['ok'] else 1
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'sticky: {exc}', file=sys.stderr)
        return 1
