#!/usr/bin/env bash
# Build pymdview_<version>_all.deb  (works on Ubuntu 22.04 and later)
# The version comes from pymdview/__init__.py. Dependencies: keep in sync with
# CONTRIBUTING.md ("Dependencies").
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(cd "$HERE" && python3 -c 'import pymdview; print(pymdview.VERSION)')"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

install -d "$STAGE/usr/share/pymdview/pymdview"
install -m644 "$HERE"/pymdview/*.py "$HERE/pymdview/style.css" "$STAGE/usr/share/pymdview/pymdview/"
install -Dm755 "$HERE/bin/pymdview"     "$STAGE/usr/bin/pymdview"
install -Dm644 "$HERE/pymdview.desktop" "$STAGE/usr/share/applications/pymdview.desktop"
install -Dm644 "$HERE/pymdview.svg"     "$STAGE/usr/share/icons/hicolor/scalable/apps/pymdview.svg"
install -Dm644 "$HERE/README.md"        "$STAGE/usr/share/doc/pymdview/README.md"
install -Dm644 "$HERE/CHANGELOG.md"     "$STAGE/usr/share/doc/pymdview/CHANGELOG.md"
install -Dm644 "$HERE/sample.md"        "$STAGE/usr/share/doc/pymdview/sample.md"
sed -i '1s|.*|#!/usr/bin/python3|' "$STAGE/usr/bin/pymdview"

mkdir -p "$STAGE/DEBIAN"
cat > "$STAGE/DEBIAN/control" <<EOF
Package: pymdview
Version: $VERSION
Section: text
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1 | gir1.2-webkit2-4.0, python3-markdown
Recommends: python3-markdown-it, python3-mdit-py-plugins, python3-pygments
Suggests: python3-linkify-it
Conflicts: mdview
Replaces: mdview
Installed-Size: $(du -sk "$STAGE/usr" | cut -f1)
Maintainer: Joseph Anthony C. Hermocilla <jachermocilla@gmail.com>
Description: Simple Markdown viewer with live reload
 PyMDView renders Markdown files in a native GTK window and refreshes
 automatically whenever the file is saved. It supports GitHub-style
 tables, task lists, strikethrough, footnotes and syntax-highlighted
 code, plus light and dark themes, find, zoom, printing and PDF export.
EOF

cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t /usr/share/icons/hicolor || true
EOF

cat > "$STAGE/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
# Python writes bytecode caches next to the package at run time; dpkg doesn't track them.
rm -rf /usr/share/pymdview/pymdview/__pycache__
rmdir --ignore-fail-on-non-empty /usr/share/pymdview/pymdview /usr/share/pymdview 2>/dev/null || true
command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t /usr/share/icons/hicolor || true
EOF
chmod 755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/postrm"

OUT="$HERE/pymdview_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT" >/dev/null
echo "Built $OUT"
