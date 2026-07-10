# Live Slide-Edit Tool

Serves an HTML deck directory with an editable overlay, so a person can make continuous inline edits and notes in the browser while an already-running Claude Code session applies each one and merges it into the version being served.

## When to use

Use this when someone wants to make hands-on edits to an HTML deck (any repo that publishes HTML decks via a git-based pipeline) without going through a manual PR-per-change cycle, and you (Claude) are already attached to that deck's repo in an interactive session.

## Skill structure

```
skill/
├── SKILL.md                     # this file
├── tools/
│   ├── edit_log.py               # append-only JSONL event log
│   ├── overlay.py                # injects the editable overlay into served HTML
│   ├── edit_server.py            # local HTTP server tying the above together
│   └── watch_edits.py            # tails the log, notifies on each new edit
└── references/
    ├── subagent-dispatch.md      # what to do when notified of a new edit
    └── merge-and-publish.md      # live branch + end-of-session draft PR
```

## Starting a session

1. Pick the deck directory to edit (e.g. `/path/to/repo/published-slides/some-deck/`).
2. Create the session's `live` branch — `git checkout -b live/<deck-slug>` in the deck's repo — so the edit server never runs against `main`. Full detail in `references/merge-and-publish.md`.
3. Start the server in the background:
   ```bash
   python3 skill/tools/edit_server.py /path/to/deck-dir 8791
   ```
4. Start the watcher, piped through the Monitor tool so each new edit surfaces as a notification in this conversation:
   ```bash
   python3 skill/tools/watch_edits.py /path/to/deck-dir/.slide-edits/edits.jsonl 1
   ```
5. Tell the person the URL to open: `http://127.0.0.1:8791/index.html`.
6. On each notification, follow `references/subagent-dispatch.md`.
7. When the person says they're done editing, follow `references/merge-and-publish.md`.
