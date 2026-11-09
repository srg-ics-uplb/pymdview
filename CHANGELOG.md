# Changelog

All notable changes to PyMDView are listed here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- Renamed from MD View to **PyMDView**. The command, package and installed files are now `pymdview` instead of `mdview`. The `.deb` replaces an installed `mdview` package, and `install.sh` removes old `mdview` files.
- Code split from a single `mdview.py` into the `pymdview/` package. Page CSS now lives in `pymdview/style.css`.
- The keyboard shortcuts dialog is generated from the same list as the accelerators, and now also shows New window and Keyboard shortcuts.
- `install.sh` also installs the optional `python3-linkify-it` when it is available.

### Fixed
- Printing in dark mode now waits for the light re-render to finish instead of a fixed 300 ms delay.

### Added
- **Export as PDF…** (menu, <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>E</kbd>): saves the document as a PDF without going through the print dialog. It always uses the light theme.
- `--debug` flag (or `MDVIEW_DEBUG=1`) that logs which optional renderers and plugins were loaded.
- Unit tests, ruff configuration, GitHub Actions CI, CONTRIBUTING.md.

## [1.0.0]

- First release.
