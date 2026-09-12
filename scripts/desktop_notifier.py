#!/usr/bin/env python3
"""
Taskforce Desktop Agent Notifier
Native, ultra-lightweight animated desktop popup for coding agents (Antigravity, Gemini CLI, IDEs).
"""

import sys
import os
import json
import argparse
import subprocess
import threading
import time
from pathlib import Path

# Prefer X11 backend if DISPLAY is available so window positioning and dragging work reliably on Linux (X11 / XWayland)
if os.environ.get("DISPLAY") and not os.environ.get("GDK_BACKEND"):
    os.environ["GDK_BACKEND"] = "x11,wayland"

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib

CONFIG_DIR = Path.home() / ".config" / "taskforce"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_ASSETS_DIR = Path(__file__).resolve().parent.parent / "public"

DEFAULT_CONFIG = {
    "position": "bottom-right",  # "bottom-right", "top-right", "bottom-left", "top-left", "center", or "custom"
    "custom_x": None,
    "custom_y": None,
    "margin_x": 32,
    "margin_y": 48,
    "duration_ms": 4000,
    "sound_enabled": True,
    "volume": 0.8,
    "completed_gif": str(DEFAULT_ASSETS_DIR / "taskforce-mascot.gif"),
    "completed_sound": str(DEFAULT_ASSETS_DIR / "taskforce-chime.wav"),
    "help_gif": str(DEFAULT_ASSETS_DIR / "taskforce-help.gif"),
    "help_sound": str(DEFAULT_ASSETS_DIR / "taskforce-help.wav"),
    "card_background": "rgba(15, 23, 42, 0.94)",
    "border_completed": "#34d399",
    "border_help": "#fbbf24",
    "border_radius": 16,
}

def load_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                config = DEFAULT_CONFIG.copy()
                config.update(data)
                return config
        except Exception:
            pass
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()

