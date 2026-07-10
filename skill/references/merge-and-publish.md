# Setting up `live` and publishing at end of session

## Starting a session: create the `live` branch

Before opening the edit server for a deck, from the deck's repo:

```bash
git checkout -b live/<deck-slug>
```

This is the branch the edit server's deck-root directory should be checked out to (or a worktree of it) — every subagent merge in `subagent-dispatch.md` step 3 lands here. `main` is never touched until the session ends.

## Ending a session: draft PR

When the person says they're done editing (there is no automatic idle-timeout — this is always an explicit instruction), from the deck's repo on the `live/<deck-slug>` branch:

```bash
git push -u origin live/<deck-slug>
gh pr create --draft \
  --title "Live edits: <deck-slug>" \
  --body "Edits made via the live slide-edit tool during an interactive session. Convert to ready-for-review when you're happy with the content."
```

Opening as a **draft** matters: this repo's existing slide-publish pipeline (see its own `_README.md` / `publish-slides-validate.yml`) already skips auto-merge for draft PRs, so nothing goes live until the person explicitly converts the PR to ready-for-review. Don't build a separate approval gate — this reuses one that already exists.

## If the session is abandoned

Delete the `live/<deck-slug>` branch. `main` was never touched, so there is nothing to clean up on the published site.
