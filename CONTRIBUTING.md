# Contributing to PyMDView

PyMDView is a small GTK 3 + WebKitGTK Markdown viewer written in Python. Its main rule is that **every dependency comes from Ubuntu's own repositories (22.04 and later)**: no pip packages and no virtualenv. Keep that rule when you add features.

## Run from source

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 python3-markdown \
                 python3-markdown-it python3-mdit-py-plugins python3-pygments python3-pytest
./bin/pymdview sample.md          # or: python3 -m pymdview sample.md
./bin/pymdview --debug sample.md  # shows which optional renderers/plugins loaded
```

Edit `sample.md` while it is open to see the live reload.

## Test and lint

```bash
python3 -m pytest                 # unit tests (no display needed)
pip install --user ruff==0.17.4  # same version as CI (RUFF_VERSION in ci.yml)
ruff check . && ruff format .     # lint + format
```

CI (`.github/workflows/ci.yml`) runs on every push and pull request, on Ubuntu 22.04 and 24.04. It runs ruff, the tests, a GTK import smoke test under Xvfb, and a `.deb` build.

## Code map

| Module | What it does | GTK? |
|---|---|---|
| `pymdview/__init__.py` | `APP_ID`, `APP_NAME`, `PRG_NAME`, `VERSION` — **the** place to change them | no |
| `pymdview/render.py` | Markdown → HTML: renderer selection, plugins, syntax highlighting, `[TOC]`, task lists, front matter, page wrapper | no |
| `pymdview/style.css` | All page styling. Theme colours are CSS variables under `body.light` / `body.dark` | — |
| `pymdview/util.py` | Small pure helpers (`js_str`, `pretty_path`) | no |
| `pymdview/shortcuts.py` | The one list of keyboard shortcuts (accelerators + help-dialog labels) | no |
| `pymdview/compat.py` | Pins GTK/WebKit versions and hides API differences between Ubuntu releases. Other modules import GTK names **from here** | yes |
| `pymdview/window.py` | `ViewerWindow`: UI, file watching, link handling, find, zoom, print | yes |
| `pymdview/app.py` | `Gtk.Application`, windows, command-line parsing, `main()` | yes |
| `bin/pymdview` | Launcher that finds the package (repo, `~/.local/share`, or `/usr/share`) | — |

Code that doesn't need GTK should go in a GTK-free module, so it can be tested without a display.

### How a document gets on screen

```
Gio folder monitor ─► ViewerWindow.on_dir_changed ─► _schedule_reload (150 ms debounce)
   ─► ViewerWindow.render ─► render.load_text ─► render.render_markdown ─► render.build_page
   ─► WebView.load_html ─► ViewerWindow.on_load_changed (restore scroll, #anchor, find, after-load callback)
```

Design decisions worth knowing:
- **The folder is watched, not the file.** Editors that save by writing a temp file and renaming it over the original (Vim, VS Code, gedit) would otherwise break the watch.
- **Page JavaScript is disabled.** Markdown can contain raw HTML. The app still runs its own scripts through `compat.run_js`, which uses the WebKit API.
- **Links never navigate the web view.** `on_decide_policy` sends every click to `follow_link`. That function scrolls to `#anchors`, opens `.md` files in the viewer, and hands any other link to the default app.
- **Optional dependencies degrade quietly.** Without markdown-it, the Python-Markdown fallback is used. Without Pygments, code is not highlighted. Missing mdit plugins are skipped. Use `--debug` to see what was actually loaded.

### Ubuntu version differences (handled in `compat.py` / `render.py`)

| | 22.04 | 24.04 |
|---|---|---|
| WebKit2 GI | 4.0 (4.1 if installed) | 4.1 |
| JS API | `run_javascript` | `evaluate_javascript` |
| Disable page JS | `set_enable_javascript` | `set_enable_javascript_markup` |
| mdit-py-plugins | 0.3 (no `admon`) | 0.4 |

## Dependencies

This is the canonical list. When you change it, also update **all three** places that repeat it:
1. `install.sh` (`DEPS` / `OPT`)
2. `build-deb.sh` (`Depends` / `Recommends` / `Suggests`)
3. `README.md` (*Option C*) and the apt line in `.github/workflows/ci.yml`

| Package | Role |
|---|---|
| `python3` (≥ 3.10), `python3-gi`, `gir1.2-gtk-3.0` | required |
| `gir1.2-webkit2-4.1` or `gir1.2-webkit2-4.0` | required |
| `python3-markdown` | required (fallback renderer) |
| `python3-markdown-it`, `python3-mdit-py-plugins` | recommended (CommonMark + GitHub extras) |
| `python3-pygments` | recommended (syntax highlighting) |
| `python3-linkify-it` | optional (auto-link bare URLs; not packaged on 22.04) |

## Common changes

- **Add a keyboard shortcut:** add a row to `SHORTCUTS` in `shortcuts.py` and a handler in `ViewerWindow._install_actions` (or `MdViewApp.do_startup` for `app.` actions). Then add the row to the README table; a test fails if you forget.
- **Change the page look:** edit `pymdview/style.css`. Change colours in the `body.light` / `body.dark` variable blocks.
- **Support a new Markdown feature:** add the plugin to `_MDIT_PLUGINS` in `render.py` (it is skipped automatically where it isn't available). If you can, add the equivalent Python-Markdown extension to the fallback, and add a test in `tests/test_render.py`.

## Releasing

1. Bump `VERSION` in `pymdview/__init__.py`.
2. In `CHANGELOG.md`, rename *Unreleased* to the new version (`## [x.y.z]`). A test checks that the current version is listed.
3. `./build-deb.sh`, then install the result and test it: `sudo apt install ./pymdview_x.y.z_all.deb`.
4. Commit, tag `vx.y.z`, push, and attach the `.deb` to the GitHub release.
