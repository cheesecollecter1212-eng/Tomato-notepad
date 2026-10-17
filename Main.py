import os
import json
import time
import math
import random
import wave
import struct
import tempfile
import threading
import subprocess
import sys
import re
import keyword
import html
import calendar
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk


# ==================================================
# APP ICONS
# ==================================================

def resource_path(filename):
    """Find an asset both when running from source and from a PyInstaller EXE."""
    bundle_dir = getattr(sys, "_MEIPASS", None)
    candidates = []
    if bundle_dir:
        candidates.append(os.path.join(bundle_dir, filename))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename))
    candidates.append(os.path.join(os.getcwd(), filename))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def apply_tomato_icon(window):
    """Apply tomato.ico to the Windows title/taskbar and tomato.png to the window."""
    ico_path = resource_path("tomato.ico")
    png_path = resource_path("tomato.png")

    if ico_path:
        try:
            window.iconbitmap(default=ico_path)
        except (tk.TclError, AttributeError):
            pass

    if png_path:
        try:
            icon_image = tk.PhotoImage(file=png_path)
            window.iconphoto(True, icon_image)
            # Keep a reference so Tk does not garbage-collect the image.
            window._tomato_icon_image = icon_image
        except (tk.TclError, AttributeError):
            pass


# ==================================================
# THEME
# ==================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Tomato-inspired modern dark theme
BG = "#181716"
SIDEBAR = "#201C1A"
CARD = "#272321"
CARD_HOVER = "#342925"
BLUE = "#F0523A"          # Primary tomato-red accent (kept name to avoid changing callbacks)
BLUE_HOVER = "#D9412B"
TEXT = "#FFF7F2"
MUTED = "#B8A9A1"
BORDER = "#3D302B"
RED = "#FF6255"
TOMATO = "#F0523A"
TOMATO_DARK = "#4A211D"



# ==================================================
# NOTES STORAGE
# ==================================================

class TomatoNotepad:
    def __init__(self, filename="notes.json"):
        self.filename = filename
        self.notes = self.load_notes()

    def load_notes(self):
        if not os.path.exists(self.filename):
            return {}

        try:
            with open(self.filename, "r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, dict):
                return {}

            # Upgrade notes saved by the earlier version.
            for title, note in list(data.items()):
                if isinstance(note, str):
                    data[title] = {
                        "content": note,
                        "pinned": False,
                        "trashed": False,
                        "folder": "",
                        "modified": 0
                    }
                elif isinstance(note, dict):
                    note.setdefault("content", "")
                    note.setdefault("pinned", False)
                    note.setdefault("trashed", False)
                    note.setdefault("folder", "")
                    note.setdefault("modified", 0)
                else:
                    data[title] = {
                        "content": "",
                        "pinned": False,
                        "trashed": False,
                        "folder": "",
                        "modified": 0
                    }

            return data

        except (OSError, json.JSONDecodeError) as error:
            messagebox.showwarning(
                "Tomato Notepad",
                f"Could not load notes.json:\n{error}"
            )
            return {}

    def save_notes(self):
        with open(self.filename, "w", encoding="utf-8") as file:
            json.dump(self.notes, file, indent=4, ensure_ascii=False)

    def add_note(self, title, content=""):
        if title in self.notes:
            return False

        self.notes[title] = {
            "content": content,
            "pinned": False,
            "trashed": False,
            "folder": "",
            "modified": time.time()
        }
        self.save_notes()
        return True

    def update_note(self, title, content):
        if title not in self.notes:
            return False

        self.notes[title]["content"] = content
        self.notes[title]["modified"] = time.time()
        self.save_notes()
        return True

    def delete_note(self, title):
        if title not in self.notes:
            return False

        del self.notes[title]
        self.save_notes()
        return True




# ==================================================
# TOMATO SPLASH SCREEN + OPTIONAL MUSIC
# ==================================================

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(APP_DIR, "tomato_settings.json")
MUSIC_DIR = os.path.join(APP_DIR, "MUSIC")

STYLE_PALETTES = {
    "Tomato":  {"accent": "#F0523A", "hover": "#D9412B", "dark": "#4A211D"},
    "Ocean":   {"accent": "#3298D4", "hover": "#2179AD", "dark": "#173B52"},
    "Forest":  {"accent": "#42A66A", "hover": "#2E8752", "dark": "#1D422E"},
    "Lavender":{"accent": "#9B83E8", "hover": "#7E65CA", "dark": "#352A54"},
    "Rose":    {"accent": "#E45D8B", "hover": "#C94773", "dark": "#51253A"},
}

def load_app_settings():
    """Load persistent app preferences."""
    defaults = {"music_enabled": True, "style": "Tomato", "selected_song": "Random", "volume": 65, "visualizer_enabled": False, "festive_enabled": True}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as file:
            settings = json.load(file)
        if not isinstance(settings, dict):
            return defaults
        return {
            "music_enabled": bool(settings.get("music_enabled", True)),
            "style": settings.get("style", "Tomato")
            if settings.get("style", "Tomato") in STYLE_PALETTES else "Tomato",
            "selected_song": str(settings.get("selected_song", "Random")),
            "volume": max(0, min(100, int(settings.get("volume", 65)))),
            "visualizer_enabled": bool(settings.get("visualizer_enabled", False)),
            "festive_enabled": bool(settings.get("festive_enabled", True)),
        }
    except (OSError, json.JSONDecodeError, AttributeError):
        return defaults

def save_app_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as file:
            json.dump(settings, file, indent=4)
    except OSError:
        pass

class MusicPlayer:
    """Optional MP3/WAV player. Tracks are selected randomly without immediate repeats."""
    def __init__(self):
        self.available = False
        self.playing = False
        self.files = []
        self.current_file = None
        self._pygame = None
        self._after_id = None
        self.volume = 0.65
        self.selected_song = "Random"
        os.makedirs(MUSIC_DIR, exist_ok=True)
        self.refresh_files()

    def refresh_files(self):
        theme_path = os.path.join(APP_DIR, "tomato_notepad_theme.wav")
        try:
            playlist = [os.path.join(MUSIC_DIR, name) for name in os.listdir(MUSIC_DIR)
                        if os.path.isfile(os.path.join(MUSIC_DIR, name))
                        and os.path.splitext(name)[1].lower() in (".mp3", ".wav")]
        except OSError:
            playlist = []
        self.files = ([theme_path] if os.path.isfile(theme_path) else []) + [
            track for track in playlist if os.path.abspath(track) != os.path.abspath(theme_path)]
        self.files.sort(key=lambda path: (os.path.basename(path).lower() == "tomato_notepad_theme.wav", os.path.basename(path).lower()))

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, float(volume)))
        if self._pygame:
            try: self._pygame.mixer.music.set_volume(self.volume)
            except Exception: pass

    def _choose_track(self, requested=None):
        self.refresh_files()
        if requested and requested != "Random":
            match = next((p for p in self.files if os.path.basename(p) == requested), None)
            if match:
                return match
        choices = [p for p in self.files if p != self.current_file]
        if not choices:
            choices = self.files[:]
        return random.choice(choices) if choices else None

    def start(self, root=None, requested=None):
        track = self._choose_track(requested if requested is not None else self.selected_song)
        if not track:
            self.playing = False
            return False, "Add .mp3 or .wav files to the MUSIC folder."
        try:
            import pygame
            if self._pygame is None:
                pygame.mixer.init()
                self._pygame = pygame
            self._pygame.mixer.music.stop()
            self._pygame.mixer.music.load(track)
            self._pygame.mixer.music.set_volume(self.volume)
            self._pygame.mixer.music.play()
            self.current_file = track
            self.playing = True
            self.available = True
            if root is not None:
                self._schedule_next(root)
            return True, os.path.basename(track)
        except Exception as error:
            self.playing = False
            return False, f"Could not play audio. Install pygame (pip install pygame). Details: {error}"

    def skip(self, root=None):
        return self.start(root, "Random")

    def _schedule_next(self, root):
        if self._after_id:
            try: root.after_cancel(self._after_id)
            except tk.TclError: pass
        self._after_id = root.after(700, lambda: self._check_next(root))

    def _check_next(self, root):
        self._after_id = None
        if not self.playing: return
        try:
            if self._pygame and not self._pygame.mixer.music.get_busy():
                ok, _ = self.start(root, "Random")
                if not ok: self.playing = False; return
            self._schedule_next(root)
        except Exception:
            self.playing = False

    def stop(self):
        self.playing = False
        if self._pygame:
            try: self._pygame.mixer.music.stop()
            except Exception: pass

