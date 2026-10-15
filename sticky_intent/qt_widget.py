"""Qt Quick desktop. Imported only after widget ownership is acquired.

The bridge is a thin QObject view of the toolkit-independent controller. Note
reload signals are separate from UI metadata so autosave never resets caret/undo.
"""
from pathlib import Path
import sys
from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, Qt, QSize
from PySide6.QtGui import QGuiApplication, QFontDatabase, QIcon, QSyntaxHighlighter, QTextCharFormat, QFont, QColor
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow, QQuickTextDocument
from .pocket import PocketController
from .store import Store


class NoteSyntax(QSyntaxHighlighter):
    def __init__(self, document, bridge):
        super().__init__(document)
        self.bridge = bridge

    def highlightBlock(self, text):
        if not self.bridge.controller.preferences['styled_text']: return
        style=QTextCharFormat()
        if text.startswith('#'):
            style.setFontWeight(QFont.Bold)
            # Locked agent-reply styling: reply blocks render in the letterpress grammar — serif italic, muted violet — while user text keeps the operator's font untouched.
            if text.startswith('## ✉ Reply'):
                serif=QTextCharFormat(style)
                current=serif.font(); current.setFamily('Georgia'); current.setItalic(True)
                serif.setFont(current)
                serif.setForeground(QColor('#5a4a7d'))
                self.setFormat(0,len(text),serif); return
            self.setFormat(0,len(text),style)
        elif text.startswith('> ') or text.startswith('❝'):
            style.setForeground(QColor('#5a4a7d'))
            italic=QTextCharFormat(style); current=italic.font(); current.setItalic(True)
            style.setFont(current)
            self.setFormat(0,len(text),style)
        elif text.startswith('```') or text.startswith('    '):
            style.setFontItalic(True)
            self.setFormat(0,len(text),style)


