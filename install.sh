#!/usr/bin/env bash
# Install PyMDView for the current user (no root needed for the app itself).
# Usage:  ./install.sh              install to ~/.local
#         ./install.sh --uninstall
# Dependencies: keep in sync with CONTRIBUTING.md ("Dependencies").
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PREFIX="${PREFIX:-$HOME/.local}"
BIN="$PREFIX/bin/pymdview"
LIB="$PREFIX/share/pymdview"
APPS="$PREFIX/share/applications"
ICONS="$PREFIX/share/icons/hicolor/scalable/apps"

remove_old_mdview() {  # files from releases before the rename to pymdview
  rm -f "$PREFIX/bin/mdview" "$APPS/mdview.desktop" "$ICONS/mdview.svg"
}

if [[ "${1:-}" == "--uninstall" ]]; then
  rm -f "$BIN" "$APPS/pymdview.desktop" "$ICONS/pymdview.svg"
  rm -rf "$LIB"
  remove_old_mdview
  update-desktop-database "$APPS" 2>/dev/null || true
  echo "PyMDView removed."
  exit 0
fi

# Runtime dependencies (all in Ubuntu's main/universe repos)
DEPS=(python3-gi gir1.2-gtk-3.0 python3-markdown)
OPT=(python3-markdown-it python3-mdit-py-plugins python3-pygments python3-linkify-it)
if apt-cache show gir1.2-webkit2-4.1 >/dev/null 2>&1; then
  DEPS+=(gir1.2-webkit2-4.1)
else
  DEPS+=(gir1.2-webkit2-4.0)
fi

MISSING=()
for p in "${DEPS[@]}" "${OPT[@]}"; do
  if ! dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed"; then
    # Optional packages may not exist on every release; skip those quietly.
    if [[ " ${OPT[*]} " == *" $p "* ]] && ! apt-cache show "$p" >/dev/null 2>&1; then
      continue
    fi
    MISSING+=("$p")
  fi
done
if ((${#MISSING[@]})); then
  echo "Installing dependencies: ${MISSING[*]}"
  sudo apt-get install -y "${MISSING[@]}"
fi

remove_old_mdview
rm -rf "$LIB"
install -d "$LIB/pymdview"
install -m644 "$HERE"/pymdview/*.py "$HERE/pymdview/style.css" "$LIB/pymdview/"
install -Dm755 "$HERE/bin/pymdview"     "$BIN"
install -Dm644 "$HERE/pymdview.desktop" "$APPS/pymdview.desktop"
install -Dm644 "$HERE/pymdview.svg"     "$ICONS/pymdview.svg"
sed -i "s|^Exec=pymdview|Exec=$BIN|" "$APPS/pymdview.desktop"

update-desktop-database "$APPS" 2>/dev/null || true
gtk-update-icon-cache -q "$PREFIX/share/icons/hicolor" 2>/dev/null || true

echo
echo "PyMDView installed."
echo "  • Find it in Activities as \"PyMDView\", or run:  $BIN README.md"
echo "  • To make it the default for .md files:"
echo "      xdg-mime default pymdview.desktop text/markdown"
case ":$PATH:" in *":$PREFIX/bin:"*) ;; *) echo "  • Note: $PREFIX/bin is not on your PATH yet (log out and back in).";; esac
