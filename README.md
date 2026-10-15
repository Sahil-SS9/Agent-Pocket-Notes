# Sticky Intent — Pocket Notes

Private desktop notes for agent chats. Store, CLI and plugin remain stdlib-only.
The optional desktop extra provides Qt Quick; legacy Tk stays available.
Saving, pinning and searching never send data or start an agent.

## Install

Python 3.12+:

```sh
uv tool install --python 3.12 '/absolute/path/sticky_intent-0.4.0-py3-none-any.whl[desktop]'
sticky doctor
sticky install-launcher
```

The pinned operator updater verifies package bytes, refuses a running widget,
preserves notes/startup/settings and prepares missing XCB cursor support locally
in the operator account. No sudo, system packages, GUI launch, startup, Claude
hooks or Hermes activation is involved. Existing desktop launchers keep working.

`sticky widget` selects Qt when the optional extra is installed, otherwise Tk.
Use `--renderer qt` or `--renderer tk` explicitly. Qt 6.12.0 uses software
rendering and the host's real available fonts. It is a substantial optional
runtime, not imported by CLI/plugin paths or the already-running fast path.
On Linux, platform XCB libraries are required; a missing runtime is reported,
not disguised as the approved design. The updater installs a verified account-
local libxcb-cursor where this tested Ubuntu x86-64 host needs it.

```sh
uv sync --locked --extra desktop
xvfb-run -a uv run --locked --extra desktop pytest -q
```

## Desktop

B / Pocket Notes is compact and note-first. Collection opens on demand instead
of squeezing the editor into a stacked workspace. The editor remains alive
across themes, library, capture, collapse and icon to preserve caret/undo.

- Modern: quiet white note and dark horizontal capture toolbar. Sticker Club:
  pink chrome, outlined round yellow note, tape and offset sticker shadow.
  Retro: purple title bar, square bevels, cream workbench and teal edge.
  Paper/Midnight are retained for legacy preferences; light/dark is available.
- Header: collection, window settings and quit. Quick capture is available from the
  view switcher, not a header icon.
- Agent history is a replacement screen, not a modal, opened from the clock in the
  collection's search row. It lists the notes sent to a harness newest-activity-first:
  each card carries chips for the harness(es) the note was used with, the session id it
  belongs to, its last state, and Open note / Continue in that harness actions. The
  header switches between Recent and By harness (sections with counts). History is
  derived from the run records under `runs/`, so it needs no new note fields; Continue
  resumes the note's own session only when that harness still holds it in this
  workspace/profile, and otherwise offers a clearly labelled new run. Provider
  configuration is not where history lives.
- Footer: Send plus Note actions. Copy, Pin and
  Research show directly in Notes when space allows; HUD keeps the note-focused
  surface and moves secondary actions into Note actions. Note titles are capped
  at 48 displayed characters before one-line elision, so wrapping cannot enlarge
  the header.
- Create/edit/paste/search, All/Inbox/Pinned/Done, pin/unpin, done/restore, copy
  and confirmed move-to-trash use the existing private Markdown store and IDs.
  Typing into an empty board autosaves its first note; Ctrl+N creates a separate
  blank note. Clipboard capture preserves existing drafts rather than replacing.
- Autosave is revision-checked. External research refreshes clean text only.
  Conflicting dirty text blocks hide/close. Keep both saves it as a separate
  note; Reload confirms before discarding. Private checkpoints recover drafts.
- Quick capture is a frameless horizontal Hermes-style toolbar, not the selected
  note's editor. Multiline draft + Ctrl/Cmd+Enter saves a NEW note then returns
  to icon. Blank/save errors remain visible; minimise preserves exact draft.
- Generated folded-note mascot has a processed true alpha channel. Drag does
  not open; double-click/Enter/Space restores the prior note/capture/HUD view.
  Right-click opens notes with recovery controls. HUD is a focused always-on-top
  note surface; the collapse-to-header view is removed. Header drag and resize
  handles on all edges and corners are supported.
- Global actual-font picker; reading 25–200%, interface 25–200% (default 100%),
  both with drag/wheel sliders and editable numeric controls. Each size control is
  one label row carrying a compact bounded stepper (its +/− disable at the limits)
  over a single slim slider. Interface scale
  grows/shrinks the window while respecting the screen bounds. Optional
  heading/code presentation (no byte changes). Themes, typography, geometry,
  mode, selected note, drafts and last target persist in pocket-state.json.
  Supported legacy appearance is read without modifying widget-state.json.