class PocketBridge(QObject):
    changed = Signal()
    documentLoaded = Signal()
    draftLoaded = Signal()
    requestSend = Signal()
    requestFocus = Signal(str)

    def __init__(self, store, instance=None):
        super().__init__()
        self.controller = PocketController(store)
        self.instance = instance
        self.window = None
        self._sessions = []
        self._notes = []
        self._highlighter = None
        self._applying_geometry = False
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(650)
        self.timer.timeout.connect(self.save)
        self.draft_timer = QTimer(self); self.draft_timer.setSingleShot(True); self.draft_timer.setInterval(300)
        self.draft_timer.timeout.connect(self.checkpoint)
        self.poller = QTimer(self); self.poller.setInterval(400); self.poller.timeout.connect(self.poll)
        self._update_notes()

    @Property(str,notify=changed)
    def mode(self): return self.controller.mode
    @Property(str,notify=changed)
    def body(self): return self.controller.body
    @Property(str,notify=changed)
    def draft(self): return self.controller.capture_draft
    @Property(str,notify=changed)
    def error(self): return self.controller.error
    @Property(str,notify=changed)
    def message(self): return 'Editing…' if self.controller.dirty and not self.controller.error else self.controller.message
    @Property(bool,notify=changed)
    def conflict(self): return self.controller.conflict
    @Property(bool,notify=changed)
    def hasNote(self): return self.controller.selected is not None
    @Property(str,notify=changed)
    def title(self): return self.controller.selected.title if self.hasNote else 'Capture a thought'
    @Property(str,notify=changed)
    def noteStatus(self): return self.controller.selected.status if self.hasNote else ''
    @Property(str,notify=changed)
    def researchState(self): return self.controller.selected.research if self.hasNote else 'none'
    @Property('QVariantMap',notify=changed)
    def preferences(self): return self.controller.preferences.copy()
    @Property('QVariantList',notify=changed)
    def notes(self): return self._notes
    @Property('QVariantMap',notify=changed)
    def counts(self):
        try:
            notes=self.controller.store.list('all')
            return {status:len(notes) if status=='all' else sum(n.status==status for n in notes) for status in ['all','inbox','pinned','done']}
        except (OSError,ValueError): return {}
    @Property('QVariantList',notify=changed)
    def sessions(self): return self._sessions
    @Property('QStringList',constant=True)
    def families(self): return QFontDatabase.families()
    @Property('QVariantList',notify=changed)
    def logs(self):
        from .runs import jobs
        selected=self.controller.selected
        native=[dict(path=j['log'],runner=j['kind'],state=j['state']) for j in jobs(self.controller.store,selected.id if selected else -1) if j.get('log')]
        return self.controller.research_logs()+native

    def _update_notes(self):
        c=self.controller
        try:
            rows=[dict(noteId=n.id,title=n.title,preview=n.body.replace('\n',' ')[:140],status=n.status,research=n.research,selected=bool(c.selected and c.selected.id==n.id)) for n in c.store.list(c.status_filter,c.query)]
            if rows!=self._notes: self._notes=rows; return True
        except (OSError,ValueError) as exc: c.error=str(exc)
        return False

    def update(self, reload=False):
        self._update_notes(); self.changed.emit()
        if reload: self.documentLoaded.emit()

    @Slot(str)
    def edit(self, body):
        self.controller.body=body
        self.timer.start(); self.draft_timer.start(); self.changed.emit()
    @Slot(str)
    def editDraft(self, body):
        self.controller.capture_draft=body; self.draft_timer.start()
    @Slot()
    def checkpoint(self):
        self.controller.checkpoint(); self.changed.emit()
    @Slot(result=bool)
    def save(self):
        ok=self.controller.save(); self.update(); return ok
    @Slot(int,result=bool)
    def select(self,note_id):
        ok=self.controller.select(note_id); self.update(reload=ok); return ok
    @Slot(result=bool)
    def newNote(self):
        ok=self.controller.new_note(); self._apply_window(); self.update(reload=ok)
        if ok: self.requestFocus.emit('editor')
        return ok
    @Slot(str)
    def filter(self,query):
        self.controller.query=query; self.update()
    @Slot(str)
    def statusFilter(self,status):
        if status in {'all','inbox','pinned','done'}: self.controller.status_filter=status; self.update()
    @Slot(str,int,result=bool)
    def sizePreference(self,name,value):
        return self.preference(name,value)

    @Slot(str,'QVariant',result=bool)
    def preference(self,name,value):
        previous_size=self.controller.preferences['interface_size']
        if name=='interface_size': self._remember_geometry()
        try: ok=self.controller.set_preference(name,value)
        except ValueError as exc: self.controller.error=str(exc); ok=False
        if ok and name=='interface_size' and previous_size!=value:
            ratio=value/previous_size
            for mode,geometry in self.controller.geometries.items():
                if mode!='icon':
                    geometry[2]=round(geometry[2]*ratio); geometry[3]=round(geometry[3]*ratio)
            self._apply_window(activate=False)
            self._remember_geometry(); self.controller.checkpoint()
        self.changed.emit()
        if name=='font_family': QGuiApplication.setFont(QFont(self.controller.preferences['font_family']))
        if name=='on_top': self._apply_window(resize=False)
        if self._highlighter: self._highlighter.rehighlight()
        return ok

    def _remember_geometry(self):
        if self.window and not self._applying_geometry:
            w=self.window
            previous=self.controller.geometries.get(self.mode)
            if previous and getattr(self,'_applied_size',None)==(self.mode,w.width(),w.height()):
                self.controller.geometries[self.mode]=[w.x(),w.y(),previous[2],previous[3]]
            else:
                self.controller.geometries[self.mode]=[w.x(),w.y(),w.width(),w.height()]

    def _apply_window(self, resize=True, activate=True):
        if not self.window: return
        self._applying_geometry=True
        w=self.window; mode=self.mode
        try:
            top=mode in {'capture','icon','hud'} or self.preferences['on_top']
            w.setFlag(Qt.WindowStaysOnTopHint,top)
            if resize:
                ui=self.preferences['interface_size']/100
                defaults={'notes':[120,80,round(480*ui),round(620*ui)],'hud':[120,80,round(460*ui),round(540*ui)],'capture':[160,160,round(780*ui),round(130*ui)],'icon':[160,160,96,96]}
                x,y,width,height=self.controller.geometries.get(mode,defaults[mode])
                area=w.screen().availableGeometry()
                minw=min(area.width(),360 if mode in {'notes','capture','hud'} else 80)
                minh=min(area.height(),360 if mode in {'notes','hud'} else max(90,int(100*ui)) if mode=='capture' else 90)
                width=min(area.width(),max(minw,width)); height=min(area.height(),max(minh,height))
                w.setMinimumSize(QSize(minw,minh))
                w.resize(width,height)
                self._applied_size=(mode,width,height)
                w.setPosition(max(area.x(),min(x,area.right()-width+1)),max(area.y(),min(y,area.bottom()-height+1)))
            if activate: w.show(); w.raise_(); w.requestActivate()
        finally: self._applying_geometry=False

    @Slot(str,result=bool)
    def show(self,mode):
        self._remember_geometry()
        ok=self.controller.transition(mode)
        if ok: self._apply_window()
        self.changed.emit()
        if ok: self.requestFocus.emit('captureInput' if mode=='capture' else 'mascot' if mode=='icon' else 'editor')
        return ok
    @Slot()
    def restore(self): self.show(self.controller.icon_restore)
    @Slot()
    def raiseNotes(self): self.show('notes')
    @Slot()
    def resetWindow(self):
        self.controller.geometries.pop('notes',None); self.controller.mode='notes'
        self._apply_window(); self.checkpoint()
    @Slot()
    def captureSave(self):
        self._remember_geometry()
        ok=self.controller.capture_save(); self.update()
        if ok: self.draftLoaded.emit(); self._apply_window()
    @Slot(str,result=bool)
    def mark(self,status):
        ok=self.controller.mark(status); self.update(); return ok
    @Slot()
    def togglePin(self): self.mark('inbox' if self.noteStatus=='pinned' else 'pinned')
    @Slot()
    def copy(self):
        QGuiApplication.clipboard().setText(self.body); self.controller.message='Note copied'; self.changed.emit()
    @Slot()
    def copyContext(self):
        if self.hasNote:
            QGuiApplication.clipboard().setText(f'Context from my notes (#{self.controller.selected.id}):\n{self.body}')
            self.controller.last_target=['clipboard',None]; self.controller.message='Context copied'; self.checkpoint()
    @Slot()
    def pasteCapture(self):
        # Preserve an existing capture rather than silently replace it.
        if self.controller.capture_draft:
            self.controller.error='Capture already contains a draft. Save or clear it before capturing clipboard.'
            self.show('capture'); return
        self.controller.capture_draft=QGuiApplication.clipboard().text()
        self.draftLoaded.emit(); self.show('capture')
    @Slot()
    def openSend(self):
        if not self.hasNote or not self.save(): return
        from .targets import Registry
        try:
            self._sessions=[dict(s,label=s['kind']+' · '+s['cwd']+(' · next message' if s['kind']=='claude' else ' · classic CLI')) for s in Registry(self.controller.store.home).list()]
        except (OSError,ValueError) as exc: self.controller.error=str(exc)
        self.changed.emit(); self.requestSend.emit()
    @Slot(str,str,result=bool)
    def send(self,kind,session):
        if kind=='clipboard': self.copyContext(); return True
        ok=self.controller.send(kind,session or None); self.update(); return ok
    @Slot()
    def sendLast(self):
        target=self.controller.last_target
        if target: self.send(target[0],target[1] or '')
        else: self.openSend()
    @Property('QVariantMap',notify=changed)
    def researchOptions(self):
        from .research import hermes_options
        try: return hermes_options(self.controller.store)
        except (OSError,ValueError) as exc:
            self.controller.error=str(exc); return {}

    @Property(str,notify=changed)
    def researchAccount(self):
        import os
        from .research import hermes_options
        try:
            options=hermes_options(self.controller.store)
            home=options['home'] or os.getenv('HERMES_HOME') or str(Path.home()/'.hermes')
            return 'Runs as '+Path.home().name+' · Hermes home: '+home+' · profile: '+(options['profile'] or 'default')
        except (OSError,ValueError) as exc: return str(exc)

    @Slot(str,str,str,str,str,result=bool)
    def saveResearchOptions(self,executable,profile,provider,model,home):
        from .research import save_hermes_options
        try:
            save_hermes_options(self.controller.store,dict(executable=executable,profile=profile,provider=provider,model=model,home=home))
            self.controller.error=''; self.controller.message='Research settings saved'
            self.changed.emit(); return True
        except (OSError,ValueError) as exc:
            self.controller.error=str(exc); self.changed.emit(); return False

    @Slot()
    def copyResearchSetup(self):
        from .research import hermes_setup_command
        try:
            command=hermes_setup_command(self.controller.store)
            QGuiApplication.clipboard().setText(command)
            self.controller.message='Setup command copied. Run it as '+Path.home().name+', then retry Research.'
            self.controller.error=''
        except (OSError,ValueError) as exc: self.controller.error=str(exc)
        self.changed.emit()

    @Slot(str,result=bool)
    def research(self,runner):
        ok=self.controller.research(runner); self.update(); return ok
    @Slot(result=bool)
    def deleteNote(self):
        ok=self.controller.delete_note(); self.update(reload=ok); return ok
    @Slot()
    def keepBoth(self): self.update(reload=self.controller.keep_both())
    @Slot()
    def reload(self): self.update(reload=self.controller.reload())
    @Slot(str,result=str)
    def readLog(self,path):
        p=Path(path)
        if p.parent not in {self.controller.store.home/'research',self.controller.store.home/'runs'} or p.is_symlink() or p.suffix!='.log': return 'Invalid log path'
        try:
            with p.open('r',errors='replace') as f:
                text=f.read(1024*1024+1)
            return text[:1024*1024]+('\n[Display limited to 1 MiB; full log: '+str(p)+']' if len(text)>1024*1024 else '')
        except OSError as exc: return str(exc)
    @Slot(QObject)
    def attachDocument(self,quick_document):
        self._highlighter=NoteSyntax(quick_document.textDocument(),self)
    @Slot(result=bool)
    def closeAllowed(self):
        self._remember_geometry(); ok=self.controller.close(); self.changed.emit(); return ok

    def poll(self):
        old_body=self.body
        modified=self.controller.refresh()
        rows=self._update_notes()
        if modified or rows or self.controller.error:
            self.changed.emit()
            if self.body!=old_body: self.documentLoaded.emit()
        if getattr(self,'agents',None): self.agents.poll()
        if self.instance and self.instance.poll_raise(): self.raiseNotes()


