"""Hermes command, context reference and tool contracts. Pure core imports only."""
from __future__ import annotations
from dataclasses import asdict
import json
import shlex
from ..cli import board_text
from ..research import start_research
from ..targets import context_message

TOOL_SCHEMA={
    'name':'sticky_notes',
    'description':'Save, find and pin private sticky-board notes. Saving never sends or researches a note.',
    'parameters':{
        'type':'object',
        'properties':{
            'action':{'type':'string','enum':['search','get','add','pin','list']},
            'id':{'type':'integer','minimum':1},
            'body':{'type':'string'},
            'query':{'type':'string'},
            'status':{'type':'string','enum':['inbox','pinned','done','all']},
        },
        'required':['action'],
        'additionalProperties':False,
    },
}


def make_reference(store,base,item_class):
    class NoteReference(base):
        prefix='note'
        description='Private sticky-board note'
        async def autocomplete(self,query,*,limit=10):
            notes=store.list('all',query)
            if query.isdigit():
                notes=[n for n in store.list('all') if str(n.id).startswith(query)]
            return [item_class(text=f'@note:{n.id}',display=f'#{n.id} · {n.title}',meta=n.status) for n in notes[:max(0,limit)]]
        async def expand(self,target):
            try:
                return context_message(store.get(target))
            except (OSError,ValueError):
                return None
    return NoteReference()


def make_tool(store):
    def handler(args,**kwargs):
        try:
            action=args.get('action')
            if action=='add':
                result={'note':asdict(store.add(args['body'],source='hermes'))}
            elif action=='get':
                result={'note':asdict(store.get(args['id']))}
            elif action=='pin':
                result={'note':asdict(store.update(args['id'],status='pinned'))}
            elif action=='search':
                result={'notes':[asdict(n) for n in store.list('all',args.get('query',''))]}
            elif action=='list':
                result={'notes':[asdict(n) for n in store.list(args.get('status','inbox'))]}
            else:
                raise ValueError('Unknown sticky action')
            return json.dumps({'success':True,**result},ensure_ascii=False)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            return json.dumps({'success':False,'error':str(exc)})
    return handler


def make_command(ctx,store,has_display,launch):
    def command(raw_args=''):
        try:
            raw=raw_args.strip()
            if not raw:
                if has_display():
                    opened,reason=launch(wait=True)
                    if opened:
                        return reason
                else:
                    reason='No display available'
                return f'{reason}; showing the board as text.\n'+board_text(store,'all')
            action,_,rest=raw.partition(' ')
            if action=='add':
                note=store.add(rest,source='hermes')
                return f'Added #{note.id}: {note.title}'
            if action=='list':
                return board_text(store,'all')
            args=shlex.split(rest)
            if action not in {'pin','done','send','research'} or not args:
                return 'Usage: /sticky [add TEXT | list | pin N | done N | send N | research N]'
            note=store.get(args[0])
            if action in {'pin','done'}:
                state='pinned' if action=='pin' else 'done'
                store.update(note.id,status=state)
                return f'#{note.id}: {state}'
            if action=='send':
                if not ctx.inject_message(context_message(note)):
                    raise ValueError('No classic CLI host accepted this note; use sticky send or clipboard')
                return f'Sent #{note.id} into this CLI session'
            job=start_research(store,note.id,'hermes')
            return f'Research started for #{note.id}; log: {job["log"]}'
        except (OSError,ValueError,RuntimeError) as exc:
            return f'sticky: {exc}'
    return command
