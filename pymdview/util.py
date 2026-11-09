"""Small pure helpers with no GTK dependency (so they can be unit-tested headless)."""

import os


def js_str(s):
    """Quote a Python string as a JavaScript string literal."""
    escaped = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def pretty_path(p):
    """Abbreviate the user's home directory to `~` for display."""
    home = os.path.expanduser("~")
    if p and (p == home or p.startswith(home + os.sep)):
        return "~" + p[len(home) :]
    return p
