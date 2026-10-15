"""Field-notes desktop board. Only this production module imports tkinter.

Board, Focus and collapsed views share the same editor and store. Native Tk
controls retain keyboard focus and activation; styling is token-based.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, font

from .io import atomic_write
from .research import start_research
from .store import Store
from .targets import Registry, send_note

THEMES = {
    'paper': {'bg': '#F1F0EA', 'paper': '#FFFBEF', 'ink': '#292D29', 'muted': '#62665E',
              'line': '#D8DBD1', 'accent': '#EDC778', 'accent_ink': '#302816', 'accent_hover': '#F4D796',
              'selection': '#E2E7D9', 'focus': '#687C50', 'hover': '#E8E9E0',
              'disabled': '#A6AA9E', 'error': '#A43D31'},
    'midnight': {'bg': '#171D21', 'paper': '#232C30', 'ink': '#EDF0E8', 'muted': '#AFB9B0',
                 'line': '#414B4D', 'accent': '#E9C57B', 'accent_ink': '#242C28', 'accent_hover': '#F4D796',
                 'selection': '#37463E', 'focus': '#C0D49F', 'hover': '#303B3E',
                 'disabled': '#727D76', 'error': '#F5AEA2'},
    'sticker': {'bg': '#FFE6EC', 'paper': '#FFFDF7', 'ink': '#241E32', 'muted': '#655D72',
                'line': '#2F2940', 'accent': '#FFCE4F', 'accent_ink': '#281F00', 'accent_hover': '#FFDF88',
                'selection': '#C9F6DC', 'focus': '#6C459B', 'hover': '#F7C8D8',
                'disabled': '#8C8495', 'error': '#953744'},
    'retro': {'bg': '#3A8179', 'paper': '#FFFDF3', 'ink': '#101010', 'muted': '#4E4E46',
              'line': '#18151F', 'accent': '#F4D46B', 'accent_ink': '#181000', 'accent_hover': '#FFE8A0',
              'selection': '#E3D9FA', 'focus': '#382A69', 'hover': '#DDD8C8',
              'disabled': '#8C897F', 'error': '#A42D38'},
}
COLOURS = THEMES['paper']  # Legacy palettes remain compatible with saved preferences.


def age(created):
    seconds = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(created.replace('Z', '+00:00'))).total_seconds())
    if seconds < 60:
        return 'now'
    if seconds < 3600:
        return f'{int(seconds // 60)}m'
    if seconds < 86400:
        return f'{int(seconds // 3600)}h'
    return f'{int(seconds // 86400)}d'


def fit_text(text, face, width):
    if face.measure(text) <= width:
        return text
    while text and face.measure(text + '…') > width:
        text = text[:-1]
    return text.rstrip() + '…'


class TargetPicker:
    """One deliberately selected target; a Claude send is not an immediate turn."""
    def __init__(self, parent):
        self.parent = parent
        self.note_id = parent.selected.id
        self.window = tk.Toplevel(parent.root)
        self.window.title(f'Send note #{self.note_id}')
        width = max(parent._px(360), min(parent._px(440), parent.root.winfo_screenwidth()))
        x = max(0, min(parent.root.winfo_rootx() + 12, parent.root.winfo_screenwidth() - width))
        y = max(0, min(parent.root.winfo_rooty() + 60, parent.root.winfo_screenheight() - 340))
        self.window.geometry(f'{width}x{parent._px(340)}+{x}+{y}')
        self.window.minsize(parent._px(360), parent._px(320))
        self.window.transient(parent.root)
        self.window.configure(bg=parent.colours['bg'])
        frame = ttk.Frame(self.window, padding=16); frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Send to your agent', style='Heading.TLabel').pack(anchor='w')
        ttk.Label(frame, text=f'Note #{self.note_id} · choose a destination', style='Meta.TLabel').pack(anchor='w', pady=(3, 12))
        self.tree = ttk.Treeview(frame, columns=('target',), show='headings', selectmode='browse', height=4, style='Target.Treeview')
        self.tree.heading('target', text='Live sessions + clipboard')
        self.tree.column('target', width=width - 40, minwidth=290)
        self.tree.pack(fill='both', expand=True)
        self.targets = {}
        self.face = parent.face
        for index, session in enumerate(Registry(parent.store.home).list()):
            key = str(index); kind = session['kind']
            stamp = datetime.fromtimestamp(session['started']).strftime('%H:%M')
            suffix = ' (next message)' if kind == 'claude' else f' · {stamp}'
            prefix = 'Hermes' if kind == 'hermes' else 'Claude'
            folder = Path(session['cwd']).name or session['cwd']
            label = f'{prefix} · {folder}{suffix}'
            while folder and self.face.measure(label) > int(self.tree.column('target', 'width')) - 8:
                folder = folder[:-1]
                label = f'{prefix} · {folder.rstrip()}…{suffix}'
            self.tree.insert('', 'end', iid=key, values=(label,))
            self.targets[key] = (kind, session['session_id'])
        self.tree.insert('', 'end', iid='clipboard', values=('Clipboard',))
        self.targets['clipboard'] = ('clipboard', None)
        ttk.Label(frame, text='Hermes starts a turn. Claude attaches to your next message.\nClipboard works with any other agent.', style='Meta.TLabel', wraplength=width - 40).pack(anchor='w', pady=(10, 10))
        footer = ttk.Frame(frame); footer.pack(fill='x')
        self.send_button = ttk.Button(footer, text='Send selected note', style='Primary.TButton', command=self.send)
        self.send_button.pack(side='right')
        ttk.Button(footer, text='Cancel', style='Quiet.TButton', command=self.close).pack(side='left')
        self.tree.bind('<Double-1>', lambda event: self.send())
        self.window.bind('<Return>', lambda event: self.send())
        self.window.bind('<Escape>', lambda event: self.close())
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        first = self.tree.get_children()[0]
        self.tree.selection_set(first); self.tree.focus(first); self.tree.focus_set()

    def send(self):
        if self.parent.selected is None or self.parent.selected.id != self.note_id:
            self.close()
            return
        selected = self.tree.selection()
        if selected and self.parent.send_to(*self.targets[selected[0]]):
            self.close()

    def close(self):
        if self.window.winfo_exists():
            self.window.destroy()
        if self.parent.picker is self:
            self.parent.picker = None


class Appearance:
    """Real runtime fonts and continuous reading zoom; chrome stays usable at 25%."""
    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent.root)
        self.window.title('Typography and appearance')
        self.window.transient(parent.root)
        self.window.configure(background=parent.colours['bg'])
        frame = ttk.Frame(self.window, padding=16); frame.pack(fill='both', expand=True)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text='Make it comfortable to read', style='Heading.TLabel').grid(row=0, column=0, sticky='w', pady=(0, 12))
        ttk.Label(frame, text='Skin', style='Meta.TLabel').grid(row=1, column=0, sticky='w')
        self.skin_box = ttk.Combobox(frame, state='readonly', values=['Sticker Club', 'Retro Workbench', 'Paper', 'Midnight'])
        self.skin_box.grid(row=2, column=0, sticky='ew', pady=(4, 12))
        self.skin_box.set({'sticker':'Sticker Club', 'retro':'Retro Workbench', 'paper':'Paper', 'midnight':'Midnight'}[parent.theme])
        self.skin_box.bind('<<ComboboxSelected>>', lambda e: parent.safe(lambda: parent.set_theme({'Sticker Club':'sticker', 'Retro Workbench':'retro', 'Paper':'paper', 'Midnight':'midnight'}[self.skin_box.get()])))
        ttk.Label(frame, text='Font family (available in this runtime)', style='Meta.TLabel').grid(row=3, column=0, sticky='w')
        self.font_box = ttk.Combobox(frame, state='readonly', values=parent.available_fonts)
        self.font_box.configure(font=parent._font(11))
        self.font_box.set(parent.family); self.font_box.grid(row=4, column=0, sticky='ew', pady=(4, 12))
        self.font_box.bind('<<ComboboxSelected>>', lambda e: parent.safe(lambda: parent.set_font_family(self.font_box.get())))
        ttk.Label(frame, text='Reading text: 25% to 200%', style='Heading.TLabel').grid(row=5, column=0, sticky='w')
        self.size_scale = tk.Scale(frame, from_=25, to=200, resolution=1, orient='horizontal',
                                   variable=parent.text_size_var, command=lambda value: parent.safe(lambda: parent.set_text_size(int(float(value)))),
                                   background=parent.colours['bg'], foreground=parent.colours['ink'], highlightthickness=0,
                                   troughcolor=parent.colours['selection'], font=parent._font(11))
        self.size_scale.grid(row=6, column=0, sticky='ew', pady=8)
        self.percentage = ttk.Spinbox(frame, from_=25, to=200, textvariable=parent.text_size_var, width=8,
                                      command=self.apply_size)
        self.percentage.grid(row=7, column=0, sticky='w')
        self.percentage.bind('<Return>', lambda e: self.apply_size())
        self.percentage.bind('<FocusOut>', lambda e: self.apply_size())
        self.sample = tk.Label(frame, text='The quick brown fox.\nA note worth keeping.', justify='left', anchor='w',
                               background=parent.colours['paper'], foreground=parent.colours['ink'],
                               font=parent._font(13, reading=True), wraplength=parent._px(350))
        self.sample.grid(row=8, column=0, sticky='ew', pady=12)
        ttk.Label(frame, text='Reading text changes. Controls stay readable.\n25% is deliberately tiny; reset to 100% any time.\nOnly fonts actually available to Tk are listed.', style='Meta.TLabel', wraplength=parent._px(350)).grid(row=9, column=0, sticky='w', pady=(0, 12))
        ttk.Label(frame, text='Interface text: 100% to 200%', style='Meta.TLabel').grid(row=10, column=0, sticky='w')
        self.interface_percentage = ttk.Spinbox(frame, from_=100, to=200, textvariable=parent.interface_size_var, width=8, command=self.apply_interface_size)
        self.interface_percentage.grid(row=11, column=0, sticky='w', pady=(4, 12))
        self.interface_percentage.bind('<Return>', lambda e: self.apply_interface_size())
        self.interface_percentage.bind('<FocusOut>', lambda e: self.apply_interface_size())
        footer=ttk.Frame(frame); footer.grid(row=12, column=0, sticky='ew')
        ttk.Button(footer, text='Reset to 100%', command=lambda: parent.set_text_size(100)).pack(side='left')
        ttk.Button(footer, text='Done', command=self.close).pack(side='right')
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.bind('<Escape>', lambda e: self.close())
        self.update()

    def apply_interface_size(self):
        try:
            self.parent.set_interface_size(self.parent.interface_size_var.get())
        except (ValueError, tk.TclError):
            self.parent.interface_size_var.set(self.parent.interface_size)
            self.parent.status.set('Choose an interface percentage from 100 to 200')

    def apply_size(self):
        try:
            self.parent.set_text_size(self.parent.text_size_var.get())
        except (ValueError, tk.TclError) as exc:
            self.parent.text_size_var.set(self.parent.text_size)
            self.parent.status.set('Choose a whole percentage from 25 to 200')

    def update(self):
        p=self.parent
        self.font_box.set(p.family)
        self.font_box.configure(font=p._font(11))
        self.skin_box.configure(font=p._font(11))
        self.percentage.configure(font=p._font(11))
        self.interface_percentage.configure(font=p._font(11))
        self.size_scale.configure(font=p._font(11))
        self.sample.configure(font=p._font(13, reading=True), background=p.colours['paper'], foreground=p.colours['ink'])
        self.size_scale.configure(background=p.colours['bg'], foreground=p.colours['ink'], troughcolor=p.colours['selection'])
        self.window.configure(background=p.colours['bg'])

    def close(self):
        if self.window.winfo_exists(): self.window.destroy()
        if self.parent.appearance is self: self.parent.appearance=None


class Widget:
    def __init__(self, root, store, *, instance=None):
        self.root = root; self.store = store; self.instance = instance
        self.selected = None; self.dirty = False; self.loading = False; self.closed = False
        self.save_timer = None; self.poll_timer = None; self.fingerprint = None
        self.picker = None; self.last_target = None; self._refreshing = False
        self._selecting = False; self._resizing = False; self._drag_origin = None
        self._notes = {}
        self.appearance = None
        self.presentation = 'window'; self._icon_restore = 'window'
        self._library_open = False
        self._drag_moved = False; self._icon_position = None
        self.view = 'board'; self.collapsed = False
        self.state_path = store.home / 'widget-state.json'
        try:
            state = json.loads(self.state_path.read_bytes())
            if not isinstance(state, dict):
                state = {}
        except (OSError, ValueError):
            state = {}
        families = {f.casefold(): f for f in font.families(root)}
        self.available_fonts = sorted(families.values(), key=str.casefold)
        default_family = next((families[f.casefold()] for f in ('Noto Sans', 'Segoe UI', 'DejaVu Sans', 'Helvetica') if f.casefold() in families), font.nametofont('TkDefaultFont').actual('family'))
        self.ui_family = default_family
        raw_family = state.get('font_family')
        self.family = families.get(raw_family.casefold(), default_family) if isinstance(raw_family, str) else default_family
        self.ui_family = self.family
        self.styled_text = state.get('styled_text') is True
        self.styled_text_var = tk.BooleanVar(value=self.styled_text)
        interface_size = state.get('interface_size', 100)
        self.interface_size = interface_size if type(interface_size) is int and 100 <= interface_size <= 200 else 100
        self.interface_size_var = tk.IntVar(value=self.interface_size)
        self.mono_family = font.nametofont('TkFixedFont').actual('family')
        self.display_scale = max(1.0, round(root.winfo_fpixels('1i') / 96 * 4) / 4)
        saved_size = state.get('text_size', 100)
        self.text_size = saved_size if type(saved_size) is int and 25 <= saved_size <= 200 else 100
        self.text_size_var = tk.IntVar(value=self.text_size)
        self.face = font.Font(root, font=self._font(11))
        raw_theme = state.get('theme', 'sticker')
        self.theme = raw_theme if isinstance(raw_theme, str) and raw_theme in THEMES else 'paper'
        self.theme_var = tk.StringVar(value=self.theme)
        self.colours = THEMES[self.theme]
        root.title('Sticky Intent'); root.minsize(self._px(360), self._px(520))
        try:
            root.geometry(state.get('geometry', self._default_geometry(960, 680)))
        except (tk.TclError, TypeError):
            root.geometry(self._default_geometry(960, 680))
        root.update_idletasks()
        self._board_geometry = root.geometry()
        self._expanded_geometry = self._board_geometry
        self._focus_geometry = state.get('focus_geometry', self._default_geometry(460, 540))
        raw_position = state.get('icon_position')
        if isinstance(raw_position, list) and len(raw_position) == 2 and all(type(n) is int for n in raw_position):
            self._icon_position = tuple(raw_position)
        target = state.get('last_target')
        if (isinstance(target, (list, tuple)) and len(target) == 2
                and isinstance(target[0], str) and target[0] in {'hermes', 'claude', 'clipboard'}
                and (target[1] is None or isinstance(target[1], str))):
            self.last_target = tuple(target)
        self.top = tk.BooleanVar(value=bool(state.get('on_top', False)))
        root.attributes('-topmost', self.top.get())
        self.status = tk.StringVar(value='Local only · Send and Research are always your choice.')
        self.detail_title = tk.StringVar(value='Capture a thought.')
        self.save_state = tk.StringVar(value='Stored on this device')
        self.research_state = tk.StringVar(value='')
        self.empty_text = tk.StringVar(value='Capture a thought.\nA question, a snippet or a plan for later.')
        self.search = tk.StringVar()
        self.buttons = {}
        self.style = ttk.Style(root); self.style.theme_use('clam')
        self._style()
        self.icon_canvas = tk.Canvas(root, width=self._px(80), height=self._px(80), highlightthickness=0, takefocus=True)
        self._mascot_image = None
        try:
            mascot = Path(__file__).with_name('assets') / 'pocket-note-mascot-alpha.png'
            if mascot.is_file():
                self._mascot_image = tk.PhotoImage(file=str(mascot))
                scale = max(1, self._mascot_image.width() // self._px(64))
                if scale > 1: self._mascot_image = self._mascot_image.subsample(scale, scale)
        except (tk.TclError, OSError):
            self._mascot_image = None
        self.icon_canvas.bind('<ButtonPress-1>', self._drag_start)
        self.icon_canvas.bind('<B1-Motion>', self._drag)
        self.icon_canvas.bind('<ButtonRelease-1>', self._drag_end)
        self.icon_canvas.bind('<Double-Button-1>', self._icon_open_event)
        self.icon_canvas.bind('<Return>', lambda e: self.open_from_icon())
        self.icon_canvas.bind('<space>', lambda e: self.open_from_icon())
        self.icon_menu = tk.Menu(root, tearoff=False)
        self.icon_menu.add_command(label='Open notes', command=lambda: self.safe(self.open_from_icon))
        self.icon_menu.add_command(label='Typography and skin…', command=lambda: self.safe(self.open_appearance))
        self.icon_menu.add_command(label='Quit Sticky Intent', command=self.close)
        self.icon_canvas.bind('<Button-3>', lambda e: self.icon_menu.tk_popup(e.x_root, e.y_root))
        self.outer = ttk.Frame(root, style='Workspace.TFrame', padding=self._px(16)); self.outer.pack(fill='both', expand=True)
        self.outer.columnconfigure(1, weight=1); self.outer.rowconfigure(1, weight=1)
        self.header = ttk.Frame(self.outer, style='Workspace.TFrame'); self.header.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, self._px(14)))
        self.header.columnconfigure(0, weight=1)
        self.brand = ttk.Label(self.header, text='Sticky Intent', style='Heading.TLabel')
        self.brand.grid(row=0, column=0, sticky='w')
        self._button(self.header, 'focus', 'HUD', self.toggle_focus).grid(row=0, column=1, padx=(4, 3))
        self._button(self.header, 'collapse', 'Hide', self.toggle_collapse).grid(row=0, column=2, padx=(0, 3))
        self._button(self.header, 'icon', 'Icon', self.minimize_to_icon).grid(row=0, column=3, padx=(0, 3))
        self._button(self.header, 'close', 'Close', self.close).grid(row=0, column=6)
        self._button(self.header, 'library', 'Notes', self.toggle_library).grid(row=0, column=4)
        self.buttons['library'].grid_remove()
        for key in ('focus', 'collapse', 'icon', 'library', 'close'): self.buttons[key].configure(width=0)
        more = ttk.Menubutton(self.header, text='Menu', style='Quiet.TMenubutton', width=4)
        more.grid(row=0, column=5); self.buttons['more'] = more
        self.more_menu = tk.Menu(more, tearoff=False)
        self.more_menu.add_checkbutton(label='Keep window on top', variable=self.top, command=lambda: root.attributes('-topmost', self.top.get()))
        self.more_menu.add_separator()
        for key, label in [('sticker', 'Sticker Club'), ('retro', 'Retro Workbench'), ('paper', 'Paper appearance'), ('midnight', 'Midnight appearance')]:
            self.more_menu.add_radiobutton(label=label, variable=self.theme_var, value=key, command=lambda key=key: self.set_theme(key))
        self.more_menu.add_separator()
        self.more_menu.add_command(label='New note                Ctrl+N', command=lambda: self.safe(self.new_note))
        self.more_menu.add_command(label='Capture clipboard    Ctrl+Shift+V', command=lambda: self.safe(self.paste_note))
        self.more_menu.add_separator()
        for size, label in [(100, 'Normal text'), (125, 'Larger text'), (150, 'Largest text')]:
            self.more_menu.add_radiobutton(label=label, variable=self.text_size_var, value=size, command=lambda size=size: self.safe(lambda: self.set_text_size(size)))
        self.more_menu.add_command(label='Typography and text size…', command=lambda: self.safe(self.open_appearance))
        self.more_menu.add_checkbutton(label='Styled headings and code', variable=self.styled_text_var, command=lambda: self.safe(self.toggle_styled_text))
        for size in (100, 125, 150, 200):
            self.more_menu.add_radiobutton(label=f'Interface text: {size}%', variable=self.interface_size_var, value=size, command=lambda size=size: self.safe(lambda: self.set_interface_size(size)))
        self.more_menu.add_command(label='Pin or unpin note', command=lambda: self.safe(self.pin))
        self.more_menu.add_command(label='Mark done', command=lambda: self.safe(self.done))
        self.more_menu.add_command(label='Research with Hermes', command=lambda: self.safe(lambda: self.research('hermes')))
        self.more_menu.add_command(label='Research with Claude Code', command=lambda: self.safe(lambda: self.research('claude')))
        self.more_menu.add_separator()
        self.more_menu.add_command(label='Full window', command=lambda: self.safe(lambda: self.set_presentation('window')))
        self.more_menu.add_command(label='Collapse or expand note', command=lambda: self.safe(self.toggle_collapse))
        self.more_menu.add_command(label='Floating HUD', command=lambda: self.safe(lambda: self.set_presentation('hud')))
        self.more_menu.add_command(label='Minimise to floating icon', command=lambda: self.safe(self.minimize_to_icon))
        self.more_menu.add_command(label='About Sticky Intent', command=lambda: self.status.set('Sticky Intent 0.5.0 · Local notes · No automatic startup'))
        self.more_menu.add_command(label='Quit Sticky Intent', command=self.close)
        self.more_menu.add_command(label='Reset window size', command=lambda: self.safe(self.reset_window))
        more.configure(menu=self.more_menu)
        self.brand.bind('<ButtonPress-1>', self._drag_start); self.brand.bind('<B1-Motion>', self._drag)
        self.header.bind('<ButtonPress-1>', self._drag_start); self.header.bind('<B1-Motion>', self._drag)
        for surface in (self.header, self.brand):
            surface.bind('<ButtonRelease-1>', self._drag_end)
        self.library = ttk.Frame(self.outer, style='Library.TFrame', padding=self._px(12))
        self.library.grid(row=1, column=0, sticky='nsew', padx=(0, 20))
        self.library.columnconfigure(0, weight=1); self.library.rowconfigure(3, weight=1)
        self.library_caption = tk.Label(self.library, text='YOUR STICKERS', anchor='w', padx=8, pady=8, font=self._font(10, bold=True))
        self.library_caption.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        self.capture = ttk.Frame(self.library, style='Library.TFrame'); self.capture.grid(row=2, column=0, sticky='ew', pady=(0, 12))
        self.capture.columnconfigure(0, weight=1); self.capture.columnconfigure(1, weight=1)
        self._button(self.capture, 'new', '+ New note', self.new_note, 'Secondary.TButton').grid(row=0, column=0, sticky='ew', padx=(0, 4))
        self._button(self.capture, 'paste', 'Paste', self.paste_note).grid(row=0, column=1, sticky='ew', padx=(4, 0))
        self.searchbar = ttk.Frame(self.library, style='Library.TFrame'); self.searchbar.grid(row=1, column=0, sticky='ew', pady=(0, 12))
        self.searchbar.columnconfigure(1, weight=1)
        self.search_label = ttk.Label(self.searchbar, text='Find', style='LibraryMeta.TLabel')
        self.search_label.grid(row=0, column=0, padx=(0, 8))
        self.search_entry = ttk.Entry(self.searchbar, textvariable=self.search, style='Search.TEntry')
        self.search_entry.grid(row=0, column=1, sticky='ew', ipady=4)
        self.search_entry.bind('<Escape>', lambda event: self._clear_search())
        self.search.trace_add('write', lambda *args: self.safe(self._search_changed))
        self.notebook = ttk.Notebook(self.library, style='Board.TNotebook')
        self.notebook.grid(row=3, column=0, sticky='nsew')
        self.trees = {}; self.tabs = {}; self.tree_scrolls = {}
        self.card_views = {}; self.card_canvases = {}; self.card_hosts = {}; self.card_buttons = {}
        self._card_signature = None
        for status, label in [('inbox', 'Inbox'), ('pinned', 'Pinned'), ('done', 'Done')]:
            tab = ttk.Frame(self.notebook); self.tabs[status] = tab; self.notebook.add(tab, text=label)
            tree = ttk.Treeview(tab, columns=('title', 'age', 'research'), show='tree', displaycolumns=(), height=3, selectmode='browse', style='Sticky.Treeview')
            tree.column('#0', width=340, minwidth=180, stretch=True)
            # Hidden values preserve the semantic row data separately from its preview.
            tree.column('title', width=250); tree.column('age', width=40); tree.column('research', width=80)
            scroll = ttk.Scrollbar(tab, orient='vertical', command=tree.yview, style='Slim.Vertical.TScrollbar')
            tree.configure(yscrollcommand=scroll.set)
            tree.pack(side='left', fill='both', expand=True); scroll.pack(side='right', fill='y')
            tree.bind('<<TreeviewSelect>>', lambda event, t=tree: self._tree_selected(t))
            self.trees[status] = tree; self.tree_scrolls[status] = scroll
            deck = ttk.Frame(tab); self.card_views[status] = deck
            canvas = tk.Canvas(deck, width=1, height=self._px(110), highlightthickness=0, background=self.colours['bg'])
            card_scroll = ttk.Scrollbar(deck, orient='vertical', command=canvas.yview)
            canvas.configure(yscrollcommand=card_scroll.set)
            canvas.pack(side='left', fill='both', expand=True); card_scroll.pack(side='right', fill='y')
            host = ttk.Frame(canvas, style='Library.TFrame'); host.columnconfigure(0, weight=1)
            item = canvas.create_window(0, 0, window=host, anchor='nw')
            host.bind('<Configure>', lambda e, c=canvas: c.configure(scrollregion=c.bbox('all')))
            canvas.bind('<Configure>', lambda e, c=canvas, i=item: c.itemconfigure(i, width=e.width))
            self.card_canvases[status] = canvas; self.card_hosts[status] = host
            self._bind_card_scroll(canvas, canvas)
        self.notebook.bind('<<NotebookTabChanged>>', lambda event: self.safe(self._tab_changed))
        self.paper = tk.Frame(self.outer, background=self.colours['paper'], highlightthickness=1, highlightbackground=self.colours['line'])
        self.paper.grid(row=1, column=1, sticky='nsew')
        self.paper.columnconfigure(0, weight=1); self.paper.rowconfigure(1, weight=1)
        self.skin_caption = tk.Label(self.paper, text='YOUR STICKER', anchor='w', padx=self._px(16), pady=self._px(8), font=self._font(10, bold=True))
        metadata = ttk.Frame(self.paper, style='Paper.TFrame', padding=(self._px(16), self._px(10), self._px(16), 0))
        self.metadata = metadata
        metadata.grid(row=0, column=0, sticky='ew'); metadata.columnconfigure(0, weight=1)
        ttk.Label(metadata, textvariable=self.detail_title, style='PaperMeta.TLabel').grid(row=0, column=0, sticky='w')
        ttk.Label(metadata, textvariable=self.save_state, style='PaperMeta.TLabel').grid(row=0, column=1, sticky='e')
        self.editor_frame = tk.Frame(self.paper, background=self.colours['paper'])
        self.editor_frame.grid(row=1, column=0, sticky='nsew', padx=self._px(8), pady=self._px(10))
        self.editor_frame.columnconfigure(0, weight=1); self.editor_frame.rowconfigure(0, weight=1)
        self.editor = tk.Text(self.editor_frame, wrap='word', undo=True, autoseparators=True,
                              font=self._font(13, reading=True), width=1, height=3, background=self.colours['paper'], foreground=self.colours['ink'],
                              insertbackground=self.colours['ink'], relief='flat', borderwidth=0, padx=self._px(14), pady=self._px(10),
                              spacing1=2, spacing3=5, selectbackground=self.colours['selection'], selectforeground=self.colours['ink'],
                              highlightthickness=1, highlightbackground=self.colours['paper'], highlightcolor=self.colours['focus'])
        scrollbar = ttk.Scrollbar(self.editor_frame, orient='vertical', command=self.editor.yview, style='Paper.Vertical.TScrollbar')
        self.editor.configure(yscrollcommand=scrollbar.set)
        self.editor.grid(row=0, column=0, sticky='nsew'); scrollbar.grid(row=0, column=1, sticky='ns')
        self.empty_label = ttk.Label(self.editor_frame, textvariable=self.empty_text, style='Empty.TLabel', justify='left', wraplength=290)
        self.editor.bind('<<Modified>>', self._modified)
        note_footer = ttk.Frame(self.paper, style='Paper.TFrame', padding=(self._px(12), self._px(4), self._px(12), self._px(10)))
        self.note_footer = note_footer
        note_footer.grid(row=2, column=0, sticky='ew'); note_footer.columnconfigure(2, weight=1)
        self._button(note_footer, 'pin', 'Pin', self.pin, 'Paper.TButton').grid(row=0, column=0, padx=(0, 2))
        self._button(note_footer, 'done', 'Done', self.done, 'Paper.TButton').grid(row=0, column=1)
        self.research_badge = ttk.Label(metadata, textvariable=self.research_state, style='PaperMeta.TLabel')
        self.research_badge.grid(row=1, column=0, columnspan=2, sticky='w')
        self.research_badge.grid_remove()
        self._button(note_footer, 'copy', 'Copy', self.copy, 'Paper.TButton').grid(row=0, column=2, padx=(4, 0))
        note_footer.columnconfigure(2, weight=0); note_footer.columnconfigure(3, weight=1)
        for key in ('pin', 'done', 'copy'): self.buttons[key].configure(width=0)
        self.actions = ttk.Frame(note_footer, style='Paper.TFrame'); self.actions.grid(row=0, column=4, sticky='e', padx=(12, 0))
        self.actions.columnconfigure(0, weight=1, uniform='agent'); self.actions.columnconfigure(1, weight=1, uniform='agent')
        self._button(self.actions, 'send', 'Send', self.open_picker, 'Primary.TButton').grid(row=0, column=0, sticky='ew', padx=(0, 4))
        self.buttons['send'].configure(width=0)
        research = ttk.Menubutton(self.actions, text='Research', style='Secondary.TMenubutton')
        research.grid(row=0, column=1, sticky='ew', padx=(4, 0)); self.buttons['research'] = research
        self.research_menu = tk.Menu(research, tearoff=False)
        for runner, label in [('hermes', 'Research with Hermes'), ('claude', 'Research with Claude Code')]:
            self.research_menu.add_command(label=label, command=lambda runner=runner: self.safe(lambda: self.research(runner)))
        research.configure(menu=self.research_menu)
        self.status_label = ttk.Label(self.outer, textvariable=self.status, style='Status.TLabel', wraplength=390, justify='left')
        self.status_label.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        self._shortcuts()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Configure>', self._resize)
        self.set_theme(self.theme)
        self.refresh()
        preferred = state.get('last_selected')
        if isinstance(preferred, int) and not isinstance(preferred, bool):
            try:
                self.select(preferred)
            except (OSError, ValueError):
                pass
        if state.get('view') == 'focus':
            self.toggle_focus()
        if state.get('presentation') == 'hud' and self.view == 'board':
            self.set_presentation('hud')
        if state.get('collapsed') is True:
            self.toggle_collapse()
        if state.get('presentation') == 'icon':
            if state.get('icon_restore') == 'hud' and self.view == 'board':
                self.set_presentation('hud')
            self.minimize_to_icon()
        self._poll()

    def _font(self, points, *, bold=False, mono=False, reading=False):
        # Point sizes honour actual display DPI; zoom applies to reading text,
        # not the controls needed to recover from an intentionally tiny 25%.
        scale = (self.text_size if reading else self.interface_size) / 100
        size = max(1 if reading else 8, round(points * scale))
        value = (self.mono_family if mono else (self.family if reading else self.ui_family), size)
        return value + ('bold',) if bold else value

    def _px(self, value):
        return round(value * self.display_scale)

    def _default_geometry(self, width, height):
        available_w = max(self._px(360), self.root.winfo_screenwidth() - self._px(40))
        available_h = max(self._px(360), self.root.winfo_screenheight() - self._px(80))
        return f'{min(self._px(width), available_w)}x{min(self._px(height), available_h)}+40+40'

    def reset_window(self):
        if self.presentation == 'icon': self.open_from_icon()
        if self.collapsed: self.toggle_collapse()
        self.root.geometry(self._default_geometry(960 if self.view == 'board' else 460, 680 if self.view == 'board' else 540))
        self.status.set('Window size reset for this display')

    def set_interface_size(self, size):
        if type(size) is not int or not 100 <= size <= 200:
            raise ValueError('Choose an interface percentage from 100 to 200')
        if size == self.interface_size:
            return
        self.interface_size = size
        if self.interface_size_var.get() != size: self.interface_size_var.set(size)
        self._apply_typography()
        self.status.set(f'Interface text: {size}%')

    def set_text_size(self, size):
        if type(size) is not int or not 25 <= size <= 200:
            raise ValueError('Choose a whole text percentage from 25 to 200')
        if size == self.text_size:
            return
        self.text_size = size
        if self.text_size_var.get() != size: self.text_size_var.set(size)
        self._apply_typography()
        self.status.set(f'Reading text: {size}%')

    def set_font_family(self, family):
        available = {f.casefold(): f for f in self.available_fonts}
        if not isinstance(family, str) or family.casefold() not in available:
            raise ValueError('Choose a font actually available in this runtime')
        self.family = available[family.casefold()]
        self.ui_family = self.family
        self._apply_typography()
        self.status.set(f'Font: {self.family}')

    def _apply_typography(self):
        if self.picker: self.picker.close()
        self.face.configure(family=self.ui_family, size=self._font(11)[1])
        self._style(); self.editor.configure(font=self._font(13, reading=True))
        for menu in (self.more_menu, self.research_menu, self.icon_menu):
            menu.configure(font=self._font(11))
        self.library_caption.configure(font=self._font(10, bold=True))
        self.search_entry.configure(font=self._font(11))
        self.skin_caption.configure(font=self._font(10, bold=True))
        self._format_editor()
        self._card_signature = None; self._render_cards()
        if self.appearance: self.appearance.update()
        self._fit_header()
        if self.presentation == 'icon': self._paint_icon()

    def toggle_styled_text(self):
        self.styled_text = self.styled_text_var.get()
        self._format_editor()

    def open_appearance(self):
        if self.appearance and self.appearance.window.winfo_exists():
            self.appearance.window.lift(); return
        self.appearance = Appearance(self)

    def set_presentation(self, mode):
        if mode not in ('window', 'hud', 'icon'):
            raise ValueError('Choose Window, HUD or Icon')
        if mode == 'icon': return self.minimize_to_icon()
        if self.presentation == 'icon': self.open_from_icon()
        if mode == self.presentation: return
        if (mode == 'hud') != (self.view == 'focus'):
            self.toggle_focus()

    def minimize_to_icon(self):
        if self.presentation == 'icon': return
        self.save()  # Failure must leave the visible editor and draft intact.
        if self.picker: self.picker.close()
        if self.appearance: self.appearance.close()
        if self.collapsed: self.toggle_collapse()
        self.root.update_idletasks()
        self._icon_restore = self.presentation
        self._icon_expanded_geometry = self.root.geometry()
        if self.view == 'board': self._board_geometry = self.root.geometry()
        else: self._focus_geometry = self.root.geometry()
        self.presentation = 'icon'
        self.outer.pack_forget(); self.icon_canvas.pack(fill='both', expand=True)
        self.root.overrideredirect(True); self.root.attributes('-topmost', True)
        size = self._px(80); self.root.minsize(size, size)
        x, y = self._icon_position or (self.root.winfo_x(), self.root.winfo_y())
        x = max(0, min(x, self.root.winfo_screenwidth() - size))
        y = max(0, min(y, self.root.winfo_screenheight() - size))
        self.root.geometry(f'{size}x{size}+{x}+{y}')
        self._paint_icon(); self.root.lift(); self.icon_canvas.focus_set()

    def open_from_icon(self):
        if self.presentation != 'icon': return
        self._icon_position = (self.root.winfo_x(), self.root.winfo_y())
        self.presentation = self._icon_restore
        self.icon_canvas.pack_forget(); self.outer.pack(fill='both', expand=True)
        self.root.overrideredirect(self.presentation == 'hud')
        self.root.attributes('-topmost', True if self.presentation == 'hud' else self.top.get())
        self.root.minsize(self._px(360), self._px(360 if self.view == 'focus' else 520))
        self.root.geometry(self._icon_expanded_geometry)
        self._apply_view(); self.root.deiconify(); self.root.lift(); self.editor.focus_set()

    def _icon_open_event(self, event):
        if not self._drag_moved: self.safe(self.open_from_icon)
        return 'break'

    def _paint_icon(self):
        c=self.colours; canvas=self.icon_canvas; p=self._px
        canvas.configure(background=c['bg']); canvas.delete('all')
        if self._mascot_image is not None:
            canvas.create_image(p(40), p(40), image=self._mascot_image)
            canvas.configure(cursor='hand2')
            return
        if self.theme == 'retro':
            canvas.create_rectangle(p(8),p(8),p(70),p(70),fill=c['paper'],outline=c['line'],width=p(2))
            canvas.create_rectangle(p(8),p(8),p(70),p(23),fill='#382A69',outline=c['line'])
            canvas.create_line(p(18),p(53),p(60),p(53),fill=c['line'],width=p(2))
        else:
            canvas.create_polygon(*[p(n) for n in (12,12,66,8,73,61,61,72,8,66)],fill=c['accent'],outline=c['line'],width=p(2))
            canvas.create_rectangle(p(25),p(4),p(57),p(17),fill=c['selection'],outline=c['line'])
        canvas.configure(cursor='hand2')

    def _style(self):
        c = self.colours; s = self.style
        for name in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont', 'TkTooltipFont', 'TkCaptionFont', 'TkSmallCaptionFont', 'TkIconFont'):
            try:
                font.nametofont(name, root=self.root).configure(family=self.family, size=self._font(11)[1])
            except tk.TclError:
                pass
        chrome = '#ECE9D8' if self.theme == 'retro' else c['bg']
        s.configure('.', font=self._font(11), background=chrome, foreground=c['ink'])
        s.configure('TFrame', background=chrome); s.configure('Paper.TFrame', background=c['paper'])
        s.configure('Workspace.TFrame', background=c['bg'])
        s.configure('Status.TLabel', background=c['bg'], foreground=c['muted'] if self.theme != 'retro' else '#FFFDF3', font=self._font(10))
        library_bg = c['selection'] if self.theme == 'sticker' else chrome
        s.configure('Library.TFrame', background=library_bg)
        s.configure('LibraryMeta.TLabel', background=library_bg, foreground=c['muted'], font=self._font(10))
        s.configure('TLabel', background=chrome, foreground=c['ink'])
        s.configure('Brand.TLabel', font=self._font(14, bold=True, mono=False),
                    background='#382A69' if self.theme == 'retro' else c['bg'],
                    foreground='#FFFFFF' if self.theme == 'retro' else c['ink'], padding=(6, 4))
        s.configure('Heading.TLabel', font=self._font(15, bold=True))
        s.configure('Meta.TLabel', font=self._font(10), foreground=c['muted'])
        s.configure('PaperMeta.TLabel', background=c['paper'], foreground=c['muted'], font=self._font(10))
        s.configure('Empty.TLabel', background=c['paper'], foreground=c['muted'], font=self._font(13))
        for name, bg, fg in [('Quiet', chrome, c['ink']), ('Secondary', c['selection'], c['ink']),
                             ('Primary', c['accent'], c['accent_ink']), ('Paper', c['paper'], c['muted'])]:
            for kind in ('TButton', 'TMenubutton'):
                key = name + '.' + kind
                s.configure(key, background=bg, foreground=fg, borderwidth=2 if self.theme == 'retro' else 0, padding=(self._px(8), self._px(6)), relief='raised' if self.theme == 'retro' else 'flat',
                            focuscolor=c['focus'], focusthickness=1, font=self._font(11), arrowcolor=fg)
                pressed = c['accent'] if name == 'Primary' else (c['selection'] if self.theme in ('sticker', 'retro') else c['line'])
                hover = c['accent_hover'] if name == 'Primary' else c['hover']
                s.map(key, background=[('disabled', bg if name == 'Paper' else c['bg']), ('pressed', pressed), ('active', hover)],
                      foreground=[('disabled', c['disabled'])])
        s.configure('Search.TEntry', fieldbackground=c['paper'], foreground=c['ink'], insertcolor=c['ink'], bordercolor=c['line'], lightcolor=c['line'], darkcolor=c['line'], padding=(8, 2))
        s.map('Search.TEntry', bordercolor=[('focus', c['focus'])])
        s.configure('Board.TNotebook', background=c['bg'], borderwidth=0, tabmargins=(0, 0, 0, 6))
        s.configure('Board.TNotebook.Tab', background=c['bg'], foreground=c['muted'], padding=(10, 7), borderwidth=0, font=self._font(10))
        s.map('Board.TNotebook.Tab', background=[('selected', c['selection']), ('active', c['hover'])], foreground=[('selected', c['ink'])])
        s.configure('Treeview', font=self._font(11))
        s.configure('Sticky.Treeview', background=c['bg'], fieldbackground=c['bg'], foreground=c['ink'], rowheight=max(44, self.face.metrics('linespace') * 2 + 8), borderwidth=0, font=self._font(11), indent=6)
        s.layout('Sticky.Treeview', [('Treeview.treearea', {'sticky': 'nswe'})])
        s.map('Sticky.Treeview', background=[('selected', c['selection'])], foreground=[('selected', c['ink'])])
        s.configure('Target.Treeview', background=c['paper'], fieldbackground=c['paper'], foreground=c['ink'], rowheight=max(32, self.face.metrics('linespace') + 12), font=self._font(11))
        s.map('Target.Treeview', background=[('selected', c['selection'])], foreground=[('selected', c['ink'])])
        s.configure('Treeview.Heading', background=c['bg'], foreground=c['muted'], font=self._font(10), padding=6, relief='flat')
        for name, bg in [('Slim', c['bg']), ('Paper', c['paper'])]:
            s.configure(name + '.Vertical.TScrollbar', troughcolor=bg, background=c['line'], bordercolor=bg, arrowcolor=c['muted'], width=self._px(16), arrowsize=self._px(12))

    def _button(self, parent, key, label, action, style='Quiet.TButton'):
        button = ttk.Button(parent, text=label, style=style, command=lambda: self.safe(action), takefocus=True)
        self.buttons[key] = button
        return button

    def set_theme(self, theme):
        if theme not in THEMES:
            raise ValueError('Choose an available skin')
        self.theme = theme; self.theme_var.set(theme); self.colours = THEMES[theme]
        self._style(); c = self.colours
        self.root.configure(background=c['bg'])
        self.paper.configure(background=c['paper'], highlightbackground=c['line'], highlightthickness=3 if self.theme == 'retro' else 2, relief='ridge' if self.theme == 'retro' else 'flat')
        self.library_caption.configure(text='NOTE INDEX' if self.theme == 'retro' else 'YOUR STICKERS',
                                       background='#382A69' if self.theme == 'retro' else c['selection'],
                                       foreground='#FFFFFF' if self.theme == 'retro' else c['ink'],
                                       font=self._font(10, bold=True, mono=False))
        self.editor_frame.configure(background=c['paper'])
        self.editor.configure(background=c['paper'], foreground=c['ink'], insertbackground=c['ink'],
                              selectbackground=c['selection'], selectforeground=c['ink'], highlightbackground=c['paper'], highlightcolor=c['focus'])
        for menu in (self.more_menu, self.research_menu, self.icon_menu):
            menu.configure(background=c['paper'], foreground=c['ink'], activebackground=c['selection'], activeforeground=c['ink'], font=self._font(11))
        self._format_editor()
        self._apply_skin(); self._header_text(); self._fit_header(); self._paint_icon()
        if self.appearance: self.appearance.update()
        if self.picker:
            self.picker.window.configure(background=c['bg'])

    def _apply_skin(self):
        c=self.colours
        for status, tree in self.trees.items():
            if self.theme == 'sticker':
                tree.pack_forget(); self.tree_scrolls[status].pack_forget()
                self.card_views[status].pack(fill='both', expand=True)
            else:
                self.card_views[status].pack_forget()
                tree.pack(side='left', fill='both', expand=True); self.tree_scrolls[status].pack(side='right', fill='y')
        styled = self.theme in ('sticker','retro')
        if styled and self.view != 'focus':
            self.skin_caption.grid(row=0, column=0, sticky='ew')
            self.metadata.grid_configure(row=1); self.editor_frame.grid_configure(row=2); self.note_footer.grid_configure(row=3)
            self.paper.rowconfigure(1, weight=0); self.paper.rowconfigure(2, weight=1)
            self.skin_caption.configure(background='#382A69' if self.theme=='retro' else c['selection'],
                                        foreground='#FFFFFF' if self.theme=='retro' else c['ink'],
                                        text=(f'NOTE_{self.selected.id:03d}.TXT' if self.selected else 'NOTE EDITOR') if self.theme=='retro' else 'YOUR NOTE')
        else:
            self.skin_caption.grid_remove()
            self.metadata.grid_configure(row=0); self.editor_frame.grid_configure(row=1); self.note_footer.grid_configure(row=2)
            self.paper.rowconfigure(1, weight=1); self.paper.rowconfigure(2, weight=0)
        self._card_signature = None; self._render_cards()

    def _render_cards(self):
        if self.theme != 'sticker': return
        signature = (self.fingerprint, self.selected.id if self.selected else None, self.ui_family)
        if signature == self._card_signature: return
        self._card_signature = signature; self.card_buttons = {}
        colours = ['#FFF3A9','#C8ECFF','#E4DDFF']
        for status, host in self.card_hosts.items():
            canvas = self.card_canvases[status]
            old_scroll = canvas.yview()[0]
            canvas.configure(background=self.colours['selection'])
            for child in host.winfo_children(): child.destroy()
            notes = [n for n in self._notes.values() if n.status==status]
            for index, note in enumerate(notes):
                selected = self.selected is not None and self.selected.id==note.id
                preview = next((line.strip() for line in note.body.splitlines()[1:] if line.strip()), 'A new thought…')
                title = fit_text(note.title or 'Untitled note', self.face, self._px(210))
                preview = fit_text(preview, self.face, self._px(210))
                button = tk.Button(host, text=f'{title}\n{preview}\n\n#{note.id} · {age(note.updated)}',
                                   command=lambda note_id=note.id: self.safe(lambda: self.select(note_id)),
                                   background=colours[index % len(colours)], foreground=self.colours['ink'],
                                   activebackground=self.colours['selection'], activeforeground=self.colours['ink'],
                                   font=self._font(11, bold=selected), borderwidth=3 if selected else 1, relief='solid',
                                   highlightthickness=1, highlightbackground=self.colours['line'], highlightcolor=self.colours['focus'],
                                   wraplength=self._px(210), justify='left', anchor='w', padx=self._px(12), pady=self._px(12), takefocus=True)
                button.grid(row=index, column=0, sticky='ew', padx=4, pady=(0, 12))
                self._bind_card_scroll(button, canvas)
                self.card_buttons[note.id]=button
            canvas.yview_moveto(old_scroll)
            if not notes:
                ttk.Label(host, text='No matches.' if self.search.get() else 'No notes here yet.', style='Meta.TLabel').grid(row=0,column=0,padx=12,pady=18)

    def _bind_card_scroll(self, surface, canvas):
        def scroll(event):
            units = -1 if getattr(event, 'num', 0) == 4 else (1 if getattr(event, 'num', 0) == 5 else (-1 if event.delta > 0 else 1))
            canvas.yview_scroll(units, 'units')
            return 'break'
        for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            surface.bind(sequence, scroll)

    def safe(self, action):
        try:
            return action()
        except (OSError, ValueError, RuntimeError, tk.TclError) as exc:
            self.status.set(str(exc))
            if self.dirty:
                self.save_state.set('Not saved')
            return None

    def _format_editor(self):
        self.editor.tag_configure('title', font=self._font(17, bold=True, reading=True), spacing3=10)
        self.editor.tag_configure('heading', font=self._font(12, bold=True, reading=True), spacing1=10, spacing3=6)
        self.editor.tag_configure('code', font=self._font(11, mono=True, reading=True), background=self.colours['selection'])
        for tag in ('title', 'heading', 'code'):
            self.editor.tag_remove(tag, '1.0', 'end')
        line = font.Font(self.root, font=self.editor.cget('font')).metrics('linespace')
        self.editor.configure(spacing1=0, spacing2=round(line * .35), spacing3=round(line * .35))
        if not self.styled_text:
            return
        self.editor.tag_add('title', '1.0', '1.end')
        fenced = False
        for index, line in enumerate(self.editor.get('1.0', 'end-1c').splitlines(), 1):
            if line.startswith('```'):
                fenced = not fenced
                self.editor.tag_add('code', f'{index}.0', f'{index}.end')
            elif fenced:
                self.editor.tag_add('code', f'{index}.0', f'{index}.end')
            elif line.startswith('## '):
                self.editor.tag_add('heading', f'{index}.0', f'{index}.end')

    def _short_title(self, note, tree):
        return fit_text(note.title, self.face, max(50, int(tree.column('title', 'width')) - 12))

    def _row_text(self, note, tree):
        title = self._short_title(note, tree)
        research = {'none': '', 'running': ' · researching', 'done': ' · research done', 'failed': ' · research failed'}[note.research]
        return f'{title}\n#{note.id} · {age(note.updated)} · {note.source}{research}'

    def rows(self, status):
        return [int(i) for i in self.trees[status].get_children()]

    def _active_status(self):
        active = self.notebook.select()
        return next((status for status, frame in self.tabs.items() if str(frame) == active), 'inbox')

    def _tree_selected(self, tree):
        if self._refreshing or self._selecting:
            return
        chosen = tree.selection()
        if chosen and (self.selected is None or self.selected.id != int(chosen[0])):
            self.safe(lambda: self.select(int(chosen[0])))

    def _metadata(self, note):
        self.detail_title.set(f'Note #{note.id} · {note.source}')
        if self.theme == 'retro': self.skin_caption.configure(text=f'NOTE_{note.id:03d}.TXT')
        self.buttons['pin'].configure(text='Unpin' if note.status == 'pinned' else 'Pin')
        self.save_state.set('Editing…' if self.dirty else 'Saved locally')
        self.research_state.set({'none': '', 'running': 'Researching…', 'done': 'Research done', 'failed': 'Failed'}[note.research])
        self.research_badge.grid() if note.research != 'none' else self.research_badge.grid_remove()
        self._header_text()

    def _load(self, note):
        if self.picker and (self.selected is None or self.selected.id != note.id):
            self.picker.close()
        self.loading = True; self.selected = note
        self.editor.configure(state='normal')
        self.editor.delete('1.0', 'end'); self.editor.insert('1.0', note.body)
        self.editor.edit_reset(); self.editor.edit_modified(False); self.editor.mark_set('insert', '1.0')
        self.dirty = False; self.loading = False
        self.empty_label.place_forget(); self._format_editor(); self._metadata(note)

    def _clear_detail(self):
        if self.picker:
            self.picker.close()
        self.loading = True; self.selected = None
        self.editor.configure(state='normal'); self.editor.delete('1.0', 'end'); self.editor.edit_modified(False)
        self.editor.configure(state='disabled'); self.dirty = False; self.loading = False
        self.detail_title.set('Your local scratchpad'); self.save_state.set(''); self.research_state.set('')
        self.empty_label.place(relx=0.5, rely=0.45, anchor='center')
        self._header_text()

    def select(self, note_id):
        self.save()
        note = self.store.get(note_id); self._selecting = True
        try:
            self._load(note); self.notebook.select(self.tabs[note.status]); self.refresh()
            tree = self.trees[note.status]
            if tree.exists(str(note.id)):
                tree.selection_set(str(note.id)); tree.see(str(note.id))
        finally:
            self._selecting = False
        self._see_card(note.id)
        if self._library_open:
            self._library_open = False; self._layout_workspace(); self._layout_header()

    def _see_card(self, note_id):
        button = self.card_buttons.get(note_id)
        if button is None: return
        canvas = self.card_canvases[self.selected.status]
        self.root.update_idletasks()
        region = canvas.bbox('all')
        if not region or region[3] <= canvas.winfo_height(): return
        top = button.winfo_y(); bottom = top + button.winfo_height()
        visible = canvas.canvasy(0)
        if top < visible: canvas.yview_moveto(top / region[3])
        elif bottom > visible + canvas.winfo_height():
            canvas.yview_moveto((bottom - canvas.winfo_height()) / region[3])

    def _modified(self, event=None):
        if self.loading or not self.editor.edit_modified():
            return
        self.editor.edit_modified(False)
        self.dirty = self.selected is not None
        if self.dirty:
            self.save_state.set('Editing…')
            self._format_editor()
            if self.save_timer:
                self.root.after_cancel(self.save_timer)
            self.save_timer = self.root.after(500, lambda: self.safe(self.save))

    def save(self):
        if self.closed or self.selected is None:
            return
        body = self.editor.get('1.0', 'end-1c')
        if body == self.selected.body:
            self.dirty = False; self.save_state.set('Saved locally')
            return
        try:
            updated = self.store.update(self.selected.id, body=body, expected_updated=self.selected.updated)
            # No delete/insert: keep caret, selection, scroll and the native undo stack.
            self.selected = updated; self.dirty = False
            self._metadata(updated); self.status.set(f'Saved #{updated.id} on this device')
        except ValueError as exc:
            if 'changed on disk' not in str(exc):
                raise
            old_id = self.selected.id
            copy = self.store.add(body, source='widget', pin=self.selected.status == 'pinned')
            self.selected = copy; self.dirty = False; self._metadata(copy)
            self.notebook.select(self.tabs[copy.status])
            self.status.set(f'#{old_id} changed elsewhere. Your edit is safe as #{copy.id}.')
        self.refresh()

    def _ensure_visible(self):
        tree = self.trees[self._active_status()]
        visible = tree.get_children()
        if self.selected is None or not tree.exists(str(self.selected.id)):
            # Never silently discard an unsaved edit while switching filters.
            if self.selected is not None and self.dirty:
                self.save()
            if visible:
                self._load(self.store.get(int(visible[0])))
            else:
                self._clear_detail()
        if self.selected and tree.exists(str(self.selected.id)):
            tree.selection_set(str(self.selected.id))

    def refresh(self):
        if self.closed or self._refreshing:
            return
        self._refreshing = True
        try:
            notes = self.store.list('all', self.search.get())
            self._notes = {note.id: note for note in notes}
            fingerprint = tuple((n.id, n.updated, n.status, n.research) for n in notes)
            if fingerprint != self.fingerprint:
                self.fingerprint = fingerprint
                for status, tree in self.trees.items():
                    old_scroll = tree.yview()
                    tree.delete(*tree.get_children())
                    subset = [n for n in notes if n.status == status]
                    self.notebook.tab(self.tabs[status], text=f'{status.title()}  {len(subset)}')
                    for note in subset:
                        tree.insert('', 'end', iid=str(note.id), text=self._row_text(note, tree), values=(self._short_title(note, tree), age(note.updated), note.research))
                    if old_scroll:
                        tree.yview_moveto(old_scroll[0])
                if self.selected:
                    try:
                        latest = self.store.get(self.selected.id)
                        if latest.research != self.selected.research and latest.research in {'done', 'failed'}:
                            self.status.set(f'Research #{latest.id}: {latest.research}')
                        if latest.updated != self.selected.updated and not self.dirty and self.editor.get('1.0', 'end-1c') == self.selected.body:
                            self._load(latest)
                    except FileNotFoundError:
                        if not self.dirty:
                            self._clear_detail()
            self._set_empty_message()
            if not self._selecting:
                self._ensure_visible()
            enabled = self.selected is not None
            for name in ('send', 'pin', 'done', 'copy'):
                self.buttons[name].configure(state='normal' if enabled else 'disabled')
            running = enabled and self.store.get(self.selected.id).research == 'running'
            self.buttons['research'].configure(state='normal' if enabled and not running else 'disabled')
            self._render_cards()
        finally:
            self._refreshing = False

    def _set_empty_message(self):
        if self.search.get():
            self.empty_text.set(f'No matches in {self._active_status().title()}.\nTry another tab or clear your search.')
        elif self._active_status() == 'pinned':
            self.empty_text.set('Keep the useful ones.\nPin a note and it will wait here for you.')
        elif self._active_status() == 'done':
            self.empty_text.set('Nothing finished yet.\nMark a note Done when you no longer need it.')
        else:
            self.empty_text.set('Capture a thought.\nA question, a snippet or a plan for later.')

    def _tab_changed(self):
        if not self._selecting and not self._refreshing:
            self.save(); self.refresh()

    def _search_changed(self):
        self.save(); self.fingerprint = None; self.refresh()

    def _clear_search(self):
        self.search.set('')
        return 'break'

    def new_note(self):
        self.save(); self.search.set('')
        note = self.store.add('', source='widget'); self.select(note.id)
        if self.collapsed:
            self.toggle_collapse()
        self.editor.focus_set(); self.status.set(f'New note #{note.id} · start typing')

    def paste_note(self):
        body = self.root.clipboard_get(); self.save(); self.search.set('')
        note = self.store.add(body, source='clipboard'); self.select(note.id)
        if self.collapsed:
            self.toggle_collapse()
        self.status.set(f'Captured #{note.id} from clipboard')

    def pin(self):
        self.save()
        if self.selected:
            state = 'inbox' if self.selected.status == 'pinned' else 'pinned'
            note = self.store.update(self.selected.id, status=state); self.select(note.id)
            self.status.set(f'#{note.id}: {state}')

    def done(self):
        self.save()
        if self.selected:
            note = self.store.update(self.selected.id, status='done'); self.select(note.id)
            self.status.set(f'#{note.id}: done')

    def copy(self, *, context=False):
        self.save()
        if self.selected:
            text = (f'Context from my notes (#{self.selected.id}):\n' if context else '') + self.selected.body
            self.root.clipboard_clear(); self.root.clipboard_append(text); self.root.update_idletasks()
            self.status.set(f'Copied #{self.selected.id}')

    def open_picker(self):
        self.save()
        if self.selected:
            if self.picker and self.picker.window.winfo_exists():
                self.picker.window.lift(); self.picker.tree.focus_set()
            else:
                self.picker = TargetPicker(self)

    def send_to(self, kind, session=None):
        if self.selected is None:
            return False
        try:
            self.save()
            if kind == 'clipboard':
                self.copy(context=True)
            else:
                self.status.set(send_note(self.store, self.selected.id, kind, session=session))
            self.last_target = (kind, session)
            return True
        except (OSError, ValueError, RuntimeError) as exc:
            self.status.set(str(exc)); return False

    def send_last(self):
        if self.last_target:
            self.send_to(*self.last_target)
        else:
            self.open_picker()

    def research(self, runner):
        self.save()
        if self.selected:
            if self.store.get(self.selected.id).research == 'running':
                self.status.set(f'Research #{self.selected.id} is already running')
                return
            start_research(self.store, self.selected.id, runner)
            self.status.set(f'Research #{self.selected.id} with {runner} is running'); self.refresh()

    def _shortcuts(self):
        shortcuts = {'n': self.new_note, 'Return': self.send_last, 'r': lambda: self.research('hermes'),
                     'p': self.pin, 'f': self.focus_search, 'Shift-V': self.paste_note}
        for modifier in ('Control', 'Command') if sys.platform == 'darwin' else ('Control',):
            for key, action in shortcuts.items():
                def callback(event, action=action):
                    self.safe(action); return 'break'
                self.root.bind(f'<{modifier}-{key}>', callback)
            def paste(event):
                if event.widget in (self.editor, self.search_entry):
                    return None  # Native Text/Entry paste keeps the caret and undo behaviour.
                self.safe(self.paste_note); return 'break'
            self.root.bind(f'<{modifier}-v>', paste)

    def focus_search(self):
        if self.presentation == 'icon': self.open_from_icon()
        if self.collapsed:
            self.toggle_collapse()
        if self.view == 'focus':
            self.toggle_focus()
        if self.root.winfo_width() < self._px(720):
            self._library_open = True; self._layout_workspace(); self._layout_header()
        self.search_entry.focus_set(); self.search_entry.selection_range(0, 'end')

    def _header_text(self):
        if self.collapsed and self.selected:
            suffix = {'none': '', 'running': ' · researching', 'done': ' · done', 'failed': ' · failed'}[self.selected.research]
            controls_width = sum(self.buttons[k].winfo_reqwidth() for k in ('collapse','icon','more'))
            available = max(50, self.root.winfo_width() - controls_width - 50)
            title = fit_text(f'#{self.selected.id} · {self.selected.title}', self.face, available - self.face.measure(suffix))
            self.brand.configure(text=title + suffix, style='TLabel')
        else:
            label = {'sticker': 'Sticker Club', 'retro': 'Retro Notes'}.get(self.theme, 'Sticky Intent')
            self.brand.configure(text=label, style='Brand.TLabel')

    def _library_width(self):
        return max(self._px(276), self.face.measure('Inbox 99  Pinned 99  Done 99') + self._px(48))

    def _workspace_wide(self):
        return self.view == 'board' and self.root.winfo_width() >= self._library_width() + self._px(444)

    def _layout_workspace(self):
        if self.presentation == 'icon': return
        for row in (1, 2): self.outer.rowconfigure(row, weight=0)
        self.outer.columnconfigure(0, weight=0, minsize=0)
        self.outer.columnconfigure(1, weight=0, minsize=0)
        for widget in (self.library, self.paper, self.status_label): widget.grid_remove()
        if self.collapsed: return
        self.status_label.grid()
        hud = self.view == 'focus'
        wide = self._workspace_wide()
        self.library_caption.grid_remove() if hud else self.library_caption.grid()
        for widget in (self.searchbar, self.notebook):
            widget.grid_remove() if hud else widget.grid()
        self.capture.grid_remove() if hud else self.capture.grid()
        self.skin_caption.grid_remove()  # Decorative headings no longer consume reading space.
        if wide:
            self.library.configure(padding=self._px(12), width=self._library_width() - self._px(20)); self.library.grid_propagate(False)
            self.outer.columnconfigure(0, minsize=self._library_width())
            self.outer.columnconfigure(1, weight=1)
            self.outer.rowconfigure(1, weight=1)
            self.library.grid(row=1, column=0, columnspan=1, sticky='nsew', padx=(0, self._px(20)), pady=0)
            self.paper.grid(row=1, column=1, columnspan=1, sticky='nsew', padx=0, pady=0)
        elif hud:
            self.library.configure(padding=0); self.library.grid_propagate(True)
            self.outer.columnconfigure(0, weight=1); self.outer.rowconfigure(2, weight=1)
            # HUD is a note surface; collection/capture remain in the menu.
            self.library.grid_remove()
            self.paper.grid(row=2, column=0, columnspan=2, sticky='nsew', padx=0, pady=0)
        else:
            self.outer.columnconfigure(0, weight=1); self.outer.rowconfigure(1, weight=1)
            self.library.configure(padding=self._px(12), width=self._library_width() - self._px(20)); self.library.grid_propagate(False)
            if self._library_open:
                self.library.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=0, pady=0)
            else:
                self.paper.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=0, pady=0)
        self._layout_note_actions()

    def _layout_note_actions(self):
        hud = self.view == 'focus'
        for key in ('pin', 'done'):
            self.buttons[key].grid_remove() if hud else self.buttons[key].grid()
        self.buttons['research'].grid_remove() if hud else self.buttons['research'].grid()
        width = self.root.winfo_width() - self._px(32) - self._px(32)
        if self._workspace_wide():
            width -= self._library_width()
        required = sum(self.buttons[k].winfo_reqwidth() for k in (('copy',) if hud else ('pin', 'done', 'copy'))) + self.buttons['send'].winfo_reqwidth() + (0 if hud else self.buttons['research'].winfo_reqwidth()) + self._px(24)
        compact = width < required
        self.actions.grid_configure(row=1 if compact else 0, column=0 if compact else 4,
                                    columnspan=4 if compact else 1, sticky='ew' if compact else 'e',
                                    padx=0 if compact else (12, 0), pady=(8, 0) if compact else 0)

    def toggle_library(self):
        if self.presentation == 'icon': self.open_from_icon()
        if self.view == 'focus': self.toggle_focus()
        if self.collapsed: self.toggle_collapse()
        self._library_open = not self._library_open
        self._layout_workspace(); self._layout_header()

    def _apply_view(self):
        if self.collapsed: self.buttons['focus'].grid_remove()
        else: self.buttons['focus'].grid()
        self.buttons['focus'].configure(text='Window' if self.view == 'focus' else 'HUD')
        self.buttons['collapse'].configure(text='Open' if self.collapsed else 'Hide')
        self.outer.configure(padding=(self._px(16), self._px(8)) if self.collapsed else self._px(16))
        self._header_text(); self._layout_workspace(); self._layout_header()

    def toggle_focus(self):
        if self.presentation == 'icon': self.open_from_icon()
        self.save()
        if self.collapsed:
            self.toggle_collapse()
        self.root.update_idletasks()
        if self.view == 'board':
            self._board_geometry = self.root.geometry(); self.view = 'focus'; self.presentation = 'hud'
            self.root.overrideredirect(True); self.root.attributes('-topmost', True)
            self.root.minsize(self._px(360), self._px(360))
            # Follow the current location instead of jumping back to a stale one.
            try:
                size = str(self._focus_geometry).split('+', 1)[0]
                self.root.geometry(f'{size}+{self.root.winfo_x()}+{self.root.winfo_y()}')
            except tk.TclError:
                self.root.geometry(f'420x480+{self.root.winfo_x()}+{self.root.winfo_y()}')
        else:
            self._focus_geometry = self.root.geometry(); self.view = 'board'; self.presentation = 'window'
            self.root.overrideredirect(False); self.root.attributes('-topmost', self.top.get())
            self.root.minsize(self._px(360), self._px(520)); self.root.geometry(self._board_geometry)
        self._apply_view()

    def toggle_collapse(self):
        self.save(); self.root.update_idletasks()
        if not self.collapsed:
            self._expanded_geometry = self.root.geometry(); self.collapsed = True
            self.root.minsize(self._px(360), self._px(64))
            self.root.geometry(f'{self.root.winfo_width()}x{self._px(64)}+{self.root.winfo_x()}+{self.root.winfo_y()}')
        else:
            self.collapsed = False
            self.root.minsize(self._px(360), self._px(520 if self.view == 'board' else 360))
            self.root.geometry(self._expanded_geometry)
        self._apply_view()

    def _drag_start(self, event):
        self._drag_moved = False
        self._drag_origin = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())

    def _drag(self, event):
        if self._drag_origin:
            x, y, left, top = self._drag_origin
            dx, dy = event.x_root - x, event.y_root - y
            if abs(dx) + abs(dy) >= self._px(4): self._drag_moved = True
            left = max(0, min(left + dx, self.root.winfo_screenwidth() - self.root.winfo_width()))
            top = max(0, min(top + dy, self.root.winfo_screenheight() - self.root.winfo_height()))
            self.root.geometry(f'+{left}+{top}')

    def _drag_end(self, event):
        self._drag_origin = None
        if self.presentation == 'icon':
            self._icon_position = (self.root.winfo_x(), self.root.winfo_y())

    def _layout_header(self):
        show_library = not self.collapsed and self.view == 'board' and not self._workspace_wide()
        self.buttons['library'].grid_remove()
        self.buttons['library'].configure(text='Back' if self._library_open else 'Notes')
        keys = ['collapse', 'icon', 'more'] if self.collapsed else ['focus', 'collapse', 'icon'] + (['library'] if show_library else []) + ['more']
        keys.append('close')
        available = self.root.winfo_width() - self._px(32)
        if sum(self.buttons[k].winfo_reqwidth() for k in keys) + self._px(24) > available:
            # Mode actions remain in Menu when accessibility text outgrows chrome.
            keys = (['library'] if show_library else []) + ['more', 'close']
        for key in ('focus', 'collapse', 'icon'):
            if key not in keys: self.buttons[key].grid_remove()
        controls = [self.buttons[k] for k in keys]
        if self.collapsed: self.buttons['focus'].grid_remove()
        # Label width is measured in characters, not pixels. Feeding its
        # requested pixel width back into width causes exponential growth on
        # Configure events. Reflow using natural requested sizes instead.
        required = self.brand.winfo_reqwidth() + sum(b.winfo_reqwidth() for b in controls) + 20
        compact = not self.collapsed and self.root.winfo_width() - self._px(32) < required
        self.brand.grid_configure(row=0, column=0, columnspan=len(controls) if compact else 1)
        for column in range(8): self.header.columnconfigure(column, weight=1 if column==0 else 0)
        for index, control in enumerate(controls):
            control.grid_configure(row=1 if compact else 0, column=index if compact else index+1)

    def _fit_header(self):
        self._layout_workspace()
        self.root.update_idletasks()
        self._layout_header(); self._layout_note_actions()

    def _resize(self, event):
        if event.widget is not self.root or self._resizing or self.presentation == 'icon':
            return
        self._resizing = True
        try:
            self._layout_header(); self._layout_workspace()
            width = max(120, self.notebook.winfo_width() - self._px(20))
            self.status_label.configure(wraplength=max(240, self.root.winfo_width() - 52))
            self.empty_label.configure(wraplength=max(120, self.editor_frame.winfo_width() - 36))
            height = 3
            if self.theme in ('sticker', 'retro'):
                self.skin_caption.grid_remove()
            for tree in self.trees.values():
                tree.configure(height=height)
                tree.column('title', width=width - 12)
                tree.column('#0', width=width)
                for key in tree.get_children():
                    note = self._notes.get(int(key))
                    if note is not None:
                        tree.item(key, text=self._row_text(note, tree), values=(self._short_title(note, tree), age(note.updated), note.research))
            self._header_text()
        finally:
            self._resizing = False

    def _poll(self):
        if self.closed:
            return
        self.safe(self.refresh)
        if self.instance and self.instance.poll_raise():
            if self.presentation == 'icon': self.safe(self.open_from_icon)
            self.root.deiconify(); self.root.lift(); self.root.focus_force()
            if self.collapsed:
                self.safe(self.toggle_collapse)
        self.poll_timer = self.root.after(200, self._poll)

    def close(self):
        if self.closed:
            return
        try:
            self.save(); self.root.update_idletasks()
            visible_geometry = self._icon_expanded_geometry if self.presentation == 'icon' else (self._expanded_geometry if self.collapsed else self.root.geometry())
            if self.presentation == 'icon': self._icon_position = (self.root.winfo_x(), self.root.winfo_y())
            state = {'geometry': visible_geometry if self.view == 'board' else self._board_geometry,
                     'focus_geometry': visible_geometry if self.view == 'focus' else self._focus_geometry,
                     'on_top': self.top.get(), 'last_target': self.last_target, 'theme': self.theme,
                     'view': self.view, 'collapsed': self.collapsed, 'text_size': self.text_size,
                     'font_family': self.family, 'styled_text': self.styled_text, 'interface_size': self.interface_size, 'presentation': self.presentation,
                     'icon_restore': self._icon_restore, 'icon_position': self._icon_position,
                     'last_selected': self.selected.id if self.selected else None}
            atomic_write(self.state_path, json.dumps(state).encode())
        except (OSError, ValueError, RuntimeError, tk.TclError) as exc:
            self.save_state.set('Not saved'); self.status.set(str(exc)); return
        self.closed = True
        if self.appearance: self.appearance.close()
        if self.picker:
            self.picker.close()
        for timer in (self.save_timer, self.poll_timer):
            if timer:
                try:
                    self.root.after_cancel(timer)
                except tk.TclError:
                    pass
        if self.instance:
            self.instance.close()
        self.root.destroy()


def clipboard_hold(text):
    root = tk.Tk(); root.withdraw(); root.clipboard_clear(); root.clipboard_append(text); root.update()
    print('CLIPBOARD READY', flush=True)
    def poll():
        try:
            if root.clipboard_get() != text:
                root.destroy(); return
            root.after(500, poll)
        except tk.TclError:
            root.destroy()
    root.after(500, poll); root.mainloop()


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    for flag in ('clipboard-read', 'clipboard-write', 'clipboard-hold', 'tk-version'):
        group.add_argument('--' + flag, action='store_true')
    args = parser.parse_args()
    if args.tk_version:
        print(tk.TkVersion); return 0
    if args.clipboard_read:
        root = tk.Tk(); root.withdraw()
        try:
            sys.stdout.write(root.clipboard_get()); return 0
        finally:
            root.destroy()
    if args.clipboard_hold:
        clipboard_hold(sys.stdin.read()); return 0
    if args.clipboard_write:
        text = sys.stdin.read()
        holder = subprocess.Popen([sys.executable, '-m', 'sticky_intent.widget', '--clipboard-hold'], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, start_new_session=os.name != 'nt')
        assert holder.stdin is not None and holder.stdout is not None
        holder.stdin.write(text); holder.stdin.close()
        ready = holder.stdout.readline(); holder.stdout.close()
        if ready.strip() != 'CLIPBOARD READY':
            raise RuntimeError('Tk clipboard owner failed')
        return 0
    from .instance import run_widget
    return run_widget(Store())


if __name__ == '__main__':
    raise SystemExit(main())
