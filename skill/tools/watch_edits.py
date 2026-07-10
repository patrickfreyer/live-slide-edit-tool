import sys
import time
from pathlib import Path

from edit_log import read_all_events


def new_edit_events(events, seen_ids):
    """Return (new_edit_events, updated_seen_ids) for edit events not already in seen_ids."""
    new_events = [e for e in events if e["event"] == "edit" and e["id"] not in seen_ids]
    updated_seen_ids = seen_ids | {e["id"] for e in new_events}
    return new_events, updated_seen_ids


def format_notification(event):
    return (
        f"New slide edit: id={event['id']} file={event['file']} "
        f"type={event['type']} selector={event.get('selector')}"
    )


def watch(log_path, poll_interval=1.0, max_iterations=None):
    """Poll the edit log and print one notification line per new edit event.

    Runs forever unless max_iterations is given (used by tests).
    """
    seen_ids = set()
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        events = read_all_events(Path(log_path))
        new_events, seen_ids = new_edit_events(events, seen_ids)
        for event in new_events:
            print(format_notification(event), flush=True)
        iterations += 1
        if max_iterations is None or iterations < max_iterations:
            time.sleep(poll_interval)
    return seen_ids


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: watch_edits.py <log_path> [poll_interval_seconds]")
        sys.exit(1)
    watch(sys.argv[1], poll_interval=float(sys.argv[2]) if len(sys.argv) > 2 else 1.0)
