# Pocket Notes 0.4.0 — harness-aware local candidate

## Verdict

The round-two desktop flow, six adapter contracts and success-only write-back are implemented and exercised locally. This is a local candidate, not a claim that six signed-in provider accounts have been exercised. Operator sign-in and a live run per installed harness remain required.

## Approved behaviour

- Send offers an existing compatible session or an explicitly started new run.
- Successful replies append automatically, labelled with harness/session/time. Original text is never replaced by this adapter path; no replacement API is exposed to agents.
- Hermes, Claude Code, Codex, Pi, Command Code and OpenCode are all included.
- Pocket Notes creates no kanban task automatically. Existing terminal sessions retain their own harness rules/tools.
- Authentication/execution/protocol errors remain in status/private logs, not the note body.

## Implemented

- Shared harness-first Send/Research chooser, installation/version/auth status, native user-triggered Connect/configure and model-picker actions, setup help and only applicable model/provider/profile fields. Raw paths are Advanced.
- App-owned native session continuation; classic Hermes CLI and Claude hooks remain context-only, clearly labelled. Other terminal windows are not silently discovered/injected. Source return identifiers, not invented IDs, populate managed-session choices.
- Detached workers, local receipts/logs, run status and desktop notifications, read-only/plan/web-only invocation modes, real deadline/output bounds, overlap refusal and recoverable interrupted supervision.
- Private input files/stdin keep note content out of process arguments and avoid argument-size truncation. Input digest validation and atomic, idempotent append preserve original/concurrently edited text.
- Copy/Pin/Unpin/Trash SVG buttons with accessible names/hover labels. Trash keeps confirmation. Lucide attribution is bundled.
- Native appearance palette and styled scrollbars; readable disabled actions. Contrast tests caught and fixed Sticker Club secondary text and disabled blue/purple action labels. The previous icon-alpha, slider, wrap and no-hover-message gates remain intact.
- Offline updater now also refuses active detached agent runs before replacement; previous program and all protected notes/settings/startup files remain preserved.

## Verification

- Full source gate through scripts/run_tests.sh: 396 passed in 136.00 seconds, zero failures/skips.
- High-DPI native gate: 46 passed at QT_SCALE_FACTOR=3, Xvfb 3000x2400.
- Six labelled fake transports: new/resumed runs, full payload delivery, native GUI reply append and 160,000-character input cases. These are test fixtures, not fabricated live-provider results.
- Native setup/model-picker dispatch tested without opening terminals or making real auth/model calls.
- Updater rehearsal covers widget lock, detached active run, missing artifact refusal, note/settings/startup preservation, backup and installed Qt icon transparency.
- Actual native theme/Appearance/picker/Research captures in feedback-0.4.0; Xvfb has no session DBus, so desktop notification and host-theme reaction are not live-desktop evidence.

Evidence directory: the release evidence folder for this version.

## Operator step

Wait for any current agent work to finish. Save and quit Pocket Notes. From your normal desktop terminal, without sudo:

    sh <release-dir>/update-pocket-notes.sh

Open Send or Research, choose a harness, use Connect/configure if needed, then Check connection. Only then explicitly start/continue work. Installing/signing into the harness itself is not done automatically by the updater. Unsupported versions/unverified native states remain unavailable with a reason.

Native connection checks establish local credentials/configuration, not successful provider execution. Complete one live Send/Research run and continuation per harness you install before calling the live integration validated. No real Claude calls, credential copying, live app restarts, autostart edits, publishing or fleet changes were made during this build.

## Artifact ideas (not extra implemented scope)

A brief card can hold the question/context/outcome; a result card can collect agent output/sources/review; a handoff card can retain completed work/open questions/next action. Keep these optional; ordinary stickies should remain ordinary notes. Task creation, arbitrary-session integrations and direct agent edits require separate explicit capabilities, not assumed behaviour.

## Interface evidence

- Hermes: official stream-json init/result events and query-file/resume CLI.
- Claude Code: documented print JSON result and resume/plan flags.
- Codex: thread.started/item.completed/turn.completed JSONL, exec/resume/stdin/read-only.
- Pi: session header, authoritative message_end and agent_settled. Retry recovery is not confused with a completed turn; LF framing preserves Unicode separators.
- Command Code: documented print JSON/finalText/sessionId; inspected public npm command-code 1.81.0 buildCommandAuthStatusJson and print input handling, without executing the package.
- OpenCode: documented run JSON and public CLI text/step_finish events with native sessionID.

Known distinction: legacy CLI Research/custom argv remains compatible, while the new desktop deliberately uses structured harnesses.json adapters. A raw legacy custom command is not silently treated as one of these proven protocols.
