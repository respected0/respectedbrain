# Antigravity Worker Orchestration

Codex is the control plane; Antigravity is the bounded execution worker. Small mechanical changes
stay in Codex. Non-trivial investigation, implementation, testing, and review use the repository
launcher in `scripts/antigravity_orchestrator.py`.

Every worker runs in a sibling worktree under `../secondbrain-worktrees`, never in the primary
checkout. Branches use `agy/<task-slug>`. The launcher allows one write worker, preserves dirty user
work, validates path ownership, reruns safe acceptance checks, and produces a worker-only patch for
Codex review. Runtime state lives beside the worktrees under `.orchestration-state` and does not enter
Git or `qa-evidence`.

Workers use `--dangerously-skip-permissions` by explicit user choice. Worktrees isolate Git state but
are not OS sandboxes. Do not delegate machine-wide or uncertain destructive operations without a
disposable environment.

If Antigravity reports an authentication, quota, timeout, or execution failure, the launcher records
one terminal result and stops. It does not retry automatically and Codex does not take over the
implementation.

The existing QA master, run state, phase files, and evidence contract remain authoritative. Workers
may prepare source or test fixes, but cannot write canonical QA state or award `VERIFIED` status.

## Commands

Use a working Python executable from the active Codex environment:

```text
<python> scripts/antigravity_orchestrator.py doctor
<python> scripts/antigravity_orchestrator.py run-read --background --timeout-seconds 300 --slug <slug> --objective <text> --owner <path>
<python> scripts/antigravity_orchestrator.py run-write --background --timeout-seconds 600 --slug <slug> --objective <text> --owner <path> --accept <json-array>
<python> scripts/antigravity_orchestrator.py inspect --run-root <state/run-id>
<python> scripts/antigravity_orchestrator.py check-patch --patch <state/run-id/worker.patch>
<python> scripts/antigravity_orchestrator.py apply-patch --patch <state/run-id/worker.patch>
```

`apply-patch` is an explicit integration step. Run it only after Codex has reviewed the structured
result, changed paths, patch, and acceptance results.

## Durable, low-cost runs

Use `--background` from Codex: the launcher detaches from the tool console and Windows job,
redirects output to `launcher.log`, and immediately returns a persistent `run_root`. Inspect
that directory every 30–60 seconds until terminal status. Silence is not failure. Never cancel
a worker just because an exec session disappears. No retry or duplicate worker is needed.

On this Windows host, run the launcher with approved host access when sandbox filesystem access
hides `agy.exe`. Use the bundled Python executable, not the inaccessible Store Python alias.
Worker lookup uses PATH or `%LOCALAPPDATA%/agy/bin/agy.exe`.

Keep one objective, a few owned files, one deterministic acceptance command, and a short result.
Do not feed the whole QA history to workers or request full discovery for a focused gate. Local
tests consume no model tokens; worker timeout limits time, not a guaranteed token budget.
Required untracked fixtures must be both explicit inputs and owned paths; forbid those same
fixture paths to prevent worker modifications. Do not copy unrelated dirty files.

