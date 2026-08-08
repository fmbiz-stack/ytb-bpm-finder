#!/bin/bash
# macOS: double-click this in Finder to start the toolkit.
#
# Finder can't run start.sh directly - .command is the extension it opens in
# Terminal - so this is the macOS entry point. It leaves the Terminal window
# open, which is what you want: that window is what keeps the proxy running.
cd "$(dirname "$0")" || exit 1

find_python() {
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
        echo "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

PYTHON=$(find_python)
if [ -z "$PYTHON" ]; then
  echo "Python 3.9 or newer is required but wasn't found."
  echo
  echo "Install it from https://www.python.org/downloads/ or with Homebrew:"
  echo "  brew install python3"
  echo
  read -r -p "Press Return to close."
  exit 1
fi

if ! "$PYTHON" -c 'import PIL' >/dev/null 2>&1; then
  echo "Installing Pillow (needed to draw emblem previews)..."
  # --user keeps this out of the system Python, which macOS marks read-only.
  "$PYTHON" -m pip install --user -r requirements.txt || {
    echo
    echo "That didn't work. Install it by hand with:"
    echo "  $PYTHON -m pip install --user -r requirements.txt"
    echo
    read -r -p "Press Return to close."
    exit 1
  }
fi

"$PYTHON" run.py
echo
read -r -p "Stopped. Press Return to close this window."
