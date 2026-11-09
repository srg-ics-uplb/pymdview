# PyMDView

A small native Markdown viewer for Ubuntu 22.04 and later. Open a `.md` file and it stays in sync: every time you save the file in your editor, the view re-renders and keeps your scroll position.

Built with GTK 3, WebKitGTK and Python — every dependency comes from Ubuntu's own repositories, so there is nothing to `pip install`.

## Install

**Option A — Debian package (recommended)**

```bash
sudo apt install ./pymdview_1.0.0_all.deb
```

`apt` pulls in the dependencies automatically. Remove it later with `sudo apt remove pymdview`.

**Option B — per-user install from source**

```bash
./install.sh              # installs to ~/.local (asks for sudo only to apt-install missing deps)
./install.sh --uninstall
```

**Option C — just run it**

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 \
                 python3-markdown python3-markdown-it python3-mdit-py-plugins python3-pygments
./bin/pymdview README.md        # or: python3 -m pymdview README.md
```

### Make it the default for Markdown files

```bash
xdg-mime default pymdview.desktop text/markdown
```

Or right-click any `.md` file in Files → *Open With…* → *PyMDView* → *Always use for this file type*.

## Use

```bash
pymdview notes.md               # open a file
pymdview a.md b.md              # one window per file
pymdview --debug notes.md       # log diagnostics to the terminal
```

You can also drag a file onto the window, or launch **PyMDView** from Activities.

| Shortcut | Action |
|---|---|
| <kbd>Ctrl</kbd>+<kbd>O</kbd> | Open a file |
| <kbd>Ctrl</kbd>+<kbd>R</kbd> / <kbd>F5</kbd> | Reload (normally automatic) |
| <kbd>Ctrl</kbd>+<kbd>F</kbd> | Find in document |
| <kbd>Ctrl</kbd>+<kbd>D</kbd> | Toggle dark theme |
| <kbd>Ctrl</kbd>+<kbd>+</kbd> | Zoom in |
| <kbd>Ctrl</kbd>+<kbd>−</kbd> | Zoom out |
| <kbd>Ctrl</kbd>+<kbd>0</kbd> | Reset zoom |
| <kbd>Ctrl</kbd>+<kbd>P</kbd> | Print |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>E</kbd> | Export as PDF |
| <kbd>Ctrl</kbd>+<kbd>E</kbd> | Open in text editor |
| <kbd>Ctrl</kbd>+<kbd>?</kbd> / <kbd>F1</kbd> | Keyboard shortcuts |
| <kbd>Ctrl</kbd>+<kbd>N</kbd> | New window |
| <kbd>Ctrl</kbd>+<kbd>W</kbd> | Close window |
| <kbd>Ctrl</kbd>+<kbd>Q</kbd> | Quit |

## What renders

CommonMark plus the GitHub extras: tables, task lists, ~~strikethrough~~, footnotes, fenced code with syntax highlighting, definition lists and heading anchors. A paragraph containing just `[TOC]` becomes a table of contents. YAML front matter is hidden. On Ubuntu 24.04+ `!!! note` admonitions render too.

Links behave the way you'd expect: links to other `.md` files open in the viewer, `#anchors` scroll, relative images load, and web links open in your browser.

## Notes

- **Safe by default.** Scripts inside Markdown files never run; raw HTML is displayed but `<script>` and inline handlers are inert.
- **Theme** follows the GNOME light/dark setting at start-up; <kbd>Ctrl</kbd>+<kbd>D</kbd> flips it per window. Printing and PDF export always use the light theme.
- **PDF export** (menu → *Export as PDF…*) asks where to save and writes the file directly, using your locale's default paper size. For other paper sizes or margins, use *Print…* → *Print to File*.
- **Renderer.** Uses `markdown-it-py` (CommonMark) when installed and falls back to `python3-markdown` otherwise.
- **Live reload** watches the file's folder, so it also works with editors that save by writing a temp file and renaming it (Vim, VS Code, gedit).

## Files

| File | Purpose |
|---|---|
| `bin/pymdview` | Launcher script (finds the package and starts the app) |
| `pymdview/` | The application package — see [CONTRIBUTING.md](CONTRIBUTING.md) for a module map |
| `pymdview.desktop`, `pymdview.svg` | Launcher entry and icon |
| `install.sh` | Per-user install / uninstall |
| `build-deb.sh` | Builds the `.deb` |
| `tests/` | Unit tests (`python3 -m pytest`) |
| `sample.md` | A demo document |

Contributing: see [CONTRIBUTING.md](CONTRIBUTING.md). Changes are listed in [CHANGELOG.md](CHANGELOG.md).

License: MIT.
