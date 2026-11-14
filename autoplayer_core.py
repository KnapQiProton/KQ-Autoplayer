"""
Virtual-/Roblox-Piano Autoplayer – density- & Shift-aware humaniser
KQ Autoplayer Core Engine with Hardware-Level Win32 SendInput & Advanced Humanisation.

Features:
• STEALTH_MODE: Low-level Win32 SendInput using hardware scancodes to avoid Roblox (Byfron/Hyperion) macro detection.
• Left-to-right keyboard physical column sorting for natural piano chord strumming.
• Micro-delay arpeggiation (10–30ms) for realistic multi-finger note strikes.
• Density-adaptive timing, human drift, and accidental miss/slip simulation.
• Logging integration across all core player events.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from pathlib import Path
from queue import Queue
from typing import Dict, List, Optional, Tuple
import ctypes
from ctypes import wintypes
import json
import logging
import math
import random
import sys
import threading
import time
import win32gui
from pynput.keyboard import Controller, Key

__all__ = [
    'CFG',
    'Config',
    'save_cfg',
    'windows',
    'Player',
    'press',
    'release',
    'win32_press',
    'win32_release',
    'char_to_vk_info',
    'SHIFT_MAP',
    'KEYBOARD_COLUMNS',
    'read_sheet_meta',
    'write_sheet_meta',
    'logger',
]

# --- Logging Initialization ---
logger = logging.getLogger('KQAutoplayer.Core')
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(
        logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s', datefmt='%H:%M:%S')
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

DATA_FILE = Path(__file__).with_name('vp_autoplayer.json')

# --- Win32 Hardware-Level SendInput Definitions ---
user32 = ctypes.WinDLL('user32', use_last_error=True)

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
MAPVK_VK_TO_VSC = 0
VK_SHIFT = 0x10


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong)
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong)
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD)
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT)
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", _INPUT_UNION)
    ]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


# --- Sheet Notation Shift & OEM Mappings ---
SHIFT_MAP: Dict[str, str] = {
    '!': '1',
    '@': '2',
    '#': '3',
    '$': '4',
    '%': '5',
    '^': '6',
    '&': '7',
    '*': '8',
    '(': '9',
    ')': '0',
    '_': '-',
    '+': '=',
    '{': '[',
    '}': ']',
    ':': ';',
    '"': "'",
    '<': ',',
    '>': '.',
    '?': '/',
    '~': '`',
}

SHIFT_REV: Dict[str, str] = {v: k for k, v in SHIFT_MAP.items()}

OEM_MAP: Dict[str, int] = {
    ' ': 0x20,  # Spacebar (Virtual Key code for Sustain Pedal)
    '-': 0xBD,
    '=': 0xBB,
    '[': 0xDB,
    ']': 0xDD,
    ';': 0xBA,
    "'": 0xDE,
    ',': 0xBC,
    '.': 0xBE,
    '/': 0xBF,
    '`': 0xC0,
}

NEIGHBOURS: Dict[str, List[str]] = {
    'a': ['s', 'q', 'w', 'z'],
    's': ['a', 'd', 'w', 'e', 'x', 'z'],
    'd': ['s', 'f', 'e', 'r', 'c', 'x'],
    'f': ['d', 'g', 'r', 't', 'v', 'c'],
    'g': ['f', 'h', 't', 'y', 'b', 'v'],
    'h': ['g', 'j', 'y', 'u', 'n', 'b'],
    'j': ['h', 'k', 'u', 'i', 'm', 'n'],
    'k': ['j', 'l', 'i', 'o', ',', 'm'],
    'l': ['k', 'o', 'p', '.'],
    'q': ['w', 'a'],
    'w': ['q', 'e', 's', 'a'],
    'e': ['w', 'r', 'd', 's'],
    'r': ['e', 't', 'f', 'd'],
    't': ['r', 'y', 'g', 'f'],
    'y': ['t', 'u', 'h', 'g'],
    'u': ['y', 'i', 'j', 'h'],
    'i': ['u', 'o', 'k', 'j'],
    'o': ['i', 'p', 'l', 'k'],
    'p': ['o', 'l'],
}

# Approximate physical column X-position on standard ANSI QWERTY (left to right)
KEYBOARD_COLUMNS: Dict[str, float] = {
    # Row 1 (Number row)
    '`': 0.0, '~': 0.0,
    '1': 1.0, '!': 1.0,
    '2': 2.0, '@': 2.0,
    '3': 3.0, '#': 3.0,
    '4': 4.0, '$': 4.0,
    '5': 5.0, '%': 5.0,
    '6': 6.0, '^': 6.0,
    '7': 7.0, '&': 7.0,
    '8': 8.0, '*': 8.0,
    '9': 9.0, '(': 9.0,
    '0': 10.0, ')': 10.0,
    '-': 11.0, '_': 11.0,
    '=': 12.0, '+': 12.0,

    # Row 2 (Tab row)
    'q': 1.5, 'Q': 1.5,
    'w': 2.5, 'W': 2.5,
    'e': 3.5, 'E': 3.5,
    'r': 4.5, 'R': 4.5,
    't': 5.5, 'T': 5.5,
    'y': 6.5, 'Y': 6.5,
    'u': 7.5, 'U': 7.5,
    'i': 8.5, 'I': 8.5,
    'o': 9.5, 'O': 9.5,
    'p': 10.5, 'P': 10.5,
    '[': 11.5, '{': 11.5,
    ']': 12.5, '}': 12.5,

    # Row 3 (Home row)
    'a': 1.75, 'A': 1.75,
    's': 2.75, 'S': 2.75,
    'd': 3.75, 'D': 3.75,
    'f': 4.75, 'F': 4.75,
    'g': 5.75, 'G': 5.75,
    'h': 6.75, 'H': 6.75,
    'j': 7.75, 'J': 7.75,
    'k': 8.75, 'K': 8.75,
    'l': 9.75, 'L': 9.75,
    ';': 10.75, ':': 10.75,
    "'": 11.75, '"': 11.75,

    # Row 4 (Bottom row)
    'z': 2.25, 'Z': 2.25,
    'x': 3.25, 'X': 3.25,
    'c': 4.25, 'C': 4.25,
    'v': 5.25, 'V': 5.25,
    'b': 6.25, 'B': 6.25,
    'n': 7.25, 'N': 7.25,
    'm': 8.25, 'M': 8.25,
    ',': 9.25, '<': 9.25,
    '.': 10.25, '>': 10.25,
    '/': 11.25, '?': 11.25,
}

KB = Controller()


def char_to_vk_info(ch: str) -> tuple[int | None, bool]:
    """Map piano notation character to Windows Virtual Key code and Shift state."""
    if not ch:
        return (None, False)

    if ch.isdigit():
        return (0x30 + int(ch), False)
    if ch.isalpha():
        return (0x41 + (ord(ch.upper()) - ord('A')), ch.isupper())
    if ch in SHIFT_MAP:
        base = SHIFT_MAP[ch]
        if base.isdigit():
            return (0x30 + int(base), True)
        if base in OEM_MAP:
            return (OEM_MAP[base], True)
    if ch in OEM_MAP:
        return (OEM_MAP[ch], False)
    return (None, False)


def send_win32_key(vk: int, is_up: bool) -> bool:
    """Send low-level hardware scan code key event using Windows user32.SendInput."""
    try:
        scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
        flags = KEYEVENTF_SCANCODE
        if is_up:
            flags |= KEYEVENTF_KEYUP

        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wVk = vk
        inp.union.ki.wScan = scan
        inp.union.ki.dwFlags = flags
        inp.union.ki.time = 0
        inp.union.ki.dwExtraInfo = 0

        res = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        return res == 1
    except Exception as exc:
        logger.debug("SendInput exception for VK 0x%02X: %s", vk, exc)
        return False


def win32_press(ch: str) -> bool:
    """Press key using low-level Win32 hardware scancode (anti-cheat stealth mode)."""
    vk, needs_shift = char_to_vk_info(ch)
    if vk is None:
        return False
    if needs_shift:
        send_win32_key(VK_SHIFT, False)
    send_win32_key(vk, False)
    return True


def win32_release(ch: str) -> bool:
    """Release key using low-level Win32 hardware scancode."""
    vk, needs_shift = char_to_vk_info(ch)
    if vk is None:
        return False
    send_win32_key(vk, True)
    if needs_shift:
        send_win32_key(VK_SHIFT, True)
    return True


def read_sheet_meta(path: Path) -> dict:
    """
    Return dict from first non-blank line that starts with “#META”.
    May include 'bpm', 'subdiv', and optional 'note'.
    """
    try:
        with path.open('r', encoding='utf-8') as f:
            for line in f:
                line_s = line.strip()
                if not line_s:
                    continue
                if line_s.startswith('#META'):
                    return json.loads(line.split(None, 1)[1])
        return {}
    except Exception:
        return {}


def write_sheet_meta(
    path: Path,
    bpm: int | None = None,
    subdiv: float | None = None,
    note: str | None = None,
) -> None:
    """
    Update the #META line at the top of *path*.
    Any argument left as None keeps its previous value.
    """
    try:
        meta = read_sheet_meta(path)
        if bpm is not None:
            meta['bpm'] = bpm
        if subdiv is not None:
            meta['subdiv'] = subdiv
        if note is not None:
            meta['note'] = note

        header = f"#META {json.dumps(meta, ensure_ascii=False)}"
        lines = path.read_text('utf-8').splitlines()
        if lines and lines[0].lstrip().startswith('#META'):
            lines[0] = header
        else:
            lines.insert(0, header)
        path.write_text('\n'.join(lines), 'utf-8')
    except Exception as exc:
        logger.error("Failed to write sheet metadata: %s", exc)


@dataclass
class Config:
    folder: Path = Path.cwd()
    sheet: Path | None = None
    bpm: int = 120
    subdiv: float = 4.0
    human: float = 0.3
    hold: float = 0.8
    toggle: str = 'f4'
    auto_pause: bool = True
    dark: bool = False
    stealth_mode: bool = True  # STEALTH_MODE (Low-level Win32 hardware SendInput)
    use_sustain: bool = False   # Sustain Pedal Simulation (Spacebar hold/damping)
    target_title: Optional[str] = field(default=None, repr=False)
    geometry: str | None = None

    def sec_per_tok(self) -> float:
        return 60.0 / (self.bpm * self.subdiv)


CFG = Config()

if DATA_FILE.exists():
    try:
        raw = json.loads(DATA_FILE.read_text('utf-8'))
        for k, v in raw.items():
            setattr(CFG, k, Path(v) if k in ('folder', 'sheet') and v is not None else v)
    except Exception as exc:
        logger.warning("Failed to load settings file: %s", exc)


def save_cfg() -> None:
    try:
        data = asdict(CFG)
        for k, v in data.items():
            if isinstance(v, Path):
                data[k] = str(v)
        DATA_FILE.write_text(json.dumps(data, indent=2), 'utf-8')
    except Exception as exc:
        logger.warning("Failed to save settings file: %s", exc)


def press(ch: str) -> None:
    """
    Press a character key.
    Uses Win32 SendInput (stealth hardware scancode) when CFG.stealth_mode is True,
    falling back seamlessly to pynput if needed.
    """
    if CFG.stealth_mode:
        if win32_press(ch):
            return

    # Fallback / Non-stealth Controller
    if ch in SHIFT_MAP:
        KB.press(Key.shift)
        KB.press(SHIFT_MAP[ch])
        return
    if ch.isupper():
        KB.press(Key.shift)
        KB.press(ch.lower())
        return
    KB.press(ch)


def release(ch: str) -> None:
    """Release a character key."""
    if CFG.stealth_mode:
        if win32_release(ch):
            return

    # Fallback / Non-stealth Controller
    if ch in SHIFT_MAP:
        KB.release(SHIFT_MAP[ch])
        KB.release(Key.shift)
        return
    if ch.isupper():
        KB.release(ch.lower())
        KB.release(Key.shift)
        return
    KB.release(ch)


def windows() -> list[Tuple[int, str]]:
    out = []

    def _enum(h, _):
        if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h):
            out.append((h, win32gui.GetWindowText(h)))

    win32gui.EnumWindows(_enum, None)
    return sorted(out, key=lambda t: t[1].lower())


class Player(threading.Thread):
    def __init__(self, sheet: Path, queue: Queue, playlist: list[Path] | None = None):
        super().__init__(daemon=True)
        self.sheet = sheet
        self.q = queue
        self.playlist = playlist if playlist else [sheet]
        self.current_playlist_index = 0
        self.resume_evt = threading.Event()
        self.resume_evt.set()
        self.stop_evt = threading.Event()
        self._last_token_time = time.time()
        self._last_shift_needed = False
        self._sustain_held = False

    def toggle(self) -> None:
        if self.resume_evt.is_set():
            self.resume_evt.clear()
            logger.info("Playback paused by user.")
        else:
            self.resume_evt.set()
            logger.info("Playback resumed by user.")

    def stop(self) -> None:
        self.stop_evt.set()
        logger.info("Playback stopped.")

    def _human_strength(self) -> float:
        h = CFG.human * 100
        if h == 0:
            return 0.0
        if h <= 50:
            return 0.3 * (h / 50.0)
        if h <= 75:
            return 0.3 + 0.3 * (h - 50.0) / 25.0
        return 0.6 + 0.4 * (h - 75.0) / 25.0

    def _params(self, dens: float):
        s = self._human_strength()
        if s == 0:
            return (0, 0, 0, 0, 0, 0, 0)
        σ = 0.12 * (s ** 2)
        span = 0.08 * (s ** 2)
        drift = 0.2 * (s ** 2)
        hold_jit = 1.2 * (s ** 2)
        hi = max(0.0, (CFG.human * 100 - 75.0) / 25.0)
        p_drop = 0.4 * (hi ** 2)
        p_slip = 0.1 * (hi ** 3)
        p_shift = 0.25 * (hi ** 2)
        factor = 0.3 + 0.7 * dens
        return (σ, span, drift, hold_jit, p_drop * factor, p_slip * factor, p_shift * factor)

    @staticmethod
    def _tokenise(txt: str):
        for line in txt.splitlines():
            if line.lstrip().startswith('#'):
                continue
            i = 0
            while i < len(line):
                if line[i] == '[':
                    chord = []
                    i += 1
                    while i < len(line) and line[i] != ']':
                        if not line[i].isspace() and (line[i].isalnum() or line[i] in SHIFT_MAP):
                            chord.append(line[i])
                        i += 1
                    if chord:
                        yield chord
                elif line[i].isspace():
                    pass
                else:
                    yield line[i]
                i += 1

    def _needs_shift(self, tok) -> bool:
        if isinstance(tok, list):
            return any(t in SHIFT_MAP or t.isupper() for t in tok)
        return tok in SHIFT_MAP or tok.isupper()

    def _neighbour(self, ch: str) -> str:
        return random.choice(NEIGHBOURS.get(ch.lower(), list(NEIGHBOURS.keys())))

    @staticmethod
    def _window_matches(target: str, current: str) -> bool:
        if not target or not current:
            return False
        t_low, c_low = target.lower().strip(), current.lower().strip()
        return t_low == c_low or t_low in c_low or c_low in t_low

    def run(self) -> None:
        try:
            if CFG.use_sustain:
                press(' ')
                self._sustain_held = True
                logger.info("Sustain pedal engaged (Spacebar).")

            while self.current_playlist_index < len(self.playlist):
                self.sheet = self.playlist[self.current_playlist_index]
                if self.stop_evt.is_set():
                    break

                logger.info(
                    "Starting playback of '%s' (Track %d/%d, Stealth: %s, Sustain: %s)...",
                    self.sheet.name,
                    self.current_playlist_index + 1,
                    len(self.playlist),
                    CFG.stealth_mode,
                    CFG.use_sustain,
                )

                raw = self.sheet.read_text('utf-8')
                toks = list(self._tokenise(raw))
                total = len(toks)
                self.q.put(('total', total))
                t0 = time.time()
                self._last_token_time = time.time()

                for idx, tok in enumerate(toks, 1):
                    if self.stop_evt.is_set():
                        break

                    now = time.time()
                    ios = now - self._last_token_time
                    self._last_token_time = now
                    density = max(0.0, min(1.0, (0.15 - ios) / 0.1))
                    (σ, span, drift, h_jit, p_drop, p_slip, p_shift) = self._params(density)
                    robot = (σ == 0)

                    if self._last_shift_needed and isinstance(tok, str) and tok in SHIFT_REV and random.random() < p_shift:
                        tok = SHIFT_REV[tok]

                    slipped = False
                    if p_drop and random.random() < p_drop:
                        self.q.put(('progress', (idx, tok)))
                        self._last_shift_needed = False
                        continue

                    if p_slip and isinstance(tok, str) and random.random() < p_slip:
                        tok = self._neighbour(tok)
                        slipped = True

                    sec = CFG.sec_per_tok() * (1 + drift * math.sin(2 * math.pi * 0.25 * (time.time() - t0)))
                    onset_off = random.gauss(0, σ) if σ > 0 else 0.0

                    # Window focus check & pause loop
                    was_paused = False
                    while (not self.resume_evt.is_set()) or (
                        CFG.auto_pause
                        and CFG.target_title
                        and not self._window_matches(CFG.target_title, win32gui.GetWindowText(win32gui.GetForegroundWindow()))
                    ):
                        if self.stop_evt.is_set():
                            break
                        if CFG.use_sustain and self._sustain_held:
                            release(' ')
                            self._sustain_held = False
                            was_paused = True
                        time.sleep(0.015)

                    if self.stop_evt.is_set():
                        break

                    if was_paused and CFG.use_sustain and not self._sustain_held:
                        press(' ')
                        self._sustain_held = True

                    if onset_off > 0:
                        time.sleep(onset_off)

                    # Play token
                    if tok == '|':
                        # Rest notation / bar line (pedal damping if sustain enabled)
                        if CFG.use_sustain and self._sustain_held:
                            release(' ')
                            self._sustain_held = False
                            damp_time = min(sec, 0.080)
                            time.sleep(damp_time)
                            press(' ')
                            self._sustain_held = True
                            time.sleep(max(0.0, sec - damp_time))
                        else:
                            time.sleep(sec)
                    elif isinstance(tok, list):
                        # Sort notes in chord by physical keyboard columns (left to right)
                        sorted_tok = sorted(tok, key=lambda ch: KEYBOARD_COLUMNS.get(ch, 99.0))

                        if robot:
                            for n in sorted_tok:
                                press(n)
                            hold_len = max(0.06, CFG.hold * sec)
                            time.sleep(hold_len)
                            for n in reversed(sorted_tok):
                                release(n)
                            time.sleep(max(0.0, sec - hold_len))
                        else:
                            base = time.perf_counter()
                            # Humanized sequential micro-delays (10–30ms strumming / arpeggiation)
                            for i, n in enumerate(sorted_tok):
                                press(n)
                                if i < len(sorted_tok) - 1:
                                    time.sleep(random.uniform(0.010, 0.030))

                            hold_var = 1 + random.uniform(-h_jit, h_jit)
                            main_hold = max(0.06, sec * CFG.hold * hold_var)
                            elapsed = time.perf_counter() - base
                            time.sleep(max(0.0, main_hold - elapsed))

                            # Release notes
                            for n in reversed(sorted_tok):
                                release(n)
                            time.sleep(max(0.0, sec - (time.perf_counter() - base)))
                    else:
                        press(tok)
                        hold_var = (1 + random.uniform(-h_jit, h_jit)) if not robot else 1.0
                        hold_len = max(0.06, CFG.hold * sec * hold_var)
                        time.sleep(hold_len + max(0.0, onset_off))
                        release(tok)
                        time.sleep(max(0.0, sec - hold_len - max(0.0, onset_off)))

                    if onset_off < 0:
                        time.sleep(-onset_off)

                    # Emit progress with current token for real-time visualizer
                    self.q.put(('progress', (idx, tok)))
                    self._last_shift_needed = self._needs_shift(tok)

                    if slipped and random.random() < 0.2:
                        time.sleep(random.uniform(0.3, 0.6))

                if self.stop_evt.is_set():
                    break

                logger.info("Track '%s' completed.", self.sheet.name)

                # Playlist progression logic
                if self.current_playlist_index < len(self.playlist) - 1:
                    self.current_playlist_index += 1
                    next_sheet = self.playlist[self.current_playlist_index]
                    self.sheet = next_sheet
                    logger.info("Advancing to next playlist song: %s", next_sheet.name)
                    self.q.put(('playlist_next', next_sheet.name))
                    if CFG.use_sustain and self._sustain_held:
                        release(' ')
                        time.sleep(0.080)
                        press(' ')
                    time.sleep(1.0)
                else:
                    self.q.put(('done', 1))
                    logger.info("All tracks in playlist completed successfully.")
                    break
        except Exception as exc:
            logger.exception("Playback exception encountered: %s", exc)
            self.q.put(('error', str(exc)))
        finally:
            if self._sustain_held:
                try:
                    release(' ')
                    self._sustain_held = False
                    logger.info("Sustain pedal released on finish/stop.")
                except Exception as exc:
                    logger.debug("Error releasing sustain pedal in finally: %s", exc)
