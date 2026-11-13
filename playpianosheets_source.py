"""
PlayPianoSheets.com Online Sheet Integration for KQ Autoplayer.

Allows searching, browsing, and 1-click downloading of 1,800+ sheets
from https://playpianosheets.com/ into the local sheets library.
"""
from __future__ import annotations

import re
import socket
import threading
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

# Color Palette matching KQ Autoplayer tech-minimalist dark theme
COLOR_BG = '#343A40'
COLOR_SURFACE = '#2B3035'
COLOR_SURFACE_DARK = '#212529'
COLOR_TEXT = '#F8F9FA'
COLOR_TEXT_MUTED = '#8E959D'
COLOR_TEXT_HOVER = '#CED4DA'
COLOR_ACCENT = '#406185'
COLOR_ACCENT_HOVER = '#334D6B'
COLOR_BORDER = '#495057'

FONT_TITLE = ('Segoe UI', 14, 'bold')
FONT_LABEL = ('Segoe UI', 12)
FONT_LABEL_BOLD = ('Segoe UI', 12, 'bold')
FONT_SUBTLE = ('Segoe UI', 10)
FONT_NUMERIC = ('Consolas', 11)
FONT_NUMERIC_BOLD = ('Consolas', 11, 'bold')


def check_internet(timeout: float = 2.0) -> bool:
    """Ultra-fast non-blocking internet connectivity check."""
    try:
        # Fast DNS probe (Cloudflare DNS)
        socket.create_connection(('1.1.1.1', 53), timeout=timeout).close()
        return True
    except OSError:
        try:
            req = urllib.request.Request('https://playpianosheets.com', headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status == 200
        except Exception:
            return False


def slug_to_title(slug: str) -> str:
    """Format hyphenated slug into readable title casing."""
    parts = slug.split('-')
    return ' '.join(p.capitalize() for p in parts)


def fetch_playpianosheets_catalog() -> list[str]:
    """Fetch complete catalog of song slugs from playpianosheets.com sitemap."""
    url = 'https://playpianosheets.com/sitemap.xml'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = resp.read().decode('utf-8', errors='ignore')
    slugs = re.findall(r'<loc>https://playpianosheets\.com/sheets/([^<]+)</loc>', data)
    return slugs


def download_playpianosheet(slug_or_url: str, output_dir: Path) -> tuple[Path, str]:
    """
    Download sheet notation from playpianosheets.com, format it with metadata,
    and save it as a ready-to-play .txt sheet in output_dir.
    """
    slug = slug_or_url.strip().lower()
    if 'playpianosheets.com/sheets/' in slug:
        slug = slug.split('playpianosheets.com/sheets/')[-1].split('/')[0].split('?')[0]
    elif slug.startswith('http'):
        slug = slug.rstrip('/').split('/')[-1]

    url = f'https://playpianosheets.com/sheets/{slug}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    with urllib.request.urlopen(req, timeout=12) as resp:
        html = resp.read().decode('utf-8', errors='ignore')

    # Song title
    h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
    title = re.sub(r'<[^>]+>', '', h1.group(1)).strip() if h1 else slug_to_title(slug)

    # Full title & artist details
    title_tag = re.search(r'<title>(.*?) Roblox Piano Sheet</title>', html)
    header_info = title_tag.group(1) if title_tag else title

    # React Server Component stream extraction
    pushes = re.findall(r'self\.__next_f\.push\(\[1,\s*\"(.*?)\"\]\)', html, re.DOTALL)
    full_text = ''
    for p in pushes:
        decoded = p.encode('utf-8').decode('unicode_escape', errors='ignore')
        full_text += decoded

    sheet_music = None
    matches = re.finditer(r'\d+:T([0-9a-fA-F]+),', full_text)
    for m in matches:
        hex_len = m.group(1)
        length = int(hex_len, 16)
        start = m.end()
        text = full_text[start:start + length]
        if any(f'[{c}' in text for c in 'abcdefghijklmnopqrstuvwxyz0123456789'):
            sheet_music = text
            break

    # Fallback: extract from token spans
    if not sheet_music:
        tokens = re.findall(r'<span id="token-\d+"[^>]*>(.*?)</span>', html)
        if tokens:
            sheet_music = ' '.join(tokens)

    if not sheet_music:
        raise ValueError(f"Could not extract sheet notes from {url}")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize Windows file name
    safe_title = re.sub(r'[<>:"/\\|?*]', '', title).strip()
    out_file = output_dir / f"{safe_title}.txt"

    # Meta header compatible with VP/KQ Autoplayer
    meta_line = f'#META {{"bpm": 120, "subdiv": 4.0, "note": "Source: playpianosheets.com/sheets/{slug} | {header_info}"}}\n'
    out_file.write_text(meta_line + sheet_music.strip() + '\n', encoding='utf-8')
    return out_file, title


class SmoothScrollableFrame(ctk.CTkScrollableFrame):
    """
    Enhanced CTkScrollableFrame with synchronous redraw, solid background,
    and anti-ghosting smooth scroll engine for Windows.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._target_scroll = 0.0
        self._is_animating = False

    def _mouse_wheel_all(self, event):
        if not self._check_if_valid_scroll(event.widget):
            return

        yview = self._parent_canvas.yview()
        if yview == (0.0, 1.0):
            return

        delta = event.delta
        # Invert for Windows: positive delta is scroll UP (negative y offset)
        scroll_delta = - (delta / 120.0) * 44.0
        self._target_scroll += scroll_delta

        # Clamp target to prevent boundary pile-up
        if yview[0] <= 0.0 and self._target_scroll < 0:
            self._target_scroll = 0.0
        elif yview[1] >= 1.0 and self._target_scroll > 0:
            self._target_scroll = 0.0

        if not self._is_animating and abs(self._target_scroll) > 0.5:
            self._is_animating = True
            self._smooth_step()

    def _smooth_step(self):
        yview = self._parent_canvas.yview()
        if (yview[0] <= 0.0 and self._target_scroll < 0) or (yview[1] >= 1.0 and self._target_scroll > 0):
            self._target_scroll = 0.0
            self._is_animating = False
            return

        if abs(self._target_scroll) > 0.8:
            step = self._target_scroll * 0.40
            self._target_scroll -= step

            int_step = int(step)
            if int_step == 0:
                int_step = 1 if step > 0 else -1
                self._target_scroll = 0.0

            self._parent_canvas.yview_scroll(int_step, "units")
            # Force Windows to synchronously clear background and repaint child widgets
            self._parent_canvas.update_idletasks()
            self.after(16, self._smooth_step)
        else:
            if abs(self._target_scroll) > 0:
                int_step = int(self._target_scroll)
                if int_step != 0:
                    self._parent_canvas.yview_scroll(int_step, "units")
                    self._parent_canvas.update_idletasks()
            self._target_scroll = 0.0
            self._is_animating = False


class OnlineSheetsDialog(ctk.CTkToplevel):
    """
    Modern modal dialog to browse, search, and download sheets from PlayPianoSheets.com.
    """
    def __init__(self, parent, target_folder: Path, on_selected=None):
        super().__init__(parent)
        self.target_folder = target_folder
        self.on_selected = on_selected

        self.title('PlayPianoSheets.com – Online Sheet Source')
        self.geometry('540x650')
        self.minsize(460, 480)
        self.configure(fg_color=COLOR_BG)

        icon_path = Path(__file__).with_name('Icon.ico')
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

        self.transient(parent)
        self.grab_set()

        self._all_slugs: list[str] = []
        self._search_timer = None
        self._is_online = False

        self._build_ui()
        self._check_and_load_catalog()

    def _build_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color='transparent')
        hdr.pack(fill='x', padx=16, pady=(14, 6))

        ctk.CTkLabel(
            hdr,
            text='PLAYPIANOSHEETS.COM',
            font=FONT_TITLE,
            text_color=COLOR_TEXT,
        ).pack(side='left')

        self.status_badge = ctk.CTkLabel(
            hdr,
            text='CHECKING...',
            font=FONT_NUMERIC_BOLD,
            text_color=COLOR_TEXT_MUTED,
            fg_color=COLOR_SURFACE,
            corner_radius=6,
            padx=8,
            pady=2,
        )
        self.status_badge.pack(side='right')

        # Subtitle
        ctk.CTkLabel(
            self,
            text='Browse & download over 1,800+ Virtual Piano sheets directly into your active library.',
            font=FONT_SUBTLE,
            text_color=COLOR_TEXT_MUTED,
            wraplength=500,
            justify='left',
        ).pack(fill='x', padx=16, pady=(0, 8))

        # Search Bar
        s_box = ctk.CTkFrame(self, fg_color='transparent')
        s_box.pack(fill='x', padx=16, pady=(0, 6))

        self.var_search = tk.StringVar()
        self.var_search.trace_add('write', self._on_search_type)

        self.entry_search = ctk.CTkEntry(
            s_box,
            textvariable=self.var_search,
            placeholder_text='Search song title, artist, or paste playpianosheets.com link...',
            font=FONT_LABEL,
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            corner_radius=8,
            height=34,
        )
        self.entry_search.pack(side='left', fill='x', expand=True, padx=(0, 6))

        self.btn_fetch = ctk.CTkButton(
            s_box,
            text='Download',
            font=FONT_LABEL_BOLD,
            width=84,
            height=34,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT,
            corner_radius=8,
            command=self._download_typed_query,
        )
        self.btn_fetch.pack(side='right')

        # Quick Tag Filter Pills
        tag_bar = ctk.CTkFrame(self, fg_color='transparent')
        tag_bar.pack(fill='x', padx=16, pady=(0, 8))

        quick_tags = ['Popular', 'Anime', 'Gaming', 'Rush', 'Interstellar', 'Golden', 'Classical']
        for tag in quick_tags:
            btn = ctk.CTkButton(
                tag_bar,
                text=tag,
                font=FONT_SUBTLE,
                width=50,
                height=22,
                fg_color=COLOR_SURFACE,
                hover_color=COLOR_ACCENT,
                text_color=COLOR_TEXT,
                corner_radius=6,
                command=lambda t=tag: self._set_tag(t),
            )
            btn.pack(side='left', padx=(0, 4))

        # Results Count Readout
        self.lbl_count = ctk.CTkLabel(
            self,
            text='Connecting to PlayPianoSheets.com...',
            font=FONT_SUBTLE,
            text_color=COLOR_TEXT_MUTED,
        )
        self.lbl_count.pack(anchor='w', padx=16, pady=(0, 4))

        # Scrollable Results List (Smooth & Anti-Ghosting)
        self.scroll_results = SmoothScrollableFrame(
            self,
            fg_color=COLOR_BG,
            scrollbar_fg_color='transparent',
            scrollbar_button_color=COLOR_BORDER,
            scrollbar_button_hover_color=COLOR_ACCENT,
            corner_radius=0,
        )
        self.scroll_results.pack(fill='both', expand=True, padx=16, pady=(0, 10))

    def _set_tag(self, tag: str):
        if tag == 'Popular':
            self.var_search.set('')
        else:
            self.var_search.set(tag.lower())

    def _check_and_load_catalog(self):
        def worker():
            is_on = check_internet()
            self._is_online = is_on
            if not is_on:
                self.after(0, self._render_offline)
                return

            self.after(0, lambda: self.status_badge.configure(text='● ONLINE', text_color='#51CF66'))
            try:
                slugs = fetch_playpianosheets_catalog()
                self._all_slugs = slugs
                self.after(0, lambda: self._apply_filter(''))
            except Exception as e:
                self.after(0, lambda: self.lbl_count.configure(text=f'Error loading catalog: {e}'))

        threading.Thread(target=worker, daemon=True).start()

    def _render_offline(self):
        self.status_badge.configure(text='● OFFLINE', text_color='#FA5252')
        self.lbl_count.configure(text='You are currently offline. Connect to the internet to load sheets.')
        for w in self.scroll_results.winfo_children():
            w.destroy()

        card = ctk.CTkFrame(
            self.scroll_results,
            fg_color=COLOR_SURFACE,
            corner_radius=8,
            border_color=COLOR_BORDER,
            border_width=1,
        )
        card.pack(fill='x', pady=20, padx=10)

        ctk.CTkLabel(
            card,
            text='⚠ No Internet Connection',
            font=FONT_LABEL_BOLD,
            text_color='#FFA94D',
        ).pack(pady=(16, 4))

        ctk.CTkLabel(
            card,
            text='PlayPianoSheets.com requires an active internet connection to browse and download sheets.\n\nPlease connect to WiFi or the internet and click Retry.',
            font=FONT_SUBTLE,
            text_color=COLOR_TEXT_MUTED,
            wraplength=400,
            justify='center',
        ).pack(pady=(0, 12))

        ctk.CTkButton(
            card,
            text='Retry Connection',
            font=FONT_LABEL_BOLD,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT,
            corner_radius=6,
            height=30,
            command=self._check_and_load_catalog,
        ).pack(pady=(0, 16))

    def _on_search_type(self, *_):
        if self._search_timer:
            self.after_cancel(self._search_timer)
        self._search_timer = self.after(150, lambda: self._apply_filter(self.var_search.get()))

    def _apply_filter(self, query: str):
        if not self._all_slugs:
            return

        q = query.strip().lower()
        if not q:
            popular = [
                'golden-hour', 'rush-e', 'interstellar', 'river-flows-in-you', 'fur-elise', 'runaway',
                'another-love', 'blue', 'fnaf-song-1', 'minecraft-sweden', 'blue-bird-naruto-shippuden',
                'moonlight-sonata-3rd-movement', 'super-mario-bros-theme', 'erika', 'canon-in-d'
            ]
            matches = [s for s in popular if s in self._all_slugs]
            matches += [s for s in self._all_slugs if s not in matches][:50 - len(matches)]
            self.lbl_count.configure(
                text=f'Showing {len(matches)} Popular / Featured Sheets (Total: {len(self._all_slugs):,})'
            )
        else:
            matches = [s for s in self._all_slugs if q in s or q in s.replace('-', ' ')][:60]
            self.lbl_count.configure(
                text=f'Found {len(matches)} matches for "{q}" (Total: {len(self._all_slugs):,})'
            )

        self._render_results(matches)

    def _render_results(self, slugs: list[str]):
        for w in self.scroll_results.winfo_children():
            w.destroy()

        if not slugs:
            ctk.CTkLabel(
                self.scroll_results,
                text='No sheets found matching your search.\nTry pasting a direct link or different keywords.',
                font=FONT_LABEL,
                text_color=COLOR_TEXT_MUTED,
                justify='center',
            ).pack(pady=30)
            return

        for slug in slugs:
            self._create_card(slug)

    def _create_card(self, slug: str):
        card = ctk.CTkFrame(
            self.scroll_results,
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=8,
        )
        card.pack(fill='x', pady=3)

        left = ctk.CTkFrame(card, fg_color='transparent')
        left.pack(side='left', fill='both', expand=True, padx=12, pady=8)

        title = slug_to_title(slug)
        ctk.CTkLabel(
            left,
            text=title,
            font=FONT_LABEL_BOLD,
            text_color=COLOR_TEXT,
            anchor='w',
        ).pack(fill='x')

        ctk.CTkLabel(
            left,
            text=f"playpianosheets.com/sheets/{slug}",
            font=FONT_SUBTLE,
            text_color=COLOR_TEXT_MUTED,
            anchor='w',
        ).pack(fill='x')

        btn = ctk.CTkButton(
            card,
            text='Download',
            font=FONT_SUBTLE,
            width=80,
            height=28,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT,
            corner_radius=6,
        )
        btn.configure(command=lambda s=slug, b=btn: self._start_download(s, b))
        btn.pack(side='right', padx=12, pady=8)

    def _start_download(self, slug_or_url: str, btn: ctk.CTkButton | None = None):
        if btn:
            btn.configure(text='Downloading...', state='disabled', fg_color=COLOR_BORDER)

        def worker():
            try:
                out_file, title = download_playpianosheet(slug_or_url, self.target_folder)
                if btn:
                    self.after(0, lambda: btn.configure(text='✓ Loaded', fg_color='#2B8A3E'))
                if self.on_selected:
                    self.after(0, lambda: self.on_selected(out_file))
                self.after(600, self.destroy)
            except Exception as exc:
                if btn:
                    self.after(0, lambda: btn.configure(text='Retry', state='normal', fg_color='#E03131'))
                self.after(0, lambda: messagebox.showerror('Download Error', str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _download_typed_query(self):
        txt = self.var_search.get().strip()
        if not txt:
            return
        self.btn_fetch.configure(text='Loading...', state='disabled')
        self._start_download(txt, self.btn_fetch)
