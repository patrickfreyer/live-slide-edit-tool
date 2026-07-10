import json
import threading
import time
import uuid

VALID_STATUSES = {"pending", "in-progress", "resolved"}

# Serializes appends to the log file across threads within this process.
_LOCK = threading.Lock()


def append_edit(log_path, file, type_, selector=None, before=None, after=None, note=None):
    """Append a new edit event to the log. Returns the generated edit id."""
    edit_id = uuid.uuid4().hex[:12]
    event = {
        "event": "edit",
        "id": edit_id,
        "file": file,
        "type": type_,
        "selector": selector,
        "before": before,
        "after": after,
        "note": note,
        "ts": time.time(),
    }
    _append_line(log_path, event)
    return edit_id


def append_status(log_path, edit_id, status):
    """Append a status-change event for an existing edit id."""
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status {status!r}; must be one of {sorted(VALID_STATUSES)}"
        )
    event = {"event": "status", "id": edit_id, "status": status, "ts": time.time()}
    _append_line(log_path, event)


def read_all_events(log_path):
    """Read and parse every line in the log. Returns a list of dicts, oldest first."""
    if not log_path.exists():
        return []
    events = []
    with log_path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                # Incomplete/corrupted write (e.g. process killed mid-write).
                # Skip it rather than breaking the whole read path; per the
                # design spec, only the unprocessed tail needs replaying.
                continue
    return events


def compute_status_details(events):
    """Given events from read_all_events, return {edit_id: {status, file, type, selector, note}}."""
    details = {}
    for event in events:
        if event["event"] == "edit":
            details[event["id"]] = {
                "status": "pending",
                "file": event.get("file"),
                "type": event.get("type"),
                "selector": event.get("selector"),
                "note": event.get("note"),
            }
        elif event["event"] == "status":
            if event["id"] in details:
                details[event["id"]]["status"] = event["status"]
    return details


def compute_statuses(events):
    """Given events from read_all_events, return {edit_id: latest_status}."""
    return {edit_id: info["status"] for edit_id, info in compute_status_details(events).items()}


def _append_line(log_path, event):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # This lock protects against interleaved writes from concurrent
    # request-handling threads within this process (the actual deployment
    # model: one ThreadingHTTPServer process handling all requests). It
    # does not protect against multiple separate OS processes writing to
    # the same file — out of scope, since this tool runs as a single
    # server process.
    with _LOCK:
        with log_path.open("a") as f:
            f.write(json.dumps(event) + "\n")
