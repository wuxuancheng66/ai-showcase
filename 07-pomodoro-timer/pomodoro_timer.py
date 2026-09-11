# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
🍅 Pomodoro Timer — Compact mini widget with circular progress & desktop notifications.
Pure Python + tkinter. Zero external dependencies.

Usage:  python3 pomodoro_timer.py

Keys:   Space = Start/Pause   |   R = Reset   |   Right = Skip   |   1/2/3 = Switch mode
"""

import tkinter as tk
import sys
import subprocess
from enum import Enum


# ---------------------------------------------------------------------------
# Design Tokens
# ---------------------------------------------------------------------------

class Theme:
    BG_DEEP     = "#0d1117"
    BG_CARD     = "#161b22"
    BG_ELEVATED = "#1c2333"

    TOMATO      = "#e5533c"
    TOMATO_SOFT = "#f06b58"
    TOMATO_DIM  = "#5c1f16"

    TEAL        = "#3fb950"
    TEAL_DIM    = "#1b4a2c"

    PURPLE      = "#a371f7"
    PURPLE_DIM  = "#38285a"

    GOLD        = "#d2991d"

    TEXT_PRIMARY   = "#e6edf3"
    TEXT_SECONDARY = "#8b949e"
    TEXT_MUTED     = "#484f58"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class TimerState(Enum):
    WORK        = "work"
    SHORT_BREAK = "short_break"
    LONG_BREAK  = "long_break"


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

class PomodoroApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Pomodoro")
        self.root.resizable(False, False)
        self.root.configure(bg=Theme.BG_DEEP)

        # ---- State ----
        self.state           = TimerState.WORK
        self.work_sec        = 25 * 60
        self.short_break_sec = 5 * 60
        self.long_break_sec  = 15 * 60
        self.duration        = self.work_sec
        self.remaining       = self.work_sec
        self.running         = False
        self.sessions_done   = 0
        self._after_id       = None

        # ---- Platform ----
        self._mac = sys.platform == "darwin"

        # ---- Build & centre ----
        self._build_ui()
        self._draw()
        self._update_mode_highlight()

        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = self.root.winfo_reqwidth()
        h = self.root.winfo_reqheight()
        self.root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

        # ---- Keyboard shortcuts ----
        self.root.bind("<space>",  lambda _: self.toggle())
        self.root.bind("<r>",      lambda _: self.reset())
        self.root.bind("<Right>",  lambda _: self._skip_to_next())
        self.root.bind("<Escape>", lambda _: self._on_close())
        self.root.bind("1", lambda _: self.set_mode(TimerState.WORK))
        self.root.bind("2", lambda _: self.set_mode(TimerState.SHORT_BREAK))
        self.root.bind("3", lambda _: self.set_mode(TimerState.LONG_BREAK))
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- UI Construction ----------------------------------------------------

    def _build_ui(self):
        outer = tk.Frame(self.root, bg=Theme.BG_DEEP)
        outer.pack(padx=16, pady=(14, 12))

        # ---- Top bar: icon + title + mode tabs ----
        top = tk.Frame(outer, bg=Theme.BG_DEEP)
        top.pack(fill=tk.X)

        tk.Label(
            top, text="🍅 Pomodoro",
            font=("Helvetica Neue", 14, "bold"),
            fg=Theme.TEXT_PRIMARY, bg=Theme.BG_DEEP
        ).pack(side=tk.LEFT)

        # Mini mode tabs
        self._mode_btns = {}
        modes = [
            ("Focus", TimerState.WORK,        Theme.TOMATO),
            ("Break", TimerState.SHORT_BREAK, Theme.TEAL),
            ("Long",  TimerState.LONG_BREAK,  Theme.PURPLE),
        ]
        tab_frame = tk.Frame(outer, bg=Theme.BG_DEEP)
        tab_frame.pack(pady=(8, 0), fill=tk.X)

        for text, st, color in modes:
            lbl = tk.Label(
                tab_frame, text=text,
                font=("Helvetica Neue", 11),
                fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD,
                padx=0, pady=4,
                cursor="hand2"
            )
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)
            lbl.bind("<Button-1>", lambda e, s=st: self.set_mode(s))
            lbl._state = st
            lbl._color = color
            self._mode_btns[st] = lbl

        # ---- Canvas (circular timer) ----
        self.cv_w, self.cv_h = 240, 240
        self.canvas = tk.Canvas(
            outer, width=self.cv_w, height=self.cv_h,
            bg=Theme.BG_DEEP, highlightthickness=0
        )
        self.canvas.pack(pady=(12, 6))

        # ---- Button row ----
        btn_row = tk.Frame(outer, bg=Theme.BG_DEEP)
        btn_row.pack(pady=(4, 0))

        self.start_btn = self._pill("▶  Start", Theme.TOMATO, Theme.TOMATO_SOFT, self.toggle)
        self.start_btn.pack(side=tk.LEFT, padx=4)

        self.reset_btn = self._pill("↺", Theme.TEXT_MUTED, Theme.TEXT_SECONDARY, self.reset)
        self.reset_btn.pack(side=tk.LEFT, padx=4)

        self.skip_btn = self._pill("⏭", Theme.TEXT_MUTED, Theme.TEXT_SECONDARY, self._skip_to_next)
        self.skip_btn.pack(side=tk.LEFT, padx=4)

        # ---- Session dots + counter ----
        foot = tk.Frame(outer, bg=Theme.BG_DEEP)
        foot.pack(pady=(10, 0))

        self._dot_labels = []
        for i in range(4):
            dot = tk.Label(
                foot, text="●",
                font=("Arial", 8),
                fg=Theme.TEXT_MUTED, bg=Theme.BG_DEEP
            )
            dot.pack(side=tk.LEFT, padx=3)
            self._dot_labels.append(dot)

        self.counter_lbl = tk.Label(
            foot, text="",
            font=("Helvetica Neue", 9),
            fg=Theme.TEXT_SECONDARY, bg=Theme.BG_DEEP
        )
        self.counter_lbl.pack(side=tk.LEFT, padx=(8, 0))
        self._update_dots()
        self._update_counter()

    def _pill(self, text, bg, hover_bg, cmd):
        """Compact pill button."""
        btn = tk.Label(
            self.root, text=text,
            font=("Helvetica Neue", 11, "bold"),
            fg="#fff", bg=bg,
            padx=18, pady=5,
            cursor="hand2"
        )
        btn._bg = bg
        btn._hover_bg = hover_bg
        btn.bind("<Enter>",    lambda e, b=btn: b.configure(bg=b._hover_bg))
        btn.bind("<Leave>",    lambda e, b=btn: b.configure(bg=b._bg))
        btn.bind("<Button-1>", lambda _, c=cmd: c())
        return btn

    # -- Drawing ------------------------------------------------------------

    def _draw(self):
        """Render circular progress ring + timer digits."""
        self.canvas.delete("all")
        cx = self.cv_w // 2
        cy = self.cv_h // 2
        r  = 90
        sw = 8

        accent = {
            TimerState.WORK:        Theme.TOMATO,
            TimerState.SHORT_BREAK: Theme.TEAL,
            TimerState.LONG_BREAK:  Theme.PURPLE,
        }[self.state]
        track = {
            TimerState.WORK:        Theme.TOMATO_DIM,
            TimerState.SHORT_BREAK: Theme.TEAL_DIM,
            TimerState.LONG_BREAK:  Theme.PURPLE_DIM,
        }[self.state]

        # Outer glow rings
        for i in range(3, 0, -1):
            self.canvas.create_oval(
                cx - r - i*4, cy - r - i*4,
                cx + r + i*4, cy + r + i*4,
                outline=accent, width=1
            )

        # Background track
        self.canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            outline=track, width=sw
        )

        # Progress arc
        pct = self.remaining / self.duration if self.duration > 0 else 0
        if pct > 0.0001:
            self.canvas.create_arc(
                cx - r, cy - r, cx + r, cy + r,
                start=90, extent=-pct * 360,
                outline=accent, width=sw,
                style="arc"
            )

        # Inner disc
        pad = 16
        self.canvas.create_oval(
            cx - r + sw + pad, cy - r + sw + pad,
            cx + r - sw - pad, cy + r - sw - pad,
            fill=Theme.BG_ELEVATED, outline=""
        )

        # Timer text
        mins = self.remaining // 60
        secs = self.remaining % 60

        self.canvas.create_text(
            cx, cy - 10,
            text=f"{mins:02d}",
            font=("Menlo", 46, "bold"),
            fill=Theme.TEXT_PRIMARY
        )
        self.canvas.create_text(
            cx, cy + 10,
            text=":",
            font=("Menlo", 16, "bold"),
            fill=Theme.TEXT_MUTED
        )
        self.canvas.create_text(
            cx, cy + 38,
            text=f"{secs:02d}",
            font=("Menlo", 24, "bold"),
            fill=accent
        )

    # -- Timer Logic --------------------------------------------------------

    def toggle(self):
        if self.running:
            self._pause()
        else:
            self._start()

    def _start(self):
        self.running = True
        self._sync_start_btn()
        self._tick()

    def _pause(self):
        self.running = False
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self._sync_start_btn()

    def reset(self):
        self._pause()
        self.remaining = self.duration
        self._draw()

    def _skip_to_next(self):
        self.remaining = 0
        self._draw()
        self._on_complete()

    def _tick(self):
        if not self.running:
            return
        if self.remaining > 0:
            self.remaining -= 1
            self._draw()
            self._after_id = self.root.after(1000, self._tick)
        else:
            self.running = False
            self._sync_start_btn()
            self._on_complete()

    # -- Session Completion -------------------------------------------------

    def _on_complete(self):
        if self.state == TimerState.WORK:
            self.sessions_done += 1
            self._notify(
                "Focus Session Complete!",
                f"{self.sessions_done} session(s) done - take a break!"
            )
            if self.sessions_done % 4 == 0:
                self.set_mode(TimerState.LONG_BREAK)
            else:
                self.set_mode(TimerState.SHORT_BREAK)
        elif self.state == TimerState.SHORT_BREAK:
            self._notify("Break Over", "Short break finished. Ready to focus?")
            self.set_mode(TimerState.WORK)
        elif self.state == TimerState.LONG_BREAK:
            self._notify("Long Break Over", "Back to work!")
            self.set_mode(TimerState.WORK)

        self._update_counter()
        self._update_dots()
        self._draw()
        self._flash_window()

    # -- Mode Switching -----------------------------------------------------

    def set_mode(self, state):
        if self.running:
            self._pause()

        self.state = state
        if state == TimerState.WORK:
            self.duration = self.work_sec
        elif state == TimerState.SHORT_BREAK:
            self.duration = self.short_break_sec
        else:
            self.duration = self.long_break_sec

        self.remaining = self.duration
        self._draw()
        self._update_mode_highlight()

    # -- UI Sync Helpers ----------------------------------------------------

    def _sync_start_btn(self):
        if self.running:
            self.start_btn.configure(text="⏸  Pause", bg=Theme.GOLD)
            self.start_btn._bg = Theme.GOLD
            self.start_btn._hover_bg = Theme.GOLD
        else:
            self.start_btn.configure(text="▶  Start", bg=Theme.TOMATO)
            self.start_btn._bg = Theme.TOMATO
            self.start_btn._hover_bg = Theme.TOMATO_SOFT

    def _update_mode_highlight(self):
        for st, lbl in self._mode_btns.items():
            if st == self.state:
                lbl.configure(fg="#fff", bg=lbl._color)
            else:
                lbl.configure(fg=Theme.TEXT_SECONDARY, bg=Theme.BG_CARD)

    def _update_counter(self):
        n = self.sessions_done
        self.counter_lbl.config(
            text=f"{n} done" if n else ""
        )

    def _update_dots(self):
        pos = self.sessions_done % 4
        for i, dot in enumerate(self._dot_labels):
            if i < pos:
                dot.configure(fg=Theme.TOMATO)
            else:
                dot.configure(fg=Theme.TEXT_MUTED)

    # -- Desktop Notifications ----------------------------------------------

    def _notify(self, title, body):
        if self._mac:
            try:
                safe_title = title.replace('"', '\\"')
                safe_body  = body.replace('"', '\\"')
                subprocess.run([
                    "osascript", "-e",
                    f'display notification "{safe_body}" with title "{safe_title}" sound name "Glass"'
                ], timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        elif sys.platform.startswith("linux"):
            try:
                subprocess.run(
                    ["notify-send", title, body],
                    timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except Exception:
                pass
        else:
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, body, title, 0x40)
            except Exception:
                pass

        sys.stdout.write("\a")
        sys.stdout.flush()

    def _flash_window(self):
        try:
            self.root.attributes("-topmost", True)
            self.root.after(1800, lambda: self.root.attributes("-topmost", False))
        except Exception:
            pass

    # -- Lifecycle ----------------------------------------------------------

    def _on_close(self):
        self.running = False
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    PomodoroApp().run()