def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def play_sound(sound_file, volume=0.8):
    if not sound_file or not os.path.exists(sound_file):
        return
    
    # Try mpv first (supports all audio formats: MP3, WAV, OGG, AAC, FLAC, M4A)
    try:
        vol = int(max(0.0, min(1.0, volume)) * 100)
        res = subprocess.run(
            ["mpv", "--no-video", f"--volume={vol}", sound_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=4
        )
        if res.returncode == 0:
            return
    except Exception:
        pass

    # Try canberra-gtk-play
    try:
        res = subprocess.run(
            ["canberra-gtk-play", "--file=" + sound_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3
        )
        if res.returncode == 0:
            return
    except Exception:
        pass

    # Try paplay
    try:
        res = subprocess.run(
            ["paplay", sound_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3
        )
        if res.returncode == 0:
            return
    except Exception:
        pass

    # Try aplay
    try:
        subprocess.run(
            ["aplay", "-q", sound_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3
        )
    except Exception:
        pass

class AgentPopup(Gtk.Window):
    def __init__(self, status="completed", message=None, config=None, drag_mode=False):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.status = status
        self.message = message
        self.config = config or load_config()
        self.drag_mode = drag_mode
        self.dragging = False
        self.has_moved = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.win_start_x = 0
        self.win_start_y = 0

        # Window settings
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_role("agent-notification")
        self.set_title("Taskforce Agent Notification")

        # RGBA visual for smooth rounded transparent background
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)

        # Style with GTK CSS using config
        card_bg = self.config.get("card_background", "rgba(15, 23, 42, 0.94)")
        border_comp = self.config.get("border_completed", "#34d399")
        border_help = self.config.get("border_help", "#fbbf24")
        radius = self.config.get("border_radius", 16)

        css_provider = Gtk.CssProvider()
        css = f"""
        window {{
            background-color: transparent;
        }}
        .agent-card {{
            background-color: {card_bg};
            border-radius: {radius}px;
            border: 2px solid {border_comp};
            padding: 14px 18px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }}
        .agent-card.status-help {{
            border-color: {border_help};
        }}
        .agent-card.status-drag {{
            border-color: #60a5fa;
        }}
        """
        css_provider.load_from_data(css.encode('utf-8'))
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Build UI layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        main_box.get_style_context().add_class("agent-card")
        if self.status == "help":
            main_box.get_style_context().add_class("status-help")
        elif self.drag_mode:
            main_box.get_style_context().add_class("status-drag")

        # Determine GIF asset
        gif_path = self.config.get("completed_gif")
        if self.status == "help":
            gif_path = self.config.get("help_gif") or gif_path

        if not gif_path or not os.path.exists(gif_path):
            gif_path = str(DEFAULT_ASSETS_DIR / "taskforce-mascot.gif")

        # Animated image
        if os.path.exists(gif_path):
            try:
                anim = GdkPixbuf.PixbufAnimation.new_from_file(gif_path)
                image = Gtk.Image.new_from_animation(anim)
            except Exception:
                image = Gtk.Image.new_from_icon_name("dialog-information", Gtk.IconSize.DIALOG)
        else:
            image = Gtk.Image.new_from_icon_name("dialog-information", Gtk.IconSize.DIALOG)
        
        main_box.pack_start(image, False, False, 0)

        # Text box
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        text_box.set_valign(Gtk.Align.CENTER)

        # Status title & text
        if self.drag_mode:
            title_text = "Drag to Position"
            desc_text = "Drag to preferred spot and click to save"
            badge_color = "#60a5fa"
        elif self.status == "help":
            title_text = "Agent Needs Help"
            desc_text = self.message or "Waiting for your answer / permission"
            badge_color = "#fbbf24"
        else:
            title_text = "Task Complete"
            desc_text = self.message or "Ready for your next instruction!"
            badge_color = "#34d399"

        import html
        escaped_title = html.escape(title_text)
        escaped_desc = html.escape(desc_text)

        title_lbl = Gtk.Label()
        title_lbl.set_markup(f'<span font_weight="bold" font_size="11500" color="{badge_color}">✦ {escaped_title}</span>')
        title_lbl.set_halign(Gtk.Align.START)
        text_box.pack_start(title_lbl, False, False, 0)

        desc_lbl = Gtk.Label()
        desc_lbl.set_markup(f'<span font_size="9500" color="#f1f5f9">{escaped_desc}</span>')
        desc_lbl.set_halign(Gtk.Align.START)
        desc_lbl.set_line_wrap(True)
        desc_lbl.set_max_width_chars(32)
        text_box.pack_start(desc_lbl, False, False, 0)

        self.desc_lbl = desc_lbl
        self.auto_close_timer = None
        self.has_moved = False

        if self.drag_mode:
            btn_done = Gtk.Button(label="✔ Done")
            btn_done.get_style_context().add_class("action-btn")
            btn_done.connect("clicked", lambda w: self.close_popup())
            main_box.pack_end(btn_done, False, False, 0)

        main_box.pack_start(text_box, True, True, 0)
        self.add(main_box)

        # Mouse and keyboard events
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.KEY_PRESS_MASK
        )
        self.connect("button-press-event", self.on_button_press)
        self.connect("button-release-event", self.on_button_release)
        self.connect("motion-notify-event", self.on_motion)
        self.connect("key-press-event", self.on_key_press)

        # Calculate position after realized
        self.connect("realize", self.on_realize)

        # Dismiss timer for normal notifications
        if not self.drag_mode:
            duration_ms = self.config.get("duration_ms", 4000)
            GLib.timeout_add(duration_ms, self.close_popup)

    def on_key_press(self, widget, event):
        if event.keyval in (Gdk.KEY_Escape, Gdk.KEY_Return, Gdk.KEY_space):
            self.close_popup()

    def on_realize(self, widget):
        self.reposition()
        if self.drag_mode:
            gdk_win = self.get_window()
            if gdk_win:
                cursor = Gdk.Cursor.new_from_name(Gdk.Display.get_default(), "grab")
                gdk_win.set_cursor(cursor)

    def reposition(self):
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        geom = monitor.get_geometry()
        screen_w = geom.width
        screen_h = geom.height
        screen_x = geom.x
        screen_y = geom.y

        self.show_all()
        win_w, win_h = self.get_size()

        pos = self.config.get("position", "bottom-right")
        mx = self.config.get("margin_x", 32)
        my = self.config.get("margin_y", 48)

        if pos == "custom" and self.config.get("custom_x") is not None and self.config.get("custom_y") is not None:
            x = self.config["custom_x"]
            y = self.config["custom_y"]
        elif pos == "top-left":
            x = screen_x + mx
            y = screen_y + my
        elif pos == "top-right":
            x = screen_x + screen_w - win_w - mx
            y = screen_y + my
        elif pos == "bottom-left":
            x = screen_x + mx
            y = screen_y + screen_h - win_h - my
        elif pos == "center":
            x = screen_x + (screen_w - win_w) // 2
            y = screen_y + (screen_h - win_h) // 2
        else:  # bottom-right
            x = screen_x + screen_w - win_w - mx
            y = screen_y + screen_h - win_h - my

        self.move(max(0, x), max(0, y))

    def on_button_press(self, widget, event):
        if event.button == 1:  # Left click
            if self.drag_mode:
                self.dragging = True
                self.has_moved = False
                self.drag_start_x = event.x_root
                self.drag_start_y = event.y_root
                cur_x, cur_y = self.get_position()
                self.win_start_x = cur_x
                self.win_start_y = cur_y
                gdk_win = self.get_window()
                if gdk_win:
                    cursor = Gdk.Cursor.new_from_name(Gdk.Display.get_default(), "grabbing")
                    gdk_win.set_cursor(cursor)
            else:
                self.close_popup()
        elif event.button in (2, 3):  # Right or middle click
            self.close_popup()

    def on_motion(self, widget, event):
        if self.drag_mode and self.dragging:
            dx = event.x_root - self.drag_start_x
            dy = event.y_root - self.drag_start_y
            if abs(dx) > 2 or abs(dy) > 2:
                self.has_moved = True
            new_x = int(self.win_start_x + dx)
            new_y = int(self.win_start_y + dy)
            self.move(max(0, new_x), max(0, new_y))

    def on_button_release(self, widget, event):
        if self.drag_mode and self.dragging:
            self.dragging = False
            gdk_win = self.get_window()
            if gdk_win:
                cursor = Gdk.Cursor.new_from_name(Gdk.Display.get_default(), "grab")
                gdk_win.set_cursor(cursor)
            if self.has_moved:
                cur_x, cur_y = self.get_position()
                self.config["position"] = "custom"
                self.config["custom_x"] = cur_x
                self.config["custom_y"] = cur_y
                save_config(self.config)
                self.desc_lbl.set_markup('<span font_size="9500" color="#34d399">✔ Saved! Click [Done] to close</span>')

    def close_popup(self):
        if self.drag_mode and self.has_moved:
            cur_x, cur_y = self.get_position()
            self.config["position"] = "custom"
            self.config["custom_x"] = cur_x
            self.config["custom_y"] = cur_y
            save_config(self.config)
        if self.auto_close_timer:
            GLib.source_remove(self.auto_close_timer)
            self.auto_close_timer = None
        self.destroy()
        Gtk.main_quit()
        return False

def show_popup(status="completed", message=None, config=None, drag_mode=False):
    cfg = config or load_config()
    if cfg.get("sound_enabled", True) and not drag_mode:
        sound_file = cfg.get("help_sound" if status == "help" else "completed_sound")
        threading.Thread(target=play_sound, args=(sound_file, cfg.get("volume", 0.8)), daemon=True).start()

    popup = AgentPopup(status=status, message=message, config=cfg, drag_mode=drag_mode)
    popup.show_all()
    Gtk.main()

NOTIFIED_STEPS_FILE = Path("/tmp/taskforce_notified_steps")

def mark_and_check_step(conv_id, step_idx, event_type="completed", min_gap=1.0):
    """
    Ensure each conversation turn (whether tools were used or pure thinking/chat)
    is notified exactly once, eliminating duplicate popups without dropping turns.
    """
    now = time.time()
    key = f"{conv_id}:{step_idx}:{event_type}"
    notified = {}

    if NOTIFIED_STEPS_FILE.exists():
        try:
            with open(NOTIFIED_STEPS_FILE, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 2:
                        notified[parts[0]] = float(parts[1])
        except Exception:
            pass

    # If this exact step was already notified within the last 120s, skip duplicate
    if key in notified and (now - notified[key]) < 120:
        return False

    # Prevent instant sound/popup collision within min_gap (1.0s)
    for k, t in notified.items():
        if now - t < min_gap:
            return False

    notified[key] = now
    # Clean up entries older than 300 seconds
    cleaned = {k: t for k, t in notified.items() if now - t < 300}
    try:
        with open(NOTIFIED_STEPS_FILE, "w") as f:
            for k, t in cleaned.items():
                f.write(f"{k} {t}\n")
    except Exception:
        pass

    return True

SUBAGENT_CACHE = {}

def is_subagent_transcript(conv_path):
    """Returns True if the transcript belongs to an internal subagent."""
    conv_path = Path(conv_path)
    conv_id = conv_path.parent.parent.parent.name
    if conv_id in SUBAGENT_CACHE:
        return SUBAGENT_CACHE[conv_id]

    if not conv_path.exists():
        return False

    try:
        with open(conv_path, "r", encoding="utf-8", errors="replace") as f:
            # Check the first few lines of transcript
            for _ in range(4):
                line = f.readline()
                if not line:
                    break
                data = json.loads(line)
                # Subagents are injected with CHECKPOINT in step 1
                if data.get("type") == "CHECKPOINT" and "{{ CHECKPOINT" in data.get("content", ""):
                    SUBAGENT_CACHE[conv_id] = True
                    return True
    except Exception:
        pass

    SUBAGENT_CACHE[conv_id] = False
    return False

def has_pending_work(conv_path):
    """
    Returns True if the session has active background tasks or active subagents
    that have not yet finished or responded.
    """
    try:
        size = os.path.getsize(conv_path)
        with open(conv_path, "r", encoding="utf-8", errors="replace") as f:
            # Read last 64KB
            f.seek(max(0, size - 65536))
            lines = f.readlines()
            if not lines:
                return False
            if size > 65536 and len(lines) > 1:
                lines = lines[1:]

            import re
            pending_tasks = set()
            pending_subagents = set()

            for ln in lines:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    d = json.loads(ln)
                except Exception:
                    continue

                content = d.get("content", "")
                if isinstance(content, str):
                    if "Tool is running as a background task with task id:" in content:
                        m = re.search(r'task id: ([\w\-]+(?:/[\w\-]+)?)', content)
                        if m:
                            pending_tasks.add(m.group(1).split("/")[-1])
                    if "finished with result:" in content:
                        m = re.search(r'Task id \"([^\"]+)\" finished', content)
                        if m:
                            tid = m.group(1).split("/")[-1]
                            pending_tasks.discard(tid)

                    if "Created the following subagents:" in content:
                        ids = re.findall(r'\"conversationId\":\s*\"([^\"]+)\"', content)
                        for sid in ids:
                            pending_subagents.add(sid)
                            SUBAGENT_CACHE[sid] = True
                    if "sender=" in content:
                        m = re.search(r'sender=([\w\-]+)', content)
                        if m:
                            pending_subagents.discard(m.group(1))

            if len(pending_tasks) > 0 or len(pending_subagents) > 0:
                return True
    except Exception:
        pass
    return False

def handle_hook_stop():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        transcript_path = payload.get("transcriptPath")
        conv_id = payload.get("conversationId", "unknown")
        step_idx = payload.get("stepIdx", 0)

        if transcript_path:
            if is_subagent_transcript(transcript_path) or has_pending_work(transcript_path):
                return

        # Ensure the agent engine reports fullyIdle (all background tasks done)
        if payload.get("fullyIdle") is False:
            return

        termination = payload.get("terminationReason", "model_stop")
        if termination in ("model_stop", "normal", None, ""):
            if not mark_and_check_step(conv_id, step_idx, event_type="completed"):
                return
            env = os.environ.copy()
            if "DISPLAY" not in env:
                env["DISPLAY"] = ":0"
            cmd = [sys.executable, str(Path(__file__).resolve()), "--status", "completed"]
            subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    finally:
        sys.stdout.write("{}\n")
        sys.stdout.flush()

def handle_hook_tool():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        transcript_path = payload.get("transcriptPath")
        conv_id = payload.get("conversationId", "unknown")
        step_idx = payload.get("stepIdx", 0)

        if transcript_path and is_subagent_transcript(transcript_path):
            return

        tool_call = payload.get("toolCall", {})
        tool_name = tool_call.get("name", "")
        if tool_name == "ask_question":
            if not mark_and_check_step(conv_id, step_idx, event_type="help"):
                return
            env = os.environ.copy()
            if "DISPLAY" not in env:
                env["DISPLAY"] = ":0"
            cmd = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--status", "help",
                "--message", "Agent needs your answer to proceed!"
            ]
            subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    finally:
        sys.stdout.write(json.dumps({"decision": "allow"}) + "\n")
        sys.stdout.flush()

def get_last_json(conv_path):
    try:
        size = os.path.getsize(conv_path)
        with open(conv_path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(max(0, size - 262144))
            lines = f.readlines()
            if not lines:
                return None
            if size > 262144 and len(lines) > 1:
                lines = lines[1:]
            for ln in reversed(lines):
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    return json.loads(ln)
                except Exception:
                    continue
    except Exception:
        pass
    return None

OPENCODE_DB = Path.home() / ".local" / "share" / "opencode" / "opencode.db"

def get_latest_opencode_event_id():
    """Get the highest event id currently in OpenCode's sqlite database."""
    if not OPENCODE_DB.exists():
        return None
    try:
        import sqlite3
        con = sqlite3.connect(f"file:{OPENCODE_DB}?mode=ro", uri=True)
        cur = con.cursor()
        cur.execute("SELECT id FROM event ORDER BY id DESC LIMIT 1;")
        row = cur.fetchone()
        con.close()
        return row[0] if row else None
    except Exception:
        return None

def check_opencode_events(last_seen_id, env):
    """
    Query OpenCode database for newly finished assistant turns (both thinking and tool calls)
    and permission requests.
    """
    if not OPENCODE_DB.exists():
        return last_seen_id
    try:
        import sqlite3
        con = sqlite3.connect(f"file:{OPENCODE_DB}?mode=ro", uri=True)
        cur = con.cursor()
        if last_seen_id:
            cur.execute(
                "SELECT id, aggregate_id, type, data FROM event WHERE id > ? ORDER BY id ASC LIMIT 50;",
                (last_seen_id,)
            )
        else:
            cur.execute("SELECT id, aggregate_id, type, data FROM event ORDER BY id DESC LIMIT 1;")
        rows = cur.fetchall()
        con.close()

        for row in rows:
            evt_id, session_id, event_type, data_str = row
            last_seen_id = max(last_seen_id or evt_id, evt_id)
            if not data_str:
                continue
            try:
                data = json.loads(data_str)
            except Exception:
                continue

            # Assistant finished generation (pure talk/thinking OR tool-calling)
            if event_type == "message.updated.1":
                info = data.get("info", {})
                if info.get("role") == "assistant" and info.get("finish") == "stop" and "completed" in info.get("time", {}):
                    msg_id = info.get("id", evt_id)
                    if mark_and_check_step(session_id, msg_id, event_type="completed"):
                        cmd = [sys.executable, str(Path(__file__).resolve()), "--status", "completed"]
                        subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Permission requested (user assistance needed)
            elif event_type in ("permission.updated.1", "permission.updated"):
                status = data.get("status") or data.get("properties", {}).get("status")
                if status == "ask":
                    perm_id = data.get("id") or evt_id
                    if mark_and_check_step(session_id, perm_id, event_type="help"):
                        cmd = [
                            sys.executable,
                            str(Path(__file__).resolve()),
                            "--status", "help",
                            "--message", "OpenCode needs your permission to proceed!"
                        ]
                        subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    return last_seen_id

def run_watcher():
    brain_dir = Path.home() / ".gemini" / "antigravity-cli" / "brain"
    last_notified_step = {}

    # Initialize with current latest step_index for Antigravity
    if brain_dir.exists():
        for conv_path in brain_dir.glob("*/.system_generated/logs/transcript.jsonl"):
            if is_subagent_transcript(conv_path):
                continue
            conv_id = conv_path.parent.parent.parent.name
            data = get_last_json(conv_path)
            if data:
                last_notified_step[conv_id] = data.get("step_index", 0)

    # Initialize OpenCode last seen event
    last_opencode_event_id = get_latest_opencode_event_id()

    print("Taskforce watcher active. Monitoring active root sessions (Antigravity & OpenCode)...")
    env = os.environ.copy()
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"

    while True:
        try:
            time.sleep(0.5)

            # 1. Check OpenCode events (works for simple talk, thinking, and tool execution)
            if OPENCODE_DB.exists():
                last_opencode_event_id = check_opencode_events(last_opencode_event_id, env)

            # 2. Check Antigravity CLI events
            if brain_dir.exists():
                now = time.time()
                for conv_path in brain_dir.glob("*/.system_generated/logs/transcript.jsonl"):
                    # Ignore internal subagents completely
                    if is_subagent_transcript(conv_path):
                        continue

                    conv_id = conv_path.parent.parent.parent.name
                    try:
                        mtime = os.path.getmtime(conv_path)
                        if now - mtime > 300:  # Skip sessions idle for more than 5 minutes
                            continue

                        data = get_last_json(conv_path)
                        if not data:
                            continue

                        step_idx = data.get("step_index", 0)
                        last_seen = last_notified_step.get(conv_id, 0)
                        if step_idx <= last_seen:
                            continue

                        source = data.get("source")
                        msg_type = data.get("type")
                        status = data.get("status")

                        if source == "MODEL" and msg_type == "PLANNER_RESPONSE" and status == "DONE":
                            tool_calls = data.get("tool_calls", [])
                            if tool_calls:
                                for tc in tool_calls:
                                    if tc.get("name") == "ask_question":
                                        last_notified_step[conv_id] = step_idx
                                        if mark_and_check_step(conv_id, step_idx, event_type="help"):
                                            cmd = [sys.executable, str(Path(__file__).resolve()), "--status", "help"]
                                            subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                        break
                            else:
                                # Check if the parent agent has pending background tasks or subagents
                                if has_pending_work(conv_path):
                                    continue

                                # True completion! (Covers both tool execution tasks AND pure thinking/talk responses)
                                last_notified_step[conv_id] = step_idx
                                if mark_and_check_step(conv_id, step_idx, event_type="completed"):
                                    cmd = [sys.executable, str(Path(__file__).resolve()), "--status", "completed"]
                                    subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass
        except KeyboardInterrupt:
            break
        except Exception:
            time.sleep(1)

def main():
    parser = argparse.ArgumentParser(description="Taskforce Agent Desktop Notifier")
    parser.add_argument("--status", choices=["completed", "help"], default="completed", help="Event status")
    parser.add_argument("--message", type=str, default=None, help="Custom notification text")
    parser.add_argument("--position", choices=["bottom-right", "top-right", "bottom-left", "top-left", "center"], help="Set default screen position")
    parser.add_argument("--duration", type=int, help="Display time in milliseconds (e.g. 4000)")
    parser.add_argument("--volume", type=float, help="Signal volume (0.0 - 1.0)")
    parser.add_argument("--sound", choices=["on", "off"], help="Enable or disable audio ring")
    parser.add_argument("--drag", action="store_true", help="Launch interactive draggable mode to position anywhere")
    parser.add_argument("--test", action="store_true", help="Test notification popup")
    parser.add_argument("--bg", action="store_true", help="Run detached in background (non-blocking for hooks)")
    parser.add_argument("--hook-stop", action="store_true", help="Antigravity Stop lifecycle hook runner")
    parser.add_argument("--hook-tool", action="store_true", help="Antigravity PreToolUse lifecycle hook runner")
    parser.add_argument("--watch", action="store_true", help="Run background watcher for all active terminal sessions")
    parser.add_argument("--daemon", action="store_true", help="Spawn watcher detached in the background")
    parser.add_argument("--gui", "--settings", dest="gui", action="store_true", help="Open visual Settings UI")

    args = parser.parse_args()

    if args.gui:
        settings_script = Path(__file__).resolve().parent / "settings_gui.py"
        subprocess.Popen([sys.executable, str(settings_script)])
        return

    if args.daemon:
        cmd = [sys.executable, str(Path(__file__).resolve()), "--watch"]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        print("Taskforce background watcher started.")
        return

    if args.watch:
        run_watcher()
        return

    if args.hook_stop:
        handle_hook_stop()
        return

    if args.hook_tool:
        handle_hook_tool()
        return

    config = load_config()
    updated = False

    if args.position:
        config["position"] = args.position
        config["custom_x"] = None
        config["custom_y"] = None
        updated = True
        print(f"Position preset set to: {args.position}")

    if args.duration is not None:
        config["duration_ms"] = max(1000, min(30000, args.duration))
        updated = True
        print(f"Display duration set to: {config['duration_ms']}ms")

    if args.volume is not None:
        config["volume"] = max(0.0, min(1.0, args.volume))
        updated = True
        print(f"Volume set to: {int(config['volume'] * 100)}%")

    if args.sound is not None:
        config["sound_enabled"] = (args.sound == "on")
        updated = True
        print(f"Sound ring enabled: {config['sound_enabled']}")

    if updated:
        save_config(config)
        if not args.test and not args.drag:
            return

    if args.drag:
        print("Draggable mode: Click and drag the mascot anywhere on your screen. Release when placed.")
        show_popup(status="completed", message="Drag me anywhere on your screen!", config=config, drag_mode=True)
        return

    if args.bg:
        cmd = [sys.executable, str(Path(__file__).resolve()), "--status", args.status]
        if args.message:
            cmd.extend(["--message", args.message])
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    show_popup(status=args.status, message=args.message, config=config)

if __name__ == "__main__":
    main()

