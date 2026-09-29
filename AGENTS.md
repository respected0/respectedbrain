# AI Development Workflow

Codex is the control-plane technical lead for this repository. It owns user intent, architecture,
task boundaries, risk, acceptance criteria, final review, QA status, and integration decisions.

Use Codex directly only for explicit, low-risk mechanical work. For non-trivial exploration,
debugging, implementation, testing, regression analysis, or review, use the `antigravity-fleet`
skill and the guarded launcher documented in `.orchestration/README.md`.

From Codex, launch workers with `--background --timeout-seconds <bound>` and monitor the
returned `run_root` using `inspect` every 30–60 seconds. Do not cancel silent workers or
depend on a long-lived exec session. Keep deterministic tests in launcher acceptance commands;
do not ask the model to repeatedly rediscover or rerun the same suite. Use approved host access
when the sandbox cannot see the installed Antigravity executable.

Never run an Antigravity worker in the primary working tree. Use a dedicated sibling worktree for
every read or write worker. Allow at most one active write worker. Do not let concurrent workers own
overlapping paths.

Antigravity workers intentionally run with `--dangerously-skip-permissions`. A worktree is not an OS
sandbox. Safety comes from narrow briefs, explicit ownership and forbidden paths, diff enforcement,
tests, and Codex verification.

Never discard, stash, reset, clean, restore, or overwrite existing user work to prepare a lane.
Worker claims are not proof. Verify the targeted diff and acceptance checks before integration.

If Antigravity is unavailable, unauthenticated, out of quota, or times out, report the blocker and
stop. Codex must not silently become the implementation worker.