- Shared harness-first Send/Research picker: Hermes, Claude Code, Codex, Pi,
  Command Code and OpenCode. Separate installed/version/authentication states;
  native user-triggered Connect/configure and model-picker actions. Paths stay
  under Advanced; only applicable profile/provider fields are shown. Provider
  status is scoped to Provider Settings and the connection checklist, not the
  widget header/capture controls; both indicators reserve a scaled 24px slot.
  Setup Back is in the title row; Recheck and Set-up share the footer row, with
  a full-width outlined Cancel button below. Scrollable panels own their
  scrollbars — never hand-assign one to a `ScrollView`, which this Qt build
  leaves unplaced and paints over the first row — and long wrapping labels are
  width-capped so no panel scrolls sideways.
- Explicit new runs or continuation of compatible app-owned sessions. Registered
  classic Hermes CLI/Claude sessions remain available as context only: Claude
  receives context on the next user message; this does not start a turn or capture
  a reply. No arbitrary terminal injection or automatic kanban integration.
- Managed runs use web-only/read-only/plan tool access. Successful structured
  replies append, labelled with harness/session/time, without replacing original
  text. Failures stay in status/private logs, not the body. Deadlines/output bounds,
  overlap refusal, interrupted-worker recovery and append idempotency are checked.
  Note payloads use private input files/stdin, not process arguments. New/resumed
  runs use the selected harness provider/quota; no run starts implicitly.
- Native controls/scrollbars follow the selected palette; light/dark contrast
  checks cover all themes. Copy, Pin/Unpin and Trash use accessible SVG icons;
  Trash retains confirmation. The icon window retains actual alpha transparency.
- Legacy CLI Research (Hermes/Claude) and custom `[research]` argv configuration
  remain compatible. The desktop now uses structured adapter settings in
  `harnesses.json`; legacy custom argv is not silently executed by that flow.
  Per-harness binaries and sign-in remain the operator's responsibility. Harness
  connections in the isolated review launcher are explicitly disabled: it probes
  no agent executable and cannot start a run. Its review-only status is not a live
  CLI-compatibility result. Offline transport/UI fixtures are not live-provider
  verification.
- Single-instance kernel lock/raise protocol is unchanged. Strict <100ms
  already-open regression is retained. Headless CLI/plugin imports load no Qt
  or Tk. Qt and Tk cannot own one store concurrently; background errors/readiness
  stay local. Window topmost is independent of note pinning.

Keyboard: Ctrl/Cmd+N new blank; Ctrl/Cmd+Shift+V clipboard capture; Ctrl/Cmd+F
search (Esc clears/returns); Ctrl/Cmd+P pin; Ctrl/Cmd+Enter last send (capture:
save); Ctrl/Cmd+R research confirmation. Ctrl+S explicit save. Native paste,
Tab/focus rings, Enter/Space and text undo remain available.

## Hermes and adapters

Install/activate separately; nothing in the desktop update edits Hermes core,
profile settings or Claude hooks. Scanner CAUTION/consent is not bypassed.

```sh
hermes plugins install file:///absolute/path/to/sticky-intent --enable --yes-deps
hermes plugins list
```

The core wheel still provides the hermes_agent.plugins entry point. Optional
startup/Claude installers remain explicit, reversible and default-off.
The application-menu launcher is NOT autostart. Uninstalling it preserves notes.

## Commands

```text
sticky add [TEXT] [--clipboard] [--pin]  # no TEXT: read stdin
sticky list [--pinned | --done | --all]
sticky show N
sticky pin N | unpin N | done N | rm N
sticky send N --to hermes|claude|clipboard [--session ID]
sticky research N [--with hermes|claude]
sticky sessions
sticky widget [--renderer auto|qt|tk] [--background] [--if-not-running]
sticky install-autostart --shell bash|zsh|fish|pwsh
sticky install-autostart --login
sticky uninstall-autostart
sticky install-launcher [--executable /absolute/path/to/sticky]
sticky uninstall-launcher
sticky install-claude [--autostart]
sticky uninstall-claude
sticky doctor
```

