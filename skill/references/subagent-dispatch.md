# Reacting to a new-edit notification

Each line the watcher prints looks like:

```
New slide edit: id=a1b2c3d4e5f6 file=slides/slide-04.html type=text selector=p:nth-of-type(2)
```

or, for a freeform note (no selector):

```
New slide edit: id=a1b2c3d4e5f6 file=index.html type=note selector=None
```

On each one, do the following, in order:

## 1. Mark it in-progress

```bash
curl -s -X POST http://127.0.0.1:8791/__status__/a1b2c3d4e5f6 \
  -H "Content-Type: application/json" -d '{"status":"in-progress"}'
```

## 2. Dispatch a subagent scoped to the one file

Before dispatching, sanity-check that the `file` path from the log entry actually resolves inside the deck directory (no `..` traversal escaping it). The edit server already rejects out-of-root paths at write time, but this is a cheap belt-and-suspenders check before handing a literal file path to an autonomous, git-committing subagent — never dispatch against a path that resolves outside the deck directory.

Use the Agent tool with `isolation: "worktree"`. The subagent's prompt must include: the deck directory path, the target file (from the notification), and the edit content — read it directly from the log line, or `cat /path/to/deck/.slide-edits/edits.jsonl | tail -1` if you need the full `before`/`after`/`note` text (the printed notification line doesn't carry the full text).

Example prompt shape:

> "In the repo at `/path/to/deck-dir`, file `slides/slide-04.html`: the person changed the text at CSS selector `p:nth-of-type(2)` from '<before text>' to '<after text>'. Apply that exact change to the real file (not just the served copy) and commit it. Report back once committed."

For a `note` edit (no selector), the subagent's job is to interpret the freeform note and decide what to change in that file, same as the existing comment-review workflow other decks already use — ask rather than guess if genuinely ambiguous.

## 3. Merge the subagent's branch into `live`

The worktree-isolated subagent returns its branch name and worktree path. From the deck's own repo (not the subagent's worktree):

```bash
git checkout live
git merge --no-ff <subagent-branch-name>
```

If this conflicts (rare — only possible when two edits touch the exact same file at the exact same region, e.g. two concurrent edits to `shared.css`), resolve using judgment, or ask the person if genuinely ambiguous. Do not build automated conflict-resolution beyond this.

## 4. Mark it resolved

```bash
curl -s -X POST http://127.0.0.1:8791/__status__/a1b2c3d4e5f6 \
  -H "Content-Type: application/json" -d '{"status":"resolved"}'
```

The browser's next status poll (within ~1.5s) clears the highlight or updates the note's status text.

## Concurrent edits

If multiple notifications arrive close together, dispatch a subagent for each one in parallel — they're isolated in separate worktrees, so there's no need to process them one at a time. Only the merge-back step (3) needs to happen sequentially, one branch at a time, to avoid two merges racing on the same `live` branch.
