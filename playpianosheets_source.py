"""
PlayPianoSheets.com Online Sheet Integration for KQ Autoplayer.

Allows searching, browsing, and 1-click downloading of 1,800+ sheets
from https://playpianosheets.com/ into the local sheets library,
with rich genre/category filtering (Classical, Anime, Gaming, Pop, etc.),
BeautifulSoup fallback parsing, and robust error handling.
"""
from __future__ import annotations

import json
import logging
import re
import socket
import sys
import threading
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

# --- Logger Initialization ---
logger = logging.getLogger('KQAutoplayer.SheetsSource')
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(
        logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s', datefmt='%H:%M:%S')
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

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
FONT_SUBTLE_BOLD = ('Segoe UI', 10, 'bold')
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


def fetch_playpianosheets_catalog() -> list[dict]:
    """
    Fetch complete catalog of songs from playpianosheets.com including
    title, artist, genres/tags, and slug.
    Primary: Next.js RSC push regex.
    Fallback 1: BeautifulSoup HTML parser.
    Fallback 2: sitemap.xml.
    """
    url = 'https://playpianosheets.com/category/all'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    html = None
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)

    if html:
        # 1. Primary: Next.js RSC extraction
        try:
            cleaned = html.replace('\\"', '"').replace('\\\\', '\\')
            pattern = re.compile(
                r'\{"id":"([^"]+)","title":"([^"]+)","artist":"([^"]*)","image":"[^"]*","tags":(\[[^\]]*\]),"slug":"([^"]+)"'
            )
            items = []
            for m in pattern.finditer(cleaned):
                sheet_id, title, artist, tags_raw, slug = m.groups()
                try:
                    tags = json.loads(tags_raw)
                except Exception:
                    tags = []
                items.append({
                    'id': sheet_id,
                    'title': title.strip(),
                    'artist': artist.strip(),
                    'tags': [t.strip().lower() for t in tags],
                    'slug': slug.strip(),
                })
            if items:
                logger.info("Successfully loaded %d songs via RSC stream.", len(items))
                return items
        except Exception as exc:
            logger.warning("RSC parsing failed: %s. Trying BeautifulSoup fallback...", exc)

        # 2. Fallback 1: BeautifulSoup HTML parser
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            bs_items = []
            seen_slugs = set()
            for a in soup.find_all('a', href=True):
                href = a['href']
                if '/sheets/' in href:
                    slug = href.split('/sheets/')[-1].split('?')[0].strip('/')
                    if slug and slug not in seen_slugs:
                        seen_slugs.add(slug)
                        # Extract title text or fallback to slug
                        text = a.get_text(strip=True) or slug_to_title(slug)
                        # Clean up difficulty badges if attached to link text
                        clean_title = re.sub(r'(Easy|Normal|Hard|Expert)+$', '', text).strip() or slug_to_title(slug)
                        bs_items.append({
                            'id': slug,
                            'title': clean_title,
                            'artist': '',
                            'tags': [],
                            'slug': slug,
                        })
            if bs_items:
                logger.info("Retrieved %d items via BeautifulSoup fallback.", len(bs_items))
                return bs_items
        except Exception as bs_exc:
            logger.warning("BeautifulSoup fallback failed: %s", bs_exc)

    # 3. Fallback 2: sitemap.xml
    try:
        url_sitemap = 'https://playpianosheets.com/sitemap.xml'
        req_sm = urllib.request.Request(url_sitemap, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req_sm, timeout=8) as resp:
            data = resp.read().decode('utf-8', errors='ignore')
        slugs = re.findall(r'<loc>https://playpianosheets\.com/sheets/([^<]+)</loc>', data)
        if not slugs:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(data, 'xml')
            slugs = [loc.text.split('/sheets/')[-1].strip() for loc in soup.find_all('loc') if '/sheets/' in loc.text]
        return [
            {
                'id': s,
                'title': slug_to_title(s),
                'artist': '',
                'tags': [],
                'slug': s,
            }
            for s in slugs
        ]
    except Exception as exc:
        logger.error("All catalog fetching methods failed: %s", exc)
        return []


