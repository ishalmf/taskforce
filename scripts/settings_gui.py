#!/usr/bin/env python3
"""
Taskforce Settings Application
Modern, beginner-friendly desktop UI to customize pictures, audio chimes, backgrounds, and placement.
"""

import sys
import os
import json
import subprocess
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
BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = BASE_DIR / "public"
NOTIFIER_SCRIPT = BASE_DIR / "scripts" / "desktop_notifier.py"
ICON_PATH = BASE_DIR / "src-tauri" / "icons" / "icon.png"

DEFAULT_CONFIG = {
    "position": "bottom-right",
    "custom_x": None,
    "custom_y": None,
    "margin_x": 32,
    "margin_y": 48,
    "duration_ms": 4000,
    "sound_enabled": True,
    "volume": 0.8,
    "completed_gif": str(PUBLIC_DIR / "taskforce-mascot.gif"),
    "completed_sound": str(PUBLIC_DIR / "taskforce-chime.wav"),
    "help_gif": str(PUBLIC_DIR / "taskforce-help.gif"),
    "help_sound": str(PUBLIC_DIR / "taskforce-help.wav"),
    "card_background": "rgba(15, 23, 42, 0.94)",
    "border_completed": "#34d399",
    "border_help": "#fbbf24",
    "border_radius": 16,
}

THEME_PRESETS = {
    "Dark Slate Glass (Default)": {
        "card_background": "rgba(15, 23, 42, 0.94)",
        "border_completed": "#34d399",
        "border_help": "#fbbf24",
        "border_radius": 16,
    },
    "Obsidian Black": {
        "card_background": "rgba(5, 5, 5, 0.96)",
        "border_completed": "#10b981",
        "border_help": "#f59e0b",
        "border_radius": 12,
    },
    "Cyberpunk Neon": {
        "card_background": "rgba(24, 11, 40, 0.95)",
        "border_completed": "#ec4899",
        "border_help": "#a855f7",
        "border_radius": 18,
    },
    "Frosted Modern Light": {
        "card_background": "rgba(248, 250, 252, 0.96)",
        "border_completed": "#059669",
        "border_help": "#d97706",
        "border_radius": 20,
    },
}

def load_config():
    cfg = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                cfg.update(data)
        except Exception:
            pass
    return cfg

def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

class SettingsWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Taskforce Settings")
        self.set_default_size(620, 680)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.config = load_config()

        if ICON_PATH.exists():
            try:
                self.set_icon_from_file(str(ICON_PATH))
            except Exception:
                pass

        self.apply_theme()
        self.build_ui()

    def apply_theme(self):
        css_provider = Gtk.CssProvider()
        css = """
        window {
            background-color: #0f172a;
            color: #f1f5f9;
            font-family: system-ui, -apple-system, sans-serif;
        }
        headerbar {
            background: #1e293b;
            border-bottom: 1px solid #334155;
            color: #f1f5f9;
        }
        .section-box {
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
        }
        .section-title {
            font-weight: 700;
            font-size: 14px;
            color: #38bdf8;
            margin-bottom: 10px;
        }
        label {
            color: #e2e8f0;
            font-size: 13px;
        }
        .help-text {
            color: #94a3b8;
            font-size: 11px;
        }
        button.primary-btn {
            background-color: #10b981;
            color: #ffffff;
            font-weight: 600;
            border-radius: 8px;
            padding: 8px 18px;
            border: none;
        }
        button.primary-btn:hover {
            background-color: #059669;
        }
        button.action-btn {
            background-color: #334155;
            color: #f8fafc;
            border-radius: 6px;
            border: 1px solid #475569;
            padding: 5px 12px;
        }
        button.action-btn:hover {
            background-color: #475569;
        }
        scale slider {
            background-color: #38bdf8;
        }
        entry {
            background-color: #0f172a;
            color: #f8fafc;
            border: 1px solid #475569;
            border-radius: 6px;
            padding: 4px 8px;
        }
        combobox button {
            background-color: #0f172a;
            color: #f8fafc;
            border: 1px solid #475569;
            border-radius: 6px;
        }
        """
        css_provider.load_from_data(css.encode('utf-8'))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def build_ui(self):
        # Header bar
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("Taskforce Settings")
        header.set_subtitle("Customize pictures, sounds, and popup placement")
        self.set_titlebar(header)

        # Main scrollable container
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.add(scrolled)

        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        main_vbox.set_margin_top(16)
        main_vbox.set_margin_bottom(20)
        main_vbox.set_margin_start(20)
        main_vbox.set_margin_end(20)
        scrolled.add(main_vbox)

        # -----------------------------------------------------------------
        # SECTION 1: ANIMATED PICTURE / GIF SELECTION
        # -----------------------------------------------------------------
        sec_assets = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sec_assets.get_style_context().add_class("section-box")

        title1 = Gtk.Label(label="1. MASCOT PICTURE & ANIMATION", xalign=0)
        title1.get_style_context().add_class("section-title")
        sec_assets.pack_start(title1, False, False, 0)

        # Task complete GIF row
        grid1 = Gtk.Grid(column_spacing=12, row_spacing=10)
        sec_assets.pack_start(grid1, False, False, 0)

        lbl_comp_gif = Gtk.Label(label="Task Complete Mascot:", xalign=0)
        grid1.attach(lbl_comp_gif, 0, 0, 1, 1)

        self.img_comp_preview = Gtk.Image()
        self.update_image_preview(self.img_comp_preview, self.config.get("completed_gif"))
        grid1.attach(self.img_comp_preview, 1, 0, 1, 1)

        self.entry_comp_gif = Gtk.Entry()
        self.entry_comp_gif.set_text(self.config.get("completed_gif", ""))
        self.entry_comp_gif.set_hexpand(True)
        grid1.attach(self.entry_comp_gif, 2, 0, 1, 1)

        btn_browse_comp_gif = Gtk.Button(label="Browse...")
        btn_browse_comp_gif.get_style_context().add_class("action-btn")
        btn_browse_comp_gif.connect("clicked", self.on_browse_file, self.entry_comp_gif, "image", self.img_comp_preview)
        grid1.attach(btn_browse_comp_gif, 3, 0, 1, 1)

        btn_reset_comp_gif = Gtk.Button(label="Default")
        btn_reset_comp_gif.get_style_context().add_class("action-btn")
        btn_reset_comp_gif.connect("clicked", lambda w: self.reset_field(self.entry_comp_gif, str(PUBLIC_DIR / "taskforce-mascot.gif"), self.img_comp_preview))
        grid1.attach(btn_reset_comp_gif, 4, 0, 1, 1)

        # Help GIF row
        lbl_help_gif = Gtk.Label(label="Need Help / Question:", xalign=0)
        grid1.attach(lbl_help_gif, 0, 1, 1, 1)

        self.img_help_preview = Gtk.Image()
        self.update_image_preview(self.img_help_preview, self.config.get("help_gif"))
        grid1.attach(self.img_help_preview, 1, 1, 1, 1)

        self.entry_help_gif = Gtk.Entry()
        self.entry_help_gif.set_text(self.config.get("help_gif", ""))
        self.entry_help_gif.set_hexpand(True)
        grid1.attach(self.entry_help_gif, 2, 1, 1, 1)

        btn_browse_help_gif = Gtk.Button(label="Browse...")
        btn_browse_help_gif.get_style_context().add_class("action-btn")
        btn_browse_help_gif.connect("clicked", self.on_browse_file, self.entry_help_gif, "image", self.img_help_preview)
        grid1.attach(btn_browse_help_gif, 3, 1, 1, 1)

        btn_reset_help_gif = Gtk.Button(label="Default")
        btn_reset_help_gif.get_style_context().add_class("action-btn")
        btn_reset_help_gif.connect("clicked", lambda w: self.reset_field(self.entry_help_gif, str(PUBLIC_DIR / "taskforce-help.gif"), self.img_help_preview))
        grid1.attach(btn_reset_help_gif, 4, 1, 1, 1)

        hint1 = Gtk.Label(label="Supports animated GIF, PNG, JPG, WebP, SVG. Best size: 64x64 to 128x128.", xalign=0)
        hint1.get_style_context().add_class("help-text")
        sec_assets.pack_start(hint1, False, False, 0)
        main_vbox.pack_start(sec_assets, False, False, 0)

        # -----------------------------------------------------------------
        # SECTION 2: AUDIO CHIME & VOLUME
        # -----------------------------------------------------------------
        sec_sound = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sec_sound.get_style_context().add_class("section-box")

        title2 = Gtk.Label(label="2. SOUND RING NOTIFICATION", xalign=0)
        title2.get_style_context().add_class("section-title")
        sec_sound.pack_start(title2, False, False, 0)

        # Sound toggle switch
        switch_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl_sound_toggle = Gtk.Label(label="Enable Sound Notification:", xalign=0)
        self.switch_sound = Gtk.Switch()
        self.switch_sound.set_active(self.config.get("sound_enabled", True))
        switch_box.pack_start(lbl_sound_toggle, False, False, 0)
        switch_box.pack_start(self.switch_sound, False, False, 0)
        sec_sound.pack_start(switch_box, False, False, 0)

        # Grid for sound files
        grid2 = Gtk.Grid(column_spacing=12, row_spacing=10)
        sec_sound.pack_start(grid2, False, False, 0)

        # Complete Sound
        lbl_comp_sound = Gtk.Label(label="Complete Chime:", xalign=0)
        grid2.attach(lbl_comp_sound, 0, 0, 1, 1)

        self.entry_comp_sound = Gtk.Entry()
        self.entry_comp_sound.set_text(self.config.get("completed_sound", ""))
        self.entry_comp_sound.set_hexpand(True)
        grid2.attach(self.entry_comp_sound, 1, 0, 1, 1)

        btn_browse_comp_sound = Gtk.Button(label="Browse...")
        btn_browse_comp_sound.get_style_context().add_class("action-btn")
        btn_browse_comp_sound.connect("clicked", self.on_browse_file, self.entry_comp_sound, "audio")
        grid2.attach(btn_browse_comp_sound, 2, 0, 1, 1)

        btn_play_comp_sound = Gtk.Button(label="▶ Play")
        btn_play_comp_sound.get_style_context().add_class("action-btn")
        btn_play_comp_sound.connect("clicked", lambda w: self.play_preview_sound(self.entry_comp_sound.get_text()))
        grid2.attach(btn_play_comp_sound, 3, 0, 1, 1)

        # Help Sound
        lbl_help_sound = Gtk.Label(label="Need Help Chime:", xalign=0)
        grid2.attach(lbl_help_sound, 0, 1, 1, 1)

        self.entry_help_sound = Gtk.Entry()
        self.entry_help_sound.set_text(self.config.get("help_sound", ""))
        self.entry_help_sound.set_hexpand(True)
        grid2.attach(self.entry_help_sound, 1, 1, 1, 1)

        btn_browse_help_sound = Gtk.Button(label="Browse...")
        btn_browse_help_sound.get_style_context().add_class("action-btn")
        btn_browse_help_sound.connect("clicked", self.on_browse_file, self.entry_help_sound, "audio")
        grid2.attach(btn_browse_help_sound, 2, 1, 1, 1)

        btn_play_help_sound = Gtk.Button(label="▶ Play")
        btn_play_help_sound.get_style_context().add_class("action-btn")
        btn_play_help_sound.connect("clicked", lambda w: self.play_preview_sound(self.entry_help_sound.get_text()))
        grid2.attach(btn_play_help_sound, 3, 1, 1, 1)

        # Volume slider
        vol_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl_vol = Gtk.Label(label="Volume:", xalign=0)
        self.scale_volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
        self.scale_volume.set_value(int(self.config.get("volume", 0.8) * 100))
        self.scale_volume.set_hexpand(True)
        self.lbl_vol_val = Gtk.Label(label=f"{int(self.config.get('volume', 0.8) * 100)}%")
        self.scale_volume.connect("value-changed", lambda w: self.lbl_vol_val.set_text(f"{int(w.get_value())}%"))

        vol_box.pack_start(lbl_vol, False, False, 0)
        vol_box.pack_start(self.scale_volume, True, True, 0)
        vol_box.pack_start(self.lbl_vol_val, False, False, 0)
        sec_sound.pack_start(vol_box, False, False, 0)

        hint2 = Gtk.Label(label="Supports all audio formats: WAV, MP3, OGG, M4A, FLAC.", xalign=0)
        hint2.get_style_context().add_class("help-text")
        sec_sound.pack_start(hint2, False, False, 0)
        main_vbox.pack_start(sec_sound, False, False, 0)

        # -----------------------------------------------------------------
        # SECTION 3: SCREEN POSITION & DURATION
        # -----------------------------------------------------------------
        sec_pos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sec_pos.get_style_context().add_class("section-box")

        title3 = Gtk.Label(label="3. SCREEN POSITION & DISPLAY TIME", xalign=0)
        title3.get_style_context().add_class("section-title")
        sec_pos.pack_start(title3, False, False, 0)

        pos_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl_pos = Gtk.Label(label="Position Preset:", xalign=0)
        self.combo_pos = Gtk.ComboBoxText()
        presets = ["bottom-right", "top-right", "bottom-left", "top-left", "center", "custom"]
        for p in presets:
            self.combo_pos.append(p, p.replace("-", " ").title())
        cur_pos = self.config.get("position", "bottom-right")
        self.combo_pos.set_active_id(cur_pos if cur_pos in presets else "bottom-right")

        btn_drag = Gtk.Button(label="🖐 Drag Anywhere on Screen")
        btn_drag.get_style_context().add_class("action-btn")
        btn_drag.connect("clicked", self.on_start_drag)

        pos_box.pack_start(lbl_pos, False, False, 0)
        pos_box.pack_start(self.combo_pos, False, False, 0)
        pos_box.pack_start(btn_drag, False, False, 0)
        sec_pos.pack_start(pos_box, False, False, 0)

        # Duration slider
        dur_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl_dur = Gtk.Label(label="Display Time:", xalign=0)
        self.scale_duration = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1.5, 10.0, 0.5)
        cur_dur = self.config.get("duration_ms", 4000) / 1000.0
        self.scale_duration.set_value(cur_dur)
        self.scale_duration.set_hexpand(True)
        self.lbl_dur_val = Gtk.Label(label=f"{cur_dur:.1f} sec")
        self.scale_duration.connect("value-changed", lambda w: self.lbl_dur_val.set_text(f"{w.get_value():.1f} sec"))

        dur_box.pack_start(lbl_dur, False, False, 0)
        dur_box.pack_start(self.scale_duration, True, True, 0)
        dur_box.pack_start(self.lbl_dur_val, False, False, 0)
        sec_pos.pack_start(dur_box, False, False, 0)
        main_vbox.pack_start(sec_pos, False, False, 0)

        # -----------------------------------------------------------------
        # SECTION 4: BACKGROUND & THEME
        # -----------------------------------------------------------------
        sec_theme = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sec_theme.get_style_context().add_class("section-box")

        title4 = Gtk.Label(label="4. CARD BACKGROUND & THEME", xalign=0)
        title4.get_style_context().add_class("section-title")
        sec_theme.pack_start(title4, False, False, 0)

        theme_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl_theme = Gtk.Label(label="Color Theme Preset:", xalign=0)
        self.combo_theme = Gtk.ComboBoxText()
        for tname in THEME_PRESETS.keys():
            self.combo_theme.append(tname, tname)
        self.combo_theme.set_active(0)
        self.combo_theme.connect("changed", self.on_theme_preset_changed)

        theme_box.pack_start(lbl_theme, False, False, 0)
        theme_box.pack_start(self.combo_theme, True, True, 0)
        sec_theme.pack_start(theme_box, False, False, 0)

        # Custom styling entries
        grid4 = Gtk.Grid(column_spacing=12, row_spacing=8)
        sec_theme.pack_start(grid4, False, False, 0)

        grid4.attach(Gtk.Label(label="Background RGBA:", xalign=0), 0, 0, 1, 1)
        self.entry_bg = Gtk.Entry()
        self.entry_bg.set_text(self.config.get("card_background", "rgba(15, 23, 42, 0.94)"))
        self.entry_bg.set_hexpand(True)
        grid4.attach(self.entry_bg, 1, 0, 1, 1)

        grid4.attach(Gtk.Label(label="Border (Complete):", xalign=0), 0, 1, 1, 1)
        self.entry_border_comp = Gtk.Entry()
        self.entry_border_comp.set_text(self.config.get("border_completed", "#34d399"))
        self.entry_border_comp.set_hexpand(True)
        grid4.attach(self.entry_border_comp, 1, 1, 1, 1)

        grid4.attach(Gtk.Label(label="Border (Need Help):", xalign=0), 0, 2, 1, 1)
        self.entry_border_help = Gtk.Entry()
        self.entry_border_help.set_text(self.config.get("border_help", "#fbbf24"))
        self.entry_border_help.set_hexpand(True)
        grid4.attach(self.entry_border_help, 1, 2, 1, 1)

        main_vbox.pack_start(sec_theme, False, False, 0)

        # -----------------------------------------------------------------
        # FOOTER ACTION BAR
        # -----------------------------------------------------------------
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        footer.set_margin_top(10)

        self.lbl_status = Gtk.Label(label="Click 'Save Settings' to apply.", xalign=0)
        self.lbl_status.set_hexpand(True)
        footer.pack_start(self.lbl_status, True, True, 0)

        btn_test = Gtk.Button(label="⚡ Test Notification")
        btn_test.get_style_context().add_class("action-btn")
        btn_test.connect("clicked", self.on_test_popup)
        footer.pack_start(btn_test, False, False, 0)

        btn_save = Gtk.Button(label="✔ Save Settings")
        btn_save.get_style_context().add_class("primary-btn")
        btn_save.connect("clicked", self.on_save)
        footer.pack_start(btn_save, False, False, 0)

        main_vbox.pack_start(footer, False, False, 0)
        self.disable_scroll_on_controls(main_vbox)

    def _on_control_scroll(self, widget, event):
        widget.stop_emission_by_name("scroll-event")
        return False

    def disable_scroll_on_controls(self, container):
        if isinstance(container, (Gtk.Scale, Gtk.Range, Gtk.ComboBox, Gtk.SpinButton)):
            container.connect("scroll-event", self._on_control_scroll)
        if isinstance(container, Gtk.Container):
            for child in container.get_children():
                self.disable_scroll_on_controls(child)

    def update_image_preview(self, img_widget, path):
        if path and os.path.exists(path):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 36, 36, True)
                img_widget.set_from_pixbuf(pixbuf)
                return
            except Exception:
                pass
        img_widget.set_from_icon_name("image-x-generic", Gtk.IconSize.LARGE_TOOLBAR)

    def reset_field(self, entry_widget, default_val, preview_widget=None):
        entry_widget.set_text(default_val)
        if preview_widget:
            self.update_image_preview(preview_widget, default_val)

    def on_browse_file(self, button, entry_widget, file_type, preview_widget=None):
        action_title = "Select Notification Image / GIF" if file_type == "image" else "Select Notification Sound Audio"
        dialog = Gtk.FileChooserDialog(
            title=action_title,
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )

        filter_any = Gtk.FileFilter()
        if file_type == "image":
            filter_any.set_name("Images and GIFs (*.gif, *.png, *.jpg, *.webp, *.svg)")
            filter_any.add_mime_type("image/gif")
            filter_any.add_mime_type("image/png")
            filter_any.add_mime_type("image/jpeg")
            filter_any.add_mime_type("image/webp")
            filter_any.add_mime_type("image/svg+xml")
            filter_any.add_pattern("*.gif")
            filter_any.add_pattern("*.png")
            filter_any.add_pattern("*.jpg")
            filter_any.add_pattern("*.webp")
        else:
            filter_any.set_name("Audio Files (*.wav, *.mp3, *.ogg, *.m4a, *.flac)")
            filter_any.add_mime_type("audio/x-wav")
            filter_any.add_mime_type("audio/mpeg")
            filter_any.add_mime_type("audio/ogg")
            filter_any.add_mime_type("audio/flac")
            filter_any.add_pattern("*.wav")
            filter_any.add_pattern("*.mp3")
            filter_any.add_pattern("*.ogg")
            filter_any.add_pattern("*.m4a")
            filter_any.add_pattern("*.flac")

        dialog.add_filter(filter_any)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            chosen = dialog.get_filename()
            entry_widget.set_text(chosen)
            if preview_widget:
                self.update_image_preview(preview_widget, chosen)
        dialog.destroy()

    def on_theme_preset_changed(self, combo):
        tname = combo.get_active_text()
        if tname in THEME_PRESETS:
            preset = THEME_PRESETS[tname]
            self.entry_bg.set_text(preset["card_background"])
            self.entry_border_comp.set_text(preset["border_completed"])
            self.entry_border_help.set_text(preset["border_help"])

    def play_preview_sound(self, sound_path):
        if not sound_path or not os.path.exists(sound_path):
            self.lbl_status.set_text("File does not exist!")
            return
        vol = self.scale_volume.get_value() / 100.0
        try:
            cmd = ["mpv", "--no-video", f"--volume={int(vol * 100)}", sound_path]
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            pass
        try:
            subprocess.Popen(["canberra-gtk-play", "--file=" + sound_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def on_start_drag(self, button):
        p = subprocess.Popen([sys.executable, str(NOTIFIER_SCRIPT), "--drag"])
        import threading
        def wait_and_update():
            p.wait()
            self.config = load_config()
            x = self.config.get("custom_x")
            y = self.config.get("custom_y")
            def update_ui():
                self.combo_pos.set_active_id("custom")
                if x is not None and y is not None:
                    self.lbl_status.set_markup(f'<span color="#34d399">✔ Mascot position saved at ({x}, {y})!</span>')
            GLib.idle_add(update_ui)
        threading.Thread(target=wait_and_update, daemon=True).start()

    def collect_config(self):
        cfg = self.config.copy()
        cfg["completed_gif"] = self.entry_comp_gif.get_text().strip()
        cfg["help_gif"] = self.entry_help_gif.get_text().strip()
        cfg["completed_sound"] = self.entry_comp_sound.get_text().strip()
        cfg["help_sound"] = self.entry_help_sound.get_text().strip()
        cfg["sound_enabled"] = self.switch_sound.get_active()
        cfg["volume"] = round(self.scale_volume.get_value() / 100.0, 2)
        cfg["duration_ms"] = int(self.scale_duration.get_value() * 1000)
        chosen_pos = self.combo_pos.get_active_id() or "bottom-right"
        cfg["position"] = chosen_pos
        if chosen_pos != "custom":
            cfg["custom_x"] = None
            cfg["custom_y"] = None
        else:
            cfg["custom_x"] = self.config.get("custom_x")
            cfg["custom_y"] = self.config.get("custom_y")
        cfg["card_background"] = self.entry_bg.get_text().strip()
        cfg["border_completed"] = self.entry_border_comp.get_text().strip()
        cfg["border_help"] = self.entry_border_help.get_text().strip()
        return cfg

    def on_save(self, button):
        self.config = self.collect_config()
        save_config(self.config)
        self.lbl_status.set_markup('<span color="#34d399">✔ Settings saved successfully!</span>')

    def on_test_popup(self, button):
        # Save first so the test uses current inputs
        self.config = self.collect_config()
        save_config(self.config)
        subprocess.Popen([sys.executable, str(NOTIFIER_SCRIPT), "--status", "completed"])
        self.lbl_status.set_text("Testing notification popup on screen...")

def main():
    app = SettingsWindow()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
