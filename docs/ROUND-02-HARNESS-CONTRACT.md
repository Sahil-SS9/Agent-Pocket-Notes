# Round 2 — approved harness-aware Pocket Notes candidate

Owner decisions:
- Send offers an existing session or an explicitly started new run.
- Successful replies append automatically; replacing original user text requires approval.
- Validate/build Hermes, Claude Code, Codex, Pi, Command Code and OpenCode in this round.
- Neither Send nor Research silently creates a kanban task.
- Authentication/execution errors stay in status/log, not in the note body.

Build boundaries:
- Direct implementation; no delegation or agent coding CLIs.
- Local candidate only. No live desktop restart, install, credential copying, login/startup edits, provider changes or publication.
- Harness binaries and credentials stay in the operator's account. Login is an explicit user-triggered native terminal/browser flow.
- Session injection and continuation differ. Retain classic Hermes CLI and Claude hook context delivery, clearly labelled context-only; new/resumed app-managed harness runs return labelled replies.
- Never claim arbitrary terminal injection. Offer only adapter-supported actions; preserve unavailable states with concrete setup/version reasons.
- Read-only/plan permissions for newly launched agent runs. No blanket permission bypass.
- Legacy CLI research remains compatible; the new desktop uses structured run receipts and success-only write-back.
- Copy/Pin/Trash use accessible theme-aware icons. Native appearance controls and scrollbars use the app palette.

Validation gates:
- All six argv builders, documented protocol parsers, capability/refusal states and native login launch selection.
- Isolated fake-harness end-to-end runs, auth/empty/partial failure preservation, note revision conflicts, resume/session provenance and no duplicate appends.
- Real Qt harness-first Send/Research journeys, palette contrast and icon actions in every theme.
- Full canonical repository tests and high-DPI native checks; final wheel/installer rehearsal.
- Live/provider validation is separate and requires the operator's installed harnesses and sign-in. Source/docs and fake transport proof are not live-provider proof.

Feasibility references:
- https://hermes-agent.nousresearch.com/docs/reference/cli-commands/
- https://code.claude.com/docs/en/cli-reference
- https://developers.openai.com/codex/noninteractive
- https://pi.dev/docs/latest/cli
- https://commandcode.ai/docs/headless
- https://opencode.ai/docs/cli/