def create_tomato_tune():
    """Create a tiny, gentle loop using only Python's standard library."""
    path = os.path.join(APP_DIR, "tomato_notepad_theme.wav")
    if os.path.exists(path):
        return path

    sample_rate = 22050
    # A soft, original four-bar chiptune-style melody.
    notes = [
        (392.00, 0.22), (493.88, 0.22), (587.33, 0.30), (493.88, 0.22),
        (440.00, 0.22), (523.25, 0.22), (659.25, 0.30), (523.25, 0.22),
        (392.00, 0.22), (493.88, 0.22), (587.33, 0.22), (659.25, 0.30),
        (587.33, 0.22), (493.88, 0.22), (440.00, 0.38), (0, 0.18),
    ]
    frames = []
    for frequency, duration in notes:
        count = int(sample_rate * duration)
        for i in range(count):
            t = i / sample_rate
            # Soft attack/release avoids clicks between notes.
            edge = min(1.0, i / 500, (count - i) / 700)
            if frequency:
                fundamental = math.sin(2 * math.pi * frequency * t)
                overtone = 0.22 * math.sin(2 * math.pi * frequency * 2 * t)
                sample = int(4800 * max(0, edge) * (fundamental + overtone))
            else:
                sample = 0
            frames.append(struct.pack("<h", sample))

    with wave.open(path, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"".join(frames))
    return path


# Ensure the loading/theme sound exists beside the app, then make it the first track.
try:
    create_tomato_tune()
except (OSError, wave.Error):
    pass
MUSIC_PLAYER = MusicPlayer()


class TomatoSplash:
    """Animated tomato welcome screen with a saved music preference."""

    def __init__(self, root, on_complete):
        self.root = root
        self.on_complete = on_complete
        self.settings = load_app_settings()
        self.music_enabled = self.settings["music_enabled"]
        self.closed = False
        self.started_at = time.monotonic()
        self.animation_started = time.monotonic()
        self.animation_duration = 1.35
        self.animation_kind = random.choice(["bounce", "float", "wiggle", "pop"])
        self.base_x = 250
        self.base_y = 170
        self.root.withdraw()

        self.window = ctk.CTkToplevel(root)
        self.window.title("Tomato Notepad")
        apply_tomato_icon(self.window)
        self.window.geometry("500x410")
        self.window.resizable(False, False)
        self.window.configure(fg_color="#181716")
        self.window.protocol("WM_DELETE_WINDOW", self.finish)

        # Center splash on screen.
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 500) // 2
        y = (self.window.winfo_screenheight() - 410) // 2
        self.window.geometry(f"500x410+{x}+{y}")

        self.canvas = tk.Canvas(
            self.window, width=500, height=255,
            bg="#181716", highlightthickness=0
        )
        self.canvas.pack(pady=(18, 0))

        self.draw_tomato(250, 126, 1.0, 0.0)

        ctk.CTkLabel(
            self.window, text="Tomato Notepad",
            font=("Segoe UI", 25, "bold"), text_color="#FFF7F2"
        ).pack(pady=(0, 3))

        ctk.CTkLabel(
            self.window, text="A little space for your thoughts.",
            font=("Segoe UI", 12), text_color="#B8A9A1"
        ).pack()

        controls = ctk.CTkFrame(self.window, fg_color="transparent")
        controls.pack(fill="x", padx=26, pady=(18, 0))

        self.music_button = ctk.CTkButton(
            controls,
            text=self.music_label(),
            width=145, height=32,
            corner_radius=9,
            fg_color="#342925", hover_color="#4A342D",
            text_color="#FFF7F2",
            font=("Segoe UI", 11),
            command=self.toggle_music
        )
        self.music_button.pack(side="left")

        self.progress = ctk.CTkProgressBar(
            controls, width=190, height=5,
            fg_color="#3D302B", progress_color="#F0523A"
        )
        self.progress.pack(side="right", padx=(10, 0), pady=13)
        self.progress.set(0)

        self.start_music()
        self.animate()

        # Keep the splash brief but give the animation time to be seen.
        self.window.after(3200, self.finish)

    def music_label(self):
        return "♫  Music: On" if self.music_enabled else "♫  Music: Off"

    def toggle_music(self):
        self.music_enabled = not self.music_enabled
        self.settings["music_enabled"] = self.music_enabled
        save_app_settings(self.settings)
        self.music_button.configure(text=self.music_label())
        if self.music_enabled:
            self.start_music()
        else:
            self.stop_music()

    def start_music(self):
        if not self.music_enabled:
            return
        # The splash screen always uses the dedicated app theme tune when available.
        ok, _message = MUSIC_PLAYER.start(self.root, "tomato_notepad_theme.wav")

    def stop_music(self):
        MUSIC_PLAYER.stop()

    def draw_tomato(self, x, y, scale, tilt):
        self.canvas.delete("tomato")
        # Soft shadow.
        self.canvas.create_oval(
            x - 68 * scale, y + 55 * scale,
            x + 68 * scale, y + 75 * scale,
            fill="#30211D", outline="", tags="tomato"
        )
        # Tomato body.
        self.canvas.create_oval(
            x - 63 * scale, y - 48 * scale,
            x + 63 * scale, y + 62 * scale,
            fill="#F0523A", outline="#FF806B",
            width=2, tags="tomato"
        )
        # Gentle highlight.
        self.canvas.create_oval(
            x - 39 * scale, y - 25 * scale,
            x - 15 * scale, y + 6 * scale,
            fill="#FF8A72", outline="", tags="tomato"
        )
        # Stem and leaves.
        leaf_points = [
            x, y - 42 * scale,
               x - 17 * scale, y - 63 * scale,
               x - 5 * scale, y - 59 * scale,
               x + 1 * scale, y - 73 * scale,
               x + 9 * scale, y - 57 * scale,
               x + 27 * scale, y - 62 * scale,
               x + 15 * scale, y - 45 * scale,
               x + 3 * scale, y - 42 * scale,
               ]
        self.canvas.create_polygon(
            leaf_points, fill="#6DBB62", outline="#8BD47B",
            smooth=True, tags="tomato"
        )
        self.canvas.create_line(
            x, y - 46 * scale, x + 2 * scale, y - 59 * scale,
            fill="#377D3B", width=3, tags="tomato"
        )
        # Tiny decorative sparkles.
        for sx, sy, radius in [(x - 91, y - 25, 4), (x + 88, y - 8, 3),
                               (x + 74, y - 59, 2)]:
            self.canvas.create_text(
                sx, sy, text="✦", fill="#FFB19C",
                font=("Segoe UI", int(max(8, radius * 3))),
                tags="tomato"
            )

    def animate(self):
        if self.closed or not self.window.winfo_exists():
            return

        now = time.monotonic()
        elapsed = now - self.animation_started
        progress = min(1.0, elapsed / self.animation_duration)
        # Smoothstep easing makes each movement feel tweened.
        eased = progress * progress * (3 - 2 * progress)

        if self.animation_kind == "bounce":
            offset = -42 * math.sin(math.pi * eased)
            scale = 1.0 + 0.08 * math.sin(math.pi * eased)
            tilt = 0
        elif self.animation_kind == "float":
            offset = -17 * math.sin(eased * math.pi)
            scale = 1.0 + 0.025 * math.sin(eased * math.pi)
            tilt = 0
        elif self.animation_kind == "wiggle":
            offset = 0
            scale = 1.0
            tilt = math.sin(eased * math.pi * 4) * 0.12
        else:  # pop
            offset = 0
            scale = 0.72 + 0.28 * eased
            tilt = 0

        sway = math.sin(eased * math.pi * 4) * 10 if self.animation_kind == "wiggle" else 0
        x = 250 + math.sin(now * 1.2) * 7 + sway
        y = 126 + offset
        self.draw_tomato(x, y, scale, tilt)
        self.progress.set(min(1.0, (now - self.started_at) / 3.2))

        if progress >= 1.0:
            self.animation_kind = random.choice(
                ["bounce", "float", "wiggle", "pop"]
            )
            self.animation_started = now
            self.animation_duration = random.uniform(0.85, 1.65)

        self.window.after(30, self.animate)

    def finish(self):
        if self.closed:
            return
        self.closed = True
        self.stop_music()
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        self.root.deiconify()
        self.root.after(10, self.on_complete)