def download_playpianosheet(slug_or_url: str, output_dir: Path) -> tuple[Path, str]:
    """
    Download sheet notation from playpianosheets.com, format it with metadata,
    and save it as a ready-to-play .txt sheet in output_dir.
    Comprehensive try-except and BeautifulSoup fallback.
    """
    slug = slug_or_url.strip().lower()
    if 'playpianosheets.com/sheets/' in slug:
        slug = slug.split('playpianosheets.com/sheets/')[-1].split('/')[0].split('?')[0]
    elif slug.startswith('http'):
        slug = slug.rstrip('/').split('/')[-1]

    url = f'https://playpianosheets.com/sheets/{slug}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
    except Exception as exc:
        logger.error("Network error fetching sheet '%s': %s", slug, exc)
        raise RuntimeError(
            "Gagal mengambil data dari PlayPianoSheets.com. Situs mungkin sedang diperbarui atau koneksi internet terputus. "
            "Silakan coba lagi nanti atau gunakan sheet lokal."
        ) from exc

    title = slug_to_title(slug)
    header_info = title
    sheet_music = None

    try:
        # Title extraction
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        if h1:
            title = re.sub(r'<[^>]+>', '', h1.group(1)).strip()
        title_tag = re.search(r'<title>(.*?) Roblox Piano Sheet</title>', html)
        if title_tag:
            header_info = title_tag.group(1)

        # 1. Primary: RSC stream extraction
        pushes = re.findall(r'self\.__next_f\.push\(\[1,\s*\"(.*?)\"\]\)', html, re.DOTALL)
        full_text = ''
        for p in pushes:
            decoded = p.encode('utf-8').decode('unicode_escape', errors='ignore')
            full_text += decoded

        matches = re.finditer(r'\d+:T([0-9a-fA-F]+),', full_text)
        for m in matches:
            hex_len = m.group(1)
            length = int(hex_len, 16)
            start = m.end()
            text = full_text[start:start + length]
            if any(f'[{c}' in text for c in 'abcdefghijklmnopqrstuvwxyz0123456789'):
                sheet_music = text
                break

        # 2. Fallback 1: Token span regex
        if not sheet_music:
            tokens = re.findall(r'<span id="token-\d+"[^>]*>(.*?)</span>', html)
            if tokens:
                sheet_music = ' '.join(tokens)

        # 3. Fallback 2: BeautifulSoup HTML parser
        if not sheet_music:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            # Look for token spans with BeautifulSoup
            spans = soup.find_all('span', id=lambda x: x and x.startswith('token-'))
            if spans:
                sheet_music = ' '.join(s.get_text() for s in spans)
            else:
                for candidate in soup.find_all(['pre', 'code', 'div']):
                    c_text = candidate.get_text()
                    if any(f'[{c}' in c_text for c in 'abcdefghijklmnopqrstuvwxyz0123456789'):
                        sheet_music = c_text
                        break
    except Exception as parse_exc:
        logger.warning("Error during sheet notation parsing: %s", parse_exc)

    if not sheet_music:
        raise RuntimeError(
            f"Gagal mengekstrak notasi piano untuk '{title}'. Format halaman mungkin berubah. "
            "Silakan periksa koneksi atau gunakan file sheet lokal."
        )

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_title = re.sub(r'[<>:"/\\|?*]', '', title).strip()
        out_file = output_dir / f"{safe_title}.txt"
        meta_line = f'#META {{"bpm": 120, "subdiv": 4.0, "note": "Source: playpianosheets.com/sheets/{slug} | {header_info}"}}\n'
        out_file.write_text(meta_line + sheet_music.strip() + '\n', encoding='utf-8')
        return out_file, title
    except Exception as file_exc:
        logger.error("Failed to save downloaded sheet file: %s", file_exc)
        raise RuntimeError(f"Gagal menyimpan file sheet lokal: {file_exc}") from file_exc


