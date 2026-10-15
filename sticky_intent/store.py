"""One private Markdown file per note, atomically updated under a process lock."""
from __future__ import annotations
from dataclasses import dataclass, asdict, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from .io import FileLock, atomic_write, private_dir

BODY_LIMIT = 1024 * 1024
STATUSES = {'inbox', 'pinned', 'done'}
SOURCES = {'clipboard', 'cli', 'widget', 'hermes', 'claude'}
RESEARCH = {'none', 'running', 'done', 'failed'}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


from .locations import default_home


def valid_id(value) -> int:
    if isinstance(value, bool) or not re.fullmatch(r'[1-9][0-9]*', str(value)):
        raise ValueError('Note id must be a positive integer')
    return int(value)


def title_for(body: str) -> str:
    return (next((line.strip() for line in body.splitlines() if line.strip()), 'Untitled note'))[:80]


def validate(note):
    valid_id(note.id)
    if note.status not in STATUSES or note.source not in SOURCES or note.research not in RESEARCH:
        raise ValueError('Invalid note status, source or research state')
    if '\n' in note.title or '\r' in note.title:
        raise ValueError('Note title must be one line')
    if len(note.body.encode('utf-8')) > BODY_LIMIT:
        raise ValueError('Note body exceeds the 1 MB limit')
    if note.remind is not None:
        try:
            datetime.fromisoformat(note.remind.replace('Z', '+00:00'))
        except (ValueError, AttributeError) as exc:
            raise ValueError('Reminder must be an ISO timestamp') from exc


@dataclass(frozen=True)
class Note:
    id: int
    status: str
    created: str
    updated: str
    source: str
    title: str
    research: str
    body: str
    remind: str | None = None

    def encode(self) -> bytes:
        validate(self)
        metadata = asdict(self)
        metadata.pop('body')
        lines = ['---']
        for key, value in metadata.items():
            if value is not None:
                scalar = str(value) if key == 'id' else json.dumps(value, ensure_ascii=False)
                lines.append(f'{key}: {scalar}')
        return ('\n'.join(lines)+'\n---\n'+self.body).encode('utf-8')

    @classmethod
    def decode(cls, raw: bytes):
        if not raw.startswith(b'---\n') or b'\n---\n' not in raw[4:]:
            raise ValueError('Invalid note header')
        header, body = raw[4:].split(b'\n---\n', 1)
        data = {}
        for line in header.decode('utf-8').splitlines():
            key, sep, value = line.partition(': ')
            if not sep:
                raise ValueError('Invalid note header field')
            if key not in cls.__dataclass_fields__ or key == 'body' or key in data:
                raise ValueError('Unknown or repeated note header field')
            # Strings written by us are JSON quoted. Human-written simple scalars
            # also work, including the handoff's example inline comments.
            if value.startswith('"') or key == 'id':
                data[key] = json.loads(value)
            else:
                data[key] = value.partition(' #')[0].rstrip()
        try:
            note = cls(**data, body=body.decode('utf-8'))
        except TypeError as exc:
            raise ValueError('Incomplete note header') from exc
        validate(note)
        return note


class Store:
    def __init__(self, home=None):
        self.home = Path(home) if home is not None else default_home()
        private_dir(self.home)
        self.notes = private_dir(self.home/'notes')
        self.trash = private_dir(self.home/'trash')
        self.lock_path = self.home/'store.lock'

    def _path(self, note_id):
        return self.notes/f'{valid_id(note_id)}.md'

    def add(self, body, *, source='cli', pin=False, remind=None):
        stamp = now()
        prototype = Note(1, 'pinned' if pin else 'inbox', stamp, stamp, source, title_for(body), 'none', body, remind)
        validate(prototype)
        with FileLock(self.lock_path):
            counter = self.home/'counter'
            if counter.exists():
                try:
                    previous = int(counter.read_text('utf-8').strip())
                    if previous < 0:
                        raise ValueError()
                except ValueError as exc:
                    raise ValueError('Corrupt note counter; restore it before adding notes') from exc
            else:
                previous = max((int(p.stem) for d in (self.notes,self.trash) for p in d.glob('*.md') if p.stem.isdigit()), default=0)
            note = replace(prototype, id=previous+1)
            atomic_write(counter, str(note.id).encode())
            atomic_write(self._path(note.id), note.encode())
            return note

    def get(self, note_id):
        path = self._path(note_id)
        try:
            note = Note.decode(path.read_bytes())
        except FileNotFoundError as exc:
            raise FileNotFoundError(f'Note #{note_id} does not exist') from exc
        if note.id != valid_id(note_id):
            raise ValueError('Note id and filename disagree')
        return note

    def list(self, status='inbox', query=''):
        if status not in STATUSES | {'all'}:
            raise ValueError('Invalid note status filter')
        notes = []
        for path in self.notes.glob('*.md'):
            if not path.stem.isdigit():
                continue
            try:
                note = self.get(path.stem)
            except FileNotFoundError:  # concurrent move to trash
                continue
            if (status == 'all' or note.status == status) and query.casefold() in (note.title+'\n'+note.body).casefold():
                notes.append(note)
        return sorted(notes, key=lambda n:n.id, reverse=True)

    def update(self, note_id, *, expected_updated=None, **changes):
        if set(changes) - {'body','status','research','remind','title','source'}:
            raise ValueError('Immutable or unknown note field')
        with FileLock(self.lock_path):
            old = self.get(note_id)
            if expected_updated is not None and old.updated != expected_updated:
                raise ValueError('Note changed on disk; reload before saving')
            if 'body' in changes and 'title' not in changes:
                changes['title'] = title_for(changes['body'])
            note = replace(old, updated=now(), **changes)
            atomic_write(self._path(note_id), note.encode())
            return note

    def delete(self, note_id):
        with FileLock(self.lock_path):
            self.get(note_id)
            target = self.trash/f'{valid_id(note_id)}.md'
            if target.exists():
                raise ValueError('Trash already contains this id; refusing to overwrite')
            os.replace(self._path(note_id), target)
            return target
