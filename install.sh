#!/usr/bin/env bash
set -e

# ==============================================================================
# Taskforce One-Step Automated Installer
# Installs desktop notification companion for Antigravity, Gemini CLI, and IDEs
# ==============================================================================

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
CONFIG_DIR="$HOME/.config/taskforce"
GEMINI_CONFIG_DIR="$HOME/.gemini/config"
GEMINI_CLI_DIR="$HOME/.gemini/antigravity-cli"

echo "=== Installing Taskforce ==="
echo "Repository: $REPO_DIR"

# 1. Check dependencies
echo "--> Checking system dependencies..."

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required. Please install Python 3."
  exit 1
fi

if ! python3 -c "import gi; gi.require_version('Gtk', '3.0')" >/dev/null 2>&1; then
  echo "Notice: PyGObject (GTK3) is missing."
  echo "To install on Ubuntu / Debian, run:"
  echo "    sudo apt update && sudo apt install -y python3-gi gir1.2-gtk-3.0"
  exit 1
fi

# 2. Check audio player
if ! command -v mpv >/dev/null 2>&1 && ! command -v canberra-gtk-play >/dev/null 2>&1 && ! command -v paplay >/dev/null 2>&1 && ! command -v aplay >/dev/null 2>&1; then
  echo "Warning: No audio player found (mpv, canberra-gtk-play, paplay, aplay)."
  echo "For best audio support, install mpv: sudo apt install -y mpv"
fi

# 3. Generate assets if missing
if [ ! -f "$REPO_DIR/public/taskforce-mascot.gif" ] || [ ! -f "$REPO_DIR/public/taskforce-chime.wav" ]; then
  echo "--> Generating mascots and sound chimes..."
  if command -v node >/dev/null 2>&1; then
    node "$REPO_DIR/scripts/generate-assets.mjs"
  fi
fi

# 4. Install binaries to ~/.local/bin
echo "--> Installing CLI binaries to $BIN_DIR..."
mkdir -p "$BIN_DIR"
chmod +x "$REPO_DIR/scripts/desktop_notifier.py"
chmod +x "$REPO_DIR/scripts/settings_gui.py"

ln -sf "$REPO_DIR/scripts/desktop_notifier.py" "$BIN_DIR/taskforce-notify"
ln -sf "$REPO_DIR/scripts/settings_gui.py" "$BIN_DIR/taskforce-settings"

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  echo "Note: $BIN_DIR is not yet in your PATH."
  echo "Add this to your ~/.bashrc or ~/.zshrc:"
  echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# 5. Initialize config.json if not already present
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/config.json" ]; then
  echo "--> Initializing default configuration..."
  cat <<EOF > "$CONFIG_DIR/config.json"
{
  "position": "bottom-right",
  "custom_x": null,
  "custom_y": null,
  "margin_x": 32,
  "margin_y": 48,
  "duration_ms": 4000,
  "sound_enabled": true,
  "volume": 0.8,
  "completed_gif": "$REPO_DIR/public/taskforce-mascot.gif",
  "completed_sound": "$REPO_DIR/public/taskforce-chime.wav",
  "help_gif": "$REPO_DIR/public/taskforce-help.gif",
  "help_sound": "$REPO_DIR/public/taskforce-help.wav",
  "card_background": "rgba(15, 23, 42, 0.94)",
  "border_completed": "#34d399",
  "border_help": "#fbbf24",
  "border_radius": 16
}
EOF
fi

# 6. Install desktop application launcher
echo "--> Installing desktop application shortcut..."
mkdir -p "$APP_DIR"
cat <<EOF > "$APP_DIR/taskforce-settings.desktop"
[Desktop Entry]
Name=Taskforce Settings
Comment=Configure Agent Notification Popups, Pictures, and Audio
Exec=$BIN_DIR/taskforce-settings
Icon=$REPO_DIR/src-tauri/icons/icon.png
Terminal=false
Type=Application
Categories=Development;Utility;Settings;
StartupNotify=true
EOF
chmod +x "$APP_DIR/taskforce-settings.desktop"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APP_DIR" 2>/dev/null || true

# 7. Configure agent hooks for Antigravity & Gemini CLI
echo "--> Configuring agent lifecycle hooks..."
mkdir -p "$GEMINI_CONFIG_DIR"
cat <<EOF > "$GEMINI_CONFIG_DIR/hooks.json"
{
  "taskforce-notifier": {
    "enabled": true,
    "Stop": [
      {
        "type": "command",
        "command": "$BIN_DIR/taskforce-notify --hook-stop",
        "timeout": 5
      }
    ],
    "PreToolUse": [
      {
        "matcher": "ask_question",
        "hooks": [
          {
            "type": "command",
            "command": "$BIN_DIR/taskforce-notify --hook-tool",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
EOF

if [ -d "$GEMINI_CLI_DIR" ]; then
  ln -sf "$GEMINI_CONFIG_DIR/hooks.json" "$GEMINI_CLI_DIR/hooks.json"
fi

# 8. Setup and start background systemd service
if command -v systemctl >/dev/null 2>&1; then
  echo "--> Setting up systemd background watcher service..."
  mkdir -p "$SYSTEMD_USER_DIR"
  cat <<EOF > "$SYSTEMD_USER_DIR/taskforce.service"
[Unit]
Description=Taskforce Desktop Agent Notifier Service
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 %h/.local/bin/taskforce-notify --watch
Restart=always
RestartSec=3
Environment=DISPLAY=:0
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

  systemctl --user daemon-reload
  systemctl --user enable --now taskforce.service
  echo "    Service active: $(systemctl --user is-active taskforce.service 2>/dev/null || echo 'running')"
fi

echo ""
echo "=== Installation Complete! ==="
echo "Taskforce is now active and watching for agent tasks."
echo ""
echo "Quick Commands:"
echo "  taskforce-notify --test     Test notification popup"
echo "  taskforce-settings          Open visual settings window"
echo "  taskforce-notify --drag     Drag character anywhere on screen"
echo ""

# Trigger test notification
"$BIN_DIR/taskforce-notify" --test --bg || true
