# Upgrade dead-end: tracked `settings.local.json`

> **Tarihsel ve çözülmüş bulgu.** Güncel kullanım talimatı değildir. Regresyonlar
> `tests/upgrade_settings_test.sh` ve `beyin-doktor` secret/duplicate-hook kontrollerinde korunur.

Found 2026-08-23 while writing the blocker 2/3 regression tests. Two defects, one root cause,
both fixed in `scripts/upgrade.sh`. Neither the gate review nor the fix lanes caught them,
because the developer's own machine masked the precondition.

## Why it was invisible here

This machine has a global gitignore at `~/.config/git/ignore` containing
`**/.claude/settings.local.json`. Every hand test therefore started from a vault where the
secret file was already untracked. On a machine without that rule, which is the normal case
for anyone cloning the template, a v1 vault has `.claude/settings.local.json` **committed**.

The test fixture now neutralises this: `tests/fixtures/v1_vault.sh` exports
`GIT_CONFIG_COUNT=1 / GIT_CONFIG_KEY_0=core.excludesFile / GIT_CONFIG_VALUE_0=/dev/null`.
`GIT_CONFIG_GLOBAL=/dev/null` alone is not enough, because `~/.config/git/ignore` is git's XDG
*default* excludes path, consulted whenever `core.excludesFile` is unset.

## Defect 1: adding the ignore rule does not untrack the file

`ensure_gitignore` appends `.claude/settings.local.json` to `.gitignore`, but gitignore has no
effect on an already-tracked path. In `finalize`, `git add -u -- .` restages the now-modified
secret file, `assert_no_secret_staged` fires, and the run dies **after every gate has passed**.
The vault is left migrated but unstamped, with no route forward: re-running hits the same wall.

Reproduction before the fix: build the fixture, run apply then finalize. All gates print ✓,
then `HATA: sır taşıyabilecek dosya commit'e girmek üzereydi` and exit 1, `.beyin-version` absent.

**Fix.** New `untrack_ignored_secrets`, called in apply immediately after `ensure_gitignore` and
before the snapshot. It runs `git rm --cached` on `.claude/settings.local.json`, `.env`, and any
tracked `*.yedek` / `*.bak` / `*.orig` artefact, leaves every file on disk, and prints a loud
warning that the secret remains in history and the key must be rotated at the provider.

## Defect 2: the leak guard could not tell removal from leakage

`assert_no_secret_staged` matched on `git diff --cached --name-only`, so the staged **deletion**
that defect 1's fix produces looked identical to a staged addition. The cure aborted the upgrade
at step 2/9.

**Fix.** The guard now reads `--name-status` and ignores entries whose status starts with `D`.
Adding or modifying a secret path still aborts; untracking one is allowed.

## Verified after both fixes

Full chain on the hermetic fixture: apply 0, finalize 0, `.beyin-version` = 2.0.0.
In the commits the upgrade created, the secret path appears only as `D`; `--diff-filter=AM`
returns nothing. It is absent from `git ls-files` and confirmed ignored. The file itself is
still on disk with `env.MEM0_API_KEY`, `permissions`, and the unrelated `Notification` hook
intact, and only the v1 beyin hook entry removed. The out-of-vault backup is mode `0600`.

## Residual risk, accepted and documented

The secret stays in git history. The upgrade cannot rewrite history safely on the user's behalf,
so it warns and stops there. `beyin-doktor` check 15 now also reports tracked secret paths and
backup artefacts, and check 14 reports duplicate effective hooks; the gate review asked for both
and neither existed.
