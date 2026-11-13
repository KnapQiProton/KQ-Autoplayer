<div align="center">

```
   ♡  ∩_∩
  （„• ֊ •„)♡
  ┏━∪∪━━━━━━━━━━━━━━━━━━━━━━━━━━┓
  ♡   ✨ ＫＱ Ａｕｔｏｐｌａｙｅｒ ✨   ♡
  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

# 🌸 KQ Autoplayer 🌸
### *~ A Cute, Modern & Adaptive Virtual Piano Autoplayer ~* 
#### ૮ ˶ᵔ ᵕ ᵔ˶ ა 🎹 💖 ✨

[![Release](https://img.shields.io/github/v/release/KnapQiProton/KQ-Autoplayer?color=ffb3c6&label=Release&style=for-the-badge&logo=github)](https://github.com/KnapQiProton/KQ-Autoplayer/releases)
[![Python](https://img.shields.io/badge/Python-3.10%2B-ffccd5?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![UI](https://img.shields.io/badge/UI-CustomTkinter-ffc0cb?style=for-the-badge)](https://github.com/TomSchimansky/CustomTkinter)
[![Platform](https://img.shields.io/badge/Platform-Windows-ff85a1?style=for-the-badge&logo=windows&logoColor=white)](https://microsoft.com/windows)
[![Vibe](https://img.shields.io/badge/Vibe-100%25%20Moe%20Core-f72585?style=for-the-badge&logo=hearts)](https://github.com/KnapQiProton/KQ-Autoplayer)

*Haii bestie~!* (｡♥‿♥｡)  
Welcome to **KQ Autoplayer** — an ultra-clean, lightweight, and stylish virtual piano autoplayer built specifically for **Roblox Piano Games** and **Virtual Piano**! Designed with a soothing tech-minimalist dark theme, smooth-as-butter animations, zero-delay hotkey triggers, and direct access to over **1,800+ online piano sheets**! (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧

---

</div>

## 🎀 ‧̍̊˙· 𓆝 𓆟 Highlights & Features 𓆞 𓆝 ‧̍̊˙· 🎀

| Feature | Description |
| :--- | :--- |
| 🌸 **Tech-Minimalist Theme** | Handcrafted dark UI in Charcoal Gray (`#343A40`), Ivory White (`#F8F9FA`), and Steel Blue (`#406185`) accents. |
| 🪞 **Adaptive & Resizable** | Freely resize, maximize, or snap your window! Smart responsive layout ensures nothing ever gets cut off. |
| 🍡 **Butter-Smooth 60 FPS Scroll** | Custom anti-ghosting scroll engine. No more tearing, frame lagging, or visual stacking artifacts! |
| 🌐 **PlayPianoSheets Integration** | Built-in online browser with instant search, category pills, and 1-click download across **1,800+ songs**! |
| ⚡ **Zero-Delay Hotkey Engine** | Instant playback toggle (no annoying delays, no need to spam keys!). Equipped with hardware-level debouncing. |
| 🎯 **Target Window Focus Lock** | Plays notes *only* inside your selected target window (e.g. Roblox) and automatically pauses if you alt-tab! |
| 🎼 **Sheet Metadata Persistence** | Automatically remembers your custom BPM, subdivision, and personal notes inside each sheet file! |
| 💖 **Humanisation & Expressiveness** | Adjust humanisation percentage & key hold duration for realistic, expressive, and human-like performances. |

---

## 📦 ‧̍̊˙· 𓆝 Download & Quick Start 𓆞 ‧̍̊˙· 📦

### 🌟 Option 1: Standalone Application (*Super Easy! No Python needed!*)
1. Head over to the **[Releases](https://github.com/KnapQiProton/KQ-Autoplayer/releases)** page.
2. Download the latest `KQ-Autoplayer-v1.0.0.zip` (or `KQ-Autoplayer.exe`).
3. Extract and double-click `KQ-Autoplayer.exe`.
4. Yay! You're ready to play! ⸜(｡˃ ᵕ ˂ )⸝♡

---

### 🐍 Option 2: Run from Source Code (*For Developers & Tinkerers*)
Ensure you have **Python 3.10+** installed:

```bash
# 1. Clone this cute repository (≧◡≦)
git clone https://github.com/KnapQiProton/KQ-Autoplayer.git
cd KQ-Autoplayer

# 2. Install dependencies (づ｡◕‿‿◕｡)づ
pip install -r requirements.txt

# 3. Launch KQ Autoplayer! ✨
python gui.py
```

---

## 🎮 ‧̍̊˙· 𓆝 How to Use 𓆞 ‧̍̊˙· 🎮

```
       ╭───────────────────────────────────────────────────╮
  Step │ 1. 📁 Select / Open Sheet Folder                  │
       │    Choose the folder where your songs (.txt) live │
       ├───────────────────────────────────────────────────┤
  Step │ 2. 🌐 Find Your Dream Songs!                      │
       │    Click [ 🌐 Online Sheets ] to browse and grab  │
       │    1,800+ songs directly from PlayPianoSheets!    │
       ├───────────────────────────────────────────────────┤
  Step │ 3. 🎯 Pick Your Target Window                     │
       │    Select your Roblox game window from the Target │
       │    Window dropdown (e.g. "Roblox").               │
       ├───────────────────────────────────────────────────┤
  Step │ 4. 🎹 Start Playing!                              │
       │    Press your hotkey (default: F4) or click the   │
       │    cute circular ▶ Play button. Enjoy! 🎶         │
       ╰───────────────────────────────────────────────────╯
```

> **Pro Tip (✧ω✧):**  
> Check the **Auto-play when focused** switch so the Autoplayer automatically pauses whenever you Alt-Tab and seamlessly resumes as soon as you refocus the game!

---

## 🎶 ‧̍̊˙· 𓆝 Sheet Music Syntax Guide 𓆞 ‧̍̊˙· 🎶

KQ Autoplayer supports the standard Virtual Piano format:

- **Single Note:** `e`, `t`, `y`, `u`, `o`, `p`
- **Chords (Keys played together):** Enclosed in brackets: `[es]`, `[18o]`, `[4qt]`
- **Pauses & Rests:** Expressed with vertical bars `|` or spaces.
- **Header Metadata:**
  ```text
  #META {"bpm": 120, "subdiv": 4.0, "note": "Lovely song"}
  ```

---

## 🎨 ‧̍̊˙· 𓆝 Color Palette Specification 𓆞 ‧̍̊˙· 🎨

```
  ┌────────────────────────────────────────────────────────┐
  │  Background:   #343A40 (Charcoal Gray)                 │
  │  Surface Card: #2B3035 (Dark Surface Depth)            │
  │  Accent / FAB: #406185 (Steel Blue)                    │
  │  Text & Icons: #F8F9FA (Ivory White)                   │
  │  Muted Labels: #8E959D (Soft Slate Gray)               │
  └────────────────────────────────────────────────────────┘
```

---

## 🌸 ‧̍̊˙· 𓆝 Contributing & Feedback 𓆞 ‧̍̊˙· 🌸

Ideas, suggestions, or found a bug? Feel free to open an **[Issue](https://github.com/KnapQiProton/KQ-Autoplayer/issues)** or submit a **Pull Request**! We'd love your love & contributions! (੭ˊ꒳​ˋ)੭✧

---

<div align="center">

Crafted with lots of 💖, tea 🍵 and music 🎶 by **[KnapQi](https://github.com/KnapQiProton)**

*Thank you for using KQ Autoplayer! Have fun playing! (つ✧ω✧)つ*

</div>
