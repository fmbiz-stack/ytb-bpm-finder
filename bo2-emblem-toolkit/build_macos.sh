#!/bin/bash
# Builds the macOS release artifacts. Only needed if you want to produce them
# yourself instead of downloading them from the Releases page.
#
#   dist/cli/BO2EmblemToolkit       a single-file binary, run from Terminal,
#                                   shows the live log
#   dist/app/BO2EmblemToolkit.app   double-clickable app, no Terminal window;
#                                   stop it with Quit in the control panel
#
# Both are ad-hoc signed at the end. That is not the same as notarising: on
# another Mac, Gatekeeper will still quarantine a download. See docs/INSTALL.md
# for the one-line fix users need (xattr -dr com.apple.quarantine).
set -euo pipefail
cd "$(dirname "$0")"

PYTHON=${PYTHON:-python3}
"$PYTHON" -m pip install -r requirements.txt pyinstaller

ROOT="$PWD"

# macOS uses ':' as the --add-data separator, unlike Windows' ';'.
#
# The source side of --add-data is absolute on purpose: PyInstaller resolves a
# relative one against the spec file's directory, not the working directory, so
# with --specpath below a relative "reference_shapes" would be looked for inside
# build/ and the build would fail.
COMMON=(
  --noconfirm
  --clean
  --onefile
  --name BO2EmblemToolkit
  --add-data "$ROOT/reference_shapes:reference_shapes"
  --add-data "$ROOT/emblemtool/web/static:emblemtool/web/static"
  --add-data "$ROOT/LICENSE:."
)

echo "==> Building the command-line binary"
"$PYTHON" -m PyInstaller "${COMMON[@]}" \
  --distpath dist/cli --workpath build/cli --specpath build \
  "$ROOT/run.py"

echo "==> Building the .app bundle"
"$PYTHON" -m PyInstaller "${COMMON[@]}" \
  --windowed \
  --osx-bundle-identifier com.github.alexkotr1.bo2emblemtoolkit \
  --distpath dist/app --workpath build/app --specpath build/appspec \
  "$ROOT/run.py"

echo "==> Ad-hoc signing"
codesign --force --deep --sign - dist/app/BO2EmblemToolkit.app
codesign --force --sign - dist/cli/BO2EmblemToolkit

cat <<'EOF'

Built:
  dist/cli/BO2EmblemToolkit
  dist/app/BO2EmblemToolkit.app

The .app keeps captured emblems in ~/Library/Application Support/BO2EmblemToolkit,
because anything written inside a bundle is lost when the app is replaced.
To make it portable instead, put a folder named "saved" next to the .app and it
will use that.

Apple Silicon note: this produces a binary for whichever architecture the Python
you built with was. For a universal build, use a universal2 Python and add
  --target-arch universal2
to COMMON above.
EOF
