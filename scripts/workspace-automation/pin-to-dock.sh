#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh" || exit 1

case "$(uname -s)" in
    Darwin)
        require_command defaults
        require_command osascript
        APP_NAME="Open Workspace"
        APP_DIR="$SCRIPT_DIR/$APP_NAME.app"
        CONTENTS="$APP_DIR/Contents"
        mkdir -p "$CONTENTS/MacOS" "$CONTENTS/Resources"
        cat > "$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>$APP_NAME</string>
<key>CFBundleDisplayName</key><string>$APP_NAME</string>
<key>CFBundleIdentifier</key><string>local.OpenWorkspace</string>
<key>CFBundleExecutable</key><string>launcher</string>
<key>CFBundlePackageType</key><string>APPL</string>
</dict></plist>
PLIST
        cat > "$CONTENTS/MacOS/launcher" <<LAUNCHER
#!/bin/bash
exec "$SCRIPT_DIR/open-workspaces.sh"
LAUNCHER
        chmod +x "$CONTENTS/MacOS/launcher"
        defaults write com.apple.dock persistent-apps -array-add "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>$APP_DIR</string><key>_CFURLStringType</key><integer>0</integer></dict></dict></dict>"
        osascript -e 'tell application "Dock" to quit'
        printf 'Pinned %s to the macOS Dock.\n' "$APP_NAME"
        ;;
    Linux)
        require_command xdg-desktop-menu
        DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
        mkdir -p "$DESKTOP_DIR"
        cat > "$DESKTOP_DIR/open-workspace.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Open Workspace
Comment=Open all configured workspace tabs in Tabby
Exec=$SCRIPT_DIR/open-workspaces.sh
Terminal=false
Categories=Development;TerminalEmulator;
DESKTOP
        xdg-desktop-menu install --novendor "$DESKTOP_DIR/open-workspace.desktop"
        printf 'Installed Open Workspace in the Linux application menu.\n'
        ;;
    *) printf 'error: unsupported operating system: %s\n' "$(uname -s)" >&2; exit 1 ;;
esac
