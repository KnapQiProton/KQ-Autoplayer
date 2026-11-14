"""
KQ Autoplayer – Modern Tech-Minimalist Dark Edition.

Refactored with CustomTkinter and strict tech-minimalist specifications:
• Main App Window Background: Charcoal Gray (#343A40)
• Text and Labels: Ivory White (#F8F9FA)
• Accent Color: Steel Blue (#406185)
• Typography: Sans-serif (Segoe UI) + Monospace (Consolas) for numerical inputs
• Inputs & Dropdowns: Rounded corners, offset dark background (#2B3035), focus rings
• Sliders: Steel Blue active track + Ivory White thumb
• Toggle Switch: Modern iOS/Android style toggle switch (CTkSwitch)
• Play Button: Large circular Steel Blue FAB with white play/pause icon
• Timer: Precision monospace timer readout near play button
• Hotkey Engine: Debounced edge-detection with zero delay and no spam required
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from queue import Empty, Queue
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from pynput.keyboard import Key, KeyCode, Listener

import autoplayer_core as core
from playpianosheets_source import OnlineSheetsDialog, check_internet, SmoothScrollableFrame

# --- Logger Initialization ---
logger = logging.getLogger('KQAutoplayer.GUI')
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(
        logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s', datefmt='%H:%M:%S')
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# Color Palette Specification
COLOR_BG = '#343A40'            # Charcoal Gray (Main App Window Background)
COLOR_SURFACE = '#2B3035'       # Offset Charcoal for input surfaces & depth
COLOR_SURFACE_DARK = '#212529'  # Deeper dark tone for inactive tracks & tooltips
COLOR_TEXT = '#F8F9FA'          # Ivory White (Text and Labels)
COLOR_TEXT_MUTED = '#8E959D'    # Faded line icons / labels (~50% opacity feel)
COLOR_TEXT_HOVER = '#CED4DA'    # Lightened muted tone on hover
COLOR_ACCENT = '#406185'        # Steel Blue (Primary buttons, active tracks, rings)
COLOR_ACCENT_HOVER = '#334D6B'  # Deep Steel Blue for button hover
COLOR_ACCENT_LIGHT = '#4E749E'  # Elevated Steel Blue for Play button hover
COLOR_BORDER = '#495057'        # Subtle border line
COLOR_THUMB = '#F8F9FA'         # Ivory White thumb for sliders & switches
COLOR_THUMB_HOVER = '#E9ECEF'   # Thumb hover state

# Typography Specification
FONT_TITLE = ('Segoe UI', 15, 'bold')
FONT_LABEL = ('Segoe UI', 12)
FONT_LABEL_BOLD = ('Segoe UI', 12, 'bold')
FONT_SUBTLE = ('Segoe UI', 10)
FONT_NUMERIC = ('Consolas', 12)
FONT_NUMERIC_BOLD = ('Consolas', 12, 'bold')
FONT_TIMER = ('Consolas', 13, 'bold')
FONT_PLAY_ICON = ('Segoe UI', 20, 'bold')

CFG = core.CFG


class MinimalistTip:
    """Subtle, minimalist tooltip floating card."""
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.top = None
        widget.bind('<Enter>', self.show, add='+')
        widget.bind('<Leave>', self.hide, add='+')

    def show(self, _event=None):
        if self.top:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.top = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.attributes('-topmost', True)
        frame = ctk.CTkFrame(
            tw,
            fg_color=COLOR_SURFACE_DARK,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=6,
        )
        frame.pack(fill='both', expand=True)
        ctk.CTkLabel(
            frame,
            text=self.text,
            font=FONT_SUBTLE,
            text_color=COLOR_TEXT,
            wraplength=260,
            justify='left',
        ).pack(padx=8, pady=5)
        tw.geometry(f'+{x}+{y}')

    def hide(self, _event=None):
        if self.top:
            self.top.destroy()
            self.top = None


def make_info_icon(parent, text: str) -> ctk.CTkLabel:
    """Subtle, minimalist faded info icon with hover highlight and tooltip."""
    lbl = ctk.CTkLabel(
        parent,
        text='ⓘ',
        font=('Segoe UI', 11),
        text_color=COLOR_TEXT_MUTED,
        cursor='hand2',
        width=18,
    )
    lbl.bind('<Enter>', lambda _e: lbl.configure(text_color=COLOR_TEXT_HOVER), add='+')
    lbl.bind('<Leave>', lambda _e: lbl.configure(text_color=COLOR_TEXT_MUTED), add='+')
    MinimalistTip(lbl, text)
    return lbl


def add_focus_ring(widget, default_border=COLOR_BORDER, focus_border=COLOR_ACCENT):
    """Binds dynamic focus ring color highlight."""
    widget.bind('<FocusIn>', lambda _e: widget.configure(border_color=focus_border), add='+')
    widget.bind('<FocusOut>', lambda _e: widget.configure(border_color=default_border), add='+')


def normalize_key(k) -> str | None:
    """Normalize pynput Key/KeyCode instances to a consistent lowercase string."""
    if k is None:
        return None
    if k in (Key.ctrl, Key.ctrl_l, Key.ctrl_r):
        return 'ctrl'
    if k in (Key.alt, Key.alt_l, Key.alt_r, getattr(Key, 'alt_gr', None)):
        return 'alt'
    if k in (Key.shift, Key.shift_l, Key.shift_r):
        return 'shift'
    if k in (Key.cmd, getattr(Key, 'cmd_l', None), getattr(Key, 'cmd_r', None)):
        return 'cmd'
    if hasattr(k, 'name') and k.name:
        name = k.name.lower()
        if name.startswith('ctrl'):
            return 'ctrl'
        if name.startswith('alt'):
            return 'alt'
        if name.startswith('shift'):
            return 'shift'
        if name.startswith('cmd'):
            return 'cmd'
        return name
    if hasattr(k, 'char') and k.char:
        return k.char.lower()
    if isinstance(k, str):
        return k.lower().strip()
    return None


def parse_combo(expr: str) -> frozenset[str]:
    """Parse a hotkey string like 'f4' or 'ctrl+alt+p' into a set of canonical keys."""
    res = []
    for p in expr.lower().split('+'):
        p = p.strip()
        if not p:
            continue
        if p in ('control', 'ctrl'):
            res.append('ctrl')
        elif p in ('alternate', 'alt'):
            res.append('alt')
        elif p == 'shift':
            res.append('shift')
        elif p in ('cmd', 'meta', 'win', 'windows'):
            res.append('cmd')
        elif p == 'escape':
            res.append('esc')
        else:
            res.append(p)
    return frozenset(res)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode('dark')
        ctk.set_default_color_theme('dark-blue')

        self.title('KQ Autoplayer')

        # Restore saved window size or default to 480x720
        initial_geom = getattr(CFG, 'geometry', None) or '480x720'
        try:
            w, h = map(int, initial_geom.split('+')[0].split('x'))
            w = max(420, w)
            h = max(520, h)
            self.geometry(f"{w}x{h}")
        except Exception:
            self.geometry('480x720')

        self.minsize(420, 520)
        self.resizable(True, True)
        self.configure(fg_color=COLOR_BG)

        icon_path = Path(__file__).with_name('Icon.ico')
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

        self.queue = Queue()
        self.player: core.Player | None = None
        self._tok_done = 0
        self.total_tokens = 0
        self._suspend_trace = False
        self._last_valid_bpm = getattr(CFG, 'bpm', 120)
        self._last_valid_sub = getattr(CFG, 'subdiv', 4.0)

        # Debounced Edge-Triggered Hotkey Engine
        self._pressed: set[str] = set()
        self._hotkey_active: bool = False
        self._last_hotkey_time: float = 0.0
        self.toggle_combo = parse_combo(CFG.toggle)

        self._build_ui()

        # Keyboard Listener (background daemon)
        self._hk_listener = Listener(
            on_press=self._hk_press,
            on_release=self._hk_release,
            daemon=True,
        )
        self._hk_listener.start()

        self.after(50, self._poll)

    def _build_ui(self):
        # 1. Header Bar (Pinned Top)
        hdr_frame = ctk.CTkFrame(self, fg_color='transparent')
        hdr_frame.pack(side='top', fill='x', padx=20, pady=(14, 6))

        ctk.CTkLabel(
            hdr_frame,
            text='KQ AUTOPLAYER',
            font=FONT_TITLE,
            text_color=COLOR_TEXT,
        ).pack(side='left')

        self.status_pill = ctk.CTkLabel(
            hdr_frame,
            text='IDLE',
            font=FONT_NUMERIC_BOLD,
            text_color=COLOR_TEXT_MUTED,
            fg_color=COLOR_SURFACE,
            corner_radius=6,
            padx=10,
            pady=2,
        )
        self.status_pill.pack(side='right')

        # 2. Bottom Player Bar (Pinned Bottom - Always Visible)
        btm_container = ctk.CTkFrame(self, fg_color='transparent')
        btm_container.pack(side='bottom', fill='x', padx=20, pady=(4, 14))

        self.prog = ctk.CTkProgressBar(
            btm_container,
            height=6,
            corner_radius=3,
            progress_color=COLOR_ACCENT,
            fg_color=COLOR_SURFACE_DARK,
        )
        self.prog.set(0.0)
        self.prog.pack(fill='x', pady=(0, 8))

        btm_bar = ctk.CTkFrame(btm_container, fg_color='transparent')
        btm_bar.pack(fill='x')

        timer_col = ctk.CTkFrame(btm_bar, fg_color='transparent')
        timer_col.pack(side='left', fill='y')

        timer_row = ctk.CTkFrame(timer_col, fg_color='transparent')
        timer_row.pack(anchor='w', fill='x')

        self.lbl_time = ctk.CTkLabel(
            timer_row,
            text='00:00 / 00:00',
            font=FONT_TIMER,
            text_color=COLOR_TEXT,
        )
        self.lbl_time.pack(side='left')

        # Real-time Visualizer Badge (displays current note/chord from progress queue)
        self.lbl_visualizer = ctk.CTkLabel(
            timer_row,
            text='NOTE: --',
            font=FONT_NUMERIC_BOLD,
            text_color=COLOR_TEXT_MUTED,
            fg_color=COLOR_SURFACE_DARK,
            corner_radius=5,
            padx=8,
            pady=1,
        )
        self.lbl_visualizer.pack(side='left', padx=(10, 0))

        self.lbl_subtext = ctk.CTkLabel(
            timer_col,
            text='Ready to play',
            font=FONT_SUBTLE,
            text_color=COLOR_TEXT_MUTED,
        )
        self.lbl_subtext.pack(anchor='w', pady=(2, 0))

        self.btn_play = ctk.CTkButton(
            btm_bar,
            text='▶',
            width=56,
            height=56,
            corner_radius=28,
            font=FONT_PLAY_ICON,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_LIGHT,
            text_color=COLOR_TEXT,
            command=self._fab_pressed,
        )
        self.btn_play.pack(side='right')

        # 3. Main Adaptive Body (Smooth-Scrolling & Responsive)
        body = SmoothScrollableFrame(
            self,
            fg_color=COLOR_BG,
            scrollbar_fg_color='transparent',
            scrollbar_button_color=COLOR_BORDER,
            scrollbar_button_hover_color=COLOR_ACCENT,
            corner_radius=0,
        )
        body.pack(side='top', fill='both', expand=True, padx=16, pady=(0, 4))
        self.body = body

        def _on_window_configure(event):
            if event.widget == self:
                try:
                    if body._parent_canvas.yview() == (0.0, 1.0):
                        body._scrollbar.grid_remove()
                    else:
                        body._scrollbar.grid()
                except Exception:
                    pass

        self.bind('<Configure>', _on_window_configure)

        info_map = {
            'Folder': 'Directory containing your sheet .txt files',
            'Sheet': 'Active song sheet to play',
            'BPM': 'Beats per minute tempo',
            'Subdivision': 'Notes per beat (4 = quarter, 8 = eighth, …)',
            'Humanise %': '0% ⇒ Strict robot\n1–49% ⇒ Tight realism\n50–74% ⇒ Balanced feel\n75–100% ⇒ Expressive / loose',
            'Hold %': 'Key-down sustain fraction for each note',
            'Toggle key': 'Global hotkey to Start / Pause playback without delay',
            'Target': 'Window that must be active for notes to play',
            'Auto': 'Automatically pauses playback when the target window loses focus',
            'Note': 'Persistent metadata note stored directly inside the active sheet header',
        }

        # 1. Folder Selection
        f_top = ctk.CTkFrame(body, fg_color='transparent')
        f_top.pack(fill='x', pady=(1, 1))
        ctk.CTkLabel(f_top, text='Sheet Folder', font=FONT_LABEL_BOLD, text_color=COLOR_TEXT).pack(side='left')
        make_info_icon(f_top, info_map['Folder']).pack(side='left', padx=(4, 0))

        f_box = ctk.CTkFrame(body, fg_color='transparent')
        f_box.pack(fill='x', pady=(0, 4))
        self.var_folder = tk.StringVar(value=str(CFG.folder))
        self.entry_folder = ctk.CTkEntry(
            f_box,
            textvariable=self.var_folder,
            font=FONT_LABEL,
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            corner_radius=8,
            height=30,
        )
        self.entry_folder.pack(side='left', fill='x', expand=True, padx=(0, 6))
        add_focus_ring(self.entry_folder)

        self.btn_browse = ctk.CTkButton(
            f_box,
            text='Browse',
            width=76,
            height=30,
            font=FONT_LABEL_BOLD,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT,
            corner_radius=8,
            command=self._pick_folder,
        )
        self.btn_browse.pack(side='right')

        # 2. Sheet Dropdown & Online Integration
        s_top = ctk.CTkFrame(body, fg_color='transparent')
        s_top.pack(fill='x', pady=(2, 1))
        ctk.CTkLabel(s_top, text='Active Sheet', font=FONT_LABEL_BOLD, text_color=COLOR_TEXT).pack(side='left')
        make_info_icon(s_top, info_map['Sheet']).pack(side='left', padx=(4, 0))

        self.btn_online = ctk.CTkButton(
            s_top,
            text='🌐 Online Sheets',
            font=FONT_SUBTLE,
            width=110,
            height=22,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT,
            corner_radius=6,
            command=self._open_online_browser,
        )
        self.btn_online.pack(side='right')

        self.var_sheet = tk.StringVar()
        self.box_sheet = ctk.CTkComboBox(
            body,
            variable=self.var_sheet,
            values=[],
            state='readonly',
            font=FONT_LABEL,
            dropdown_font=FONT_LABEL,
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT,
            corner_radius=8,
            height=30,
            command=self._on_sheet_change,
        )
        self.box_sheet.pack(fill='x', pady=(0, 4))

        # 3. Two-Column Numeric Grid (BPM & Subdivision)
        num_grid = ctk.CTkFrame(body, fg_color='transparent')
        num_grid.pack(fill='x', pady=(1, 4))
        num_grid.columnconfigure(0, weight=1)
        num_grid.columnconfigure(1, weight=1)

        # BPM Column
        bpm_col = ctk.CTkFrame(num_grid, fg_color='transparent')
        bpm_col.grid(row=0, column=0, sticky='ew', padx=(0, 6))
        bpm_top = ctk.CTkFrame(bpm_col, fg_color='transparent')
        bpm_top.pack(fill='x')
        ctk.CTkLabel(bpm_top, text='BPM', font=FONT_LABEL_BOLD, text_color=COLOR_TEXT).pack(side='left')
        make_info_icon(bpm_top, info_map['BPM']).pack(side='left', padx=(4, 0))

        self.var_bpm = tk.StringVar(value=str(CFG.bpm))
        self.var_bpm.trace_add('write', lambda *_: self._timing_changed())
        self.entry_bpm = ctk.CTkEntry(
            bpm_col,
            textvariable=self.var_bpm,
            font=FONT_NUMERIC_BOLD,
            justify='center',
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            corner_radius=8,
            height=30,
        )
        self.entry_bpm.pack(fill='x', pady=(1, 0))
        self.entry_bpm.bind('<FocusOut>', lambda _e: self._on_bpm_commit())
        self.entry_bpm.bind('<Return>', lambda _e: self._on_bpm_commit())
        add_focus_ring(self.entry_bpm)

        # Subdivision Column
        sub_col = ctk.CTkFrame(num_grid, fg_color='transparent')
        sub_col.grid(row=0, column=1, sticky='ew', padx=(6, 0))
        sub_top = ctk.CTkFrame(sub_col, fg_color='transparent')
        sub_top.pack(fill='x')
        ctk.CTkLabel(sub_top, text='Subdivision', font=FONT_LABEL_BOLD, text_color=COLOR_TEXT).pack(side='left')
        make_info_icon(sub_top, info_map['Subdivision']).pack(side='left', padx=(4, 0))

        self.var_sub = tk.StringVar(value=str(CFG.subdiv))
        self.var_sub.trace_add('write', lambda *_: self._timing_changed())
        self.entry_sub = ctk.CTkEntry(
            sub_col,
            textvariable=self.var_sub,
            font=FONT_NUMERIC_BOLD,
            justify='center',
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            corner_radius=8,
            height=30,
        )
        self.entry_sub.pack(fill='x', pady=(1, 0))
        self.entry_sub.bind('<FocusOut>', lambda _e: self._on_sub_commit())
        self.entry_sub.bind('<Return>', lambda _e: self._on_sub_commit())
        add_focus_ring(self.entry_sub)

        # 4. Humanise Slider
        hum_top = ctk.CTkFrame(body, fg_color='transparent')
        hum_top.pack(fill='x', pady=(2, 1))
        ctk.CTkLabel(hum_top, text='Humanise %', font=FONT_LABEL_BOLD, text_color=COLOR_TEXT).pack(side='left')
        make_info_icon(hum_top, info_map['Humanise %']).pack(side='left', padx=(4, 0))

        hum_box = ctk.CTkFrame(body, fg_color='transparent')
        hum_box.pack(fill='x', pady=(0, 4))

        self.var_human = tk.IntVar(value=int(CFG.human * 100))
        self.var_human_txt = tk.StringVar(value=f"{self.var_human.get()}%")

        self.slider_human = ctk.CTkSlider(
            hum_box,
            from_=0,
            to=100,
            number_of_steps=100,
            variable=self.var_human,
            progress_color=COLOR_ACCENT,
            button_color=COLOR_THUMB,
            button_hover_color=COLOR_THUMB_HOVER,
            fg_color=COLOR_SURFACE_DARK,
            command=self._on_human_slider,
        )
        self.slider_human.pack(side='left', fill='x', expand=True, padx=(0, 8))

        self.badge_human = ctk.CTkEntry(
            hum_box,
            textvariable=self.var_human_txt,
            width=54,
            height=26,
            font=FONT_NUMERIC_BOLD,
            justify='center',
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            corner_radius=6,
        )
        self.badge_human.pack(side='right')
        self.badge_human.bind('<Return>', lambda _e: self._on_human_badge_commit())
        self.badge_human.bind('<FocusOut>', lambda _e: self._on_human_badge_commit())
        add_focus_ring(self.badge_human)

        # 5. Hold Slider
        hold_top = ctk.CTkFrame(body, fg_color='transparent')
        hold_top.pack(fill='x', pady=(2, 1))
        ctk.CTkLabel(hold_top, text='Hold %', font=FONT_LABEL_BOLD, text_color=COLOR_TEXT).pack(side='left')
        make_info_icon(hold_top, info_map['Hold %']).pack(side='left', padx=(4, 0))

        hold_box = ctk.CTkFrame(body, fg_color='transparent')
        hold_box.pack(fill='x', pady=(0, 4))

        self.var_hold = tk.IntVar(value=int(CFG.hold * 100))
        self.var_hold_txt = tk.StringVar(value=f"{self.var_hold.get()}%")

        self.slider_hold = ctk.CTkSlider(
            hold_box,
            from_=0,
            to=100,
            number_of_steps=100,
            variable=self.var_hold,
            progress_color=COLOR_ACCENT,
            button_color=COLOR_THUMB,
            button_hover_color=COLOR_THUMB_HOVER,
            fg_color=COLOR_SURFACE_DARK,
            command=self._on_hold_slider,
        )
        self.slider_hold.pack(side='left', fill='x', expand=True, padx=(0, 8))

        self.badge_hold = ctk.CTkEntry(
            hold_box,
            textvariable=self.var_hold_txt,
            width=54,
            height=26,
            font=FONT_NUMERIC_BOLD,
            justify='center',
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            corner_radius=6,
        )
        self.badge_hold.pack(side='right')
        self.badge_hold.bind('<Return>', lambda _e: self._on_hold_badge_commit())
        self.badge_hold.bind('<FocusOut>', lambda _e: self._on_hold_badge_commit())
        add_focus_ring(self.badge_hold)

        # 6. Toggle Key
        key_top = ctk.CTkFrame(body, fg_color='transparent')
        key_top.pack(fill='x', pady=(2, 1))
        ctk.CTkLabel(key_top, text='Toggle Key', font=FONT_LABEL_BOLD, text_color=COLOR_TEXT).pack(side='left')
        make_info_icon(key_top, info_map['Toggle key']).pack(side='left', padx=(4, 0))

        self.var_key = tk.StringVar(value=CFG.toggle)
        self.var_key.trace_add('write', lambda *_: self._toggle_key_changed())
        self.entry_key = ctk.CTkEntry(
            body,
            textvariable=self.var_key,
            font=FONT_NUMERIC_BOLD,
            width=110,
            height=28,
            justify='center',
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            corner_radius=8,
        )
        self.entry_key.pack(anchor='w', pady=(0, 4))
        add_focus_ring(self.entry_key)

        # 7. Note Textarea
        note_top = ctk.CTkFrame(body, fg_color='transparent')
        note_top.pack(fill='x', pady=(2, 1))
        ctk.CTkLabel(note_top, text='Sheet Note', font=FONT_LABEL_BOLD, text_color=COLOR_TEXT).pack(side='left')
        make_info_icon(note_top, info_map['Note']).pack(side='left', padx=(4, 0))

        self.txt_note = ctk.CTkTextbox(
            body,
            height=48,
            font=FONT_LABEL,
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            border_width=1,
            text_color=COLOR_TEXT,
            corner_radius=8,
        )
        self.txt_note.pack(fill='x', pady=(0, 4))
        self.txt_note.bind('<KeyRelease>', lambda _e: self._note_changed())
        add_focus_ring(self.txt_note)

        # 8. Target Window
        win_top = ctk.CTkFrame(body, fg_color='transparent')
        win_top.pack(fill='x', pady=(2, 1))
        ctk.CTkLabel(win_top, text='Target Window', font=FONT_LABEL_BOLD, text_color=COLOR_TEXT).pack(side='left')
        make_info_icon(win_top, info_map['Target']).pack(side='left', padx=(4, 0))

        self.var_win = tk.StringVar()
        self.box_win = ctk.CTkComboBox(
            body,
            variable=self.var_win,
            values=[],
            state='readonly',
            font=FONT_LABEL,
            dropdown_font=FONT_LABEL,
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT,
            corner_radius=8,
            height=30,
        )
        self.box_win.pack(fill='x', pady=(0, 4))
        self.box_win.bind('<Button-1>', lambda _e: self._refresh_windows())

        # 9. Modern Toggle Switch (Auto-play)
        sw_box = ctk.CTkFrame(body, fg_color='transparent')
        sw_box.pack(fill='x', pady=(3, 2))

        self.var_auto = tk.BooleanVar(value=CFG.auto_pause)
        self.switch_auto = ctk.CTkSwitch(
            sw_box,
            text='Auto-play when focused',
            variable=self.var_auto,
            font=FONT_LABEL,
            text_color=COLOR_TEXT,
            progress_color=COLOR_ACCENT,
            button_color=COLOR_THUMB,
            button_hover_color=COLOR_THUMB_HOVER,
            fg_color=COLOR_BORDER,
            command=self._toggle_auto,
        )
        self.switch_auto.pack(side='left')
        make_info_icon(sw_box, info_map['Auto']).pack(side='left', padx=(6, 0))

        # Load initial items
        self._refresh_sheets()
        self._refresh_windows()

    # Slider & Badge Callbacks
    def _on_human_slider(self, val):
        self.var_human_txt.set(f"{int(val)}%")
        self._expressiveness_changed()

    def _on_human_badge_commit(self):
        txt = self.var_human_txt.get().replace('%', '').strip()
        try:
            val = max(0, min(100, int(txt)))
            self.var_human.set(val)
            self.var_human_txt.set(f"{val}%")
            self._expressiveness_changed()
        except ValueError:
            self.var_human_txt.set(f"{self.var_human.get()}%")

    def _on_hold_slider(self, val):
        self.var_hold_txt.set(f"{int(val)}%")
        self._expressiveness_changed()

    def _on_hold_badge_commit(self):
        txt = self.var_hold_txt.get().replace('%', '').strip()
        try:
            val = max(0, min(100, int(txt)))
            self.var_hold.set(val)
            self.var_hold_txt.set(f"{val}%")
            self._expressiveness_changed()
        except ValueError:
            self.var_hold_txt.set(f"{self.var_hold.get()}%")

    # Sheet Metadata Storage
    def _store_current_meta(self):
        try:
            bpm = int(self.var_bpm.get()) if self.var_bpm.get().strip() else None
            subdiv = float(self.var_sub.get()) if self.var_sub.get().strip() else None
            note = self._get_note_text()
            if CFG.sheet:
                core.write_sheet_meta(CFG.sheet, bpm, subdiv, note)
        except ValueError:
            pass

    def _note_changed(self):
        self._store_current_meta()

    def _get_note_text(self) -> str:
        return self.txt_note.get('1.0', 'end-1c').strip()

    def _open_online_browser(self):
        OnlineSheetsDialog(self, CFG.folder, on_selected=self._on_online_sheet_selected)

    def _on_online_sheet_selected(self, sheet_file: Path):
        self._refresh_sheets()
        self.var_sheet.set(sheet_file.name)
        self._on_sheet_change(sheet_file.name)
        self.lbl_subtext.configure(text=f"Loaded: {sheet_file.stem}")

    def _pick_folder(self):
        d = filedialog.askdirectory(initialdir=CFG.folder)
        if d:
            CFG.folder = Path(d)
            self.var_folder.set(d)
            self._refresh_sheets()

    def _refresh_sheets(self):
        try:
            vals = [p.name for p in sorted(CFG.folder.glob('*.txt'))]
        except Exception:
            vals = []
        self.box_sheet.configure(values=vals)
        if vals:
            cur = self.var_sheet.get()
            if cur not in vals:
                selected = CFG.sheet.name if CFG.sheet and CFG.sheet.name in vals else vals[0]
                self.var_sheet.set(selected)
                self._on_sheet_change(selected)

    def _refresh_windows(self):
        vals = [t for _, t in core.windows()]
        self.box_win.configure(values=vals)

    def _on_sheet_change(self, choice=None):
        new_sheet = choice or self.var_sheet.get()
        if not new_sheet:
            return
        CFG.sheet = CFG.folder / new_sheet
        meta = core.read_sheet_meta(CFG.sheet)

        self._suspend_trace = True
        bpm_val = meta.get('bpm', 120)
        sub_val = meta.get('subdiv', 4.0)
        self.var_bpm.set(str(bpm_val))
        self.var_sub.set(str(sub_val))
        self._last_valid_bpm = bpm_val
        self._last_valid_sub = sub_val

        self.txt_note.delete('1.0', 'end')
        note = meta.get('note', '')
        if note:
            self.txt_note.insert('1.0', note)
        self._suspend_trace = False

        logger.info("Sheet loaded: '%s' (BPM: %s, Subdiv: %s)", new_sheet, bpm_val, sub_val)
        self._timing_changed()
        if self.player:
            self._stop_player()
            if self._apply_cfg():
                self._start_player()
        else:
            self._update_time(self._tok_done)

    def _flash_warning(self, widget):
        """Subtle non-intrusive visual warning flash on invalid inputs."""
        try:
            widget.configure(border_color='#FA5252')
            self.after(450, lambda: widget.configure(border_color=COLOR_BORDER))
        except Exception:
            pass

    def _on_bpm_commit(self):
        txt = self.var_bpm.get().strip()
        try:
            val = int(txt)
            if val <= 0:
                raise ValueError("BPM must be greater than 0")
            if val > 1200:
                raise ValueError("BPM exceeds maximum safe limit")
            self._last_valid_bpm = val
            CFG.bpm = val
            self._store_current_meta()
            self._update_time(self._tok_done)
        except (ValueError, TypeError) as err:
            logger.warning("Invalid BPM '%s'. Reverting to %s. (%s)", txt, self._last_valid_bpm, err)
            self._flash_warning(self.entry_bpm)
            self._suspend_trace = True
            self.var_bpm.set(str(self._last_valid_bpm))
            self._suspend_trace = False

    def _on_sub_commit(self):
        txt = self.var_sub.get().strip()
        try:
            val = float(txt)
            if val <= 0:
                raise ValueError("Subdivision must be greater than 0")
            if val > 64:
                raise ValueError("Subdivision exceeds maximum limit")
            self._last_valid_sub = val
            CFG.subdiv = val
            self._store_current_meta()
            self._update_time(self._tok_done)
        except (ValueError, TypeError) as err:
            logger.warning("Invalid Subdivision '%s'. Reverting to %s. (%s)", txt, self._last_valid_sub, err)
            self._flash_warning(self.entry_sub)
            self._suspend_trace = True
            self.var_sub.set(str(self._last_valid_sub))
            self._suspend_trace = False

    def _timing_changed(self):
        if self._suspend_trace:
            return
        bpm_txt = self.var_bpm.get().strip()
        sub_txt = self.var_sub.get().strip()
        try:
            b_val = int(bpm_txt)
            if b_val > 0:
                CFG.bpm = b_val
                self._last_valid_bpm = b_val
        except ValueError:
            pass

        try:
            s_val = float(sub_txt)
            if s_val > 0:
                CFG.subdiv = s_val
                self._last_valid_sub = s_val
        except ValueError:
            pass

        self._store_current_meta()
        self._update_time(self._tok_done)

    def _expressiveness_changed(self):
        try:
            CFG.human = self.var_human.get() / 100.0
            CFG.hold = self.var_hold.get() / 100.0
        except ValueError:
            pass

    def _toggle_key_changed(self):
        txt = self.var_key.get().strip()
        try:
            combo = parse_combo(txt)
            if combo:
                CFG.toggle = txt
                self.toggle_combo = combo
                self._pressed.clear()
                self._hotkey_active = False
        except Exception:
            pass

    def _toggle_auto(self):
        if self.var_auto.get() and not self.var_win.get().strip():
            messagebox.showwarning('Target window required', 'Select a target window before enabling Auto-play.')
            self.var_auto.set(False)
            return
        CFG.auto_pause = self.var_auto.get()

    def _apply_cfg(self) -> bool:
        try:
            CFG.human = self.var_human.get() / 100.0
            CFG.hold = self.var_hold.get() / 100.0
            CFG.toggle = self.var_key.get()
            CFG.folder = Path(self.var_folder.get())
            if self.var_sheet.get():
                CFG.sheet = CFG.folder / self.var_sheet.get()
            self.toggle_combo = parse_combo(CFG.toggle)
            win_txt = self.var_win.get().strip()
            CFG.target_title = win_txt if win_txt else None

            if self.var_auto.get() and not CFG.target_title:
                messagebox.showwarning('Target window required', 'Auto-play is enabled but no target window selected.')
                return False

            self._store_current_meta()
            return True
        except Exception as exc:
            messagebox.showerror('Config error', str(exc))
            return False

    def _start_player(self):
        self.total_tokens = 0
        self._tok_done = 0
        self.prog.set(0.0)
        if not CFG.sheet or not CFG.sheet.exists():
            messagebox.showwarning('Sheet required', 'Please select a valid sheet file.')
            return
        logger.info("Starting player for '%s' (BPM: %s, Subdiv: %s)...", CFG.sheet.name, CFG.bpm, CFG.subdiv)
        self.player = core.Player(CFG.sheet, self.queue)
        self.player.start()
        self._update_fab_icon()

    def _stop_player(self):
        if self.player:
            logger.info("Stopping player thread.")
            self.player.stop()
            self.player = None
            self._update_fab_icon()
            self.lbl_visualizer.configure(text='NOTE: --', text_color=COLOR_TEXT_MUTED)

    def _fab_pressed(self):
        if self.player and not self.player.is_alive():
            self._stop_player()

        if not self.player:
            if not self._apply_cfg():
                return
            self._start_player()
        else:
            self.player.toggle()
            self._update_fab_icon()

    def _update_fab_icon(self):
        is_playing = self.player and self.player.resume_evt.is_set()
        self.btn_play.configure(text='⏸' if is_playing else '▶')
        if self.player:
            if is_playing:
                self.status_pill.configure(text='PLAYING', text_color='#51CF66')
                self.lbl_subtext.configure(text='Playing active song')
            else:
                self.status_pill.configure(text='PAUSED', text_color='#FF922B')
                self.lbl_subtext.configure(text='Paused (press hotkey to resume)')
                self.lbl_visualizer.configure(text='NOTE: (PAUSED)', text_color='#FF922B')
        else:
            self.status_pill.configure(text='IDLE', text_color=COLOR_TEXT_MUTED)
            self.lbl_subtext.configure(text='Ready to play')
            self.lbl_visualizer.configure(text='NOTE: --', text_color=COLOR_TEXT_MUTED)

    def _hk_press(self, k):
        norm_k = normalize_key(k)
        if not norm_k:
            return

        self._pressed.add(norm_k)

        if self.toggle_combo and self.toggle_combo.issubset(self._pressed):
            if not self._hotkey_active:
                now = time.monotonic()
                if now - self._last_hotkey_time >= 0.25:
                    self._hotkey_active = True
                    self._last_hotkey_time = now
                    logger.info("Hotkey combination triggered (%s).", CFG.toggle)
                    self.after(0, self._fab_pressed)

    def _hk_release(self, k):
        norm_k = normalize_key(k)
        if norm_k:
            self._pressed.discard(norm_k)

        if self.toggle_combo and not self.toggle_combo.issubset(self._pressed):
            self._hotkey_active = False

    def _poll(self):
        try:
            while True:
                tag, d = self.queue.get_nowait()
                if tag == 'total':
                    self.total_tokens = d[0] if isinstance(d, tuple) else d
                    self.prog.set(0.0)
                elif tag == 'progress':
                    if isinstance(d, (tuple, list)):
                        self._tok_done = d[0]
                        tok = d[1] if len(d) > 1 else None
                    else:
                        self._tok_done = d
                        tok = None

                    frac = (self._tok_done / self.total_tokens) if self.total_tokens else 0.0
                    self.prog.set(max(0.0, min(1.0, frac)))
                    self._update_time(self._tok_done)

                    if tok is not None:
                        if isinstance(tok, list):
                            chord_str = ''.join(tok)
                            self.lbl_visualizer.configure(text=f"NOTE: [{chord_str}]", text_color='#51CF66')
                        elif tok == '|':
                            self.lbl_visualizer.configure(text="NOTE: | (rest)", text_color='#FF922B')
                        else:
                            self.lbl_visualizer.configure(text=f"NOTE: '{tok}'", text_color='#74C0FC')
                elif tag == 'done':
                    logger.info("Song playback finished.")
                    self._stop_player()
                    self.prog.set(1.0)
                    self._update_time(self.total_tokens)
                    self.lbl_visualizer.configure(text='NOTE: --', text_color=COLOR_TEXT_MUTED)
                elif tag == 'error':
                    logger.error("Playback error: %s", d)
                    self._stop_player()
                    self.lbl_visualizer.configure(text='NOTE: --', text_color=COLOR_TEXT_MUTED)
                    messagebox.showerror('Playback error', str(d))
        except Empty:
            pass
        self.after(50, self._poll)

    def _update_time(self, done_tok=0):
        if not self.total_tokens:
            self.lbl_time.configure(text='00:00 / 00:00')
            return
        sec_done = done_tok * CFG.sec_per_tok()
        sec_tot = self.total_tokens * CFG.sec_per_tok()
        fmt = lambda s: f"{int(s // 60):02d}:{int(s % 60):02d}"
        self.lbl_time.configure(text=f"{fmt(sec_done)} / {fmt(sec_tot)}")

    def destroy(self):
        self._store_current_meta()
        self._stop_player()
        try:
            w = self.winfo_width()
            h = self.winfo_height()
            if w >= 400 and h >= 500:
                CFG.geometry = f"{w}x{h}"
        except Exception:
            pass
        core.save_cfg()
        super().destroy()


if __name__ == '__main__':
    app = App()
    app.mainloop()
