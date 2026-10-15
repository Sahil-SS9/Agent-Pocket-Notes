"""Toolkit-independent Pocket Notes state machine. All writes stay in the store.

GUI bindings never own note revisions. Dirty text is checkpointed separately;
external changes only replace clean text. Conflicts require keep-both or reload.
"""
from __future__ import annotations
import json
from .io import atomic_write
from .store import Note, BODY_LIMIT

DEFAULTS = dict(theme='modern', font_family='Noto Sans', text_size=100,
                interface_size=100, styled_text=False, on_top=False, dark=False)
MODES = {'notes', 'capture', 'icon', 'hud'}


class PocketController:
    def __init__(self, store):
        self.store = store
        self.state_path = store.home / 'pocket-state.json'
        self.capture_draft = ''
        self._capture_committed = None
        self.body = ''
        self.mode = 'notes'
        self.icon_restore = 'notes'
        self.error = ''
        self.message = 'Saved on this device'
        self.conflict = False
        self.selected = None
        self.preferences = DEFAULTS.copy()
        self.geometries = {}
        self.last_target = None
        self.query = ''
        self.status_filter = 'all'
        self._load()

    @property
    def dirty(self):
        return self.body != (self.selected.body if self.selected else '')

    def _load(self):
        path = self.state_path if self.state_path.exists() else self.store.home / 'widget-state.json'
        try:
            state = json.loads(path.read_text('utf-8')) if path.exists() else {}
            if not isinstance(state, dict): raise ValueError('Invalid saved appearance')
            preferences = state.get('preferences', state)
            for k in DEFAULTS:
                try: self._validate(k, preferences.get(k, DEFAULTS[k]))
                except ValueError: continue
                self.preferences[k] = preferences.get(k, DEFAULTS[k])
            self.mode = state.get('mode', 'notes') if state.get('mode') in MODES else 'notes'
            self.icon_restore = state.get('icon_restore') if state.get('icon_restore') in {'notes','capture','hud'} else 'notes'
            target = state.get('last_target')
            if isinstance(target, list) and len(target)==2 and target[0] in {'hermes','claude','clipboard'} and (target[1] is None or isinstance(target[1],str)):
                self.last_target = target
            geometries = state.get('geometries', {})
            if isinstance(geometries, dict):
                for k,g in geometries.items():
                    if k in MODES and isinstance(g,list) and len(g)==4 and all(type(n) is int and abs(n)<100000 for n in g) and g[2]>0 and g[3]>0:
                        self.geometries[k] = g
            draft = state.get('capture_draft','')
            if isinstance(draft,str) and len(draft.encode())<=BODY_LIMIT: self.capture_draft = draft
            committed = state.get('capture_committed')
            if isinstance(committed,list) and len(committed)==2 and type(committed[0]) is int and isinstance(committed[1],str):
                self._capture_committed = committed
            note_id = state.get('last_selected')
            if note_id:
                try: self.selected = self.store.get(note_id)
                except (ValueError,FileNotFoundError): pass
            if self.selected is None:
                notes = self.store.list('all')
                if notes: self.selected = notes[0]
            self.body = self.selected.body if self.selected else ''
            checkpoint = state.get('editor_checkpoint')
            if isinstance(checkpoint,dict) and isinstance(checkpoint.get('body'),str):
                if len(checkpoint['body'].encode())<=BODY_LIMIT:
                    raw = checkpoint.get('base')
                    base = Note.decode(raw.encode()) if isinstance(raw,str) else None
                    self.selected = base
                    self.body = checkpoint['body']
                    self.message = 'Recovered unsaved draft'
                    self.conflict = bool(base and self.store.get(base.id).updated != base.updated)
        except (OSError,ValueError,TypeError) as exc:
            self.error = 'Saved state could not be read: ' + str(exc)

    def _validate(self, name, value):
        if name not in DEFAULTS: raise ValueError('Unknown appearance preference')
        if name=='theme' and value not in {'modern','sticker','retro','paper','midnight','glass','field'}: raise ValueError('Invalid theme')
        if name=='font_family' and (not isinstance(value,str) or not value.strip() or len(value)>200): raise ValueError('Invalid font family')
        if name in {'text_size','interface_size'} and (type(value) is not int or not 25<=value<=200): raise ValueError('Invalid text percentage')
        if name in {'styled_text','on_top','dark'} and type(value) is not bool: raise ValueError('Invalid boolean preference')

    def set_preference(self, name, value):
        self._validate(name,value)
        old = self.preferences[name]
        self.preferences[name] = value
        if not self.checkpoint():
            self.preferences[name] = old
            return False
        return True

    def checkpoint(self):
        state = dict(version=1, preferences=self.preferences, mode=self.mode,
                     icon_restore=self.icon_restore, capture_draft=self.capture_draft, capture_committed=self._capture_committed,
                     geometries=self.geometries, last_target=self.last_target,
                     last_selected=self.selected.id if self.selected else None)
        if self.dirty:
            state['editor_checkpoint'] = dict(body=self.body, base=self.selected.encode().decode() if self.selected else None)
        try:
            atomic_write(self.state_path,json.dumps(state,ensure_ascii=False).encode())
        except (OSError,ValueError) as exc:
            self.error = str(exc)
            return False
        return True

    def select(self, note_id):
        if not self.save(): return False
        try: note = self.store.get(note_id)
        except (OSError,ValueError) as exc:
            self.error = str(exc); return False
        self.selected = note
        self.body = note.body
        self.conflict = False
        self.error = ''
        return self.checkpoint()

    def new_note(self):
        if not self.save(): return False
        try: note = self.store.add('',source='widget')
        except (OSError,ValueError) as exc:
            self.error = str(exc); return False
        self.selected = note; self.body = ''; self.conflict = False
        self.query = ''; self.status_filter = 'all'; self.mode = 'notes'
        return self.checkpoint()

    def capture_save(self):
        if not self.capture_draft.strip():
            self.error = 'Write a note before saving.'; self.mode = 'capture'; return False
        # A hidden dirty editor must not be bypassed by quick capture.
        if not self.save(): return False
        original_draft = self.capture_draft
        try:
            if self._capture_committed and self._capture_committed[1]==original_draft:
                note = self.store.get(self._capture_committed[0])
            else:
                note = self.store.add(original_draft,source='widget')
                self._capture_committed = [note.id,original_draft]
        except (OSError,ValueError) as exc:
            self.error = str(exc); self.mode = 'capture'; return False
        self.capture_draft = ''; self.error = ''
        self.message = f'Note #{note.id} saved'
        self.icon_restore = 'capture'; self.mode = 'icon'
        self.query = ''; self.status_filter = 'all'
        # Selected editor is intentionally unchanged; capture is a NEW note.
        committed = self._capture_committed
        self._capture_committed = None
        if not self.checkpoint():
            self._capture_committed = committed
            self.mode = 'capture'; self.capture_draft = original_draft
            self.message = f'Note #{note.id} saved; state checkpoint needs retry'
            return False
        self._capture_committed = None
        return True

    def save(self):
        if not self.dirty: return True
        try:
            if self.selected is None:
                self.selected = self.store.add(self.body,source='widget')
            else:
                self.selected = self.store.update(self.selected.id,expected_updated=self.selected.updated,body=self.body)
        except (OSError,ValueError) as exc:
            self.error = str(exc)
            self.conflict = 'changed on disk' in str(exc) or isinstance(exc,FileNotFoundError)
            self.checkpoint()
            return False
        self.error = ''; self.conflict = False; self.message = 'Saved on this device'
        return self.checkpoint()

    def refresh(self):
        if self.selected is None: return False
        try: newest = self.store.get(self.selected.id)
        except FileNotFoundError:
            if self.dirty:
                self.conflict = True; self.error = 'Note removed on disk. Keep both to preserve your draft.'
                return False
            self.selected = None; self.body = ''; return True
        except (OSError,ValueError) as exc:
            self.error = str(exc); return False
        if newest.updated == self.selected.updated: return False
        if self.dirty:
            self.conflict = True
            self.error = 'Note changed on disk. Your draft is safe; choose Keep both or Reload.'
            return False
        old_research = self.selected.research
        self.selected = newest; self.body = newest.body
        if old_research!=newest.research:
            self.message = 'Research ' + newest.research
            self.error = ''
        return True

    def keep_both(self):
        if not self.conflict: return False
        try: note = self.store.add(self.body,source='widget')
        except (OSError,ValueError) as exc:
            self.error = str(exc); return False
        self.selected = note; self.conflict = False; self.error = ''
        self.message = f'Draft preserved as note #{note.id}'
        return self.checkpoint()

    def reload(self):
        if not self.selected: return False
        try: note = self.store.get(self.selected.id)
        except (OSError,ValueError) as exc:
            self.error = str(exc); return False
        self.selected = note; self.body = note.body; self.conflict = False; self.error = ''
        return self.checkpoint()

    def transition(self, mode):
        if mode not in MODES: raise ValueError('Invalid window mode')
        if not self.save(): return False
        before = self.mode
        if mode == 'icon' and before in {'notes','capture','hud'}: self.icon_restore = before
        self.mode = mode
        if not self.checkpoint(): self.mode = before; return False
        return True

    def minimise(self): return self.transition('icon')
    def close(self): return self.save() and self.checkpoint()

    def mark(self, status):
        if not self.selected or not self.save(): return False
        try:
            self.selected = self.store.update(self.selected.id,expected_updated=self.selected.updated,status=status)
        except (OSError,ValueError) as exc:
            self.error = str(exc); return False
        self.error = ''; return True

    def delete_note(self):
        if not self.selected or not self.save(): return False
        try: self.store.delete(self.selected.id)
        except (OSError,ValueError) as exc:
            self.error = str(exc); return False
        self.selected = None; self.body = ''; self.conflict = False
        notes = self.store.list('all')
        if notes: self.selected = notes[0]; self.body = notes[0].body
        return self.checkpoint()

    def send(self, kind, session=None):
        if not self.selected or not self.save(): return False
        from .targets import send_note
        try: self.message = send_note(self.store,self.selected.id,kind,session=session)
        except (OSError,ValueError,RuntimeError) as exc:
            self.error = str(exc); return False
        self.error = ''; self.last_target = [kind,session]
        return self.checkpoint()

    def research(self, runner):
        if not self.selected or not self.save(): return False
        from .research import start_research
        try:
            job = start_research(self.store,self.selected.id,runner)
            self.selected = self.store.get(self.selected.id)
        except (OSError,ValueError,RuntimeError) as exc:
            self.error = str(exc); return False
        self.error = ''; self.message = 'Research running · full log: '+str(job['log'])
        return True

    def research_logs(self):
        if not self.selected: return []
        result = []
        for p in (self.store.home/'research').glob('*.json'):
            try:
                job=json.loads(p.read_text())
                log=self.store.home/'research'/p.with_suffix('.log').name
                if job['note_id']==self.selected.id:
                    result.append(dict(path=str(log),runner=job['runner'],state=job['state']))
            except (OSError,ValueError,KeyError): continue
        return result
