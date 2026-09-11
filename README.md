# Taskforce

Taskforce is a small desktop companion for coding agents. When a supported agent finishes a turn, Taskforce shows an animated character above your current window and plays a short signal.

The application runs locally in the system tray. It does not read or transmit prompts, responses, terminal output, or project files.

## Current integrations

- **Antigravity CLI / Gemini CLI** through automatic lifecycle hooks (`Stop` and `PreToolUse` for `ask_question`)
- **OpenCode CLI** through the `session.idle` plugin event
- **Terminal / Shell scripts / IDEs** via the `taskforce-notify` CLI

## Features

- **Animated Mascot & Audio Chime**: Native floating overlay that appears without window chrome or taskbar clutter.
- **Dual Notification States**:
  - **Task Complete** (emerald theme, victory mascot animation, pleasant two-tone chime).
  - **Needs User Help / Confirmation** (amber theme, curious mascot animation, attention chime).
- **Flexible Screen Placement**:
  - Drag mode: `taskforce-notify --drag` lets you grab and drag the mascot anywhere on screen.
  - Position presets: `bottom-right`, `top-right`, `bottom-left`, `top-left`, `center`.
- **Configurable**: Display time, volume, sound toggle, custom GIF and audio file paths via `~/.config/taskforce/config.json`.
- **Ultra-Fast & Non-Blocking**: Runs detached in the background without slowing down the agent loop.

## Quick CLI Usage

```bash
# Test the completion notification
taskforce-notify --test

# Test the "needs help / question" notification
taskforce-notify --status help

# Drag to place anywhere on your screen
taskforce-notify --drag

# Change default screen position preset
taskforce-notify --position top-right

# Adjust display duration (in ms) and volume (0.0 to 1.0)
taskforce-notify --duration 5000 --volume 0.9

# Toggle sound
taskforce-notify --sound off
```

## Development

Requirements:

- Node.js 20 or newer
- Rust 1.77.2 or newer
- The [Tauri v2 system prerequisites](https://v2.tauri.app/start/prerequisites/) for your platform

On Debian or Ubuntu, install the native packages with:

```bash
sudo apt update
sudo apt install libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf
```

Install dependencies and run Taskforce:

```bash
npm install
npm run tauri dev
```

Run the checks:

```bash
npm test
npm run build
cargo test --manifest-path src-tauri/Cargo.toml
```

## How integrations work

Taskforce opens an ephemeral HTTP listener on `127.0.0.1` and writes its port plus a random startup token to `~/.taskforce/endpoint.json`. The file is restricted to the current user on Unix systems.

Agent hooks send a minimal completion event to that endpoint. Failed notifications are silently ignored so Taskforce cannot interrupt an agent session.

The settings application installs integrations only after the user selects **Enable**. Gemini settings are backed up before the first modification, and unrelated hooks are preserved.

## Privacy

Completion events contain only:

- Protocol version
- Agent name
- Completion event name
- Optional session identifier
- Optional current working directory
- Timestamp

No cloud service, analytics system, or external network request is used.

## Platform note

Some Linux Wayland compositors prevent applications from choosing an arbitrary window position. Taskforce keeps the compositor-selected position in that environment; X11, Windows, and macOS support the draggable position flow.

## License

Taskforce is available under the MIT License. The generated mascot and chime are original project assets and are distributed under the same license.