def create_window(app,store,instance=None):
    bridge=PocketBridge(store,instance)
    app.setFont(QFont(bridge.controller.preferences['font_family']))
    engine=QQmlApplicationEngine()
    from .qt_harnesses import HarnessBridge
    bridge.agents=HarnessBridge(bridge)
    engine.rootContext().setContextProperty('pocket',bridge)
    engine.rootContext().setContextProperty('agents',bridge.agents)
    engine.load(str(Path(__file__).with_name('assets')/'Pocket.qml'))
    if not engine.rootObjects(): raise RuntimeError('Pocket QML could not load')
    window=engine.rootObjects()[0]; bridge.window=window; bridge._apply_window()
    bridge.poller.start()
    return engine,bridge,window


def run(store,instance=None):
    app=QGuiApplication.instance() or QGuiApplication([])
    app.setApplicationName('Sticky Intent')
    app.setWindowIcon(QIcon(str(Path(__file__).with_name('assets')/'pocket-note-mascot-alpha.png')))
    engine,bridge,window=create_window(app,store,instance)
    if instance: instance.ready()
    result=app.exec()
    bridge.timer.stop(); bridge.poller.stop(); bridge.draft_timer.stop()
    from shiboken6 import delete
    delete(engine)
    return result


def main():
    from .instance import run_widget
    return run_widget(Store(),renderer='qt')


if __name__=='__main__': raise SystemExit(main())
