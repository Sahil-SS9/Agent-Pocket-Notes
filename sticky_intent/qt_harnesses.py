"""Native harness picker orchestration; probes never block the Qt event loop."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import threading
from PySide6.QtCore import QObject,Property,Signal,Slot,Qt,QUrl
from PySide6.QtGui import QGuiApplication,QDesktopServices
from . import harnesses
from . import runs
from .io import atomic_write

DOCS={
'hermes':'https://hermes-agent.nousresearch.com/docs/getting-started/quickstart/',
'claude':'https://code.claude.com/docs/en/setup',
'codex':'https://developers.openai.com/codex/cli',
'pi':'https://pi.dev/docs/latest/getting-started',
'command-code':'https://commandcode.ai/docs/quickstart',
'opencode':'https://opencode.ai/docs/',
}

class HarnessBridge(QObject):
    changed=Signal()
    finished=Signal(object)
    runAccepted=Signal()

    def __init__(self,pocket):
        super().__init__(pocket)
        self.pocket=pocket; self.store=pocket.controller.store
        self.kind='hermes'; self.operation='send'; self.busy=False; self.generation=0
        self._connection={}; self._sessions=[]; self._jobs=[]; self._status=''
        self._probed=None  # (kind, options signature) of the last successful probe result
        self.finished.connect(self._finished,Qt.QueuedConnection)
        self.refresh()

    @Property('QVariantList',constant=True)
    def harnesses(self): return [dict(kind=k,label=harnesses.LABELS[k]) for k in harnesses.KINDS]
    @Property(str,notify=changed)
    def selected(self): return self.kind
    @Property(str,notify=changed)
    def intent(self): return self.operation
    @Property(bool,notify=changed)
    def checking(self): return self.busy
    @Property('QVariantMap',notify=changed)
    def status(self): return self._connection
    @Property('QVariantList',notify=changed)
    def sessions(self): return self._sessions
    @Property('QVariantList',notify=changed)
    def runJobs(self): return self._jobs
    @Property(bool,notify=changed)
    def running(self): return any(j.get('state') in runs.ACTIVE for j in self._jobs)
    @Property('QVariantMap',notify=changed)
    def configuration(self):
        try: return harnesses.options_for(self.store,self.kind)
        except (OSError,ValueError) as exc: self._status=str(exc); return {}
    @Property(str,notify=changed)
    def statusText(self): return self._status
    @Property('QVariantList',notify=changed)
    def noteHistory(self):
        try: return runs.note_history(self.store)
        except (OSError,ValueError): return []
    @Property('QVariantList',notify=changed)
    def noteHistoryGroupRows(self):
        try: return runs.note_history_group_rows(self.store)
        except (OSError,ValueError): return []

    @Slot()
    def refreshHistory(self): self.refresh()

    @Slot(int,str,str,result=bool)
    def continueWith(self,noteId,kind,session):
        """Resume the note's recorded session where the harness still has it in this
        workspace/profile. Returns False so the caller offers a labelled new run instead,
        rather than silently attaching to a session that is gone or scoped elsewhere."""
        try:
            if not self.pocket.select(noteId): return False
            self.begin('send')
            if kind: self.choose(kind)
        except (OSError,ValueError,RuntimeError): return False
        if not self._connection.get('can_run') or not session: return False
        token=next((row.get('token') for row in self._sessions
                    if row.get('mode')=='resume' and row.get('enabled') and row.get('token')==session),None)
        if not token: return False
        self.startSession(token)
        return True
    @Property(str,notify=changed)
    def account(self):
        options=self.configuration
        details='Desktop account: '+Path.home().name+' · '+harnesses.LABELS[self.kind]
        if self.kind in {'hermes','codex'}: details+=' · profile: '+(options.get('profile') or 'native default')
        if self.kind in {'hermes','pi'}: details+=' · provider: '+(options.get('provider') or 'native default')
        return details+' · model: '+(options.get('model') or 'native default')

    def refresh(self):
        options_signature=None
        try:
            options=harnesses.options_for(self.store,self.kind)
            options_signature=json.dumps(options,sort_keys=True)
            cached=self._probed if self._probed and self._probed[0]==self.kind and self._probed[1]==options_signature else None
            if cached is not None: self._connection=dict(cached[2])
            else: self._connection=harnesses.connection(self.kind,options)
            # A proven-ready probe stays valid until the kind or its options change,
            # so reopening Send/Research (or run completion) never downgrades it.
            self._sessions=[dict(row,mode='resume',token=row['session_id']) for row in runs.sessions(self.store,self.kind)]
        except (OSError,ValueError) as exc:
            options_signature=None; self._connection=dict(state='setup_required',can_run=False,reason=str(exc)); self._sessions=[]
        if options_signature is None or self._connection.get('state')=='ready':
            self._probed=(self.kind,options_signature,dict(self._connection)) if options_signature is not None else self._probed
        elif self._probed and (self._probed[0]!=self.kind or self._probed[1]!=options_signature):
            self._probed=None
        try:
            from .targets import Registry
            for row in Registry(self.store.home).list():
                if row['kind']==self.kind:
                    self._sessions.append(dict(mode='context',token=row['target'],enabled=True,label=harnesses.LABELS[self.kind]+' · '+row['cwd']+' · context only'+(' · next message' if self.kind=='claude' else ' · classic CLI')))
        except (OSError,ValueError):
            pass
        self.changed.emit()

    @Slot(str)
    def begin(self,operation):
        if operation in {'send','research'}: self.operation=operation
        self.refresh()

    @Slot(str)
    def choose(self,kind):
        if kind not in harnesses.KINDS or self.busy: return
        self.kind=kind; self.generation+=1; self._status=''; self.refresh()

    @Slot()
    def check(self):
        if self.busy: return
        kind=self.kind; options=self.configuration; generation=self.generation
        self.busy=True; self._status='Checking installed version and native authentication status…'; self.changed.emit()
        def task():
            try: result=harnesses.connection(kind,options,probe=True)
            except Exception as exc: result=dict(state='check_failed',can_run=False,reason=str(exc))
            self.finished.emit(dict(action='check',generation=generation,result=result))
        threading.Thread(target=task,daemon=True,name='pocket-harness-check').start()

    @Slot(object)
    def _finished(self,event):
        self.busy=False
        if event['action']=='check':
            if event['generation']==self.generation:
                self._connection=event['result']; self._status=self._connection['reason']
                if self._connection.get('state')=='ready':
                    try: self._probed=(self.kind,json.dumps(harnesses.options_for(self.store,self.kind),sort_keys=True),dict(self._connection))
                    except (OSError,ValueError): self._probed=None
        elif event.get('error'):
            self._status=event['error']; self._connection.update(can_run=False,state='check_failed',reason=event['error'])
        else:
            self._status='Agent run started for note #'+str(event['result']['note_id'])+'. A successful reply will append below your text.'
            self.runAccepted.emit()
        self.changed.emit()

    @Slot()
    def startNew(self): self.startSession('')

    @Slot(str)
    def startSession(self,session):
        if self.busy or self.running or not self._connection.get('can_run') or not self.pocket.hasNote: return
        if not self.pocket.save(): return
        note=self.pocket.controller.selected
        kind=self.kind; operation=self.operation
        self.busy=True; self._status='Preparing agent run…'; self.changed.emit()
        def task():
            try:
                result=runs.start_run(self.store,note.id,kind,operation,session or None,expected_updated=note.updated)
                self.finished.emit(dict(action='start',result=result))
            except Exception as exc: self.finished.emit(dict(action='start',error=str(exc)))
        threading.Thread(target=task,daemon=True,name='pocket-harness-launch').start()

    @Slot(str)
    def attachContext(self,target):
        if self.operation!='send' or not self.pocket.hasNote: return
        if self.pocket.send(self.kind,target):
            self._status='Context queued. This path does not start a turn or capture a reply.'
            self.changed.emit(); self.runAccepted.emit()
        else: self._status=self.pocket.error; self.changed.emit()

    @Slot(str,str,str,str,str,str,result=bool)
    def saveOptions(self,executable,model,provider,profile,home,cwd):
        try:
            harnesses.save_options(self.store,self.kind,dict(executable=executable,model=model,provider=provider,profile=profile,home=home,cwd=cwd))
            self.generation+=1; self.refresh(); self._status='Settings saved. Check connection before starting work.'; self.changed.emit(); return True
        except (OSError,ValueError) as exc: self._status=str(exc); self.changed.emit(); return False

    @Slot()
    def setup(self):
        options=self.configuration; exe=harnesses.resolve_executable(self.kind,options)
        if not exe:
            QDesktopServices.openUrl(QUrl(DOCS[self.kind])); self._status='Installation instructions opened. Install as this desktop user, then check connection.'; self.changed.emit(); return
        options={**options,'executable':exe}; command=harnesses.setup_command(self.kind,options)
        terminal=next((shutil.which(x) for x in ['gnome-terminal','konsole','xterm','x-terminal-emulator'] if shutil.which(x)),None)
        if not terminal:
            import shlex
            QGuiApplication.clipboard().setText(shlex.join(command))
            self._status='No terminal launcher found. Native setup command copied; run it in this desktop account.'; self.changed.emit(); return
        separator=['--'] if Path(terminal).name=='gnome-terminal' else ['-e']
        try:
            subprocess.Popen([terminal,*separator,*command],env=harnesses.environment(self.kind,options),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            self._status='Native setup requested. '+('In Pi, use /login and select a provider. ' if self.kind=='pi' else '')+'Complete setup, then Check connection.'
        except OSError as exc: self._status='Could not launch setup: '+str(exc)
        self.changed.emit()

    @Slot()
    def modelPicker(self):
        options=self.configuration; exe=harnesses.resolve_executable(self.kind,options)
        if not exe: self.setup(); return
        command=[exe]
        if self.kind in {'hermes','codex'} and options.get('profile'): command+=['--profile',options['profile']]
        if self.kind=='hermes': command+=['model']
        terminal=next((shutil.which(x) for x in ['gnome-terminal','konsole','xterm','x-terminal-emulator'] if shutil.which(x)),None)
        if not terminal:
            import shlex
            QGuiApplication.clipboard().setText(shlex.join(command))
            self._status='Native model-picker command copied. No note was sent.'
        else:
            separator=['--'] if Path(terminal).name=='gnome-terminal' else ['-e']
            try:
                subprocess.Popen([terminal,*separator,*command],env=harnesses.environment(self.kind,options),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
                self._status='Native model picker requested. Use the harness model picker (usually /model or /models). No note was sent; close it and recheck afterwards.'
            except OSError as exc: self._status='Could not launch model picker: '+str(exc)
        self.changed.emit()

    @Slot()
    def help(self): QDesktopServices.openUrl(QUrl(DOCS[self.kind]))

    @Slot()
    def copySetup(self):
        import shlex
        options=self.configuration; command=shlex.join(harnesses.setup_command(self.kind,options))
        if self.kind=='hermes' and options.get('home'): command='HERMES_HOME='+shlex.quote(options['home'])+' '+command
        QGuiApplication.clipboard().setText(command); self._status='Native setup command copied. Run it as '+Path.home().name+'.'; self.changed.emit()

    def poll(self):
        selected=self.pocket.controller.selected
        new=runs.jobs(self.store,selected.id if selected else -1)
        if new!=self._jobs:
            self._jobs=new
            if new:
                latest=new[0]
                self._status=(harnesses.LABELS[latest['kind']]+' · '+latest['operation']+' · '+latest['state']+(' · '+latest['error'] if latest.get('error') else ''))
            self.changed.emit()