# ==================================================
# APPLICATION
# ==================================================

class TomatoNotepadGUI:
    def __init__(self, root):
        self.root = root
        self.settings = load_app_settings()
        self.apply_palette_values(self.settings.get("style", "Tomato"))
        self.root.title("Tomato Notepad")
        apply_tomato_icon(self.root)
        self.root.geometry("1250x780")
        self.root.minsize(900, 580)
        self.root.configure(fg_color=BG)

        self.notepad = TomatoNotepad()
        self.current_title = None
        self.current_view = "All Notes"
        self.search_var = tk.StringVar()
        self.loading_editor = False
        self.dirty = False
        self.visualizer_phase = 0.0
        self.festive_particle_phase = 0.0
        self.code_mode = False
        self.run_process = None
        self._run_output_window = None
        self._find_dialog = None
        MUSIC_PLAYER.set_volume(self.settings.get("volume", 65) / 100)
        MUSIC_PLAYER.selected_song = self.settings.get("selected_song", "Random")

        self.build_layout()
        self.refresh_notes()
        self.apply_festive_theme()
        self.root.after(120, self.animate_visualizer)
        self.root.after(900, self.animate_festive)
        self.new_note()
        if self.settings.get("music_enabled", True):
            MUSIC_PLAYER.start(self.root)

        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

    # ------------------------------------------------
    # MAIN LAYOUT
    # ------------------------------------------------

    def build_layout(self):
        self.main = ctk.CTkFrame(
            self.root, fg_color=BG, corner_radius=0
        )
        self.main.pack(fill="both", expand=True)

        self.main.grid_columnconfigure(0, weight=0, minsize=190)
        self.main.grid_columnconfigure(1, weight=0, minsize=250)
        self.main.grid_columnconfigure(2, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        self.build_sidebar()
        self.build_note_list()
        self.build_editor()

    # ------------------------------------------------
    # LEFT SIDEBAR
    # ------------------------------------------------

    def build_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self.main,
            width=190,
            corner_radius=0,
            fg_color=SIDEBAR,
            border_color=BORDER,
            border_width=1
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=14, pady=(16, 22))

        ctk.CTkLabel(
            brand,
            text="🍅",
            font=("Segoe UI Emoji", 20),
            text_color="#FFFFFF",
            fg_color=TOMATO,
            corner_radius=11,
            width=38,
            height=38
        ).pack(side="left", padx=(0, 9))

        ctk.CTkLabel(
            brand,
            text="Tomato",
            font=("Segoe UI", 16, "bold"),
            text_color=TEXT
        ).pack(side="left")
        ctk.CTkLabel(
            self.sidebar,
            text="YOUR LITTLE SPACE TO THINK",
            font=("Segoe UI", 9, "bold"),
            text_color="#C77765",
            anchor="w"
        ).pack(fill="x", padx=15, pady=(0, 5))
        self.festive_badge = ctk.CTkLabel(
            self.sidebar, text="", font=("Segoe UI Emoji", 10), text_color=MUTED, anchor="w"
        )
        self.festive_badge.pack(fill="x", padx=15, pady=(0, 10))

        self.search = ctk.CTkEntry(
            self.sidebar,
            placeholder_text="⌕  Search notes...",
            textvariable=self.search_var,
            height=34,
            corner_radius=8,
            fg_color="#191919",
            border_color=BORDER,
            font=("Segoe UI", 11)
        )
        self.search.pack(fill="x", padx=12, pady=(0, 16))
        self.search_var.trace_add(
            "write", lambda *_: self.refresh_notes()
        )

        self.nav_buttons = {}

        for label, symbol in [
            ("All Notes", "▤"),
            ("Pinned Notes", "♧"),
            ("Trash", "♜")
        ]:
            button = ctk.CTkButton(
                self.sidebar,
                text=f"  {symbol}    {label}",
                anchor="w",
                height=34,
                corner_radius=7,
                fg_color="transparent",
                hover_color=CARD_HOVER,
                text_color=TEXT,
                font=("Segoe UI", 12),
                command=lambda name=label: self.change_view(name)
            )
            button.pack(fill="x", padx=8, pady=2)
            self.nav_buttons[label] = button

        ctk.CTkFrame(
            self.sidebar, height=1, fg_color=BORDER
        ).pack(fill="x", padx=12, pady=16)

        folder_header = ctk.CTkFrame(
            self.sidebar, fg_color="transparent"
        )
        folder_header.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(
            folder_header,
            text="Folders",
            font=("Segoe UI", 12),
            text_color=MUTED
        ).pack(side="left")

        ctk.CTkButton(
            folder_header,
            text="+",
            width=24,
            height=24,
            fg_color="transparent",
            hover_color=CARD_HOVER,
            text_color=TEXT,
            command=self.create_folder
        ).pack(side="right")

        for folder, symbol in [
            ("Work", "▰"),
            ("Personal", "▰"),
            ("Ideas", "●")
        ]:
            ctk.CTkButton(
                self.sidebar,
                text=f"  {symbol}    {folder}",
                anchor="w",
                height=32,
                fg_color="transparent",
                hover_color=CARD_HOVER,
                text_color="#D0D0D0",
                font=("Segoe UI", 12),
                command=lambda name=folder: self.change_view(name)
            ).pack(fill="x", padx=8, pady=1)

        ctk.CTkButton(
            self.sidebar,
            text="⚙  Settings",
            anchor="w",
            height=34,
            corner_radius=7,
            fg_color="transparent",
            hover_color=CARD_HOVER,
            text_color=TEXT,
            font=("Segoe UI", 12),
            command=self.open_settings
        ).pack(side="bottom", fill="x", padx=8, pady=(0, 4))

        self.sidebar_status = ctk.CTkLabel(
            self.sidebar,
            text="●  Saved locally",
            text_color="#777777",
            font=("Segoe UI", 10)
        )
        self.sidebar_status.pack(
            side="bottom", anchor="w", padx=15, pady=12
        )

    # ------------------------------------------------
    # MIDDLE NOTE LIST
    # ------------------------------------------------

    def build_note_list(self):
        self.list_panel = ctk.CTkFrame(
            self.main,
            corner_radius=0,
            fg_color=BG,
            border_color=BORDER,
            border_width=1
        )
        self.list_panel.grid(row=0, column=1, sticky="nsew")
        self.list_panel.grid_rowconfigure(1, weight=1)
        self.list_panel.grid_columnconfigure(0, weight=1)

        list_header = ctk.CTkFrame(
            self.list_panel, fg_color="transparent"
        )
        list_header.grid(
            row=0, column=0, sticky="ew", padx=12, pady=12
        )

        self.list_heading = ctk.CTkLabel(
            list_header,
            text="All Notes",
            font=("Segoe UI", 14, "bold"),
            text_color=TEXT
        )
        self.list_heading.pack(side="left")

        self.count_label = ctk.CTkLabel(
            list_header,
            text="(0)",
            font=("Segoe UI", 10),
            text_color=MUTED
        )
        self.count_label.pack(side="left", padx=5)

        ctk.CTkButton(
            list_header,
            text="+  New Note",
            width=95,
            height=29,
            corner_radius=7,
            fg_color=BLUE,
            hover_color=BLUE_HOVER,
            font=("Segoe UI", 11, "bold"),
            command=self.new_note
        ).pack(side="right")

        self.cards = ctk.CTkScrollableFrame(
            self.list_panel,
            fg_color="transparent",
            corner_radius=0
        )
        self.cards.grid(
            row=1, column=0, sticky="nsew", padx=7, pady=(0, 8)
        )

    # ------------------------------------------------
    # RIGHT EDITOR
    # ------------------------------------------------

    def build_editor(self):
        self.editor = ctk.CTkFrame(
            self.main, corner_radius=0, fg_color=BG
        )
        self.editor.grid(row=0, column=2, sticky="nsew")
        self.editor.grid_columnconfigure(0, weight=1)
        self.editor.grid_rowconfigure(4, weight=1)

        header = ctk.CTkFrame(
            self.editor, height=46, fg_color=BG, corner_radius=0
        )
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        self.header_title = ctk.CTkLabel(
            header,
            text="Untitled note",
            font=("Segoe UI", 11, "bold"),
            text_color=TEXT,
            anchor="w"
        )
        self.header_title.grid(
            row=0, column=0, sticky="ew", padx=18
        )

        ctk.CTkButton(
            header,
            text="♧  Pin",
            width=55,
            height=28,
            fg_color="transparent",
            hover_color=CARD_HOVER,
            text_color=TEXT,
            font=("Segoe UI", 11),
            command=self.toggle_pin
        ).grid(row=0, column=1, padx=2)

        ctk.CTkButton(
            header,
            text="♜  Delete",
            width=68,
            height=28,
            fg_color="transparent",
            hover_color="#482828",
            text_color=RED,
            font=("Segoe UI", 11),
            command=self.delete_note
        ).grid(row=0, column=2, padx=(2, 12))

        ctk.CTkFrame(
            self.editor, height=1, fg_color=BORDER
        ).grid(row=1, column=0, sticky="ew")

        toolbar = ctk.CTkFrame(
            self.editor, fg_color=BG, corner_radius=0, height=44
        )
        toolbar.grid(row=2, column=0, sticky="new")
        toolbar.grid_propagate(False)

        toolbar_buttons = [
            ("H1", lambda: self.insert_heading(1), 42),
            ("H2", lambda: self.insert_heading(2), 42),
            ("B", lambda: self.format_selection("bold"), 35),
            ("I", lambda: self.format_selection("italic"), 35),
            ("• List", self.insert_bullet, 54),
            ("↶", self.undo, 35),
            ("↷", self.redo, 35),
            ("Find", self.open_find_replace, 48),
            ("Date/time", self.insert_date_time, 72),
            ("Code mode", self.toggle_code_mode, 78),
            ("▶ Run", self.run_python, 58),
            ("Import", self.import_txt, 52),
            ("Export", self.save_txt, 52),
            ("HTML", self.export_html, 48),
        ]

        for label, action, width in toolbar_buttons:
            ctk.CTkButton(
                toolbar,
                text=label,
                width=width,
                height=30,
                corner_radius=5,
                fg_color="transparent",
                hover_color=CARD_HOVER,
                text_color=TEXT,
                font=(
                    "Segoe UI", 11,
                    "bold" if label == "B" else "normal"
                ),
                command=action
            ).pack(side="left", padx=2, pady=6)

        ctk.CTkFrame(
            self.editor, height=1, fg_color=BORDER
        ).grid(row=3, column=0, sticky="ew")

        self.document = ctk.CTkFrame(
            self.editor, fg_color=BG, corner_radius=0
        )
        self.document.grid(row=4, column=0, sticky="nsew")
        self.document.grid_columnconfigure(0, weight=1)
        self.document.grid_rowconfigure(1, weight=1)

        self.title_input = ctk.CTkEntry(
            self.document,
            placeholder_text="Untitled",
            height=54,
            fg_color="transparent",
            border_width=0,
            text_color=TEXT,
            placeholder_text_color=MUTED,
            font=("Segoe UI", 27, "bold")
        )
        self.title_input.grid(
            row=0, column=0, sticky="ew",
            padx=22, pady=(12, 4)
        )

        self.text_input = ctk.CTkTextbox(
            self.document,
            fg_color="transparent",
            border_width=0,
            text_color="#E5E5E5",
            font=("Segoe UI", 13),
            wrap="word",
            undo=True
        )
        self.text_input.grid(
            row=1, column=0, sticky="nsew",
            padx=22, pady=(4, 15)
        )

        # Formatting tags are visual only; JSON stores plain text.
        self.text_widget = self.text_input._textbox
        self.text_widget.tag_configure(
            "bold", font=("Segoe UI", 12, "bold")
        )
        self.text_widget.tag_configure(
            "italic", font=("Segoe UI", 12, "italic")
        )
        self.text_widget.tag_configure(
            "h1", font=("Segoe UI", 22, "bold"),
            spacing1=8, spacing3=8
        )
        self.text_widget.tag_configure(
            "h2", font=("Segoe UI", 17, "bold"),
            spacing1=6, spacing3=6
        )

        self.title_input.bind("<KeyRelease>", self.mark_dirty)
        self.text_input.bind("<KeyRelease>", self.mark_dirty)
        self.text_widget.bind("<Control-f>", lambda event: (self.open_find_replace(), "break")[1])
        self.text_widget.bind("<Control-F>", lambda event: (self.open_find_replace(), "break")[1])
        self.text_widget.bind("<Control-Return>", lambda event: (self.run_python(), "break")[1])
        self.text_widget.bind("<F6>", lambda event: (self.insert_date_time(), "break")[1])
        self.text_widget.bind("<KeyRelease>", lambda event: self.root.after_idle(self.highlight_python) if self.code_mode else None, add="+")
        self.text_widget.tag_configure("search_match", background="#8C562C", foreground="#FFFFFF")
        for tag, color in (("syn_keyword", "#C586C0"), ("syn_string", "#CE9178"),
                           ("syn_comment", "#6A9955"), ("syn_number", "#B5CEA8"),
                           ("syn_builtin", "#4EC9B0")):
            self.text_widget.tag_configure(tag, foreground=color)

        footer = ctk.CTkFrame(
            self.editor, fg_color=SIDEBAR, height=40, corner_radius=0
        )
        footer.grid(row=5, column=0, sticky="ew")
        footer.grid_propagate(False)

        self.status = ctk.CTkLabel(
            footer,
            text="Ready",
            text_color=MUTED,
            font=("Segoe UI", 10)
        )
        self.status.pack(side="left", padx=16)

        ctk.CTkButton(
            footer,
            text="Save",
            width=75,
            height=28,
            corner_radius=6,
            fg_color=BLUE,
            hover_color=BLUE_HOVER,
            command=self.save_current
        ).pack(side="right", padx=12, pady=5)

    # ------------------------------------------------
    # NAVIGATION AND NOTE CARDS
    # ------------------------------------------------

    def change_view(self, view):
        self.current_view = view

        for name, button in self.nav_buttons.items():
            button.configure(
                fg_color=TOMATO_DARK if name == view else "transparent",
                text_color="#FF9B83" if name == view else TEXT
            )

        self.refresh_notes()

    def refresh_notes(self):
        for widget in self.cards.winfo_children():
            widget.destroy()

        query = self.search_var.get().lower().strip()
        matches = []

        for title, note in self.notepad.notes.items():
            trashed = note.get("trashed", False)
            pinned = note.get("pinned", False)
            folder = note.get("folder", "")

            if self.current_view == "Trash" and not trashed:
                continue
            if self.current_view == "Pinned Notes" and (
                    not pinned or trashed
            ):
                continue
            if self.current_view == "All Notes" and trashed:
                continue
            if self.current_view not in (
                    "All Notes", "Pinned Notes", "Trash"
            ):
                if folder != self.current_view or trashed:
                    continue

            content = note.get("content", "")
            if query and query not in title.lower() and query not in content.lower():
                continue

            matches.append((title, note))

        matches.sort(
            key=lambda item: (
                not item[1].get("pinned", False),
                -item[1].get("modified", 0)
            )
        )

        self.list_heading.configure(text=self.current_view)
        self.count_label.configure(text=f"({len(matches)})")

        if not matches:
            ctk.CTkLabel(
                self.cards,
                text="No notes found",
                text_color=MUTED
            ).pack(pady=30)
            return

        for title, note in matches:
            selected = title == self.current_title
            content = note.get("content", "").replace("\n", " ")
            if len(content) > 75:
                content = content[:72] + "..."

            card = ctk.CTkFrame(
                self.cards,
                fg_color="#292929" if selected else CARD,
                border_color=BLUE if selected else CARD,
                border_width=1 if selected else 0,
                corner_radius=11
            )
            card.pack(fill="x", pady=4, padx=1)
            card.grid_columnconfigure(0, weight=1)

            title_row = ctk.CTkFrame(
                card, fg_color="transparent"
            )
            title_row.grid(
                row=0, column=0, sticky="ew",
                padx=10, pady=(10, 3)
            )
            title_row.grid_columnconfigure(0, weight=1)

            ctk.CTkButton(
                title_row,
                text=title,
                anchor="w",
                fg_color="transparent",
                hover_color=CARD_HOVER,
                text_color=TEXT,
                font=("Segoe UI", 11, "bold"),
                height=23,
                command=lambda t=title: self.select_note(t)
            ).grid(row=0, column=0, sticky="ew")

            if note.get("pinned"):
                ctk.CTkLabel(
                    title_row,
                    text="📌",
                    font=("Segoe UI", 10),
                    width=20
                ).grid(row=0, column=1)

            # FIXED: CTkButton does not accept justify="left".
            ctk.CTkButton(
                card,
                text=content if content else "Empty note",
                anchor="w",
                fg_color="transparent",
                hover_color=CARD_HOVER,
                text_color="#B6B6B6",
                font=("Segoe UI", 11),
                height=35,
                command=lambda t=title: self.select_note(t)
            ).grid(
                row=1, column=0, sticky="ew",
                padx=7, pady=(0, 3)
            )

            timestamp = self.time_ago(note.get("modified", 0))
            ctk.CTkLabel(
                card,
                text=timestamp,
                text_color="#858585",
                font=("Segoe UI", 9),
                anchor="w"
            ).grid(
                row=2, column=0, sticky="ew",
                padx=10, pady=(0, 9)
            )

            if self.current_view == "Trash":
                ctk.CTkButton(
                    card,
                    text="Restore",
                    height=25,
                    command=lambda t=title: self.restore_note(t)
                ).grid(
                    row=3, column=0, sticky="ew",
                    padx=8, pady=4
                )

    @staticmethod
    def time_ago(timestamp):
        if not timestamp:
            return "Saved note"

        seconds = max(0, time.time() - timestamp)

        if seconds < 60:
            return "Just now"
        if seconds < 3600:
            return f"{int(seconds / 60)} minutes ago"
        if seconds < 86400:
            return f"{int(seconds / 3600)} hours ago"
        return f"{int(seconds / 86400)} days ago"

    # ------------------------------------------------
    # EDITOR ACTIONS
    # ------------------------------------------------

    def mark_dirty(self, event=None):
        if not self.loading_editor:
            self.dirty = True
            self.status.configure(text="Unsaved changes")

    def new_note(self):
        if self.dirty and self.current_title in self.notepad.notes:
            if not messagebox.askyesno(
                    "Unsaved changes",
                    "Discard your unsaved changes?"
            ):
                return

        self.loading_editor = True
        self.current_title = None

        self.title_input.delete(0, "end")
        self.text_input.delete("1.0", "end")
        self.header_title.configure(text="Untitled note")

        self.loading_editor = False
        self.dirty = False
        self.status.configure(text="New note")
        self.refresh_notes()
        self.title_input.focus()

    def select_note(self, title):
        if self.dirty and self.current_title in self.notepad.notes:
            if not messagebox.askyesno(
                    "Unsaved changes",
                    "Discard your unsaved changes?"
            ):
                return

        note = self.notepad.notes.get(title)
        if not note:
            return

        self.loading_editor = True
        self.current_title = title

        self.title_input.delete(0, "end")
        self.title_input.insert(0, title)

        self.text_input.delete("1.0", "end")
        self.text_input.insert("1.0", note.get("content", ""))

        self.header_title.configure(text=title)
        self.loading_editor = False
        self.dirty = False
        self.status.configure(text="Opened " + title)
        self.refresh_notes()

    def save_current(self):
        title = self.title_input.get().strip()
        content = self.text_input.get("1.0", "end-1c")

        if not title:
            messagebox.showwarning(
                "Missing title", "Enter a title first."
            )
            return

        try:
            if self.current_title is None:
                if not self.notepad.add_note(title, content):
                    messagebox.showwarning(
                        "Duplicate title",
                        "A note with this title already exists."
                    )
                    return
                self.current_title = title

            else:
                old_title = self.current_title

                if title != old_title and title in self.notepad.notes:
                    messagebox.showwarning(
                        "Duplicate title",
                        "Another note already has that title."
                    )
                    return

                note = self.notepad.notes.pop(old_title)
                note["content"] = content
                note["modified"] = time.time()
                self.notepad.notes[title] = note
                self.current_title = title

            self.notepad.save_notes()

        except OSError as error:
            messagebox.showerror("Save error", str(error))
            return

        self.loading_editor = True
        self.header_title.configure(text=title)
        self.loading_editor = False

        self.dirty = False
        self.status.configure(text="All changes saved")
        self.refresh_notes()

    def update_note(self):
        self.save_current()

    def delete_note(self):
        title = self.current_title

        if not title or title not in self.notepad.notes:
            messagebox.showinfo(
                "No note selected", "Select a saved note first."
            )
            return

        if not messagebox.askyesno(
                "Move to Trash", f"Move '{title}' to Trash?"
        ):
            return

        try:
            if self.current_view == "Trash":
                self.notepad.delete_note(title)
            else:
                self.notepad.notes[title]["trashed"] = True
                self.notepad.save_notes()
        except OSError as error:
            messagebox.showerror("Delete error", str(error))
            return

        self.current_title = None
        self.loading_editor = True
        self.title_input.delete(0, "end")
        self.text_input.delete("1.0", "end")
        self.header_title.configure(text="Untitled note")
        self.loading_editor = False
        self.dirty = False

        self.refresh_notes()
        self.status.configure(text="Note moved to Trash")

    def toggle_pin(self):
        title = self.current_title

        if not title or title not in self.notepad.notes:
            return

        note = self.notepad.notes[title]
        note["pinned"] = not note.get("pinned", False)

        try:
            self.notepad.save_notes()
        except OSError as error:
            messagebox.showerror("Save error", str(error))
            return

        self.refresh_notes()
        self.status.configure(
            text="Note pinned" if note["pinned"] else "Note unpinned"
        )

    def restore_note(self, title):
        if title not in self.notepad.notes:
            return

        self.notepad.notes[title]["trashed"] = False
        self.notepad.save_notes()
        self.refresh_notes()

    # ------------------------------------------------
    # FOLDERS
    # ------------------------------------------------

    def create_folder(self):
        dialog = ctk.CTkInputDialog(
            text="Enter a folder name:",
            title="New Folder"
        )
        name = dialog.get_input()

        if not name:
            return

        self.change_view(name)
        self.status.configure(
            text=f"Folder '{name}' selected"
        )

    # ------------------------------------------------
    # FORMATTING
    # ------------------------------------------------

    def format_selection(self, tag):
        try:
            start = self.text_widget.index("sel.first")
            end = self.text_widget.index("sel.last")
        except tk.TclError:
            return

        if tag in self.text_widget.tag_names(start):
            self.text_widget.tag_remove(tag, start, end)
        else:
            self.text_widget.tag_add(tag, start, end)

        self.mark_dirty()

    def insert_heading(self, level):
        try:
            start = self.text_widget.index("sel.first")
            end = self.text_widget.index("sel.last")
        except tk.TclError:
            start = self.text_widget.index("insert linestart")
            end = self.text_widget.index("insert lineend")

        self.text_widget.tag_add(
            "h1" if level == 1 else "h2", start, end
        )
        self.mark_dirty()

    def insert_bullet(self):
        self.text_widget.insert("insert linestart", "• ")
        self.mark_dirty()

    def undo(self):
        try:
            self.text_input.edit_undo()
        except tk.TclError:
            pass

    def redo(self):
        try:
            self.text_input.edit_redo()
        except tk.TclError:
            pass

    # ------------------------------------------------
    # EXTRA EDITOR TOOLS (inspired by Custom Notepad)
    # ------------------------------------------------

    def insert_date_time(self):
        self.text_widget.insert("insert", datetime.now().strftime("%Y-%m-%d %H:%M"))
        self.mark_dirty()
        self.text_widget.focus_set()

    def toggle_code_mode(self):
        self.code_mode = not self.code_mode
        if self.code_mode:
            self.text_widget.configure(font=("Consolas", 12), wrap="none")
            self.status.configure(text="Python code mode — Ctrl+Enter runs this note")
            self.highlight_python()
        else:
            self.text_widget.configure(font=("Segoe UI", 13), wrap="word")
            for tag in ("syn_keyword", "syn_string", "syn_comment", "syn_number", "syn_builtin"):
                self.text_widget.tag_remove(tag, "1.0", "end")
            self.status.configure(text="Rich text mode")
        self.text_widget.focus_set()

    def highlight_python(self):
        if not self.code_mode or not self.text_widget.winfo_exists():
            return
        tx = self.text_widget
        source = tx.get("1.0", "end-1c")
        for tag in ("syn_keyword", "syn_string", "syn_comment", "syn_number", "syn_builtin"):
            tx.tag_remove(tag, "1.0", "end")
        if len(source) > 250000:
            return
        patterns = [
            ("syn_comment", r"(?m)#.*$"),
            ("syn_string", r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\""),
            ("syn_number", r"\b(?:0[xX][0-9a-fA-F]+|\d+(?:\.\d+)?)\b"),
            ("syn_keyword", r"\b(?:" + "|".join(map(re.escape, keyword.kwlist)) + r")\b"),
            ("syn_builtin", r"\b(?:" + "|".join(re.escape(x) for x in dir(__builtins__) if x.isidentifier() and not x.startswith("_")) + r")\b"),
        ]
        for tag, pattern in patterns:
            try:
                for match in re.finditer(pattern, source):
                    tx.tag_add(tag, f"1.0+{match.start()}c", f"1.0+{match.end()}c")
            except re.error:
                pass
        tx.tag_raise("syn_string")
        tx.tag_raise("syn_comment")

    def open_find_replace(self):
        if self._find_dialog is not None and self._find_dialog.winfo_exists():
            self._find_dialog.lift()
            return
        dialog = ctk.CTkToplevel(self.root)
        self._find_dialog = dialog
        dialog.title("Find / Replace")
        dialog.geometry("430x245")
        dialog.transient(self.root)
        dialog.grab_set()
        ctk.CTkLabel(dialog, text="Find in this note", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=18, pady=(16, 8))
        find_var, replace_var = tk.StringVar(), tk.StringVar()
        find_entry = ctk.CTkEntry(dialog, placeholder_text="Text to find", textvariable=find_var)
        find_entry.pack(fill="x", padx=18, pady=4)
        replace_entry = ctk.CTkEntry(dialog, placeholder_text="Replace with", textvariable=replace_var)
        replace_entry.pack(fill="x", padx=18, pady=4)

        def find_next():
            needle = find_var.get()
            if not needle:
                return
            tx = self.text_widget
            tx.tag_remove("search_match", "1.0", "end")
            start = tx.index("insert")
            found = tx.search(needle, start, stopindex="end", nocase=True)
            if not found:
                found = tx.search(needle, "1.0", stopindex=start, nocase=True)
            if found:
                end = f"{found}+{len(needle)}c"
                tx.tag_add("search_match", found, end)
                tx.tag_remove("sel", "1.0", "end")
                tx.tag_add("sel", found, end)
                tx.mark_set("insert", end)
                tx.see(found)
                tx.focus_set()
                self.status.configure(text=f"Found: {needle}")
            else:
                self.status.configure(text="No matches found")

        def replace_one():
            needle = find_var.get()
            if not needle:
                return
            tx = self.text_widget
            try:
                a, b = tx.index("sel.first"), tx.index("sel.last")
                selected = tx.get(a, b)
            except tk.TclError:
                selected = ""
                a = b = None
            if selected.lower() != needle.lower():
                find_next()
                try:
                    a, b = tx.index("sel.first"), tx.index("sel.last")
                except tk.TclError:
                    return
            tx.delete(a, b)
            tx.insert(a, replace_var.get())
            tx.tag_remove("search_match", "1.0", "end")
            self.mark_dirty()

        def replace_all():
            needle = find_var.get()
            if not needle:
                return
            tx = self.text_widget
            source = tx.get("1.0", "end-1c")
            updated, count = re.subn(re.escape(needle), lambda _m: replace_var.get(), source, flags=re.IGNORECASE)
            if count:
                tx.delete("1.0", "end")
                tx.insert("1.0", updated)
                self.mark_dirty()
                self.status.configure(text=f"Replaced {count} occurrence(s)")
            else:
                self.status.configure(text="No matches found")

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill="x", padx=18, pady=(10, 16))
        ctk.CTkButton(buttons, text="Find next", command=find_next, width=90).pack(side="left", padx=(0, 6))
        ctk.CTkButton(buttons, text="Replace", command=replace_one, width=80).pack(side="left", padx=3)
        ctk.CTkButton(buttons, text="Replace all", command=replace_all, width=90).pack(side="left", padx=3)
        find_entry.focus_set()

    def _ensure_run_window(self):
        if self._run_output_window is not None and self._run_output_window.winfo_exists():
            self._run_output_window.lift()
            return
        win = ctk.CTkToplevel(self.root)
        self._run_output_window = win
        win.title("Python Output")
        win.geometry("700x430")
        win.transient(self.root)
        ctk.CTkLabel(win, text="Python output", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=14, pady=(12, 6))
        self.run_output = ctk.CTkTextbox(win, font=("Consolas", 12), wrap="word")
        self.run_output.pack(fill="both", expand=True, padx=14, pady=6)
        controls = ctk.CTkFrame(win, fg_color="transparent")
        controls.pack(fill="x", padx=14, pady=(0, 12))
        ctk.CTkButton(controls, text="Stop process", command=self.stop_python, width=110).pack(side="left")
        ctk.CTkButton(controls, text="Clear output", command=lambda: self.run_output.delete("1.0", "end"), width=100).pack(side="right")

    def run_python(self):
        code = self.text_widget.get("1.0", "end-1c")
        if not code.strip():
            messagebox.showinfo("Run Python", "Write some Python code in the note first.")
            return
        if self.run_process is not None and self.run_process.poll() is None:
            messagebox.showinfo("Run Python", "A Python script is already running. Stop it first.")
            return
        self._ensure_run_window()
        self.run_output.delete("1.0", "end")
        self.run_output.insert("end", "Running Python code...\n\n")
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
                handle.write(code)
                temp_path = handle.name
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            process = subprocess.Popen(
                [sys.executable, "-u", temp_path],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                errors="replace", bufsize=1, creationflags=flags
            )
            self.run_process = process

            def collect():
                try:
                    output, _ = process.communicate()
                    text_out = (output or "(No output)\n") + f"\n[Process finished with exit code {process.returncode}]\n"
                except Exception as error:
                    text_out = f"\n[Run error: {error}]\n"
                finally:
                    try:
                        if temp_path and os.path.exists(temp_path):
                            os.remove(temp_path)
                    except OSError:
                        pass
                try:
                    self.root.after(0, lambda: self._show_run_result(process, text_out))
                except tk.TclError:
                    pass

            threading.Thread(target=collect, daemon=True).start()
        except Exception as error:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            self.run_process = None
            self.run_output.insert("end", f"\n[Could not start Python: {error}]\n")

    def _show_run_result(self, process, output):
        if self._run_output_window is not None and self._run_output_window.winfo_exists():
            self.run_output.delete("1.0", "end")
            self.run_output.insert("1.0", output)
        if self.run_process is process:
            self.run_process = None

    def stop_python(self):
        process = self.run_process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                self.status.configure(text="Python process stopped")
            except OSError as error:
                messagebox.showerror("Stop Python", str(error))

    def export_html(self):
        title = self.title_input.get().strip() or "Untitled"
        path = filedialog.asksaveasfilename(
            title="Export as HTML", defaultextension=".html",
            initialfile=title + ".html", filetypes=[("HTML files", "*.html")]
        )
        if not path:
            return
        source = self.text_widget.get("1.0", "end-1c")
        escaped = html.escape(source).replace("\n", "<br>\n")
        page = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{html.escape(title)}</title></head>"
            f"<body style='font-family:Segoe UI,Arial,sans-serif;max-width:850px;margin:40px auto;"
            f"line-height:1.6;white-space:normal'><h1>{html.escape(title)}</h1>{escaped}</body></html>"
        )
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(page)
            self.status.configure(text=f"Exported {os.path.basename(path)}")
        except OSError as error:
            messagebox.showerror("HTML export error", str(error))

    # ------------------------------------------------
    # TEXT FILE IMPORT / EXPORT
    # ------------------------------------------------

    def import_txt(self):
        path = filedialog.askopenfilename(
            title="Import a text file",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )

        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8-sig") as file:
                content = file.read()
        except (OSError, UnicodeError) as error:
            messagebox.showerror("Import error", str(error))
            return

        self.loading_editor = True
        self.current_title = None

        title = os.path.splitext(os.path.basename(path))[0]
        self.title_input.delete(0, "end")
        self.title_input.insert(0, title)

        self.text_input.delete("1.0", "end")
        self.text_input.insert("1.0", content)
        self.header_title.configure(text=title)

        self.loading_editor = False
        self.dirty = True
        self.status.configure(
            text="Imported — click Save to store this note"
        )

    def save_txt(self):
        title = self.title_input.get().strip() or "Untitled"

        path = filedialog.asksaveasfilename(
            title="Export note",
            defaultextension=".txt",
            initialfile=title + ".txt",
            filetypes=[("Text files", "*.txt")]
        )

        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as file:
                file.write(self.text_input.get("1.0", "end-1c"))
        except OSError as error:
            messagebox.showerror("Export error", str(error))
            return

        self.status.configure(
            text="Exported " + os.path.basename(path)
        )

    # ------------------------------------------------
    # CLOSE APP
    # ------------------------------------------------

    # ------------------------------------------------
    # SETTINGS: STYLE + MUSIC
    # ------------------------------------------------

    @staticmethod
    def apply_palette_values(style_name):
        global BLUE, BLUE_HOVER, TOMATO_DARK, TOMATO
        palette = STYLE_PALETTES.get(style_name, STYLE_PALETTES["Tomato"])
        BLUE = TOMATO = palette["accent"]
        BLUE_HOVER = palette["hover"]
        TOMATO_DARK = palette["dark"]

    def open_settings(self):
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Settings")
        dialog.geometry("440x650")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        ctk.CTkLabel(dialog, text="Settings", font=("Segoe UI", 22, "bold"), text_color=TEXT).pack(anchor="w", padx=24, pady=(18, 2))
        ctk.CTkLabel(dialog, text="Personalise music, visuals and seasonal effects", font=("Segoe UI", 11), text_color=MUTED).pack(anchor="w", padx=24, pady=(0, 12))

        ctk.CTkLabel(dialog, text="App style", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=24)
        style_var = tk.StringVar(value=self.settings.get("style", "Tomato"))
        ctk.CTkOptionMenu(dialog, values=list(STYLE_PALETTES.keys()), variable=style_var,
                          command=self.change_style, width=390).pack(fill="x", padx=24, pady=(5, 12))

        ctk.CTkLabel(dialog, text="Music", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=24, pady=(0, 4))
        music_var = tk.BooleanVar(value=self.settings.get("music_enabled", True))
        ctk.CTkSwitch(dialog, text="Background music", variable=music_var,
                      command=lambda: self.set_music_enabled(music_var.get())).pack(anchor="w", padx=24, pady=(0, 8))
        self.song_var = tk.StringVar(value=self.settings.get("selected_song", "Random"))
        song_values = ["Random"] + sorted({os.path.basename(f) for f in MUSIC_PLAYER.files}, key=str.lower)
        if self.song_var.get() not in song_values: self.song_var.set("Random")
        song_row = ctk.CTkFrame(dialog, fg_color="transparent")
        song_row.pack(fill="x", padx=24, pady=(0, 8))
        ctk.CTkLabel(song_row, text="Select song").pack(side="left")
        self.song_menu = ctk.CTkOptionMenu(song_row, values=song_values, variable=self.song_var,
                                           command=self.select_song, width=245)
        self.song_menu.pack(side="right")
        ctk.CTkButton(dialog, text="⏭  Skip song", command=self.skip_song, height=30).pack(fill="x", padx=24, pady=(0, 8))
        vol_row = ctk.CTkFrame(dialog, fg_color="transparent")
        vol_row.pack(fill="x", padx=24, pady=(0, 10))
        ctk.CTkLabel(vol_row, text="Volume").pack(side="left")
        self.volume_label = ctk.CTkLabel(vol_row, text=f"{self.settings.get('volume', 65)}%")
        self.volume_label.pack(side="right")
        ctk.CTkSlider(dialog, from_=0, to=100, number_of_steps=100, width=280,
                      command=self.change_volume).pack(fill="x", padx=24, pady=(0, 12))
        # Set slider to saved volume (find it among dialog widgets).
        for child in dialog.winfo_children():
            if isinstance(child, ctk.CTkSlider): child.set(self.settings.get("volume", 65))

        ctk.CTkLabel(dialog, text="Visual effects", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=24, pady=(0, 4))
        visual_var = tk.BooleanVar(value=self.settings.get("visualizer_enabled", False))
        ctk.CTkSwitch(dialog, text="Beat visualizer in writing area", variable=visual_var,
                      command=lambda: self.set_visualizer_enabled(visual_var.get())).pack(anchor="w", padx=24, pady=(0, 6))
        festive_var = tk.BooleanVar(value=self.settings.get("festive_enabled", True))
        ctk.CTkSwitch(dialog, text="Festive seasonal UI (on by default)", variable=festive_var,
                      command=lambda: self.set_festive_enabled(festive_var.get())).pack(anchor="w", padx=24, pady=(0, 8))
        ctk.CTkLabel(dialog, text="Season themes: summer sand + sun (Jun–Aug), Easter (Apr), Halloween (Oct), snow (Dec).\nSongs are chosen randomly without repeating the last track. Audio requires pygame.",
                     font=("Segoe UI", 10), text_color=MUTED, justify="left", wraplength=390).pack(anchor="w", padx=24, pady=(0, 10))
        ctk.CTkButton(dialog, text="Open MUSIC folder", command=self.open_music_folder).pack(anchor="e", padx=24, pady=(0, 16))

    def select_song(self, song):
        self.settings["selected_song"] = song
        MUSIC_PLAYER.selected_song = song
        save_app_settings(self.settings)
        if self.settings.get("music_enabled", True):
            ok, message = MUSIC_PLAYER.start(self.root, song)
            if not ok: messagebox.showinfo("Background music", message)

    def skip_song(self):
        MUSIC_PLAYER.selected_song = "Random"
        self.settings["selected_song"] = "Random"
        save_app_settings(self.settings)
        ok, message = MUSIC_PLAYER.skip(self.root)
        if not ok and self.settings.get("music_enabled", True): messagebox.showinfo("Background music", message)
        if hasattr(self, "song_var"): self.song_var.set("Random")

    def change_volume(self, value):
        volume = int(float(value))
        self.settings["volume"] = volume
        MUSIC_PLAYER.set_volume(volume / 100)
        save_app_settings(self.settings)
        if hasattr(self, "volume_label"):
            self.volume_label.configure(text=f"{volume}%")

    def set_visualizer_enabled(self, enabled):
        self.settings["visualizer_enabled"] = bool(enabled)
        save_app_settings(self.settings)
        self.status.configure(text="Beat visualizer enabled" if enabled else "Beat visualizer disabled")

    def set_festive_enabled(self, enabled):
        self.settings["festive_enabled"] = bool(enabled)
        save_app_settings(self.settings)
        self.apply_festive_theme()

    def _season(self):
        month = datetime.now().month
        if month in (6, 7, 8): return "summer"
        if month == 12: return "winter"
        if month == 10: return "halloween"
        if month == 4: return "easter"
        return "normal"

    def apply_festive_theme(self):
        if not self.settings.get("festive_enabled", True):
            palette = {"bg": BG, "sidebar": SIDEBAR, "card": CARD, "text": TEXT, "badge": "Festive effects off"}
        else:
            season = self._season()
            palette = {
                "summer": {"bg":"#28251D", "sidebar":"#373020", "card":"#453B29", "text":"#FFF2CE", "badge":"☀️  Summer • sandy shores"},
                "winter": {"bg":"#202A36", "sidebar":"#263747", "card":"#30465A", "text":"#F1F8FF", "badge":"❄️  Winter • let it snow"},
                "halloween": {"bg":"#241B2B", "sidebar":"#32203A", "card":"#432747", "text":"#FFE8C7", "badge":"🎃  Halloween • spooky season"},
                "easter": {"bg":"#252A2A", "sidebar":"#293B37", "card":"#354A40", "text":"#F6F4DD", "badge":"🐣  Easter • spring colours"},
                "normal": {"bg":BG, "sidebar":SIDEBAR, "card":CARD, "text":TEXT, "badge":"🍅  Tomato Notepad"},
            }[season]
        self.season_palette = palette
        self.festive_badge.configure(text=palette["badge"])
        # Apply seasonal shades to the main panels and writing surface.
        for widget_name, color in (("main", palette["bg"]), ("sidebar", palette["sidebar"]),
                                   ("list_panel", palette["bg"]), ("editor", palette["bg"]),
                                   ("document", palette["bg"])):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                try: widget.configure(fg_color=color)
                except (tk.TclError, ValueError): pass
        try: self.text_widget.configure(background=palette["bg"], insertbackground=palette["text"])
        except (tk.TclError, AttributeError): pass

    def animate_festive(self):
        if not self.root.winfo_exists(): return
        if self.settings.get("festive_enabled", True):
            season = self._season()
            if season == "winter": self.festive_badge.configure(text=f"❄️  Winter • snowflakes {random.choice(['❄', '✻', '❅', '❆'])}")
            elif season == "summer": self.festive_badge.configure(text=f"☀️  Summer • {random.choice(['·  ·  ·', 'sand • sand • sand', '☀ warm days ☀'])}")
        self.root.after(1800, self.animate_festive)

    def animate_visualizer(self):
        if not self.root.winfo_exists(): return
        if self.settings.get("visualizer_enabled", False):
            self.visualizer_phase += 0.42
            # A lightweight beat pulse (pygame mixer doesn't expose a spectrum stream).
            pulse = (math.sin(self.visualizer_phase) + 1) / 2
            accent = STYLE_PALETTES.get(self.settings.get("style", "Tomato"), STYLE_PALETTES["Tomato"])["accent"]
            shade = self.season_palette.get("bg", BG) if hasattr(self, "season_palette") else BG
            try:
                self.text_widget.configure(background=shade if pulse < 0.45 else self._blend_color(shade, accent, 0.18 + 0.2*pulse))
                self.editor.configure(border_width=2 if pulse > 0.7 else 0, border_color=accent)
                self.status.configure(text="♫ Visualizer active" if pulse > 0.75 else "")
            except (tk.TclError, AttributeError): pass
        else:
            try:
                self.text_widget.configure(background=self.season_palette.get("bg", BG) if hasattr(self, "season_palette") else BG)
                self.editor.configure(border_width=0)
            except (tk.TclError, AttributeError): pass
        self.root.after(90, self.animate_visualizer)

    @staticmethod
    def _blend_color(base, accent, amount):
        try:
            b = tuple(int(base[i:i+2], 16) for i in (1,3,5))
            a = tuple(int(accent[i:i+2], 16) for i in (1,3,5))
            return "#" + "".join(f"{int(x*(1-amount)+y*amount):02x}" for x,y in zip(b,a))
        except Exception: return base

    def change_style(self, style_name):
        self.settings["style"] = style_name
        save_app_settings(self.settings)
        old_accent = BLUE
        self.apply_palette_values(style_name)
        palette = STYLE_PALETTES[style_name]
        replacements = {
            old_accent: palette["accent"],
            "#F0523A": palette["accent"], "#D9412B": palette["hover"],
            "#4A211D": palette["dark"], "#FF9B83": palette["accent"],
            "#FF6255": palette["accent"],
        }
        def recolor(widget):
            try:
                for key in ("fg_color", "hover_color", "border_color", "progress_color",
                            "button_color", "button_hover_color", "text_color"):
                    value = widget.cget(key)
                    if isinstance(value, str) and value in replacements:
                        widget.configure(**{key: replacements[value]})
            except (tk.TclError, ValueError, TypeError):
                pass
            for child in widget.winfo_children():
                recolor(child)
        recolor(self.root)
        self.refresh_notes()
        self.status.configure(text=f"Style changed to {style_name}")

    def set_music_enabled(self, enabled):
        self.settings["music_enabled"] = bool(enabled)
        save_app_settings(self.settings)
        if enabled:
            ok, message = MUSIC_PLAYER.start(self.root, self.settings.get("selected_song", "Random"))
            if not ok:
                messagebox.showinfo("Background music", message)
        else:
            MUSIC_PLAYER.stop()

    def open_music_folder(self):
        os.makedirs(MUSIC_DIR, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(MUSIC_DIR)
            elif os.sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", MUSIC_DIR])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", MUSIC_DIR])
        except (OSError, AttributeError):
            messagebox.showinfo("MUSIC folder", MUSIC_DIR)

    def close_app(self):
        if self.dirty:
            if not messagebox.askyesno(
                    "Unsaved changes",
                    "You have unsaved changes. Close anyway?"
            ):
                return

        MUSIC_PLAYER.stop()
        self.stop_python()
        self.root.destroy()


# ==================================================
# RUN
# ==================================================

if __name__ == "__main__":
    root = ctk.CTk()
    apply_tomato_icon(root)

    def launch_app():
        global app
        app = TomatoNotepadGUI(root)

    splash = TomatoSplash(root, launch_app)
    root.mainloop()
