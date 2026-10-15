# Pocket Notes — approved native design contract

Owner approved B / Pocket Notes, faithful Sticker Club and Retro Workbench skins,
a Hermes-style toolbar input and generated quirky minimise icon. Owner explicitly
relaxed stdlib-Tk-only for the desktop UI; CLI/plugin remain toolkit-independent.
Direct implementation only. Build approval is NOT live installation approval.

## Composition

Compact note-first window (480 × 620 logical px). Collection is an on-demand
replacement pane, never a cramped stacked form. Header: title when space permits,
collection, new capture, window/appearance menu and quit. Footer: content actions,
Send primary and local save/research/error state. Menus separately group window/
appearance and note operations. Narrow/interface-scaled windows keep collection,
Menu, Close and Send accessible. Editor stays instantiated across mode changes.

Capture is a separate horizontal input toolbar (default 780 × 130 logical px),
with mascot, multiline draft, save arrow, Notes and minimise. It is not a dialog
editing the selected note. Save creates a new note then returns to icon; failure
stays on capture with exact draft and readable error. Shrink preserves draft.

Icon is a movable ~96px standalone transparent window. Actual image-generated
mascot, processed true alpha (original RGB checkerboard retained for provenance).
Drag threshold separates moving from double-click/open. Enter/Space restore,
right-click raises Notes/recovery. Window, capture, icon and collapsed geometry
are saved independently, clamped to the current screen. Topmost is separate from
collection pinning; capture/icon/collapsed are topmost utility surfaces.

## Theme grammar

Modern Pocket: neutral white reading surface, subtle line, restrained blue primary
Send; capture is dark like the Hermes toolbar reference.
Sticker Club: pink shell, yellow note, mint tape, 3px dark illustrated outline,
rounded 22px framing, offset physical sticker shadow and outlined note cards.
Retro Workbench: square geometry, cream chrome, purple #382a69 title bar, white/
grey button bevels and teal-edge desktop/workbench treatment.
Paper/Midnight: legacy appearance retained. Light/dark is explicit, not forced
by the host. A standalone native window does not change the user's wallpaper.

## Typography and behaviour

Actual OS font picker; one selected family throughout app-owned text. Default
Noto Sans where installed; native fallback is reported rather than pretending
an unavailable family resolved exactly. Reading size 25–200% at 18px baseline,
interface scale 100–200% at 14px baseline. Qt rounds to whole pixels. Optional
syntax presentation highlights headings/code without converting Markdown to
rich text or altering stored bytes. Plain text is the default.

Native edit, paste, select, undo/redo and scroll persist across UI metadata/theme
updates. Autosave does not reassign editor text. Actual external document changes
use a separate reload signal; dirty revision conflicts never overwrite the draft.
Keep both is explicit; Reload requires confirmation. Checkpoints retain unsaved
editor/capture text for recovery. Store permissions/atomic/revision writes unchanged.

Send shows only registered classic CLI / Claude targets; Claude says next message.
Cancel never queues. Clipboard is the universal fallback. Last target persists.
Research uses existing explicit configured argv supervisors, with running/done/
failed/result updates, duplicate guard, local full-log path and read-only viewer.

## Verification boundary

Approved browser reference is retained at ui-directions-round-01/pocket-round-03.
Native screenshots and operator rehearsal live separately in qt-release. Source
and installed-wheel tests exercise Qt input/recovery plus the existing wider
suite. Green old-Tk tests do not establish Qt parity. Linux/X11 Xvfb proof does
not certify a live compositor, Windows/macOS or Wayland. Final operator visual
confirmation remains separate from implementation review. No publication,
startup hooks, live agent calls or live installation is authorised by this file.