def item_matches_genre(item: dict, genre: str) -> bool:
    """
    Check if a sheet matches a given music genre category based on
    its tags, artist, title, or slug.
    """
    if genre == 'All':
        return True

    tags = item.get('tags', [])
    title = item.get('title', '').lower()
    artist = item.get('artist', '').lower()
    slug = item.get('slug', '').lower()

    if genre == 'Classical':
        composers = [
            'chopin', 'beethoven', 'bach', 'mozart', 'liszt', 'debussy', 'tchaikovsky',
            'rachmaninoff', 'brahms', 'vivaldi', 'pachelbel', 'handel', 'schubert',
            'schumann', 'satie', 'mussorgsky', 'ravel', 'dvorak', 'grieg', 'mendelssohn',
            'strauss', 'shostakovich', 'haydn'
        ]
        classical_tags = [
            'classical', 'baroque', 'romanticism', 'romantic', 'opera', 'waltz',
            'sonata', 'nocturne', 'prelude', 'etude'
        ]
        return any(t in tags for t in classical_tags) or any(c in artist or c in title or c in slug for c in composers)

    elif genre == 'Anime':
        anime_keywords = [
            'anime', 'jpop', 'j-pop', 'ghibli', 'vocaloid', 'radwimps', 'yoasobi', 'lisa',
            'naruto', 'one piece', 'attack on titan', 'evangelion', 'tokyo ghoul',
            'demon slayer', 'jujutsu kaisen', 'your lie in april', 'genshin', 'bleach',
            'dragon ball', 'hunter x hunter', 'death note', 'suzume', 'weathering with you',
            'spirited away', 'howl', 'inuyasha', 'sword art online', 'chainsaw man'
        ]
        return any(t in ['anime', 'jpop', 'vocaloid', 'j-pop'] for t in tags) or any(k in title or k in artist or k in slug for k in anime_keywords)

    elif genre == 'Gaming':
        game_keywords = [
            'video game', 'game', 'gaming', 'nintendo', 'roblox', 'genshin', 'minecraft',
            'undertale', 'deltarune', 'fnaf', 'zelda', 'mario', 'pokemon', 'toby fox',
            'hollow knight', 'omori', 'sonic', 'cuphead', 'celeste', 'touhou', 'final fantasy',
            'dark souls', 'elden ring', 'terraria', 'portal', 'halo', 'tetris', 'persona'
        ]
        return any(t in ['video game', 'game', 'gaming'] for t in tags) or any(k in title or k in artist or k in slug for k in game_keywords)

    elif genre == 'Pop':
        return any('pop' in t for t in tags) or any(k in tags for k in ['r&b', 'soul', 'indie', 'ballad'])

    elif genre == 'Movie':
        movie_keywords = [
            'movie', 'soundtrack', 'film', 'disney', 'hans zimmer', 'john williams',
            'interstellar', 'star wars', 'la la land', 'harry potter'
        ]
        return any(t in ['movie', 'soundtrack', 'film', 'disney'] for t in tags) or any(k in title or k in artist or k in slug for k in movie_keywords)

    elif genre == 'Meme':
        meme_keywords = [
            'meme', 'phonk', 'viral', 'tiktok', 'rush e', 'rickroll',
            'never gonna give you up', 'gigachad', 'coffin dance'
        ]
        return any(t in ['meme', 'phonk', 'viral', 'tiktok'] for t in tags) or any(k in title or k in artist or k in slug for k in meme_keywords)

    return True


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
    Equipped with real genre categorization (Classical, Anime, Gaming, Pop, etc.)
    and local catalog caching for instant loading.
    """
    def __init__(self, parent, target_folder: Path, on_selected=None):
        super().__init__(parent)
        self.target_folder = target_folder
        self.on_selected = on_selected
        self.cache_file = target_folder / '.playpianosheets_cache.json'

        self.title('PlayPianoSheets.com – Online Sheet Catalog')
        self.geometry('560x660')
        self.minsize(480, 500)
        self.configure(fg_color=COLOR_BG)

        icon_path = Path(__file__).with_name('Icon.ico')
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

        self.transient(parent)
        self.grab_set()

        self._all_items: list[dict] = []
        self._active_genre: str = 'All'
        self._genre_buttons: dict[str, ctk.CTkButton] = {}
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
            text='CONNECTING...',
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
            text='Browse and 1-click download over 1,800+ Virtual Piano sheets into your local library.',
            font=FONT_SUBTLE,
            text_color=COLOR_TEXT_MUTED,
            wraplength=520,
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
            placeholder_text='Search song title, artist, or paste a playpianosheets link...',
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
            width=88,
            height=34,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT,
            corner_radius=8,
            command=self._download_typed_query,
        )
        self.btn_fetch.pack(side='right')

        # Genre / Category Filter Bar
        tag_bar = ctk.CTkFrame(self, fg_color='transparent')
        tag_bar.pack(fill='x', padx=16, pady=(0, 8))

        genres = ['All', 'Classical', 'Anime', 'Gaming', 'Pop', 'Movie', 'Meme']
        for g in genres:
            is_active = (g == self._active_genre)
            btn = ctk.CTkButton(
                tag_bar,
                text=g,
                font=FONT_SUBTLE_BOLD,
                width=54 if len(g) <= 4 else 68,
                height=24,
                fg_color=COLOR_ACCENT if is_active else COLOR_SURFACE,
                hover_color=COLOR_ACCENT_HOVER if is_active else COLOR_BORDER,
                text_color=COLOR_TEXT if is_active else COLOR_TEXT_MUTED,
                corner_radius=6,
                command=lambda genre=g: self._on_genre_click(genre),
            )
            btn.pack(side='left', padx=(0, 5))
            self._genre_buttons[g] = btn

        # Results Count Readout
        self.lbl_count = ctk.CTkLabel(
            self,
            text='Loading catalog...',
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

    def _on_genre_click(self, genre: str):
        """Switch active music category without modifying the search input box."""
        if self._active_genre == genre:
            return

        self._active_genre = genre
        for g_name, btn in self._genre_buttons.items():
            if g_name == genre:
                btn.configure(
                    fg_color=COLOR_ACCENT,
                    hover_color=COLOR_ACCENT_HOVER,
                    text_color=COLOR_TEXT,
                )
            else:
                btn.configure(
                    fg_color=COLOR_SURFACE,
                    hover_color=COLOR_BORDER,
                    text_color=COLOR_TEXT_MUTED,
                )

        self._apply_filter(self.var_search.get())

    def _check_and_load_catalog(self):
        # 1. Fast path: load local cache immediately if available
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cached_items = json.load(f)
                if cached_items and isinstance(cached_items, list):
                    self._all_items = cached_items
                    self.status_badge.configure(text='● CACHED', text_color='#74C0FC')
                    self._apply_filter('')
            except Exception as exc:
                logger.warning("Error reading local cache: %s", exc)

        # 2. Background thread: probe internet & sync fresh catalog
        def worker():
            is_on = check_internet()
            self._is_online = is_on
            if not is_on:
                if not self._all_items:
                    self.after(0, self._render_offline)
                else:
                    self.after(0, lambda: self.status_badge.configure(text='● OFFLINE (CACHED)', text_color='#FFA94D'))
                return

            self.after(0, lambda: self.status_badge.configure(text='● ONLINE', text_color='#51CF66'))
            try:
                items = fetch_playpianosheets_catalog()
                if items:
                    self._all_items = items
                    # Save local cache
                    try:
                        with open(self.cache_file, 'w', encoding='utf-8') as f:
                            json.dump(items, f, ensure_ascii=False)
                    except Exception as ce:
                        logger.warning("Failed to save local catalog cache: %s", ce)
                self.after(0, lambda: self._apply_filter(self.var_search.get()))
            except Exception as e:
                logger.error("Failed to load catalog: %s", e)
                if not self._all_items:
                    self.after(
                        0,
                        lambda: self.lbl_count.configure(
                            text='Gagal mengambil katalog online. Situs mungkin sedang diperbarui atau koneksi terputus. Silakan coba lagi.'
                        )
                    )

        threading.Thread(target=worker, daemon=True).start()

    def _render_offline(self):
        self.status_badge.configure(text='● OFFLINE', text_color='#FA5252')
        self.lbl_count.configure(text='Koneksi internet terputus. Sambungkan internet untuk memuat sheets online.')
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
            text='⚠ Tidak Ada Koneksi Internet',
            font=FONT_LABEL_BOLD,
            text_color='#FFA94D',
        ).pack(pady=(16, 4))

        ctk.CTkLabel(
            card,
            text='PlayPianoSheets.com memerlukan koneksi internet aktif untuk menelusuri dan mengunduh sheet musik.\n\nSilakan periksa koneksi WiFi / internet kamu atau gunakan sheet lokal.',
            font=FONT_SUBTLE,
            text_color=COLOR_TEXT_MUTED,
            wraplength=400,
            justify='center',
        ).pack(pady=(0, 12))

        ctk.CTkButton(
            card,
            text='Coba Lagi',
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
        if not self._all_items:
            return

        # 1. Filter by active category/genre
        genre = self._active_genre
        matched = [it for it in self._all_items if item_matches_genre(it, genre)]

        # 2. Filter by search query if provided
        q = query.strip().lower()
        if q:
            keywords = q.split()
            filtered = []
            for it in matched:
                text_corpus = f"{it.get('title', '')} {it.get('artist', '')} {' '.join(it.get('tags', []))} {it.get('slug', '')}".lower()
                if all(kw in text_corpus for kw in keywords):
                    filtered.append(it)
            matched = filtered

        # 3. If query is empty and genre is 'All', prioritize popular/featured sheets
        if not q and genre == 'All':
            popular_slugs = {
                'golden-hour', 'rush-e', 'interstellar', 'river-flows-in-you', 'fur-elise',
                'runaway', 'another-love', 'blue', 'fnaf-song-1', 'minecraft-sweden',
                'canon-in-d', 'moonlight-sonata-3rd-movement', 'super-mario-bros-theme',
                'erika', 'blue-bird-naruto-shippuden'
            }
            featured = [it for it in matched if it.get('slug') in popular_slugs]
            others = [it for it in matched if it.get('slug') not in popular_slugs]
            matched = featured + others

        # 4. Update count label
        total_in_genre = len(matched)
        if not q:
            if genre == 'All':
                self.lbl_count.configure(
                    text=f'Showing {min(60, total_in_genre)} Featured & All Sheets (Total: {len(self._all_items):,})'
                )
            else:
                self.lbl_count.configure(
                    text=f'Showing {min(60, total_in_genre)} {genre} Sheets (Total: {total_in_genre:,})'
                )
        else:
            self.lbl_count.configure(
                text=f'Found {total_in_genre} matches in {genre} for "{q}"'
            )

        self._render_results(matched[:60])

    def _render_results(self, items: list[dict]):
        for w in self.scroll_results.winfo_children():
            w.destroy()

        if not items:
            ctk.CTkLabel(
                self.scroll_results,
                text=f'Tidak ada sheet ditemukan di kategori "{self._active_genre}".\nCoba hapus kata kunci pencarian atau pilih kategori lain.',
                font=FONT_LABEL,
                text_color=COLOR_TEXT_MUTED,
                justify='center',
            ).pack(pady=30)
            return

        for it in items:
            self._create_card(it)

    def _create_card(self, item: dict):
        card = ctk.CTkFrame(
            self.scroll_results,
            fg_color=COLOR_SURFACE,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=8,
        )
        card.pack(fill='x', pady=3)

        left = ctk.CTkFrame(card, fg_color='transparent')
        left.pack(side='left', fill='both', expand=True, padx=12, pady=7)

        title = item.get('title') or slug_to_title(item.get('slug', ''))
        ctk.CTkLabel(
            left,
            text=title,
            font=FONT_LABEL_BOLD,
            text_color=COLOR_TEXT,
            anchor='w',
        ).pack(fill='x')

        # Subtitle: Artist + Tags / Genres
        sub_parts = []
        artist = item.get('artist', '').strip()
        if artist:
            sub_parts.append(f"by {artist}")

        tags = item.get('tags', [])
        if tags:
            top_tags = [t.title() for t in tags[:3]]
            tag_str = ', '.join(top_tags)
            sub_parts.append(f"• {tag_str}")

        if not sub_parts:
            sub_parts.append(f"playpianosheets.com/sheets/{item.get('slug', '')}")

        ctk.CTkLabel(
            left,
            text=' '.join(sub_parts),
            font=FONT_SUBTLE,
            text_color=COLOR_TEXT_MUTED,
            anchor='w',
        ).pack(fill='x')

        slug = item.get('slug', '')
        btn = ctk.CTkButton(
            card,
            text='Download',
            font=FONT_SUBTLE_BOLD,
            width=84,
            height=28,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT,
            corner_radius=6,
        )
        btn.configure(command=lambda s=slug, b=btn: self._start_download(s, b))
        btn.pack(side='right', padx=12, pady=7)

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
                logger.error("Download failure: %s", exc)
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
