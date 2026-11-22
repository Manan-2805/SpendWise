# SpendWise: rules for AI agents

## Session start (every session)
1. Run `git status`. It must be clean. If not, stop and ask me.
2. Run `git fetch`, then create a NEW branch: `codex/<YYYYMMDD>-<short-topic>` from `main`.
   Exception: if I already made a `codex/*` branch for this session, use it.
3. One session = one requirement = one branch. Never reuse an old branch.

## Never, without my explicit approval
- Merge into `main`, push to `main`, run `gh pr merge`, or force-push.
- Add, remove, or upgrade any package. Ask first, then log it in docs/DEPENDENCY_CHANGES.md.
- Use `--no-verify`, delete or skip or weaken a test, or edit CI to make it pass.
- Run destructive commands: `git reset --hard`, `git clean`, `docker system prune`,
  `docker volume rm`, dropping a database or table, deleting data.
- Print, copy, log, or commit values from `.env*`, keys, or tokens.

## Change log (required)
- Keep `docs/CHANGELOG_AI.md` up to date. Add one section per session:
  date, branch, requirement. Under it, a table row for EVERY file you change:
  | File | What changed | Why |
- Commit the log update together with the change it describes.
- Commit messages: Conventional Commits. The body lists each change and its reason.

## Tests
- Run the full tests and linter before every commit and before saying done.
- If tests are missing for the code you touch, write them FIRST.
- For a bug fix: write a test that fails, then fix, then show it passes.
- If a test fails, fix the cause. If it was already failing before you started,
  report it and do not hide it.
- Done means: all tests and lint pass, and you showed me the output.

## Work style
- Smallest change that solves the problem. No unrelated refactors.
- One concern per commit.
- For version-sensitive choices, check the official docs and note the source in the log.
- If the plan is wrong or unclear, stop and ask. Do not improvise.

## End of every session
Give me: files changed (with reasons), tests run and results, open questions.
Push the branch only if I approve, then open a pull request. I merge it myself.

## Commands
(To be filled in after the first audit: install, run, test, lint, build, docker.)
