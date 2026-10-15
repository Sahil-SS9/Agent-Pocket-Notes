"""Hermes adapter: classic CLI delivery only. No GUI imports in this package."""
from __future__ import annotations
import atexit
import logging
import os
import threading
from ..store import Store
from ..targets import Registry, deliver_pending
from ..clipboard import has_display
from ..launch import launch_widget
from .surface import TOOL_SCHEMA, make_command, make_reference, make_tool

log=logging.getLogger(__name__)


class SessionBridge:
    def __init__(self,ctx,store,*,interval=1):
        self.ctx=ctx
        self.store=store
        self.registry=Registry(store.home)
        self.interval=interval
        self.thread=None
        self.stopping=threading.Event()
        self.target=None
        self.session_id=None
        self.guard=threading.Lock()
        ctx.on_unload(self.stop)
        atexit.register(self.stop)

    def on_start(self,session_id='',model='',platform='',**kwargs):
        if platform!='cli' or not session_id:
            return
        manager=getattr(self.ctx,'_manager',None)
        if manager is not None and getattr(manager,'_cli_ref',None) is None:
            # Hermes labels one-shot research runs as cli, but those processes
            # have no attached REPL queue and cannot receive injected messages.
            return
        try:
            with self.guard:
                self.session_id=session_id
                record=self.registry.register('hermes',session_id,pid=os.getpid())
                self.target=record['target']
                if self.thread is None:
                    self.thread=threading.Thread(target=self._watch,name='sticky-outbox',daemon=True)
                    self.thread.start()
        except Exception:
            log.exception('Sticky CLI session registration failed')

    def _watch(self):
        while not self.stopping.wait(self.interval):
            try:
                with self.guard:
                    if self.target is None:
                        continue
                    self.registry.register('hermes',self.session_id,pid=os.getpid())
                    deliver_pending(self.store.home,self.target,self.ctx.inject_message)
            except Exception:
                log.exception('Sticky watcher iteration failed; will retry')

    def stop(self):
        self.stopping.set()
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(timeout=2)
        if self.target:
            try:
                self.registry.remove(self.target)
            except OSError:
                log.exception('Sticky session cleanup failed')
        atexit.unregister(self.stop)


def register(ctx, *, reference_api=None):
    store=Store()
    bridge=SessionBridge(ctx,store)
    if reference_api is None:
        from agent.context_references import ContextReferenceProvider, ContextCompletionItem
        reference_api=(ContextReferenceProvider,ContextCompletionItem)
    ctx.register_context_reference(make_reference(store,*reference_api))
    ctx.register_command('sticky',make_command(ctx,store,lambda:has_display(),lambda **kwargs:launch_widget(**kwargs)),
                         description='Open the sticky board or manage a local note',args_hint='[add TEXT | list | pin N | done N | send N | research N]')
    ctx.register_tool(name='sticky_notes',toolset='sticky',schema=TOOL_SCHEMA,handler=make_tool(store))

    def on_start(session_id='',model='',platform='',**kwargs):
        bridge.on_start(session_id=session_id,model=model,platform=platform)
        try:
            if not os.getenv('STICKY_INTENT_SUPERVISED_RUN') and platform=='cli' and ctx.get_config('autostart_widget',False) and has_display():
                launch_widget()
        except Exception:
            log.exception('Sticky optional autostart failed')
    ctx.register_hook('on_session_start',on_start)
    # on_session_start does not fire on resumed sessions; this hook repairs
    # registration without changing prompts or automatically sending notes.
    ctx.register_hook('pre_llm_call',bridge.on_start)
    return bridge
