#!/usr/bin/env bash

# ==============================================================================
# Taskforce Uninstaller
# ==============================================================================

echo "=== Uninstalling Taskforce ==="

if command -v systemctl >/dev/null 2>&1; then
  echo "--> Stopping and disabling background service..."
  systemctl --user stop taskforce.service 2>/dev/null || true
  systemctl --user disable taskforce.service 2>/dev/null || true
  rm -f "$HOME/.config/systemd/user/taskforce.service"
  systemctl --user daemon-reload 2>/dev/null || true
fi

echo "--> Removing CLI symlinks..."
rm -f "$HOME/.local/bin/taskforce-notify"
rm -f "$HOME/.local/bin/taskforce-settings"

echo "--> Removing desktop shortcut..."
rm -f "$HOME/.local/share/applications/taskforce-settings.desktop"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo "--> Removing agent hooks..."
rm -f "$HOME/.gemini/config/hooks.json"
rm -f "$HOME/.gemini/antigravity-cli/hooks.json"
rm -f "$HOME/.config/opencode/plugins/taskforce.js"

echo "=== Taskforce uninstalled cleanly. ==="
echo "Note: Configuration in ~/.config/taskforce has been preserved."
echo "To remove configuration as well, run: rm -rf ~/.config/taskforce"
