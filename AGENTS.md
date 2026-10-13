# AGENTS.md: Rules for every agent in this repository

You are one of several agents building PenPress. You have no memory between sessions.
**The repository is your memory.** Everything you need is in files. Follow this document literally.

## 0. The Loop (do this every session, no exceptions)

```
START   ->  make briefing          # prints rules, active cards, next cards, last journal entries
        ->  read your card in full: tasks/<ID>.md   (Acceptance + Anti-shortcut sections especially)
WORK    ->  small steps. After every ~10 tool calls, or when unsure: RE-READ the card's
            Acceptance section and ask "does what I just did move me toward every line of it?"
        ->  make journal MSG="..." CARD=<ID>     # one line per meaningful step or decision
CHECK   ->  make gate                            # must pass before every commit
FINISH  ->  fill docs/evidence/<ID>/EVIDENCE.md  (make evidence-new CARD=<ID>)
        ->  set card Status: review   (NEVER set done yourself, a different agent reviews)
        ->  make state                           # regenerates STATE.md from the cards
        ->  update CHANGELOG.md (+ README/docs if behaviour changed)
        ->  git commit, git push, then watch CI:  gh run list --limit 3 ; gh run watch
        ->  CI red = you are not finished. Read the log, fix, push again.
```

If your context was reset mid-task: run `make briefing` and read `JOURNAL.md` (tail). Continue from there.

## 1. Non-negotiables

1. **One card at a time.** No card ID = no work. Stay inside the card's `Zone` (paths listed in `tasks/README.md`). Need a change outside your zone? Write it as a Blocker in the card and stop.
2. **No toy work.** In `src/` the following are forbidden and `scripts/forbid.py` fails the gate on them: `TODO`, `FIXME`, `XXX`, `NotImplementedError`, functions whose body is only `pass` or `...` (except Protocol/abstract/overload), `mock`/`fake`/`dummy`/`placeholder`/`lorem` identifiers, hardcoded sample outputs that stand in for real computation, commented-out code.
3. **Tests ship with code.** Every public function has a test. Never delete, skip, xfail, or weaken a test to make it pass (the gate scans for `skip`, `xfail`, `assert True`). If a test is wrong, fix it and explain why in the journal.
4. **"It runs" is not "done".** Done means every line of the card's Acceptance section is demonstrably true, with evidence in `docs/evidence/<ID>/` (command lines, real outputs, numbers, images you actually opened and looked at).
5. **You never grade yourself.** `Status: done` requires `Reviewed-by` to be a different agent than `Implemented-by`, and a filled evidence file. `scripts/state.py --check` enforces this.
6. **Documentation is part of the change.** CHANGELOG.md entry with ISO timestamp for every change under `src/`. README / `docs/` updated when behaviour, CLI, config, or architecture changes. Checklists in `docs/developer/checklists.md` ticked only with evidence.
7. **Commit small, push often.** Conventional commits (`feat(synth): ...`, `fix(plan): ...`, `docs: ...`). Minimum: push when a card moves to `review`. Never `--force`. Never commit secrets, tokens, `.env`, model weights, or datasets (see `docs/developer/compute.md`).
8. **Security (host is on a private Tailscale network).** Bind only `127.0.0.1` or `100.121.213.19`, never `0.0.0.0`. Never use `tailscale funnel`. Validate Host headers (allow loopback, `*.ts.net`, `100.64.0.0/10`). Sanitize every upload (size, type, path traversal). No outbound network calls from the product unless the user enabled an opt-in plugin.
9. **Local-first.** Core features work offline. Cloud APIs only as opt-in plugins, off by default, with a test proving zero egress when off.
10. **Licenses.** Product dependencies must be permissive (MIT/BSD/Apache). Anything GPL/AGPL/NC/unclear: subprocess boundary or do not use. Record every dependency decision in `docs/developer/licenses.md` *before* adding it. A repo with no license file is **all rights reserved**: study it, do not copy it.
11. **UI work** follows the minimalist graphite standard (dark `#0d0e12`, cards `#141722`, borders `#212638`, text `#f8fafc`/`#94a3b8`; no emoji; no giant empty boxes; no clipped text). Screenshots go in `docs/screenshots/` and you must open and inspect them.

## 2. Research protocol (for cards named R*)

Search results and your own memory are **leads, not facts**. Earlier in this project a search result invented a GitHub repo that returns 404.

1. For every repo/paper/dataset you rely on: verify existence and license with `gh api repos/OWNER/REPO --jq '[.license.spdx_id,.stargazers_count,.pushed_at]'` or by reading the actual LICENSE file / paper page. Record the result in `docs/developer/research/<card>.md` with the date.
2. Clone candidates into `research/<card>/vendor/` (git-ignored), **run them**, and measure. Reading a README is not evaluating.
3. Benchmark on the shared fixtures with the metrics named in the card. Put numbers in a table. Include failures.
4. Finish with an ADR in `docs/developer/adr/NNNN-title.md`: Context, Options with numbers, Decision, Consequences, Fallback. Unresolved unknowns must say how they will be resolved.
5. A research card is done when a **prototype that runs end-to-end on the fixtures** exists in `research/<card>/` and the ADR cites its numbers. "Looks promising" is not a result.
6. Prefer adapting proven code (with correct license and attribution in `docs/developer/licenses.md` and `NOTICE`) over rewriting from scratch. Do not hand-roll solved problems (handwriting models, OCR, PDF layout).

## 3. When blocked or unsure

Write it under `## Blockers` in your card (what you tried, what you need), journal it, set `Status: blocked`, and stop. Do not guess requirements. Do not shrink scope silently. Shrinking scope requires a journal entry plus an ADR.

## 4. Compute

CPU box (2 cores, 3 GB, no GPU) is for development, tests, and light inference. Training and heavy inference run on Colab (via MCP) or the user's machine: see `docs/developer/compute.md`. Everything produced there must be reproducible from a notebook in `notebooks/` plus a manifest line in `models/MANIFEST.md`.

## 5. Where things are

| Need | File |
|---|---|
| Product contract | `BRIEF.md` |
| Live board (generated) | `STATE.md` |
| Your task | `tasks/<ID>.md` |
| Zones and ownership | `tasks/README.md` |
| What happened so far | `JOURNAL.md` |
| Decisions | `docs/developer/adr/` |
| Verified research | `docs/developer/research/` |
| Licenses | `docs/developer/licenses.md` |
| Compute and models | `docs/developer/compute.md` |
| Checklists | `docs/developer/checklists.md` |
