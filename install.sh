#!/usr/bin/env bash
# Install gitctap! by copying one file into a directory on your PATH.
# Usage:
#   bash install.sh                 # install into ~/.local/bin
#   PREFIX=/usr/local bash install.sh   # install into /usr/local/bin
#   bash install.sh --uninstall     # remove it again

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$HERE/gitctap.py"
PREFIX="${PREFIX:-$HOME/.local}"
BIN_DIR="$PREFIX/bin"
TARGET="$BIN_DIR/gitctap"

if [ "${1:-}" = "--uninstall" ]; then
	if [ -e "$TARGET" ]; then
		rm -f "$TARGET"
		echo "removed $TARGET"
		echo "the configuration in ~/.config/gitctap/ was kept; delete that folder if you want it gone"
	else
		echo "nothing to remove at $TARGET"
	fi
	exit 0
fi

if [ ! -f "$SOURCE" ]; then
	echo "gitctap.py is not next to install.sh, so there is nothing to install" >&2
	exit 1
fi

if ! command -v git >/dev/null 2>&1; then
	echo "warning: git was not found in PATH. gitctap is a wrapper around Git and needs it." >&2
fi

PYTHON="$(command -v python3 || true)"
if [ -z "$PYTHON" ]; then
	echo "python3 was not found in PATH. gitctap needs Python 3.8 or newer." >&2
	exit 1
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)'; then
	echo "python3 is older than 3.8: $("$PYTHON" --version 2>&1)" >&2
	exit 1
fi

mkdir -p "$BIN_DIR"
install -m 755 "$SOURCE" "$TARGET"
echo "installed $TARGET"
"$TARGET" --version

case ":$PATH:" in
*":$BIN_DIR:"*) ;;
*)
	echo
	echo "$BIN_DIR is not in your PATH yet. Add this line to your shell profile:"
	echo "  export PATH=\"$BIN_DIR:\$PATH\""
	;;
esac

echo
echo "next: cd into a project and run  gitctap setup"