When several sessions match, choose `--session`; no arbitrary session is selected.
Deleting moves a note to `trash/`, and ids are never reused. Bodies are limited to
1 MiB of UTF-8 bytes. Notes are readable Markdown with manually parsed headers;
text, line endings and whitespace are preserved. Writes use fsync + atomic replace;
ids and edits use process locks (fcntl on POSIX, msvcrt on Windows).

Hermes adds `/sticky [add TEXT | list | pin N | done N | send N | research N]`,
`@note:N` with autocomplete, and the `sticky_notes` tool (`search`, `get`, `add`,
`pin`, `list`, toolset `sticky`). `/sticky send N` injects into the current CLI.
If the widget does not become ready within 3 seconds, `/sticky` returns the
board as text and the reason. The plugin launches the `sticky` executable on
PATH, not Hermes' Python, and never imports tkinter.

### Research configuration

The store's optional `config.toml` accepts argv arrays, not shell strings:

```toml
[research]
timeout_seconds = 900
hermes = ["hermes", "chat", "-Q", "-q", "{prompt}"]
claude = ["claude", "-p", "{prompt}"]
```

`{prompt}` is replaced literally, so braces, backticks and shell-like text in a
note are not executed by a shell. Timeout must be positive and at most one hour.
Each research job has a private JSON record, PID sidecar and full log in
`research/`. Oversize answers are visibly truncated with a log reference; a full
note that has no room for a result is marked failed. Failed runners and timeouts
append a clear failure section. Optional Linux notifications are skipped if
unavailable; `STICKY_INTENT_NO_NOTIFICATIONS=1` disables them.

## Start-up

Install one marked rc block for bash, zsh, fish or PowerShell, or install OS-login
startup. Neither is enabled automatically by installing the package.

Shell blocks run only in an interactive shell. On Linux they require DISPLAY or
WAYLAND_DISPLAY; macOS and Windows do not require those variables. Launch runs
in the background with no prompt output. Bash/zsh prompt overhead is measured
by sandbox tests. Native fish/PowerShell and native macOS/Windows execution still
need release testing on those platforms.

PowerShell resolves its own `$PROFILE` using a no-profile query. To choose another
profile explicitly, set `STICKY_PWSH_PROFILE` before installing. The fallback,
when PowerShell is not installed, is
`~/Documents/PowerShell/Microsoft.PowerShell_profile.ps1`.

Login variants: XDG `.desktop`, macOS LaunchAgent plist (absolute executable path),
Windows Startup `.cmd`. Uninstall restores the original bytes and permissions;
subsequent edits outside a shell block are preserved. Edited owned blocks or login
files are refused, not overwritten. Installer backup receipts live under
`installs/` in the store. Keep these until uninstalling.

Hermes optional startup is default-off. Set
`plugins.entries.sticky-intent.settings.autostart_widget: true` explicitly in your
Hermes profile to request it on `on_session_start`. `pre_llm_call` refreshes session
registration on resumed sessions without sending or researching notes.
Claude startup is opted into using `sticky install-claude --autostart`.

## Claude Code

`sticky install-claude` backs up and merges JSON hooks into `~/.claude/settings.json`
and installs `~/.claude/commands/sticky.md`. It refuses an existing unmanaged
`/sticky` command. Repeated installation is idempotent. Existing custom commands
remain supported by Claude Code's current skills documentation.

- SessionStart registers session id, cwd and transcript path.
- UserPromptSubmit refreshes registration, atomically claims that session's outbox
  and emits documented `hookSpecificOutput.additionalContext` JSON.
- `/sticky` uses `!` command expansion to run `sticky widget --background`, with
  `allowed-tools: Bash(sticky:*)` and model invocation disabled.

Claude has no push-into-chat API. Send attaches context to your **next message**;
it does not start a Claude turn. `sticky claude-hook` is an internal JSON-only
stdin/stdout command. Uninstall removes only the installer-owned hook entries and
command, preserving other settings and later unrelated edits. With unchanged
settings the original bytes are restored exactly.

References: https://code.claude.com/docs/en/hooks and
https://code.claude.com/docs/en/skills. Tests use documented payloads and fake
runners. They never execute the real `claude` binary.

## Privacy

Everything lives in `STICKY_INTENT_HOME` if set, otherwise:

- Linux: `$XDG_DATA_HOME/sticky-intent`, default `~/.local/share/sticky-intent`.
- macOS: `~/Library/Application Support/sticky-intent`.
- Windows: `%APPDATA%\\sticky-intent`.

