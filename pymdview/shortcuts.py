"""Keyboard shortcuts: the one list used for both the accelerators and the help dialog.

When you add or change a shortcut here, also update the table in README.md
(tests/test_helpers.py checks that every label below appears there).
"""

# (action name, accelerators, label shown in the shortcuts dialog)
# Action names starting with "app." are application-wide; others are "win.".
# A label of None hides the entry from the dialog.
SHORTCUTS = (
    ("open", ["<Ctrl>o"], "Open a file"),
    ("reload", ["<Ctrl>r", "F5"], "Reload"),
    ("find", ["<Ctrl>f"], "Find in document"),
    ("dark", ["<Ctrl>d"], "Toggle dark theme"),
    ("zoom-in", ["<Ctrl>plus", "<Ctrl>equal", "<Ctrl>KP_Add"], "Zoom in"),
    ("zoom-out", ["<Ctrl>minus", "<Ctrl>KP_Subtract"], "Zoom out"),
    ("zoom-reset", ["<Ctrl>0", "<Ctrl>KP_0"], "Reset zoom"),
    ("print", ["<Ctrl>p"], "Print"),
    ("export-pdf", ["<Ctrl><Shift>e"], "Export as PDF"),
    ("edit", ["<Ctrl>e"], "Open in text editor"),
    ("shortcuts", ["<Ctrl>question", "F1"], "Keyboard shortcuts"),
    ("close", ["<Ctrl>w"], "Close window"),
    ("app.new-window", ["<Ctrl>n"], "New window"),
    ("app.quit", ["<Ctrl>q"], "Quit"),
)


def detailed_name(action):
    """'open' → 'win.open'; 'app.quit' stays as is."""
    return action if action.startswith("app.") else "win." + action


def accels(action):
    """Accelerators for an action name as written in SHORTCUTS."""
    for name, keys, _label in SHORTCUTS:
        if name == action:
            return keys
    return []
