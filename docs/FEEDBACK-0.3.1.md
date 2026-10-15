# Pocket Notes 0.3.1 — first desktop walkthrough fixes

## Verdict

A–D implemented and verified in disposable native Qt sessions. E's runner configuration and authentication recovery are implemented; live Research remains pending the desktop user's Hermes sign-in. No credentials copied, provider changed, real Claude invoked, live app restarted or operator notes modified during this build.

## Changes

- Wrap constrained menu/action labels, header titles, collection titles/previews and status copy. Measure buttons using their actual inherited font, explicit padding and content-derived heights. Retain vertical dialog scrolling; final Close action verified reachable.
- Remove both shades of baked-in checkerboard from the mascot's border-connected backdrop. Preserve enclosed eye whites; feather the alpha boundary. Both full-size and 32px icons rebuilt. Installed-window transparent corners tested.
- Remove visible floating-icon hover instructions; preserve keyboard accessibility, dragging and double-click restoration.
- Add matching drag/wheel sliders and editable numeric controls for Reading Text (25–200%) and Interface (100–200%). Use typed integer bridge slots and avoid live rebinding during drag. Interface changes scale window geometry, clamp to screen bounds and retain intended dimensions for a reversible zoom.
- Add explicit Hermes executable/profile/provider/exact-model/home settings, preserving custom argv and unrelated TOML. Pass selected Hermes home to the detached runner. Classify missing authentication with an account-specific setup command; offer a Copy Hermes setup command button. Setup/settings never initiate agent work or copy credentials.

## Evidence

- Final source suite: 312 passed in 101.10s. No relaxed fast-launch assertions.
- High-DPI native suite: 21 passed at QT_SCALE_FACTOR=3, Xvfb 3000×2400.
- Exact offline updater rehearsal: 3 passed, including refusal on the actual root-store widget lock and missing runtime before program replacement.
- Final wheel package members byte-match source; installed package member verification and Qt offscreen initialisation run before and after promotion.
- Installed-wheel icon smoke: QML loaded, mascot mode shown, transparent corner asserted.
- Native theme/menu/appearance/research captures: <evidence-dir>/
- Test results and JUnit: full-suite-verified.log / full-suite-verified.xml in that directory.

The native screenshots and tests are sandbox evidence, not acceptance of the operator's live desktop. Xvfb has no session DBus; host theme-change notifications remain outside this gate.

## Operator update

Save and quit Pocket Notes. From the normal desktop terminal, without sudo:

    sh <release-dir>/update-pocket-notes.sh

The wrapper invokes a readable Python updater (no executable bit required), refuses account switching, validates every artifact before replacement, holds actual widget locks, preserves notes/settings/startup/launchers, and retains the previous program under .previous-0.3.1-* for rollback. It then launches Qt. The previous 0.3.0 wrapper now forwards to this safe updater instead of deleting program paths before validation.

Research sign-in: in Research, use Copy Hermes setup command, run the copied command as the same desktop user, select the intended provider and sign in. Retry Research afterwards. An authenticated live research answer has not been verified on this machine: the desktop account is private and the supplied failure is a real missing-token error, not something a PNG/UI or installer change can repair silently.

## Pinned artifact

Wheel: sticky_intent-0.3.1-py3-none-any.whl
SHA-256: 12e994129296e16a8d90ac5040b8ad5a08f8eb858c8530c9cb96a59950dc7d1e