There is no network service, analytics or sync. Saving, searching and pinning stay
local. Send and Research are explicit actions (or explicit plugin commands).
The `sticky_notes` tool can save/search/pin locally but has no send/research action.
Research invokes your chosen harness and therefore may use its configured remote
provider, tools and quota; choose a local-only runner configuration if required.
The handoff's E2E configuration targets only http://127.0.0.1:8091/v1, never a paid provider.

Default POSIX directories are 0700 and files/locks are 0600. Windows uses inherited
OS ACLs. PermissionError from a POSIX PID probe means alive, not dead; the Windows
probe uses OpenProcess/GetExitCodeProcess, never os.kill(pid, 0). Hermes registrations
expire after 60 seconds or a dead pid; Claude registrations expire after 12 hours.
Outbox claims are atomic so two consumers do not deliver the same queued file.
A refused injection is requeued. Invalid envelopes are kept as `.failed` files.

### Shared folder between trusted OS users

Use a dedicated folder outside either user's private home, owned by a shared
trusted group, with setgid directory inheritance and 2770 permissions. Set both
users' `STICKY_INTENT_HOME` to that folder and opt both processes into
`STICKY_INTENT_SHARED=1`. New store directories use 0770, new files and locks 0660,
with the directory's inherited group. Default mode remains private. Existing
private directories/files are not silently widened: the folder owner must adjust
those explicitly before switching an existing board to shared mode. On Windows,
set an inheritable ACL for the chosen trusted users instead.

All users granted access can read and edit the whole board, research prompts/logs,
registry/outboxes and installer receipts. This is local collaboration, not a
multi-tenant security boundary. Never point untrusted users at this store. No
shared-folder permissions or group memberships were changed by this build.

Clipboard reads/writes use Tk when a display is available, otherwise wl-clipboard,
xclip, pbcopy/pbpaste or PowerShell. A hidden Tk selection owner keeps X11 copies
alive after the CLI exits and exits when replaced or the display closes. No Tk
window is created by plugin import or headless doctor; the doctor loads only Tk's
version in a separate process.

## Limits

- Hermes **gateway, Ink TUI and Desktop sessions are not send targets in v0.1**.
  This plugin uses the classic CLI REPL injection API only; it never opts into
  gateway injection or creates a route to another profile. One-shot Hermes research
  runs have no attached REPL and are not advertised as send targets. Detection
  uses the host's `_cli_ref` ownership slot, verified at the pinned upstream version.
- Claude receives notes on your **next message**, not immediately.
- Clipboard is the fallback for Codex, Gemini, OpenCode and other harnesses.
- Tested on Linux/Python 3.12 with managed Tk 9.0 and app-scoped native Tk 8.6/Xft. Windows/macOS-specific code,
  login formats and all four shell blocks are covered by sandbox generation tests,
  not native platform execution. Wayland-only Tk needs XWayland/display access;
  `/sticky` falls back honestly if it cannot open the widget.
- Delivery claims prevent concurrent duplication, not arbitrary crash exactly-once
  guarantees. A process dying after a claim can leave a `.claim-*` file for manual
  reconciliation. Never blindly replay an ambiguous already-injected message.
- A supervisor killed by the OS can leave a running badge; inspect its PID/job log
  and reset `research` to failed in the Markdown header after confirming it died.
  Ordinary runner failures/timeouts are handled automatically.
- Research argv can hit OS argument limits for very large notes; this is reported
  as a failed runner. Small notes are the intended workflow.
- The build has not modified live shell startup, Claude settings or Hermes config,
  and has no Git remote. Publication and live activation are separate approvals.

### Tests and evidence

```sh
uv run --locked pytest -q -m 'not gui and not slow'
xvfb-run -a uv run --locked pytest -q -m gui
```

Real-host `slow` tests need a disposable upstream snapshot prepared outside this
repository. Point `STICKY_INTENT_HERMES_RUN` and `STICKY_INTENT_RELEASE_DIR` at it
to run them; they skip cleanly when those are unset.

The local evidence directory contains RED/GREEN logs, REPORT.md, PROGRESS.md,
widget.png, widget-demo.mp4 and a real local-model E2E log or an explicit skip
reason. The screenshot and demo are real Xvfb captures; their research/delivery
fixtures are explicitly labelled fake and are not model-integration proof.
