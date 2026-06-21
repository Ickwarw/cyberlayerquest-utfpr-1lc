"""
CyberLayerQuest — UTFPR-1ºLC
A 2D platformer that teaches OSI/TCP-IP network layers.
Run: python main.py  (requires pygame>=2.6.0)
"""

import sys
import math
import os
import json
import platform
import ctypes
import pygame
try:
    from netplay import NetworkManager
    _NET_AVAILABLE = True
except ImportError:
    _NET_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
W, H = 1200, 680
GRAV = 0.55
JUMP = -13
SPEED = 4.8
FPS = 60
PW, PH = 24, 40

PANEL_W = 280          # right side-panel width
GAME_W = W - PANEL_W  # playfield width  (920)
HEADER_H = 48          # top header bar height
GROUND_H = 8           # ground bar thickness
GROUND_Y = H - GROUND_H  # y-coordinate of ground bar top

# Colours
DARK_BG   = (8, 15, 30)
EMERALD   = (16, 185, 129)
RED_HAT   = (220, 38, 38)
WHITE     = (255, 255, 255)
BLACK     = (0, 0, 0)
GRAY      = (120, 120, 120)
CYAN      = (0, 220, 255)
YELLOW    = (250, 204, 21)
ORANGE    = (249, 115, 22)
PURPLE    = (147, 51, 234)
BROWN     = (120, 80, 40)
TAN       = (194, 154, 108)
DARK_RED  = (180, 30, 30)
DARK_GRAY = (30, 35, 50)
PANEL_BG  = (12, 20, 40)
NEON_GREEN = (57, 255, 20)
STEEL      = (80, 100, 130)
CABLE_BLUE = (30, 100, 220)
LED_GREEN  = (0, 255, 80)
LED_RED    = (255, 40, 40)
SCREEN_BLUE = (10, 30, 80)

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Sprite sheet configuration
# ---------------------------------------------------------------------------
_BASE = os.path.dirname(os.path.abspath(__file__))

# Procura o arquivo em vários locais possíveis
_SPRITE_CANDIDATES = [
    os.path.join(_BASE, "sprites", "spritesheet.png"),
    os.path.join(_BASE, "sprites", "sprite.png"),
    os.path.join(_BASE, "sprites", "characters.png"),
    os.path.join(_BASE, "spritesheet.png"),
]
SPRITE_SHEET_PATH = next((p for p in _SPRITE_CANDIDATES if os.path.exists(p)), None)

# ── Configure aqui após rodar find_sprites.py ────────────────────────────────
# Se SPRITE_CFG_ROWS for None, o auto-detector escolhe as duas maiores linhas.
# Se quiser fixar manualmente: SPRITE_CFG_ROWS = [(y_white, y_black)]
SPRITE_CFG_ROWS = None   # None = auto-detect

SPRITES = {}


def _row_has_pixels(sheet, y0, fh, sw):
    """Return True if any pixel in this row strip is non-transparent."""
    for x in range(0, sw, 4):
        if y0 + fh <= sheet.get_height() and sheet.get_at((x, y0 + fh // 2))[3] > 10:
            return True
    return False


def load_sprites():
    global SPRITES
    if SPRITE_SHEET_PATH is None:
        print("[sprites] Salve o spritesheet em: game/sprites/spritesheet.png")
        return
    try:
        sheet = pygame.image.load(SPRITE_SHEET_PATH).convert_alpha()
    except Exception as e:
        print(f"[sprites] Erro ao carregar: {e}")
        return

    sw, sh = sheet.get_size()
    print(f"[sprites] Spritesheet: {SPRITE_SHEET_PATH}  ({sw}×{sh}px)")

    # --- Auto-detect: scan every possible (fw, fh) grid for valid rows -------
    best = None
    for fh in (32, 24, 48, 16, 40):
        for fw in (24, 16, 32, 48):
            n = max(1, sw // fw)
            # Find rows that have at least 2 non-transparent frames
            valid_rows = []
            y = 0
            while y + fh <= sh:
                non_empty = 0
                for i in range(n):
                    for py2 in range(y, min(y+fh, sh), 4):
                        if sheet.get_at((i*fw + fw//2, py2))[3] > 10:
                            non_empty += 1
                            break
                if non_empty >= 2:
                    valid_rows.append(y)
                y += fh
            if len(valid_rows) >= 2:
                best = (fw, fh, n, valid_rows)
                break
        if best:
            break

    if best is None:
        print("[sprites] Não foi possível detectar sprites — usando desenho geométrico.")
        return

    fw, fh, n, valid_rows = best
    scale = max(1, min(4, PH // fh)) if fh < PH else 1
    if scale == 0: scale = 1
    print(f"[sprites] Auto-detect: fw={fw} fh={fh} n={n} scale={scale} rows={valid_rows[:6]}")

    # Use first valid row for white, second for black (or override via SPRITE_CFG_ROWS)
    if SPRITE_CFG_ROWS:
        row_white, row_black = SPRITE_CFG_ROWS[0], SPRITE_CFG_ROWS[1]
    else:
        row_white = valid_rows[0]
        row_black = valid_rows[1] if len(valid_rows) > 1 else valid_rows[0]

    for char, y0 in (("white", row_white), ("black", row_black)):
        frames_right, frames_left = [], []
        for i in range(min(n, 6)):
            frame = pygame.Surface((fw, fh), pygame.SRCALPHA)
            frame.blit(sheet, (0, 0), (i * fw, y0, fw, fh))
            if pygame.mask.from_surface(frame).count() == 0:
                continue
            big = pygame.transform.scale(frame, (fw * scale, fh * scale))
            frames_right.append(big)
            frames_left.append(pygame.transform.flip(big, True, False))
        if frames_right:
            SPRITES[char] = {"right": frames_right, "left": frames_left,
                             "size": (fw * scale, fh * scale)}
            print(f"[sprites] '{char}': {len(frames_right)} frames @ y={y0} ({fw*scale}×{fh*scale}px)")
        else:
            print(f"[sprites] '{char}': nenhum frame válido em y={y0}")


pygame.init()
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("CyberLayerQuest — UTFPR-1ºLC")
clock = pygame.time.Clock()
load_sprites()

# ---------------------------------------------------------------------------
# Global keyboard input — reads keys even when window is not focused (Windows)
# ---------------------------------------------------------------------------
_IS_WINDOWS = platform.system() == "Windows"
if _IS_WINDOWS:
    _u32 = ctypes.windll.user32
    def _vk_down(vk: int) -> bool:
        return bool(_u32.GetAsyncKeyState(vk) & 0x8000)
else:
    def _vk_down(vk: int) -> bool:
        return False

# pygame key constant → Windows Virtual-Key code
_PG_TO_VK: dict = {}

def _build_vk_map():
    m = {
        pygame.K_LEFT:     0x25,
        pygame.K_RIGHT:    0x27,
        pygame.K_UP:       0x26,
        pygame.K_DOWN:     0x28,
        pygame.K_SPACE:    0x20,
        pygame.K_RETURN:   0x0D,
        pygame.K_ESCAPE:   0x1B,
        pygame.K_BACKSPACE:0x08,
        pygame.K_LSHIFT:   0x10,
        pygame.K_RSHIFT:   0x10,
        pygame.K_LCTRL:    0x11,
        pygame.K_RCTRL:    0x11,
        pygame.K_LALT:     0x12,
        pygame.K_TAB:      0x09,
    }
    for i in range(26):          # a–z → VK A–Z
        m[pygame.K_a + i] = 0x41 + i
    for i in range(10):          # 0–9
        m[pygame.K_0 + i] = 0x30 + i
    for i in range(12):          # F1–F12
        m[pygame.K_F1 + i] = 0x70 + i
    _PG_TO_VK.update(m)

_build_vk_map()

def is_key_down(pg_key: int) -> bool:
    """True if key is pressed — uses GetAsyncKeyState on Windows (cross-window)."""
    if _IS_WINDOWS:
        vk = _PG_TO_VK.get(pg_key)
        if vk is not None:
            return _vk_down(vk)
    # Fallback: pygame (only works when this window is focused)
    try:
        return bool(pygame.key.get_pressed()[pg_key])
    except Exception:
        return False

# ---------------------------------------------------------------------------
# Controls configuration  (P1 = host/solo,  P2 = second player)
# ---------------------------------------------------------------------------
_CONTROLS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "controls.json")

_DEFAULT_CONTROLS: dict = {
    "P1": {"left": pygame.K_a,     "right": pygame.K_d,     "jump": pygame.K_w},
    "P2": {"left": pygame.K_LEFT,  "right": pygame.K_RIGHT, "jump": pygame.K_UP},
}

CONTROLS: dict = {
    "P1": dict(_DEFAULT_CONTROLS["P1"]),
    "P2": dict(_DEFAULT_CONTROLS["P2"]),
}

def _save_controls():
    data = {
        slot: {a: pygame.key.name(k) for a, k in binds.items()}
        for slot, binds in CONTROLS.items()
    }
    try:
        with open(_CONTROLS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def _load_controls():
    if not os.path.exists(_CONTROLS_FILE):
        return
    try:
        with open(_CONTROLS_FILE) as f:
            data = json.load(f)
        for slot, binds in data.items():
            if slot in CONTROLS:
                for action, name in binds.items():
                    code = pygame.key.key_code(name)
                    if code and action in CONTROLS[slot]:
                        CONTROLS[slot][action] = code
    except Exception:
        pass

_load_controls()

def get_actions(slot: str) -> dict:
    """Returns {left, right, jump} booleans for the given control slot."""
    c = CONTROLS[slot]
    return {
        "left":  is_key_down(c["left"]),
        "right": is_key_down(c["right"]),
        "jump":  is_key_down(c["jump"]),
    }

# Fonts
try:
    FONT_BIG   = pygame.font.SysFont("Segoe UI", 52, bold=True)
    FONT_MED   = pygame.font.SysFont("Segoe UI", 28, bold=True)
    FONT_LG    = pygame.font.SysFont("Segoe UI", 26, bold=True)
    FONT_SM    = pygame.font.SysFont("Segoe UI", 18)
    FONT_XS    = pygame.font.SysFont("Segoe UI", 14)
    FONT_EMOJI = pygame.font.SysFont("Segoe UI Emoji", 20)
    FONT_TINY  = pygame.font.SysFont("Segoe UI", 12)
except Exception:
    FONT_BIG   = pygame.font.Font(None, 60)
    FONT_MED   = pygame.font.Font(None, 34)
    FONT_LG    = pygame.font.Font(None, 30)
    FONT_SM    = pygame.font.Font(None, 22)
    FONT_XS    = pygame.font.Font(None, 18)
    FONT_EMOJI = pygame.font.Font(None, 22)
    FONT_TINY  = pygame.font.Font(None, 14)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def draw_text_centered(surf, text, font, color, cx, cy):
    s = font.render(text, True, color)
    surf.blit(s, (cx - s.get_width() // 2, cy - s.get_height() // 2))


def draw_text(surf, text, font, color, x, y):
    s = font.render(text, True, color)
    surf.blit(s, (x, y))


def draw_rect_alpha(surf, color, rect, alpha=120):
    tmp = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
    tmp.fill((*color, alpha))
    surf.blit(tmp, (rect[0], rect[1]))


def draw_glow(surf, color, cx, cy, radius, alpha=80):
    """Radial glow effect using concentric alpha circles."""
    for r in range(radius, 0, -max(1, radius // 6)):
        a = int(alpha * (1 - r / radius))
        tmp = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(tmp, (*color, a), (r, r), r)
        surf.blit(tmp, (cx - r, cy - r))


def draw_neon_rect(surf, color, rect, width=2, glow=True, radius=0):
    """Draw a rectangle with a neon glow effect."""
    x, y, w, h = rect
    if glow:
        gl = pygame.Surface((w + 12, h + 12), pygame.SRCALPHA)
        pygame.draw.rect(gl, (*color, 40), (0, 0, w + 12, h + 12), border_radius=radius + 4)
        surf.blit(gl, (x - 6, y - 6))
    pygame.draw.rect(surf, color, rect, width, border_radius=radius)


def draw_server_rack_detailed(surf, x, y, w, h, label="RACK"):
    """16-bit style server rack — the star of the data center."""
    # Cabinet body
    pygame.draw.rect(surf, (20, 25, 40), (x, y, w, h))
    pygame.draw.rect(surf, STEEL, (x, y, w, h), 2)
    # Rack units (drive bays)
    unit_h = 18
    now = pygame.time.get_ticks()
    for i in range(min(8, h // unit_h)):
        uy = y + 8 + i * unit_h
        if uy + unit_h > y + h - 4:
            break
        pygame.draw.rect(surf, (10, 15, 30), (x+4, uy, w-8, unit_h-2))
        pygame.draw.rect(surf, (40, 50, 70), (x+4, uy, w-8, unit_h-2), 1)
        # LEDs per unit
        for j in range(3):
            lx = x + 8 + j * 10
            on = (now // (300 + i*50 + j*70)) % 2
            lc = LED_GREEN if (on and j == 0) else (LED_RED if (on and j == 1) else (30,30,30))
            pygame.draw.circle(surf, lc, (lx, uy + unit_h//2), 3)
            if on:
                draw_glow(surf, lc, lx, uy + unit_h//2, 5, 120)
        # Drive slot lines
        pygame.draw.rect(surf, (60, 70, 90), (x + w//2, uy+2, w//2-8, unit_h-6), border_radius=2)
    # Label at top
    lt = FONT_TINY.render(label, True, CYAN)
    surf.blit(lt, (x + w//2 - lt.get_width()//2, y + 2))


def draw_monitor_detailed(surf, x, y, w, h, label="PC"):
    """CRT monitor with glowing screen — 16-bit style."""
    now = pygame.time.get_ticks()
    # Monitor body (dark plastic)
    pygame.draw.rect(surf, (25, 30, 45), (x, y+h//5, w, h*4//5), border_radius=4)
    pygame.draw.rect(surf, STEEL, (x, y+h//5, w, h*4//5), 1, border_radius=4)
    # Screen bezel
    pygame.draw.rect(surf, (10, 12, 20), (x+6, y, w-12, h*3//4), border_radius=3)
    # Screen glow (animated)
    screen_pulse = int(40 + 20 * math.sin(now / 1500))
    pygame.draw.rect(surf, SCREEN_BLUE, (x+8, y+2, w-16, h*3//4-4), border_radius=2)
    # Scrolling text on screen
    scroll = (now // 80) % (h * 3 // 4)
    for row in range(3):
        txt = FONT_TINY.render(f"SYS:{row+1:02d}>_", True, (*LED_GREEN, 180))
        surf.blit(txt, (x+10, y + 4 + row*12 - scroll % 36))
    # Screen border glow
    gl = pygame.Surface((w-12, h*3//4), pygame.SRCALPHA)
    pygame.draw.rect(gl, (*CYAN, screen_pulse), (0,0,w-12,h*3//4), 2, border_radius=3)
    surf.blit(gl, (x+6, y))
    # Stand
    pygame.draw.rect(surf, STEEL, (x+w//3, y+h*3//4, w//3, h//6))
    pygame.draw.rect(surf, STEEL, (x+w//4, y+h-6, w//2, 6))
    # Label
    lt = FONT_TINY.render(label, True, GRAY)
    surf.blit(lt, (x + w//2 - lt.get_width()//2, y + h - 16))


def draw_cable_bundle(surf, x1, y1, x2, y2=None, color=CABLE_BLUE, thickness=4):
    """Draw a cable bundle. If y2 is given, draws a diagonal line; otherwise horizontal."""
    if y2 is None:
        y2 = y1
    pygame.draw.line(surf, color, (x1, y1), (x2, y2), thickness)
    hi = (min(255, color[0]+60), min(255, color[1]+60), min(255, color[2]+60))
    pygame.draw.line(surf, hi, (x1, y1 - 1), (x2, y2 - 1), 1)
    steps = max(1, abs(x2 - x1) // 40)
    for i in range(1, steps):
        t = i / steps
        cx = int(x1 + (x2 - x1) * t)
        cy = int(y1 + (y2 - y1) * t)
        pygame.draw.rect(surf, STEEL, (cx - 3, cy - 5, 6, 10), border_radius=2)


def draw_datacenter_bg(surf, x, y, w, h):
    """Data center centerpiece with server bays, cable management, blinking LEDs."""
    now = pygame.time.get_ticks()
    # Cabinet frame
    pygame.draw.rect(surf, (15, 18, 30), (x, y, w, h))
    pygame.draw.rect(surf, STEEL, (x, y, w, h), 3)
    # Title bar
    pygame.draw.rect(surf, (30, 40, 70), (x, y, w, 26))
    title = FONT_XS.render("DATA CENTER — UTFPR", True, CYAN)
    surf.blit(title, (x + w//2 - title.get_width()//2, y + 5))
    # Three server columns
    col_w = (w - 20) // 3
    for col_i in range(3):
        cx = x + 8 + col_i * (col_w + 2)
        cy = y + 30
        pygame.draw.rect(surf, (10, 14, 25), (cx, cy, col_w, h - 38))
        pygame.draw.rect(surf, (40, 50, 70), (cx, cy, col_w, h - 38), 1)
        # Server units in each column
        for row_i in range(5):
            ry = cy + 4 + row_i * 22
            if ry + 20 > y + h - 6:
                break
            pygame.draw.rect(surf, (20, 25, 45), (cx+2, ry, col_w-4, 19))
            # LED cluster
            for li in range(4):
                lx = cx + 5 + li * 7
                phase = (now // (200 + col_i*60 + row_i*40 + li*30)) % 3
                lc = LED_GREEN if phase == 0 else (LED_RED if phase == 1 else (20,20,20))
                pygame.draw.circle(surf, lc, (lx, ry+9), 2)
    # Cable management panel at bottom
    pygame.draw.rect(surf, (8, 10, 20), (x+4, y+h-28, w-8, 24))
    for ci in range(6):
        cx2 = x + 10 + ci * (w-16)//6
        pygame.draw.circle(surf, (60, 80, 120), (cx2, y+h-16), 5)
        pygame.draw.circle(surf, CABLE_BLUE, (cx2, y+h-16), 3)


def draw_router_detailed(surf, x, y, w, h, label="RTR"):
    """Network router with animated signal waves."""
    now = pygame.time.get_ticks()
    pygame.draw.rect(surf, (20, 30, 50), (x, y+h//3, w, h*2//3), border_radius=5)
    pygame.draw.rect(surf, STEEL, (x, y+h//3, w, h*2//3), 2, border_radius=5)
    # Antenna
    pygame.draw.line(surf, STEEL, (x+w//2, y+h//3), (x+w//2, y), 2)
    pygame.draw.circle(surf, CYAN, (x+w//2, y), 4)
    # Signal rings
    sig_r = (now // 300) % 20
    for ring in range(3):
        r = sig_r + ring * 7
        if r < 1:
            continue
        a = max(0, 160 - ring*50 - sig_r*4)
        s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*CYAN, a), (r,r), r, 2)
        surf.blit(s, (x+w//2-r, y-r))
    # LEDs
    for j in range(3):
        lc = LED_GREEN if (now//(400+j*100))%2 else (20,40,20)
        pygame.draw.circle(surf, lc, (x+8+j*10, y+h//3+10), 3)
    lt = FONT_TINY.render(label, True, GRAY)
    surf.blit(lt, (x+w//2-lt.get_width()//2, y+h-14))


# Global binary rain columns state
_RAIN_COLS = None
_RAIN_T = 0


def _init_rain():
    global _RAIN_COLS
    if _RAIN_COLS is None:
        _RAIN_COLS = [
            {"x": i * 18, "y": (i * 73) % 680, "speed": 1.5 + (i % 4) * 0.5,
             "char": "01", "alpha": 80 + (i % 5) * 20}
            for i in range(GAME_W // 18 + 1)
        ]


def draw_binary_rain(surf, sky_top):
    global _RAIN_T
    _init_rain()
    _RAIN_T += 1
    brightness = max(sky_top)
    # Only draw rain in dark backgrounds
    if brightness > 150:
        return
    rain_surf = pygame.Surface((GAME_W, H), pygame.SRCALPHA)
    for col in _RAIN_COLS:
        col["y"] = (col["y"] + col["speed"]) % (H + 20)
        char = "0" if (_RAIN_T // 12 + int(col["x"])) % 2 == 0 else "1"
        ts = FONT_TINY.render(char, True, (*EMERALD, col["alpha"]))
        rain_surf.blit(ts, (col["x"], int(col["y"])))
        # Bright head
        ts2 = FONT_TINY.render(char, True, (*WHITE, 160))
        rain_surf.blit(ts2, (col["x"], int(col["y"]) - 14))
    surf.blit(rain_surf, (0, 0))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def wrap_text(text, font, max_w):
    words = text.split()
    lines = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        if font.size(test)[0] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------------------
# Level data
# ---------------------------------------------------------------------------
LEVELS = [
    # -----------------------------------------------------------------------
    # Level 1 — Camada Física (id=4, displayed as level 1)
    # -----------------------------------------------------------------------
    dict(
        id=4,
        name="Nível 1 — Camada Física",
        spawn=(40, 440),
        sky=("#050a12", "#0a1a28"),
        ground_color="#020508",
        centerpiece=dict(kind="datacenter", x=350, y=260, w=200, h=160),
        platforms=[
            # Starting bridge
            dict(x=0,   y=480, w=160, h=22, kind="bridge"),
            # Step up
            dict(x=150, y=360, w=120, h=22, kind="bridge"),
            # Left server body (visual, not walkable)
            dict(x=0,   y=200, w=120, h=260, kind="server", label="SRC-SRV"),
            # Bridge ON TOP of left server (walkable — cable port is here)
            dict(x=0,   y=200, w=175, h=18,  kind="bridge"),
            # Upper safe crossing
            dict(x=175, y=200, w=130, h=22, kind="bridge"),
            dict(x=325, y=200, w=130, h=22, kind="bridge"),
            dict(x=475, y=200, w=130, h=22, kind="bridge"),
            dict(x=625, y=200, w=130, h=22, kind="bridge"),
            # Step down to destination bridge
            dict(x=625, y=340, w=140, h=22, kind="bridge"),
            # Right server (tall, visual)
            dict(x=775, y=110, w=140, h=420, kind="server", label="DST-SRV"),
            # Bridge BELOW right server — destination plug point
            dict(x=735, y=500, w=185, h=22,  kind="bridge"),
            # Lower DDoS path
            dict(x=155, y=552, w=110, h=22,  kind="bridge"),
            dict(x=305, y=550, w=110, h=22,  kind="bridge"),
            dict(x=455, y=552, w=110, h=22,  kind="bridge"),
            dict(x=605, y=550, w=100, h=22,  kind="bridge"),
            # Decorative
            dict(x=10,  y=510, w=80,  h=60,  kind="monitor", label="MON"),
        ],
        pickups=[
            dict(x=62, y=174, type="cable"),   # ON TOP of left server
        ],
        enemies=[
            dict(x=210, y=522, vx=2.0, minX=155, maxX=305, kind="dos"),
            dict(x=370, y=520, vx=2.2, minX=305, maxX=455, kind="dos"),
            dict(x=530, y=522, vx=2.0, minX=455, maxX=605, kind="dos"),
        ],
        goal=dict(x=780, y=472, w=80, h=28, kind="serverport"),   # ON bridge below right server
        need="cable",
        # BlackHat alternative: pick up DDoS amp on lower path, plant at central router
        pickups_black=[dict(x=370, y=522, type="dos_amp")],
        goal_black=dict(x=420, y=350, w=80, h=60, kind="routerport"),
        need_black="dos_amp",
        enemies_black=[
            dict(x=280, y=170, vx=1.8, minX=175, maxX=475, kind="defender"),
            dict(x=630, y=170, vx=1.8, minX=475, maxX=770, kind="defender"),
        ],
        lesson="FÍSICA: Pegue o CABO na porta do servidor esquerdo. Siga o caminho SUPERIOR e PLUGUE na ponte abaixo do servidor direito!",
        tasks_white=[
            "1. Suba até o topo do servidor esquerdo e pegue o cabo RJ45.",
            "2. Siga o caminho SUPERIOR — seguro, sem DDoS.",
            "3. Desça até a ponte ABAIXO do servidor direito e conecte o cabo!",
        ],
        tasks_black=[
            "1. Use o caminho INFERIOR — seus aliados DDoS estão lá.",
            "2. Pegue o Amplificador DDoS no meio do caminho.",
            "3. Plante no roteador central para comprometer a rede!",
        ],
        thoughts_text=[
            "Porta de cabo no topo do servidor esquerdo.",
            "Cabo coletado — o fio se estica enquanto ando!",
            "Devo descer até a ponte abaixo do servidor direito.",
            "Porta destino na ponte — plugue para conectar!",
        ],
    ),
    # -----------------------------------------------------------------------
    # Level 2 — Camada de Rede (id=3)
    # -----------------------------------------------------------------------
    dict(
        id=3,
        name="Nível 2 — Camada de Rede",
        spawn=(60, 420),
        sky=("#0b1b3a", "#1e3a8a"),
        ground_color="#0a1428",
        centerpiece=dict(kind="globe", x=380, y=230, w=200, h=240),
        platforms=[
            dict(x=30,  y=110, w=120, h=80,  kind="scanner", label="SCAN"),
            dict(x=800, y=80,  w=140, h=130, kind="rack",    label="RACK"),
            dict(x=40,  y=470, w=130, h=70,  kind="tablet",  label="TABLET"),
            dict(x=380, y=480, w=200, h=60,  kind="laptop",  label="LAPTOP"),
            dict(x=800, y=470, w=130, h=70,  kind="phone",   label="PHONE"),
            dict(x=20,  y=460, w=210, h=22,  kind="bridge"),
            dict(x=250, y=400, w=160, h=22,  kind="bridge"),
            dict(x=430, y=340, w=160, h=22,  kind="bridge"),
            dict(x=400, y=260, w=160, h=22,  kind="bridge"),
            dict(x=400, y=170, w=160, h=22,  kind="bridge"),
            dict(x=610, y=280, w=180, h=22,  kind="bridge"),
            dict(x=760, y=280, w=200, h=22,  kind="bridge"),
        ],
        pickups=[dict(x=480, y=130, type="firewall_key")],
        enemies=[
            dict(x=470, y=220, vx=1.6, minX=290, maxX=660, kind="sniff"),
            dict(x=650, y=220, vx=2.3, minX=350, maxX=900, kind="opponent", chase=True),
        ],
        goal=dict(x=810, y=220, w=60, h=60),
        need="firewall_key",
        pickups_black=[dict(x=440, y=220, type="ip_bomb")],
        goal_black=dict(x=60, y=422, w=80, h=38, kind="routerport"),
        need_black="ip_bomb",
        enemies_black=[
            dict(x=500, y=220, vx=1.8, minX=400, maxX=610, kind="defender"),
            dict(x=200, y=370, vx=2.3, minX=0, maxX=530, kind="opponent", chase=True),
        ],
        lesson="O GLOBO é a Internet. Roteadores encaminham IP. Pegue a chave antes do Sniffer!",
        tasks_white=[
            "1. Escreva origem Grupo A e destino Grupo B no envelope IP.",
            "2. Pegue a chave antes de cruzar o caminho do Sniffer.",
            "3. Lição: sem criptografia, a interceptação lê a mensagem.",
        ],
        tasks_black=[
            "1. Pegue o exploit de roteamento na ponte central.",
            "2. Evite o Defensor que patrulha o caminho.",
            "3. Plante no roteador à esquerda — desvie o tráfego IP!",
        ],
        thoughts_text=[
            "BlackHat: exploit de roteamento na ponte central.",
            "Defensor vigia o caminho de cima.",
            "Plante no roteador (esq.) — desvie os pacotes!",
            "IP sem criptografia: tráfego redirecionável.",
        ],
    ),
    # -----------------------------------------------------------------------
    # Level 3 — Camada de Transporte (id=2)
    # -----------------------------------------------------------------------
    dict(
        id=2,
        name="Nível 3 — Camada de Transporte",
        spawn=(60, 300),
        sky=("#0b1b3a", "#1e3a8a"),
        ground_color="#0a1428",
        centerpiece=dict(kind="disc", x=320, y=260, w=320, h=220),
        platforms=[
            dict(x=30,  y=470, w=130, h=70,  kind="monitor", label="PC"),
            dict(x=800, y=470, w=130, h=70,  kind="pc",      label="PC"),
            dict(x=800, y=80,  w=140, h=100, kind="rack",    label="RACK"),
            dict(x=30,  y=80,  w=130, h=100, kind="scanner", label="SCAN"),
            dict(x=20,  y=340, w=200, h=22,  kind="bridge"),
            dict(x=20,  y=220, w=200, h=22,  kind="bridge"),
            dict(x=240, y=280, w=180, h=22,  kind="bridge"),
            dict(x=440, y=280, w=180, h=22,  kind="bridge"),
            dict(x=640, y=220, w=160, h=22,  kind="bridge"),
            dict(x=760, y=130, w=200, h=22,  kind="bridge"),
            dict(x=760, y=250, w=200, h=22,  kind="bridge"),
            dict(x=760, y=370, w=200, h=22,  kind="bridge"),
        ],
        pickups=[dict(x=60, y=40, type="terminal")],
        enemies=[
            dict(x=530, y=240, vx=2.0, minX=460, maxX=600, kind="dos"),
            dict(x=600, y=180, vx=2.4, minX=250, maxX=850, kind="opponent", chase=True),
        ],
        goal=dict(x=850, y=300, w=70, h=70),
        need="fragments3",
        fragment_positions=[(100, 190), (530, 242), (860, 90)],
        pickups_black=[
            dict(x=260, y=242, type="syn_packet", id=1),
            dict(x=530, y=242, type="syn_packet", id=2),
            dict(x=850, y=90,  type="syn_packet", id=3),
        ],
        goal_black=dict(x=100, y=183, w=80, h=37, kind="routerport"),
        need_black="syn_flood3",
        enemies_black=[
            dict(x=840, y=90, vx=2.0, minX=760, maxX=960, kind="defender"),
            dict(x=120, y=180, vx=2.4, minX=0, maxX=430, kind="opponent", chase=True),
        ],
        lesson="Mensagens são quebradas em PACOTES (1/3, 2/3, 3/3). Colete em ordem!",
        tasks_white=[
            "1. Corte a mensagem em 3 pacotes numerados.",
            "2. Colete 1/3, depois 2/3, depois 3/3 — fora de ordem não conta.",
            "3. Lição: DoS bloqueia o cabo e derruba a disponibilidade.",
        ],
        tasks_black=[
            "1. Pegue o SYN-flood amplifier no centro (ponte y=280).",
            "2. Evite o Defensor no topo direito.",
            "3. Plante no SCAN esquerdo — derruba o TCP!",
        ],
        thoughts_text=[
            "BlackHat: SYN-flood amplifier no centro.",
            "Aliado DoS bloqueie o canal central!",
            "Defensor no rack superior direito.",
            "Plante no SCAN (esq.) — TCP cai!",
        ],
    ),
    # -----------------------------------------------------------------------
    # Level 4 — Camada de Aplicação (id=1)
    # -----------------------------------------------------------------------
    dict(
        id=1,
        name="Nível 4 — Camada de Aplicação",
        spawn=(60, 300),
        sky=("#0b1b3a", "#1e3a8a"),
        ground_color="#0a1428",
        centerpiece=dict(kind="cloudhub", x=340, y=220, w=280, h=180),
        platforms=[
            dict(x=40,  y=470, w=120, h=70,  kind="phone",   label="PHONE"),
            dict(x=410, y=470, w=160, h=70,  kind="laptop",  label="LAPTOP"),
            dict(x=800, y=470, w=130, h=70,  kind="phone",   label="PHONE"),
            dict(x=40,  y=90,  w=130, h=90,  kind="monitor", label="PC"),
            dict(x=800, y=90,  w=140, h=100, kind="rack",    label="RACK"),
            dict(x=20,  y=340, w=220, h=22,  kind="bridge"),
            dict(x=260, y=340, w=180, h=22,  kind="bridge"),
            dict(x=440, y=300, w=180, h=22,  kind="bridge"),
            dict(x=620, y=320, w=160, h=22,  kind="bridge"),
            dict(x=780, y=320, w=180, h=22,  kind="bridge"),
        ],
        pickups=[dict(x=530, y=260, type="hash")],
        enemies=[
            dict(x=320, y=300, vx=1.6, minX=270, maxX=430, kind="tamper"),
            dict(x=700, y=280, vx=2.2, minX=400, maxX=960, kind="opponent", chase=True),
        ],
        goal=dict(x=850, y=260, w=70, h=60),
        need="hash",
        pickups_black=[dict(x=520, y=260, type="cookie_grab")],
        goal_black=dict(x=100, y=303, w=80, h=37, kind="routerport"),
        need_black="cookie_grab",
        enemies_black=[
            dict(x=700, y=280, vx=1.8, minX=620, maxX=780, kind="defender"),
            dict(x=200, y=300, vx=2.2, minX=0, maxX=530, kind="opponent", chase=True),
        ],
        lesson="Tudo converge na NUVEM via APIs. BlackHat tenta ALTERAR a mensagem — pegue o HASH!",
        tasks_white=[
            "1. Escreva a mensagem secreta para o outro grupo.",
            "2. Pegue o hash antes de entregar.",
            "3. Lição: Tampering muda dados; integridade detecta a fraude.",
        ],
        tasks_black=[
            "1. Pegue o exploit de adulteração no centro.",
            "2. Evite o Defensor na ponte direita.",
            "3. Plante no PC esquerdo — adultera a mensagem!",
        ],
        thoughts_text=[
            "BlackHat: adultera mensagem na aplicação.",
            "Aliados Tamper cobrem o caminho central.",
            "Defensor na ponte direita — cuidado!",
            "Plante no PC (esq.) — hash corrompido!",
        ],
    ),
]

# ---------------------------------------------------------------------------
# OSI model — 7 levels
# ---------------------------------------------------------------------------
LEVELS_OSI = [
    dict(
        id=7, name="OSI L1 — Física", spawn=(40, 440),
        sky=("#050a12", "#0a1a28"), ground_color="#020508",
        centerpiece=dict(kind="datacenter", x=340, y=255, w=200, h=160),
        platforms=[
            # Starting bridge
            dict(x=0,   y=480, w=160, h=22, kind="bridge"),
            # Step up toward left server
            dict(x=150, y=360, w=120, h=22, kind="bridge"),
            # Left server body (visual, not walkable)
            dict(x=0,   y=200, w=120, h=260, kind="server", label="SRC-SRV"),
            # Bridge ON TOP of left server — cable port is here
            dict(x=0,   y=200, w=175, h=18,  kind="bridge"),
            # Upper safe crossing path
            dict(x=175, y=200, w=130, h=22, kind="bridge"),
            dict(x=325, y=200, w=130, h=22, kind="bridge"),
            dict(x=475, y=200, w=130, h=22, kind="bridge"),
            dict(x=625, y=200, w=130, h=22, kind="bridge"),
            # Step down from upper path to destination bridge
            dict(x=625, y=340, w=140, h=22, kind="bridge"),
            # Right server (tall, visual)
            dict(x=775, y=110, w=140, h=420, kind="server", label="DST-SRV"),
            # Bridge BELOW right server — destination plug point
            dict(x=735, y=500, w=185, h=22,  kind="bridge"),
            # Lower DDoS path
            dict(x=155, y=552, w=110, h=22,  kind="bridge"),
            dict(x=305, y=550, w=110, h=22,  kind="bridge"),
            dict(x=455, y=552, w=110, h=22,  kind="bridge"),
            dict(x=605, y=550, w=100, h=22,  kind="bridge"),
            # Decorative
            dict(x=10,  y=510, w=80,  h=60,  kind="monitor", label="MON"),
        ],
        pickups=[dict(x=62, y=174, type="cable")],   # ON TOP of left server
        enemies=[
            dict(x=210, y=522, vx=2.0, minX=155, maxX=305, kind="dos"),
            dict(x=370, y=520, vx=2.2, minX=305, maxX=455, kind="dos"),
            dict(x=530, y=522, vx=2.0, minX=455, maxX=605, kind="dos"),
            dict(x=400, y=160, vx=2.5, minX=175, maxX=625, kind="opponent", chase=True),
        ],
        goal=dict(x=780, y=472, w=80, h=28, kind="serverport"),  # ON bridge below right server
        need="cable",
        pickups_black=[dict(x=370, y=505, type="dos_amp")],
        goal_black=dict(x=420, y=350, w=80, h=60, kind="routerport"),
        need_black="dos_amp",
        enemies_black=[
            dict(x=280, y=160, vx=1.8, minX=175, maxX=475, kind="defender"),
            dict(x=630, y=160, vx=1.8, minX=475, maxX=770, kind="defender"),
            dict(x=440, y=460, vx=2.5, minX=155, maxX=635, kind="opponent", chase=True),
        ],
        lesson="FÍSICA: Porta RJ45 no topo do SRC-SRV. Suba, pegue o cabo, cruze pelo caminho SUPERIOR e conecte na ponte abaixo do DST-SRV!",
        tasks_white=["1. Suba ao topo do SRC-SRV e pegue o cabo RJ45.", "2. Caminho SUPERIOR — DDoS fica embaixo, mas BlackHat te persegue!", "3. Desça até a ponte abaixo do DST-SRV e conecte!"],
        tasks_black=["1. Rota inferior — aliados DDoS protegem você.", "2. Pegue o Amplificador DDoS no caminho inferior.", "3. Plante no roteador — mas WhiteHat vai te perseguir!"],
        thoughts_text=["Porta RJ45 no topo do SRC-SRV!", "Cabo coletado — fio estica enquanto ando.", "BlackHat me persegue — corre!", "Porta destino na ponte abaixo do DST-SRV."],
    ),
    dict(
        id=6, name="OSI L2 — Enlace de Dados", spawn=(40, 380),
        sky=("#080d1a", "#10203a"), ground_color="#050a14",
        centerpiece=dict(kind="disc", x=330, y=240, w=240, h=160),
        platforms=[
            dict(x=0,   y=420, w=180, h=22, kind="bridge"),
            dict(x=200, y=380, w=140, h=22, kind="bridge"),
            dict(x=360, y=340, w=140, h=22, kind="bridge"),
            dict(x=520, y=310, w=140, h=22, kind="bridge"),
            dict(x=680, y=280, w=180, h=22, kind="bridge"),
            dict(x=0,   y=120, w=120, h=110, kind="rack",    label="SWITCH"),
            dict(x=800, y=100, w=110, h=130, kind="server",  label="DEST"),
            dict(x=200, y=200, w=100, h=22,  kind="bridge"),
            dict(x=600, y=180, w=100, h=22,  kind="bridge"),
        ],
        pickups=[dict(x=300, y=290, type="mac_cert")],
        enemies=[
            dict(x=450, y=268, vx=2.0, minX=360, maxX=550, kind="tamper"),
            dict(x=620, y=248, vx=2.3, minX=400, maxX=790, kind="opponent", chase=True),
        ],
        goal=dict(x=820, y=60, w=80, h=40),
        need="mac_cert",
        pickups_black=[dict(x=530, y=270, type="arp_spoofer")],
        goal_black=dict(x=10, y=385, w=80, h=35, kind="routerport"),
        need_black="arp_spoofer",
        enemies_black=[
            dict(x=430, y=240, vx=1.8, minX=340, maxX=660, kind="defender"),
            dict(x=180, y=340, vx=2.3, minX=0, maxX=500, kind="opponent", chase=True),
        ],
        lesson="ENLACE: Quadro MAC identifica dispositivos no switch. ARP Spoofing falsifica MAC — use Certificado MAC para se autenticar!",
        tasks_white=["1. Pegue o Certificado MAC no centro.", "2. Passe pelo Tamper — o cert. MAC te autentica.", "3. BlackHat te persegue! Entregue no servidor rápido."],
        tasks_black=["1. Pegue o ARP Spoofer na ponte central.", "2. Defensor te bloqueia — use o caminho alternativo.", "3. Plante o spoof no switch (esq.) — WhiteHat vai atrás!"],
        thoughts_text=["Certificado MAC = identidade de enlace.", "Tamper não consegue falsificar o MAC cert.", "BlackHat está vindo — corre para o servidor!", "ARP Spoofing troca quem é quem no switch."],
    ),
    dict(
        id=5, name="OSI L3 — Rede", spawn=(40, 420),
        sky=("#0b1b3a", "#1e3a8a"), ground_color="#0a1428",
        centerpiece=dict(kind="globe", x=380, y=230, w=200, h=240),
        platforms=[
            dict(x=0,   y=460, w=180, h=22, kind="bridge"),
            dict(x=200, y=400, w=140, h=22, kind="bridge"),
            dict(x=360, y=350, w=140, h=22, kind="bridge"),
            dict(x=520, y=300, w=140, h=22, kind="bridge"),
            dict(x=680, y=260, w=180, h=22, kind="bridge"),
            dict(x=0,   y=150, w=130, h=110, kind="scanner", label="ROUTER A"),
            dict(x=800, y=100, w=120, h=130, kind="rack",    label="ROUTER B"),
            dict(x=360, y=170, w=140, h=22,  kind="bridge"),
        ],
        pickups=[dict(x=450, y=130, type="firewall_key")],
        enemies=[
            dict(x=420, y=310, vx=1.8, minX=360, maxX=520, kind="sniff"),
            dict(x=650, y=220, vx=2.3, minX=360, maxX=850, kind="opponent", chase=True),
        ],
        goal=dict(x=820, y=60, w=80, h=40),
        need="firewall_key",
        pickups_black=[dict(x=430, y=310, type="ip_bomb")],
        goal_black=dict(x=10, y=420, w=80, h=40, kind="routerport"),
        need_black="ip_bomb",
        enemies_black=[
            dict(x=570, y=220, vx=2.0, minX=400, maxX=660, kind="defender"),
            dict(x=200, y=360, vx=2.3, minX=0, maxX=530, kind="opponent", chase=True),
        ],
        lesson="REDE: Roteadores encaminham pacotes IP. Regra de Firewall protege a rota — IP Bomb do BlackHat explode o roteador!",
        tasks_white=["1. Pegue a Regra de Firewall no Roteador A.", "2. Sniffer espia sem a regra — ela cifra a rota.", "3. BlackHat te persegue! Entregue rápido no Roteador B."],
        tasks_black=["1. Pegue a IP Bomb na ponte central.", "2. Defensor bloqueia o alto — contorne.", "3. Plante no Roteador A — WhiteHat vai atrás de você!"],
        thoughts_text=["Regra de Firewall cifra e protege a rota IP.", "Sniffer não lê pacotes cifrados!", "BlackHat vem com IP Bomb — acelera!", "IP Bomb explode roteadores não protegidos."],
    ),
    dict(
        id=4, name="OSI L4 — Transporte", spawn=(40, 300),
        sky=("#0a1520", "#142030"), ground_color="#080f18",
        centerpiece=dict(kind="disc", x=310, y=250, w=300, h=200),
        platforms=[
            dict(x=0,   y=340, w=180, h=22, kind="bridge"),
            dict(x=0,   y=220, w=180, h=22, kind="bridge"),
            dict(x=200, y=280, w=160, h=22, kind="bridge"),
            dict(x=380, y=280, w=140, h=22, kind="bridge"),
            dict(x=540, y=220, w=140, h=22, kind="bridge"),
            dict(x=700, y=140, w=180, h=22, kind="bridge"),
            dict(x=700, y=260, w=180, h=22, kind="bridge"),
            dict(x=700, y=370, w=180, h=22, kind="bridge"),
            dict(x=0,   y=90,  w=130, h=100, kind="scanner", label="PC-A"),
            dict(x=800, y=450, w=110, h=90,  kind="monitor", label="PC-B"),
        ],
        pickups=[dict(x=60, y=50, type="terminal")],
        enemies=[
            dict(x=460, y=240, vx=2.2, minX=380, maxX=540, kind="dos"),
            dict(x=550, y=180, vx=2.4, minX=200, maxX=700, kind="opponent", chase=True),
        ],
        goal=dict(x=810, y=390, w=70, h=60),
        need="fragments3",
        fragment_positions=[(90, 185), (460, 242), (800, 102)],
        pickups_black=[
            dict(x=260, y=242, type="syn_packet", id=1),
            dict(x=460, y=242, type="syn_packet", id=2),
            dict(x=750, y=182, type="syn_packet", id=3),
        ],
        goal_black=dict(x=10, y=183, w=80, h=37, kind="routerport"),
        need_black="syn_flood3",
        enemies_black=[
            dict(x=600, y=180, vx=2.0, minX=540, maxX=690, kind="defender"),
            dict(x=100, y=180, vx=2.4, minX=0, maxX=450, kind="opponent", chase=True),
        ],
        lesson="TRANSPORTE TCP: WhiteHat escreve mensagem no terminal — ela se fragmenta em 3 pacotes! BlackHat envia SYN Flood para derrubar o canal.",
        tasks_white=["1. Vá ao terminal PC-A (canto sup. esq.) e escreva uma mensagem.", "2. A mensagem fragmenta em 3 partes espalhadas no mapa!", "3. Colete frag 1→2→3 em ordem e entregue no PC-B."],
        tasks_black=["1. Colete os 3 SYN Packets espalhados no mapa.", "2. Defensor e WhiteHat vão te perseguir — seja rápido!", "3. Plante os 3 SYN no PC-A — SYN Flood derruba o TCP!"],
        thoughts_text=["Terminal no PC-A — escreva a mensagem!", "Mensagem fragmentada em 3 partes na rede.", "Colete em ordem: frag 1, depois 2, depois 3.", "BlackHat usa SYN Flood — TCP cai com 3 pacotes falsos."],
    ),
    dict(
        id=3, name="OSI L5 — Sessão", spawn=(40, 380),
        sky=("#0d0520", "#180a35"), ground_color="#08031a",
        centerpiece=dict(kind="cloudhub", x=330, y=220, w=260, h=180),
        platforms=[
            dict(x=0,   y=420, w=180, h=22, kind="bridge"),
            dict(x=200, y=380, w=130, h=22, kind="bridge"),
            dict(x=350, y=330, w=130, h=22, kind="bridge"),
            dict(x=500, y=280, w=140, h=22, kind="bridge"),
            dict(x=660, y=240, w=180, h=22, kind="bridge"),
            dict(x=0,   y=140, w=120, h=110, kind="rack",   label="SSH-SRV"),
            dict(x=800, y=120, w=110, h=120, kind="server", label="SESSION"),
            dict(x=300, y=170, w=120, h=22,  kind="bridge"),
        ],
        pickups=[dict(x=360, y=130, type="tls_cert")],
        enemies=[
            dict(x=500, y=240, vx=2.0, minX=400, maxX=600, kind="sniff"),
            dict(x=670, y=200, vx=2.3, minX=400, maxX=860, kind="opponent", chase=True),
        ],
        goal=dict(x=820, y=80, w=80, h=40),
        need="tls_cert",
        pickups_black=[dict(x=510, y=240, type="cookie_grab")],
        goal_black=dict(x=10, y=383, w=80, h=37, kind="routerport"),
        need_black="cookie_grab",
        enemies_black=[
            dict(x=360, y=290, vx=1.8, minX=280, maxX=480, kind="defender"),
            dict(x=700, y=200, vx=2.3, minX=300, maxX=860, kind="opponent", chase=True),
        ],
        lesson="SESSÃO: Certificado TLS autentica sessões SSH. Cookie Stealer rouba sessão em HTTP sem HTTPS!",
        tasks_white=["1. Pegue o Certificado TLS no SSH-SRV.", "2. Sniffer tenta roubar a sessão — TLS criptografa!", "3. BlackHat te persegue! Autentique no SESSION server."],
        tasks_black=["1. Pegue o Cookie Stealer na ponte central.", "2. Defensor bloqueia o centro — vire pela direita.", "3. Roube a sessão no SSH-SRV — WhiteHat vai atrás!"],
        thoughts_text=["TLS Cert = sessão autenticada e cifrada.", "Sniffer não quebra TLS — estou protegido!", "BlackHat usa Cookie Stealer — HTTPS previne isso.", "SESSION server aguarda autenticação TLS."],
    ),
    dict(
        id=2, name="OSI L6 — Apresentação", spawn=(40, 380),
        sky=("#15082a", "#25104a"), ground_color="#0d0520",
        centerpiece=dict(kind="cloudhub", x=320, y=220, w=280, h=180),
        platforms=[
            dict(x=0,   y=420, w=200, h=22, kind="bridge"),
            dict(x=220, y=380, w=160, h=22, kind="bridge"),
            dict(x=400, y=340, w=160, h=22, kind="bridge"),
            dict(x=580, y=300, w=180, h=22, kind="bridge"),
            dict(x=0,   y=200, w=130, h=110, kind="monitor", label="CRIPTO"),
            dict(x=800, y=150, w=110, h=120, kind="server",  label="DESTINO"),
            dict(x=300, y=200, w=140, h=22,  kind="bridge"),
            dict(x=580, y=180, w=120, h=22,  kind="bridge"),
        ],
        pickups=[dict(x=450, y=310, type="hash")],
        enemies=[
            dict(x=600, y=260, vx=2.2, minX=280, maxX=850, kind="opponent", chase=True),
        ],
        goal=dict(x=820, y=110, w=80, h=40),
        need="hash",
        pickups_black=[dict(x=450, y=305, type="hash")],
        goal_black=dict(x=820, y=110, w=80, h=40),
        need_black="hash",
        enemies_black=[
            dict(x=620, y=260, vx=1.6, minX=530, maxX=800, kind="defender"),
            dict(x=200, y=340, vx=2.2, minX=0, maxX=580, kind="opponent", chase=True),
        ],
        lesson="APRESENTAÇÃO: Cifre a mensagem com César antes de enviar. BlackHat tenta decifrar testando deslocamentos 1-9!",
        tasks_white=["1. Vá ao terminal CRIPTO (esquerda) para cifrar.", "2. Digite a mensagem e escolha deslocamento 1-9.", "3. Pegue o hash e entregue cifrado no servidor."],
        tasks_black=["1. Aproxime-se do centro para interceptar a cifra.", "2. Teste deslocamentos 1-9 para decifrar.", "3. Desvie do Defensor e entregue a mensagem decifrada!"],
        thoughts_text=["BlackHat: intercepta cifra César no centro.", "Defensor patrulha a ponte direita.", "Acerte o deslocamento — leia a mensagem!", "Sem criptografia forte qualquer um decifra."],
        minigame_layer=True,
    ),
    dict(
        id=1, name="OSI L7 — Aplicação", spawn=(40, 380),
        sky=("#0a1820", "#102030"), ground_color="#050e14",
        centerpiece=dict(kind="cloudhub", x=330, y=210, w=280, h=190),
        platforms=[
            dict(x=0,   y=420, w=180, h=22, kind="bridge"),
            dict(x=200, y=380, w=140, h=22, kind="bridge"),
            dict(x=360, y=330, w=140, h=22, kind="bridge"),
            dict(x=520, y=290, w=140, h=22, kind="bridge"),
            dict(x=680, y=250, w=180, h=22, kind="bridge"),
            dict(x=0,   y=150, w=130, h=110, kind="monitor", label="APP-CLI"),
            dict(x=800, y=120, w=110, h=120, kind="server",  label="HTTP-SRV"),
            dict(x=350, y=180, w=120, h=22,  kind="bridge"),
        ],
        pickups=[dict(x=460, y=290, type="hash")],
        enemies=[
            dict(x=380, y=290, vx=1.8, minX=300, maxX=500, kind="tamper"),
            dict(x=650, y=210, vx=2.2, minX=300, maxX=860, kind="opponent", chase=True),
        ],
        goal=dict(x=820, y=80, w=80, h=40),
        need="hash",
        pickups_black=[dict(x=460, y=285, type="hash")],
        goal_black=dict(x=820, y=80, w=80, h=40),
        need_black="hash",
        tamper_on_pickup=True,
        enemies_black=[
            dict(x=560, y=250, vx=1.8, minX=460, maxX=720, kind="defender"),
            dict(x=200, y=290, vx=2.2, minX=0, maxX=600, kind="opponent", chase=True),
        ],
        lesson="APLICAÇÃO: HTTP, SSH, DNS — camada do usuário. Defina senha SSH para proteger o hash contra Tampering!",
        tasks_white=["1. Vá ao APP-CLI (esquerda) e defina senha SSH.", "2. Pegue o hash protegido por SSH.", "3. Entregue no HTTP-SRV sem ser adulterado."],
        tasks_black=["1. Intercepte o hash no centro (adultera ao coletar).", "2. Altere o conteúdo da mensagem no diálogo.", "3. Entregue a versão adulterada no HTTP-SRV!"],
        thoughts_text=["BlackHat: adultera o hash da aplicação.", "Altere a mensagem — não pode ser igual ao original.", "Tampering modifica dados em trânsito.", "Defensor patrulha a rota da entrega."],
        ssh_layer=True,
    ),
]

# ---------------------------------------------------------------------------
# TCP/IP model — 4 levels
# ---------------------------------------------------------------------------
LEVELS_TCPIP = [
    dict(
        id=4, name="TCP/IP L1 — Acesso à Rede", spawn=(40, 440),
        sky=("#050a12", "#0a1a28"), ground_color="#020508",
        centerpiece=dict(kind="datacenter", x=340, y=255, w=200, h=160),
        platforms=[
            dict(x=0,   y=480, w=160, h=22, kind="bridge"),
            dict(x=150, y=360, w=120, h=22, kind="bridge"),
            dict(x=0,   y=200, w=120, h=260, kind="server", label="SWITCH"),
            dict(x=0,   y=200, w=175, h=18,  kind="bridge"),
            dict(x=175, y=200, w=130, h=22, kind="bridge"),
            dict(x=325, y=200, w=130, h=22, kind="bridge"),
            dict(x=475, y=200, w=130, h=22, kind="bridge"),
            dict(x=625, y=200, w=130, h=22, kind="bridge"),
            dict(x=625, y=340, w=140, h=22, kind="bridge"),
            dict(x=775, y=110, w=140, h=420, kind="server", label="DST-SRV"),
            dict(x=735, y=500, w=185, h=22,  kind="bridge"),
            dict(x=155, y=552, w=110, h=22,  kind="bridge"),
            dict(x=305, y=550, w=110, h=22,  kind="bridge"),
            dict(x=455, y=552, w=110, h=22,  kind="bridge"),
            dict(x=605, y=550, w=100, h=22,  kind="bridge"),
            dict(x=10,  y=510, w=80,  h=60,  kind="monitor", label="MON"),
        ],
        pickups=[dict(x=62, y=174, type="cable")],
        enemies=[
            dict(x=210, y=522, vx=2.0, minX=155, maxX=305, kind="dos"),
            dict(x=370, y=520, vx=2.2, minX=305, maxX=455, kind="dos"),
            dict(x=530, y=522, vx=2.0, minX=455, maxX=605, kind="dos"),
            dict(x=400, y=160, vx=2.5, minX=175, maxX=625, kind="opponent", chase=True),
        ],
        goal=dict(x=780, y=472, w=80, h=28, kind="serverport"),
        need="cable",
        pickups_black=[dict(x=370, y=505, type="dos_amp")],
        goal_black=dict(x=420, y=350, w=80, h=60, kind="routerport"),
        need_black="dos_amp",
        enemies_black=[
            dict(x=280, y=160, vx=1.8, minX=175, maxX=475, kind="defender"),
            dict(x=630, y=160, vx=1.8, minX=475, maxX=770, kind="defender"),
            dict(x=440, y=460, vx=2.5, minX=155, maxX=635, kind="opponent", chase=True),
        ],
        lesson="ACESSO À REDE: Física + Enlace combinados. Pegue o cabo no topo do switch e conecte no servidor via caminho superior!",
        tasks_white=["1. Suba ao topo do switch e pegue o cabo Ethernet.", "2. Caminho superior é seguro — DDoS fica embaixo.", "3. Desça até a ponte abaixo do servidor e conecte!"],
        tasks_black=["1. Rota inferior: aliados DDoS protegem você.", "2. Pegue o Amplificador DDoS.", "3. Plante no roteador e tombe a rede física!"],
        thoughts_text=["Acesso à Rede: Física + Enlace.", "Porta RJ45 no topo do switch!", "DDoS na rota inferior.", "Ponte abaixo do servidor: porta destino."],
    ),
    dict(
        id=3, name="TCP/IP L2 — Internet", spawn=(40, 420),
        sky=("#0b1b3a", "#1e3a8a"), ground_color="#0a1428",
        centerpiece=dict(kind="globe", x=380, y=230, w=200, h=240),
        platforms=[
            dict(x=0,   y=460, w=180, h=22, kind="bridge"),
            dict(x=200, y=400, w=140, h=22, kind="bridge"),
            dict(x=360, y=350, w=140, h=22, kind="bridge"),
            dict(x=520, y=300, w=140, h=22, kind="bridge"),
            dict(x=680, y=260, w=180, h=22, kind="bridge"),
            dict(x=0,   y=150, w=120, h=110, kind="scanner", label="ROUTER A"),
            dict(x=800, y=100, w=120, h=130, kind="rack",    label="ROUTER B"),
            dict(x=360, y=170, w=140, h=22,  kind="bridge"),
        ],
        pickups=[dict(x=450, y=130, type="firewall_key")],
        enemies=[
            dict(x=420, y=310, vx=1.8, minX=360, maxX=520, kind="sniff"),
            dict(x=650, y=220, vx=2.3, minX=360, maxX=850, kind="opponent", chase=True),
        ],
        goal=dict(x=820, y=60, w=80, h=40),
        need="firewall_key",
        pickups_black=[dict(x=430, y=310, type="ip_bomb")],
        goal_black=dict(x=10, y=420, w=80, h=40, kind="routerport"),
        need_black="ip_bomb",
        enemies_black=[
            dict(x=570, y=220, vx=2.0, minX=400, maxX=660, kind="defender"),
            dict(x=200, y=360, vx=2.3, minX=0, maxX=530, kind="opponent", chase=True),
        ],
        lesson="INTERNET: IP roteia globalmente. Regra de Firewall protege pacotes — IP Bomb do BlackHat explode roteadores!",
        tasks_white=["1. Pegue a Regra de Firewall no Roteador A.", "2. Sniffer espia rotas abertas — regra cifra.", "3. BlackHat te persegue! Entregue no Roteador B."],
        tasks_black=["1. Pegue a IP Bomb na ponte central.", "2. Defensor na ponte — contorne.", "3. Explode o Roteador A — WhiteHat vai atrás!"],
        thoughts_text=["Regra de Firewall cifra a rota IP.", "Sniffer não lê pacotes protegidos.", "BlackHat vem com IP Bomb!", "IP Bomb explode roteadores abertos."],
    ),
    dict(
        id=2, name="TCP/IP L3 — Transporte", spawn=(40, 300),
        sky=("#0a1520", "#142030"), ground_color="#080f18",
        centerpiece=dict(kind="disc", x=310, y=250, w=300, h=200),
        platforms=[
            dict(x=0,   y=340, w=180, h=22, kind="bridge"),
            dict(x=0,   y=220, w=180, h=22, kind="bridge"),
            dict(x=200, y=280, w=160, h=22, kind="bridge"),
            dict(x=380, y=280, w=140, h=22, kind="bridge"),
            dict(x=540, y=220, w=140, h=22, kind="bridge"),
            dict(x=700, y=140, w=180, h=22, kind="bridge"),
            dict(x=700, y=260, w=180, h=22, kind="bridge"),
            dict(x=700, y=370, w=180, h=22, kind="bridge"),
            dict(x=0,   y=90,  w=130, h=100, kind="scanner", label="TCP-A"),
            dict(x=800, y=450, w=110, h=90,  kind="monitor", label="TCP-B"),
        ],
        pickups=[dict(x=60, y=50, type="terminal")],
        enemies=[
            dict(x=460, y=240, vx=2.2, minX=380, maxX=540, kind="dos"),
            dict(x=550, y=180, vx=2.4, minX=200, maxX=680, kind="opponent", chase=True),
        ],
        goal=dict(x=810, y=390, w=70, h=60),
        need="fragments3",
        fragment_positions=[(90, 185), (460, 242), (800, 102)],
        pickups_black=[
            dict(x=260, y=242, type="syn_packet", id=1),
            dict(x=460, y=242, type="syn_packet", id=2),
            dict(x=750, y=182, type="syn_packet", id=3),
        ],
        goal_black=dict(x=10, y=183, w=80, h=37, kind="routerport"),
        need_black="syn_flood3",
        enemies_black=[
            dict(x=600, y=180, vx=2.0, minX=540, maxX=690, kind="defender"),
            dict(x=100, y=180, vx=2.4, minX=0, maxX=450, kind="opponent", chase=True),
        ],
        lesson="TRANSPORTE TCP/IP: WhiteHat escreve mensagem no terminal — fragmenta em 3 pacotes! BlackHat faz SYN Flood para derrubar o canal.",
        tasks_white=["1. Vá ao terminal TCP-A (canto sup. esq.) e escreva.", "2. Mensagem fragmenta em 3 partes espalhadas!", "3. Colete frag 1→2→3 e entregue no TCP-B."],
        tasks_black=["1. Colete os 3 SYN Packets espalhados.", "2. Defensor + WhiteHat vão te perseguir!", "3. Plante no TCP-A — SYN Flood derruba TCP!"],
        thoughts_text=["Terminal no TCP-A — escreva a mensagem!", "Fragmentos espalhados na rede.", "Colete frag 1, 2, 3 em ordem.", "SYN Flood usa 3 pacotes falsos para derrubar TCP."],
    ),
    dict(
        id=1, name="TCP/IP L4 — Aplicação", spawn=(40, 380),
        sky=("#0a1820", "#102030"), ground_color="#050e14",
        centerpiece=dict(kind="cloudhub", x=320, y=210, w=280, h=190),
        platforms=[
            dict(x=0,   y=420, w=180, h=22, kind="bridge"),
            dict(x=200, y=380, w=140, h=22, kind="bridge"),
            dict(x=360, y=330, w=140, h=22, kind="bridge"),
            dict(x=520, y=290, w=140, h=22, kind="bridge"),
            dict(x=680, y=250, w=180, h=22, kind="bridge"),
            dict(x=0,   y=150, w=130, h=110, kind="monitor", label="APP-CLI"),
            dict(x=800, y=120, w=110, h=120, kind="server",  label="HTTP-SRV"),
            dict(x=350, y=180, w=120, h=22,  kind="bridge"),
        ],
        pickups=[dict(x=460, y=300, type="hash")],
        enemies=[dict(x=380, y=298, vx=1.8, minX=300, maxX=500, kind="tamper")],
        goal=dict(x=820, y=80, w=80, h=40),
        need="hash",
        pickups_black=[dict(x=460, y=295, type="hash")],
        goal_black=dict(x=820, y=80, w=80, h=40),
        need_black="intercepted_phrase",
        confirm_phrase="HTTP-PAYLOAD",
        enemies_black=[dict(x=560, y=250, vx=1.8, minX=460, maxX=720, kind="defender")],
        lesson="APLICAÇÃO TCP/IP: HTTP, SSH, DNS. Cifre com César, defina senha SSH, entregue com integridade!",
        tasks_white=["1. Acesse APP-CLI e cifre sua mensagem com César.", "2. Defina senha SSH para proteger o hash.", "3. Entregue o hash no HTTP-SRV."],
        tasks_black=["1. Intercepte a frase no centro da rede.", "2. Memorize a frase exibida no toast.", "3. Leve ao HTTP-SRV e confirme digitando a frase!"],
        thoughts_text=["BlackHat: intercepta o hash da aplicação.", "Se SSH ativo — decifra César primeiro.", "Defensor cobre a rota de entrega.", "HTTP sem HTTPS: qualquer um intercepta!"],
        minigame_layer=True,
        ssh_layer=True,
    ),
]

# Shared César cipher state (persists across levels)
CESAR_STATE = {
    "original": "",
    "encrypted": "",
    "shift": 0,
    "ssh_locked": False,
    "ssh_password": "",
}

# Device colours lookup
DEVICE_COLORS = {
    "rack":    (40, 60, 100),
    "server":  (30, 80, 140),
    "pc":      (20, 100, 80),
    "monitor": (20, 80, 120),
    "laptop":  (60, 80, 40),
    "scanner": (80, 40, 100),
    "tablet":  (40, 100, 100),
    "phone":   (100, 40, 60),
    "wifi":    (0, 120, 160),
    "router":  (80, 80, 20),
    "cloud":   (60, 60, 120),
    "bridge":  (TAN[0], TAN[1], TAN[2]),
}

ENEMY_COLORS = {
    "sniff":    (200, 30, 30),
    "dos":      (230, 120, 0),
    "tamper":   (140, 30, 200),
    "defender": (0, 140, 200),
}

ENEMY_ICONS = {
    "sniff":    "👀",
    "dos":      "💥",
    "tamper":   "⚠️",
    "defender": "🛡",
}


# ---------------------------------------------------------------------------
# Drawing helpers — sprites
# ---------------------------------------------------------------------------
def draw_player(surf, x, y, char, facing=1, anim_frame=0):
    """16-bit Spy vs Spy cartoon spy character."""
    if char in SPRITES:
        sp = SPRITES[char]
        frames = sp["right"] if facing >= 0 else sp["left"]
        frame  = frames[anim_frame % len(frames)]
        sw, sh = sp["size"]
        dx = (PW - sw) // 2
        dy = (PH - sh)
        surf.blit(frame, (x + dx, y + dy))
        return

    now = pygame.time.get_ticks()
    # Walk cycle: slight body lean
    lean = int(2 * math.sin(anim_frame * 1.2)) if anim_frame else 0
    fx = 1 if facing >= 0 else -1

    if char == "white":
        skin = (255, 220, 175)
        body = (230, 230, 230)
        suit = (200, 200, 210)
        hat_col = WHITE
        eye_col = BLACK
        # Shadow
        draw_rect_alpha(surf, (0,0,0), (x+2, y+PH-3, PW-4, 5), 60)
        # Legs (animated)
        leg1_y = y + PH - 10 + (abs(lean) if lean else 0)
        leg2_y = y + PH - 10 - (abs(lean) if lean else 0)
        pygame.draw.rect(surf, suit, (x+3, leg1_y, 7, 10))
        pygame.draw.rect(surf, suit, (x+PW-10, leg2_y, 7, 10))
        # Shoes
        pygame.draw.ellipse(surf, BLACK, (x+1, y+PH-4, 10, 6))
        pygame.draw.ellipse(surf, BLACK, (x+PW-11, y+PH-4, 10, 6))
        # Body / suit
        pygame.draw.rect(surf, body, (x+2, y+PH//2, PW-4, PH//2-8), border_radius=3)
        pygame.draw.rect(surf, BLACK, (x+2, y+PH//2, PW-4, PH//2-8), 1, border_radius=3)
        # Tie
        pygame.draw.polygon(surf, BLACK,
                            [(x+PW//2, y+PH//2+2), (x+PW//2-3, y+PH-14),
                             (x+PW//2+3, y+PH-14)])
        # Arms
        arm_swing = int(3 * math.sin(anim_frame * 1.2))
        pygame.draw.line(surf, suit, (x+2, y+PH//2+4), (x-4, y+PH//2+12+arm_swing), 4)
        pygame.draw.line(surf, suit, (x+PW-2, y+PH//2+4), (x+PW+4, y+PH//2+12-arm_swing), 4)
        # Neck
        pygame.draw.rect(surf, skin, (x+PW//2-3, y+PH//2-4, 6, 6))
        # Head
        pygame.draw.ellipse(surf, skin, (x+4, y+4, PW-8, PH//2-2))
        pygame.draw.ellipse(surf, BLACK, (x+4, y+4, PW-8, PH//2-2), 1)
        # Eyes
        ex = x+7 if fx > 0 else x+PW-11
        pygame.draw.circle(surf, WHITE, (ex+3, y+PH//4+2), 4)
        pygame.draw.circle(surf, eye_col, (ex+3+(1*fx), y+PH//4+2), 2)
        # Nose
        pygame.draw.circle(surf, (220,170,130), (x+PW//2+(2*fx), y+PH//4+6), 2)
        # Hat — tall white spy hat
        pygame.draw.rect(surf, hat_col, (x-2, y+2, PW+4, 5))   # brim
        pygame.draw.rect(surf, BLACK, (x-2, y+2, PW+4, 5), 1)
        pygame.draw.rect(surf, hat_col, (x+3, y-14, PW-6, 18))  # crown
        pygame.draw.rect(surf, BLACK, (x+3, y-14, PW-6, 18), 1)
        # Hat band
        pygame.draw.rect(surf, BLACK, (x+3, y+0, PW-6, 3))

    else:  # black hat spy
        skin = (200, 160, 110)
        body = (20, 20, 20)
        eye_col = (220, 30, 30)
        # Shadow
        draw_rect_alpha(surf, (0,0,0), (x+2, y+PH-3, PW-4, 5), 80)
        # Glow aura (evil)
        draw_glow(surf, RED_HAT, x+PW//2, y+PH//2, 18, 40)
        # Legs
        lean = int(2 * math.sin(anim_frame * 1.2)) if anim_frame else 0
        pygame.draw.rect(surf, body, (x+3, y+PH-12+abs(lean), 7, 12))
        pygame.draw.rect(surf, body, (x+PW-10, y+PH-12-abs(lean), 7, 12))
        pygame.draw.ellipse(surf, (15,15,15), (x+1, y+PH-4, 10, 6))
        pygame.draw.ellipse(surf, (15,15,15), (x+PW-11, y+PH-4, 10, 6))
        # Body
        pygame.draw.rect(surf, body, (x+2, y+PH//2, PW-4, PH//2-8), border_radius=3)
        pygame.draw.rect(surf, (60,60,80), (x+2, y+PH//2, PW-4, PH//2-8), 1, border_radius=3)
        # Cape hint
        pygame.draw.polygon(surf, (40,10,10),
                            [(x-2, y+PH//2+2), (x-8, y+PH-8), (x+4, y+PH-4)])
        pygame.draw.polygon(surf, (40,10,10),
                            [(x+PW+2, y+PH//2+2), (x+PW+8, y+PH-8), (x+PW-4, y+PH-4)])
        # Arms
        arm_swing = int(3 * math.sin(anim_frame * 1.2))
        pygame.draw.line(surf, body, (x+2, y+PH//2+4), (x-5, y+PH//2+14+arm_swing), 4)
        pygame.draw.line(surf, body, (x+PW-2, y+PH//2+4), (x+PW+5, y+PH//2+14-arm_swing), 4)
        # Neck
        pygame.draw.rect(surf, skin, (x+PW//2-3, y+PH//2-4, 6, 6))
        # Head
        pygame.draw.ellipse(surf, skin, (x+4, y+4, PW-8, PH//2-2))
        pygame.draw.ellipse(surf, (60,60,80), (x+4, y+4, PW-8, PH//2-2), 1)
        # Glowing red eyes
        ex = x+7 if fx > 0 else x+PW-11
        draw_glow(surf, eye_col, ex+3, y+PH//4+2, 6, 160)
        pygame.draw.circle(surf, (40,0,0), (ex+3, y+PH//4+2), 4)
        pygame.draw.circle(surf, eye_col, (ex+3+(1*fx), y+PH//4+2), 2)
        # Tall black hat with red band
        pygame.draw.rect(surf, (10,10,10), (x-2, y+2, PW+4, 5))     # brim
        pygame.draw.rect(surf, (60,60,80), (x-2, y+2, PW+4, 5), 1)
        pygame.draw.rect(surf, (15,15,15), (x+3, y-18, PW-6, 22))   # tall crown
        pygame.draw.rect(surf, (60,60,80), (x+3, y-18, PW-6, 22), 1)
        pygame.draw.rect(surf, (120, 0, 0), (x+3, y+0, PW-6, 3))    # red band


def draw_device(surf, plat):
    x, y, w, h = plat["x"], plat["y"], plat["w"], plat["h"]
    kind = plat.get("kind", "server")
    label = plat.get("label", kind.upper()[:6])
    col = DEVICE_COLORS.get(kind, (50, 70, 110))

    if kind == "bridge":
        # Brown/tan bridge platform
        pygame.draw.rect(surf, (140, 100, 55), (x, y, w, h))
        pygame.draw.rect(surf, (170, 130, 80), (x, y, w, 4))   # highlight top
        pygame.draw.rect(surf, (100, 70, 30), (x, y, w, h), 2)
        # Wood plank lines
        for i in range(1, w // 18):
            lx = x + i * 18
            pygame.draw.line(surf, (100, 70, 30), (lx, y), (lx, y + h), 1)
        return

    # Use detailed 16-bit drawing for key device types
    if kind == "rack":
        draw_server_rack_detailed(surf, x, y, w, h, label)
        return
    if kind == "monitor":
        draw_monitor_detailed(surf, x, y, w, h, label)
        return
    if kind == "router":
        draw_router_detailed(surf, x, y, w, h, label)
        return
    if kind == "server":
        draw_server_rack_detailed(surf, x, y, w, h, label)
        return

    # Generic device box for other kinds
    pygame.draw.rect(surf, col, (x, y, w, h), border_radius=4)
    pygame.draw.rect(surf, (min(255,col[0]+40), min(255,col[1]+40), min(255,col[2]+40)), (x, y, w, h), 2, border_radius=4)
    if label:
        lt = FONT_TINY.render(label, True, WHITE)
        surf.blit(lt, (x + w//2 - lt.get_width()//2, y + h//2 - lt.get_height()//2))


def draw_pickup(surf, p):
    # Cable port stays visible even after collection (empty socket)
    if p.get("collected") and p.get("type") != "cable":
        return
    now = pygame.time.get_ticks()
    x, y = p["x"], p["y"]
    # Floating bob
    bob = int(5 * math.sin(now / 400 + x * 0.05))
    y += bob
    t = p["type"]

    if t == "key":
        # Pulsing gold glow
        gr = 28 + int(6 * math.sin(now / 300))
        draw_glow(surf, YELLOW, x, y, gr, 90)
        # Gold hex background
        pygame.draw.circle(surf, (180, 130, 0), (x, y), 16)
        pygame.draw.circle(surf, YELLOW, (x, y), 16, 2)
        emoji = FONT_EMOJI.render("🔑", True, YELLOW)
        surf.blit(emoji, (x - emoji.get_width()//2, y - emoji.get_height()//2))
    elif t == "hash":
        # Pulsing green glow
        gr = 28 + int(6 * math.sin(now / 300))
        draw_glow(surf, EMERALD, x, y, gr, 90)
        pygame.draw.circle(surf, (0, 60, 40), (x, y), 16)
        pygame.draw.circle(surf, EMERALD, (x, y), 16, 2)
        emoji = FONT_EMOJI.render("✅", True, EMERALD)
        surf.blit(emoji, (x - emoji.get_width()//2, y - emoji.get_height()//2))
    elif t == "packet":
        pid = p.get("id", 1)
        draw_glow(surf, CYAN, x, y, 22, 80)
        # Packet box with scan line
        pygame.draw.rect(surf, (0, 40, 70), (x - 14, y - 12, 28, 24), border_radius=4)
        pygame.draw.rect(surf, CYAN, (x - 14, y - 12, 28, 24), 2, border_radius=4)
        # Scan line animation
        scan_y = y - 12 + (now // 50) % 24
        pygame.draw.line(surf, (*CYAN, 100), (x - 14, scan_y), (x + 14, scan_y), 1)
        num = FONT_SM.render(f"{pid}/3", True, CYAN)
        surf.blit(num, (x - num.get_width()//2, y - num.get_height()//2))
    elif t == "cable":
        # Show empty socket even when collected (port stays on server)
        socket_col = (40, 80, 120) if p.get("collected") else CABLE_BLUE
        glow_col = (20, 60, 100) if p.get("collected") else CABLE_BLUE
        draw_glow(surf, glow_col, x, y, 20, 60)
        # RJ45 connector body (dims when collected)
        pygame.draw.rect(surf, (10, 30, 60) if p.get("collected") else (20, 60, 160),
                         (x-14, y-8, 28, 16), border_radius=3)
        pygame.draw.rect(surf, socket_col, (x-14, y-8, 28, 16), 2, border_radius=3)
        # Pins (darker when empty)
        pin_col = (20, 40, 20) if p.get("collected") else LED_GREEN
        for pi in range(4):
            pygame.draw.line(surf, pin_col, (x-8+pi*5, y-8), (x-8+pi*5, y-4), 1)
        if not p.get("collected"):
            # Cable coil (disappears when picked up — it's being carried)
            pygame.draw.arc(surf, CABLE_BLUE, (x-10, y+4, 20, 14), 0, math.pi, 3)
            label_c = FONT_TINY.render("RJ45", True, CYAN)
            surf.blit(label_c, (x - label_c.get_width()//2, y + 18 + bob))
        else:
            label_c = FONT_TINY.render("[EMPTY]", True, (60, 80, 100))
            surf.blit(label_c, (x - label_c.get_width()//2, y + 18))
    elif t == "dos_amp":
        draw_glow(surf, RED_HAT, x, y, 26, 100)
        pygame.draw.rect(surf, (80, 0, 0), (x-15, y-10, 30, 20), border_radius=3)
        pygame.draw.rect(surf, RED_HAT, (x-15, y-10, 30, 20), 2, border_radius=3)
        bpts = [(x-3,y-7),(x+5,y-1),(x+1,y-1),(x+3,y+7),(x-5,y+1),(x-1,y+1)]
        pygame.draw.polygon(surf, YELLOW, bpts)
        label_d = FONT_TINY.render("DDoS AMP", True, RED_HAT)
        surf.blit(label_d, (x - label_d.get_width()//2, y + 18 + bob))

    # ── WhiteHat layer-specific items ────────────────────────────────────────
    elif t == "mac_cert":
        draw_glow(surf, YELLOW, x, y, 26, 90)
        pygame.draw.rect(surf, (60, 50, 0), (x-16, y-12, 32, 24), border_radius=4)
        pygame.draw.rect(surf, YELLOW, (x-16, y-12, 32, 24), 2, border_radius=4)
        for i, c in enumerate(("MA", "C: ")):
            tl = FONT_TINY.render(c, True, YELLOW)
            surf.blit(tl, (x-14, y-10+i*11))
        pygame.draw.circle(surf, YELLOW, (x+10, y-4), 5, 1)
        lbl = FONT_TINY.render("MAC CERT", True, YELLOW)
        surf.blit(lbl, (x - lbl.get_width()//2, y + 18 + bob))

    elif t == "firewall_key":
        draw_glow(surf, CYAN, x, y, 26, 90)
        shd = [(x, y-14),(x-12, y),(x-12, y+8),(x+12, y+8),(x+12, y)]
        pygame.draw.polygon(surf, (0, 60, 80), shd)
        pygame.draw.polygon(surf, CYAN, shd, 2)
        pygame.draw.line(surf, CYAN, (x-8, y+3), (x+8, y+3), 1)
        pygame.draw.line(surf, CYAN, (x, y-8), (x, y+7), 1)
        khandle = FONT_SM.render("🔑", True, CYAN)
        surf.blit(khandle, (x-khandle.get_width()//2, y-khandle.get_height()//2))
        lbl = FONT_TINY.render("FW RULE", True, CYAN)
        surf.blit(lbl, (x - lbl.get_width()//2, y + 18 + bob))

    elif t == "tls_cert":
        draw_glow(surf, EMERALD, x, y, 26, 90)
        pygame.draw.rect(surf, (0, 50, 30), (x-10, y-2, 20, 16), border_radius=4)
        pygame.draw.rect(surf, EMERALD, (x-10, y-2, 20, 16), 2, border_radius=4)
        pygame.draw.arc(surf, EMERALD, (x-8, y-14, 16, 16), 0, math.pi, 3)
        pygame.draw.circle(surf, EMERALD, (x, y+6), 3)
        lbl = FONT_TINY.render("TLS CERT", True, EMERALD)
        surf.blit(lbl, (x - lbl.get_width()//2, y + 18 + bob))

    elif t == "terminal":
        draw_glow(surf, NEON_GREEN, x, y, 28, 90)
        pygame.draw.rect(surf, (5, 20, 5), (x-18, y-14, 36, 28), border_radius=4)
        pygame.draw.rect(surf, NEON_GREEN, (x-18, y-14, 36, 28), 2, border_radius=4)
        for i in range(3):
            lx = x - 12 + (now // (200+i*70)) % 24
            pygame.draw.line(surf, NEON_GREEN, (lx, y-8+i*8), (lx+8, y-8+i*8), 1)
        cur_x = x - 14 + (now // 400) % 28
        pygame.draw.rect(surf, NEON_GREEN, (cur_x, y+6, 6, 3))
        lbl = FONT_TINY.render("TERMINAL", True, NEON_GREEN)
        surf.blit(lbl, (x - lbl.get_width()//2, y + 20 + bob))
        lbl2 = FONT_TINY.render("escreva msg", True, NEON_GREEN)
        surf.blit(lbl2, (x - lbl2.get_width()//2, y + 30 + bob))

    elif t == "fragment":
        pid = p.get("id", 1)
        col_f = [(0,180,220),(0,140,200),(0,100,180)][pid-1]
        draw_glow(surf, col_f, x, y, 20, 80)
        pygame.draw.rect(surf, (0, 20, 50), (x-16, y-12, 32, 24), border_radius=4)
        pygame.draw.rect(surf, col_f, (x-16, y-12, 32, 24), 2, border_radius=4)
        num = FONT_SM.render(f"{pid}/3", True, col_f)
        surf.blit(num, (x - num.get_width()//2, y - num.get_height()//2))
        lbl = FONT_TINY.render("FRAG MSG", True, col_f)
        surf.blit(lbl, (x - lbl.get_width()//2, y + 18 + bob))

    # ── BlackHat layer-specific tools ────────────────────────────────────────
    elif t == "arp_spoofer":
        draw_glow(surf, ORANGE, x, y, 26, 100)
        pygame.draw.rect(surf, (60, 30, 0), (x-14, y-10, 28, 20), border_radius=3)
        pygame.draw.rect(surf, ORANGE, (x-14, y-10, 28, 20), 2, border_radius=3)
        pygame.draw.line(surf, ORANGE, (x-14, y), (x-20, y), 2)
        pygame.draw.circle(surf, ORANGE, (x-20, y), 3, 1)
        pygame.draw.line(surf, ORANGE, (x+14, y), (x+20, y), 2)
        pygame.draw.circle(surf, ORANGE, (x+20, y), 3, 1)
        lbl = FONT_TINY.render("ARP SPOOF", True, ORANGE)
        surf.blit(lbl, (x - lbl.get_width()//2, y + 18 + bob))

    elif t == "ip_bomb":
        draw_glow(surf, RED_HAT, x, y, 26, 100)
        pygame.draw.circle(surf, (60, 0, 0), (x, y), 14)
        pygame.draw.circle(surf, RED_HAT, (x, y), 14, 2)
        pygame.draw.line(surf, ORANGE, (x, y-14), (x+5, y-20), 2)
        pygame.draw.circle(surf, YELLOW, (x+5, y-20), 3)
        lbl2 = FONT_TINY.render("IP", True, RED_HAT)
        surf.blit(lbl2, (x-lbl2.get_width()//2, y-lbl2.get_height()//2))
        lbl = FONT_TINY.render("IP BOMB", True, RED_HAT)
        surf.blit(lbl, (x - lbl.get_width()//2, y + 18 + bob))

    elif t == "syn_packet":
        pid = p.get("id", 1)
        draw_glow(surf, DARK_RED, x, y, 20, 80)
        pygame.draw.rect(surf, (50, 0, 20), (x-16, y-12, 32, 24), border_radius=4)
        pygame.draw.rect(surf, DARK_RED, (x-16, y-12, 32, 24), 2, border_radius=4)
        syn = FONT_TINY.render(f"SYN{pid}", True, RED_HAT)
        surf.blit(syn, (x - syn.get_width()//2, y - syn.get_height()//2))
        lbl = FONT_TINY.render(f"FLOOD {pid}/3", True, DARK_RED)
        surf.blit(lbl, (x - lbl.get_width()//2, y + 18 + bob))

    elif t == "cookie_grab":
        DARK_PURPLE = (80, 0, 120)
        draw_glow(surf, PURPLE, x, y, 26, 100)
        pygame.draw.circle(surf, (30, 0, 50), (x, y), 14)
        pygame.draw.circle(surf, PURPLE, (x, y), 14, 2)
        for chip in [(-5,-4),(3,-6),(-3,4),(5,2)]:
            pygame.draw.circle(surf, (100,0,160), (x+chip[0], y+chip[1]), 3)
        lbl = FONT_TINY.render("COOKIE", True, PURPLE)
        surf.blit(lbl, (x - lbl.get_width()//2, y + 18 + bob))


def draw_enemy(surf, e):
    x, y = int(e["x"]), int(e["y"])
    kind = e["kind"]
    col = ENEMY_COLORS.get(kind, RED_HAT)
    now = pygame.time.get_ticks()
    pulse = int(3 * math.sin(now / 200 + x * 0.1))

    # Pulsing danger glow
    draw_glow(surf, col, x + 16, y + 20, 26 + pulse, 70)

    # Shadow
    draw_rect_alpha(surf, (0, 0, 0), (x - 2, y + 38, 36, 8), 100)

    # Body with rounded corners
    body_col = (min(255, col[0]+30), min(255, col[1]+10), min(255, col[2]+10))
    pygame.draw.rect(surf, body_col, (x, y + pulse, 32, 40), border_radius=6)

    # Neon outline
    bright = (min(255, col[0]+80), min(255, col[1]+60), min(255, col[2]+60))
    pygame.draw.rect(surf, bright, (x, y + pulse, 32, 40), 2, border_radius=6)

    # Visor / face (dark with glowing eyes)
    pygame.draw.rect(surf, (10, 10, 20), (x + 5, y + 8 + pulse, 22, 14), border_radius=3)
    pygame.draw.rect(surf, col, (x + 5, y + 8 + pulse, 22, 14), 1, border_radius=3)

    # Glowing eyes — animated flicker
    eye_col = WHITE if (now // 150) % 3 != 0 else col
    draw_glow(surf, eye_col, x + 11, y + 14 + pulse, 5, 180)
    draw_glow(surf, eye_col, x + 21, y + 14 + pulse, 5, 180)
    pygame.draw.circle(surf, eye_col, (x + 11, y + 14 + pulse), 3)
    pygame.draw.circle(surf, eye_col, (x + 21, y + 14 + pulse), 3)

    # Lightning bolt decoration for kind
    if kind == "dos":
        pts = [(x+14, y+25+pulse),(x+20,y+32+pulse),(x+16,y+32+pulse),(x+18,y+40+pulse),(x+12,y+33+pulse),(x+16,y+33+pulse)]
        pygame.draw.polygon(surf, YELLOW, pts)
    elif kind == "sniff":
        # Eye icon on chest
        pygame.draw.ellipse(surf, CYAN, (x+8, y+26+pulse, 16, 8))
        pygame.draw.circle(surf, DARK_BG, (x+16, y+30+pulse), 3)
    elif kind == "tamper":
        # Edit pencil icon
        pygame.draw.rect(surf, ORANGE, (x+10, y+24+pulse, 12, 4))
        pygame.draw.rect(surf, ORANGE, (x+10, y+28+pulse, 4, 8))
    elif kind == "defender":
        # Shield icon
        pts2 = [(x+16,y+22+pulse),(x+8,y+28+pulse),(x+16,y+40+pulse),(x+24,y+28+pulse)]
        pygame.draw.polygon(surf, CYAN, pts2)
        pygame.draw.polygon(surf, WHITE, pts2, 2)
        pygame.draw.line(surf, WHITE, (x+16,y+24+pulse),(x+16,y+36+pulse),2)
        pygame.draw.line(surf, WHITE, (x+10,y+30+pulse),(x+22,y+30+pulse),2)

    # Floating danger label above enemy
    icon_txt = ENEMY_ICONS.get(kind, "!")
    icon = FONT_EMOJI.render(icon_txt, True, WHITE)
    label_y = y - icon.get_height() - 4 + int(3 * math.sin(now / 250 + x))
    surf.blit(icon, (x + 16 - icon.get_width()//2, label_y))

    # Kind name tag
    tag = FONT_TINY.render(kind.upper(), True, col)
    surf.blit(tag, (x + 16 - tag.get_width()//2, y - 6))


def _draw_serverport(surf, g):
    """Server port goal — plug in the cable here."""
    x, y, w, h = g["x"], g["y"], g["w"], g["h"]
    now = pygame.time.get_ticks()
    pulse = int(3 * math.sin(now / 300))
    # Server body
    pygame.draw.rect(surf, (15, 20, 40), (x, y, w, h), border_radius=4)
    pygame.draw.rect(surf, STEEL, (x, y, w, h), 2, border_radius=4)
    # Port socket
    pygame.draw.rect(surf, BLACK, (x+w//2-14, y+h//2-8, 28, 16), border_radius=3)
    pygame.draw.rect(surf, CYAN, (x+w//2-14, y+h//2-8, 28, 16), 2, border_radius=3)
    # "PLUG HERE" label
    lt = FONT_TINY.render("PLUG", True, CYAN)
    surf.blit(lt, (x+w//2-lt.get_width()//2, y+h//2-24))
    # Pulsing arrow pointing to port
    arrow_y = y + h//2 - 32 + pulse
    pts = [(x+w//2, arrow_y+8), (x+w//2-6, arrow_y), (x+w//2+6, arrow_y)]
    pygame.draw.polygon(surf, YELLOW, pts)
    draw_glow(surf, YELLOW, x+w//2, arrow_y+4, 10, 150)
    # LEDs on sides
    for i in range(3):
        lc = LED_GREEN if (now//(300+i*80))%2 else (20,40,20)
        pygame.draw.circle(surf, lc, (x+6, y+10+i*14), 3)
        draw_glow(surf, lc, x+6, y+10+i*14, 5, 120)


def _draw_routerport(surf, g):
    """BlackHat's goal: plant DDoS amp at this router node."""
    x, y, w, h = g["x"], g["y"], g["w"], g["h"]
    now = pygame.time.get_ticks()
    pulse = int(3 * math.sin(now / 300))
    pygame.draw.rect(surf, (40, 5, 5), (x, y, w, h), border_radius=5)
    pygame.draw.rect(surf, RED_HAT, (x, y, w, h), 2, border_radius=5)
    # Target crosshair
    cx2, cy2 = x + w//2, y + h//2
    pygame.draw.circle(surf, RED_HAT, (cx2, cy2), 18+pulse, 2)
    pygame.draw.circle(surf, RED_HAT, (cx2, cy2), 8, 2)
    pygame.draw.line(surf, RED_HAT, (cx2-24, cy2), (cx2+24, cy2), 1)
    pygame.draw.line(surf, RED_HAT, (cx2, cy2-24), (cx2, cy2+24), 1)
    draw_glow(surf, RED_HAT, cx2, cy2, 26+pulse, 120)
    lt = FONT_TINY.render("PLANT HERE", True, RED_HAT)
    surf.blit(lt, (cx2 - lt.get_width()//2, y - 18))
    # Pulsing arrow
    arrow_y = y - 30 + pulse
    pts = [(cx2, arrow_y+8), (cx2-6, arrow_y), (cx2+6, arrow_y)]
    pygame.draw.polygon(surf, RED_HAT, pts)


def draw_goal(surf, g):
    goal_kind = g.get("kind", "flag")
    if goal_kind == "serverport":
        _draw_serverport(surf, g)
        return
    if goal_kind == "routerport":
        _draw_routerport(surf, g)
        return

    x, y, w, h = g["x"], g["y"], g["w"], g["h"]
    cx, cy = x + w // 2, y + h // 2
    now = pygame.time.get_ticks()
    t = now / 400

    # Pulsing portal rings
    for i in range(4):
        r = 24 + i * 12 + int(4 * math.sin(t + i * 0.8))
        alpha = max(0, 120 - i * 25)
        ring = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(ring, (*EMERALD, alpha), (r, r), r, 3)
        surf.blit(ring, (cx - r, cy - r))

    # Portal inner glow
    draw_glow(surf, EMERALD, cx, cy, 30, 130)
    portal = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(portal, (*EMERALD, 60), (0, 0, w, h))
    surf.blit(portal, (x, y))
    pygame.draw.ellipse(surf, EMERALD, (x, y, w, h), 3)

    # Flag pole
    pole_x = x + 8
    pygame.draw.line(surf, WHITE, (pole_x, y - 10), (pole_x, y + h), 3)

    # Waving flag
    flag_pts = [
        (pole_x, y - 8),
        (pole_x + 38 + int(5 * math.sin(t)), y + 4 + int(3 * math.sin(t + 0.5))),
        (pole_x, y + 18),
    ]
    pygame.draw.polygon(surf, EMERALD, flag_pts)
    pygame.draw.polygon(surf, WHITE, flag_pts, 1)

    # "GOAL" label on flag
    label = FONT_XS.render("GOAL", True, WHITE)
    surf.blit(label, (pole_x + 5, y))

    # Floating star particles around goal
    for i in range(5):
        angle = t * 1.5 + i * (2 * math.pi / 5)
        sx = cx + int(38 * math.cos(angle))
        sy = cy + int(20 * math.sin(angle))
        pygame.draw.circle(surf, YELLOW, (sx, sy), 3)
        draw_glow(surf, YELLOW, sx, sy, 6, 120)

    # Base platform
    pygame.draw.rect(surf, (100, 180, 100), (x, y + h - 6, w, 6), border_radius=3)
    draw_neon_rect(surf, EMERALD, (x, y + h - 6, w, 6), 1, radius=3)


def draw_centerpiece(surf, cp):
    kind = cp["kind"]
    x, y, w, h = cp["x"], cp["y"], cp["w"], cp["h"]
    cx, cy = x + w//2, y + h//2

    if kind == "brick":
        # Orange-red brick pattern
        bh, bw = 20, 36
        for row in range(h // bh + 1):
            offset = (bw // 2) if row % 2 else 0
            for col in range(-1, w // bw + 2):
                rx = x + col * bw - offset
                ry = y + row * bh
                if rx + bw < x or rx > x + w or ry + bh < y or ry > y + h:
                    continue
                # Clip to centerpiece bounds
                clip = surf.get_clip()
                surf.set_clip(pygame.Rect(x, y, w, h))
                pygame.draw.rect(surf, (200, 70, 20), (rx + 1, ry + 1, bw - 2, bh - 2))
                pygame.draw.rect(surf, (240, 100, 40), (rx + 2, ry + 2, bw - 4, 6))
                pygame.draw.rect(surf, (160, 50, 10), (rx + 1, ry + 1, bw - 2, bh - 2), 1)
                surf.set_clip(clip)
        pygame.draw.rect(surf, (120, 30, 5), (x, y, w, h), 3)

    elif kind == "globe":
        # Blue circle with cyan latitude/longitude lines
        pygame.draw.ellipse(surf, (20, 60, 160), (x, y, w, h))
        pygame.draw.ellipse(surf, (40, 100, 220), (x+6, y+6, w-12, h-12))
        # Latitude lines
        for i in range(1, 4):
            ly = y + h * i // 4
            half = int(math.sqrt(max(0, (w/2)**2 - ((ly - cy)/(h/w))**2)))
            pygame.draw.line(surf, CYAN, (cx - half, ly), (cx + half, ly), 1)
        # Longitude ellipses
        for i in range(3):
            angle = i * 60
            a_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(a_surf, (*CYAN, 80),
                                (0, 0, w//3, h), 2)
            rotated = pygame.transform.rotate(a_surf, angle)
            surf.blit(rotated, (cx - rotated.get_width()//2,
                                cy - rotated.get_height()//2))
        # Highlight
        pygame.draw.ellipse(surf, (180, 210, 255),
                            (x + w//4, y + h//8, w//5, h//6))
        pygame.draw.ellipse(surf, (0, 40, 120), (x, y, w, h), 3)

    elif kind == "disc":
        # Blue ellipse — top view
        pygame.draw.ellipse(surf, (20, 80, 180), (x, cy - h//4, w, h//2))
        pygame.draw.ellipse(surf, (60, 140, 220), (x + w//6, cy - h//8, w*2//3, h//4))
        pygame.draw.ellipse(surf, (120, 180, 255), (x + w*5//12, cy - h//16,
                                                     w//6, h//8))
        pygame.draw.ellipse(surf, (0, 40, 120), (x, cy - h//4, w, h//2), 3)

    elif kind == "datacenter":
        draw_datacenter_bg(surf, x, y, w, h)

    elif kind == "cloudhub":
        # Purple-ish cloud/server hub
        pygame.draw.rect(surf, (60, 20, 100), (x, y, w, h), border_radius=12)
        pygame.draw.rect(surf, (100, 40, 160), (x, y, w, h), 3, border_radius=12)
        # Server racks inside
        for i in range(3):
            ry = y + 20 + i * 44
            pygame.draw.rect(surf, (40, 10, 70), (x + 20, ry, w - 40, 34))
            pygame.draw.rect(surf, (120, 60, 180), (x + 20, ry, w - 40, 34), 1)
            # Blinking LEDs
            for j in range(4):
                lc = EMERALD if (pygame.time.get_ticks()//400 + i + j) % 2 else (20,40,20)
                pygame.draw.circle(surf, lc, (x + 35 + j*20, ry + 17), 4)
        # CLOUD label
        label = FONT_SM.render("CLOUD", True, WHITE)
        surf.blit(label, (cx - label.get_width()//2, y + h - 28))


def draw_connection_lines(surf, cp, platforms):
    """Draw semi-transparent cyan lines from centerpiece center to each platform."""
    cx = cp["x"] + cp["w"] // 2
    cy = cp["y"] + cp["h"] // 2
    line_surf = pygame.Surface((GAME_W, H), pygame.SRCALPHA)
    for p in platforms:
        px = p["x"] + p["w"] // 2
        py = p["y"] + p["h"] // 2
        pygame.draw.line(line_surf, (*CYAN, 40), (cx, cy), (px, py), 1)
    surf.blit(line_surf, (0, 0))


# ---------------------------------------------------------------------------
# Background gradient
# ---------------------------------------------------------------------------
def draw_background(surf, sky_top, sky_bot, ground_col):
    mid = H // 2
    for row in range(mid):
        t = row / mid
        c = lerp_color(sky_top, sky_bot, t)
        pygame.draw.line(surf, c, (0, row), (GAME_W, row))
    for row in range(mid, H):
        t = (row - mid) / (H - mid)
        c = lerp_color(sky_bot, ground_col, t)
        pygame.draw.line(surf, c, (0, row), (GAME_W, row))

    now = pygame.time.get_ticks()

    # Data center floor tiles
    tile_surf = pygame.Surface((GAME_W, H), pygame.SRCALPHA)
    tile_size = 60
    for tx in range(0, GAME_W, tile_size):
        for ty in range(HEADER_H, H, tile_size):
            pygame.draw.rect(tile_surf, (255,255,255,6), (tx+1, ty+1, tile_size-2, tile_size-2))
            pygame.draw.rect(tile_surf, (*CYAN, 12), (tx, ty, tile_size, tile_size), 1)
    surf.blit(tile_surf, (0, 0))

    # Overhead cable trays (horizontal lines across ceiling area)
    for cy2 in (HEADER_H + 30, HEADER_H + 80):
        draw_cable_bundle(surf, 0, cy2, GAME_W, color=(40, 60, 100), thickness=6)
        draw_cable_bundle(surf, 0, cy2 + 8, GAME_W, color=(60, 30, 100), thickness=4)

    # Animated status indicator lights in background
    for i in range(8):
        bx = 40 + i * (GAME_W // 8)
        by = HEADER_H + 16
        pulse2 = int(180 + 75 * math.sin(now / (500 + i*120) + i))
        lc = (0, pulse2, 80)
        pygame.draw.circle(surf, lc, (bx, by), 4)
        draw_glow(surf, lc, bx, by, 8, 100)

    # Binary rain
    draw_binary_rain(surf, sky_top)

    # Ground bar with neon edge
    pygame.draw.rect(surf, ground_col, (0, GROUND_Y, GAME_W, GROUND_H))
    draw_cable_bundle(surf, 0, GROUND_Y, GAME_W, color=(20, 40, 80), thickness=8)
    gl = pygame.Surface((GAME_W, 4), pygame.SRCALPHA)
    gl.fill((*CYAN, 50))
    surf.blit(gl, (0, GROUND_Y - 2))


# ---------------------------------------------------------------------------
# Toast
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Contextual win / achievement message per level mechanic
# ---------------------------------------------------------------------------
def compute_win_msg(level_data: dict, char: str) -> str:
    """Returns the achievement sentence for what the player did this level."""
    need = level_data.get("need" if char == "white" else "need_black", "")
    name = level_data.get("name", "")

    _W = {
        "cable":        "Você conduziu os bits pelo Cabo RJ45 e estabeleceu o enlace físico!",
        "mac_cert":     "Você validou o Certificado MAC e protegeu a identidade no enlace de dados!",
        "firewall_key": "Você configurou a Regra de Firewall e blindou a rota IP da rede!",
        "fragments3":   "Você escreveu a mensagem, fragmentou em 3 pacotes TCP e entregou com integridade!",
        "tls_cert":     "Você autenticou a sessão com Certificado TLS e bloqueou o sequestro de cookies!",
        "hash":         "Você entregou o hash criptografado e garantiu a integridade dos dados!",
    }
    _B = {
        "dos_amp":            "Você amplificou o ataque DDoS e derrubou a rede com tráfego malicioso!",
        "arp_spoofer":        "Você envenenou a tabela ARP do switch e redirecionou todo o tráfego!",
        "ip_bomb":            "Você detonou a IP Bomb no roteador e destruiu a camada de rede!",
        "syn_flood3":         "Você disparou o SYN Flood com 3 pacotes e esgotou as conexões TCP!",
        "cookie_grab":        "Você roubou o Cookie HTTP e sequestrou a sessão autenticada!",
        "hash":               "Você interceptou os dados da aplicação e comprometeu a integridade!",
        "intercepted_phrase": "Você interceptou o payload HTTP e confirmou o acesso não-autorizado!",
    }

    if char == "white":
        msg = _W.get(need, "Você completou o objetivo com sucesso!")
        if need == "hash":
            if level_data.get("ssh_layer"):
                msg = "Você protegeu o hash com senha SSH e entregou com integridade criptográfica!"
            elif "L6" in name or "Apresentação" in name:
                msg = "Você cifrou a mensagem com César e entregou os dados protegidos com segurança!"
        return msg
    else:
        msg = _B.get(need, "Você completou o objetivo com sucesso!")
        if need == "hash":
            if level_data.get("tamper_on_pickup"):
                msg = "Você adulterou o payload da aplicação e comprometeu a integridade dos dados!"
            elif "L6" in name or "Apresentação" in name:
                msg = "Você quebrou a Cifra César e decifrou o conteúdo interceptado!"
        return msg


class Toast:
    def __init__(self, text, duration=2500, color=EMERALD):
        self.text = text
        self.duration = duration
        self.color = color
        self.start = pygame.time.get_ticks()
        self.alive = True

    def update(self):
        if pygame.time.get_ticks() - self.start > self.duration:
            self.alive = False

    def draw(self, surf):
        elapsed = pygame.time.get_ticks() - self.start
        alpha = 255
        if elapsed > self.duration - 600:
            alpha = int(255 * (self.duration - elapsed) / 600)
        alpha = max(0, min(255, alpha))
        txt = FONT_SM.render(self.text, True, BLACK)
        pad = 16
        bw = txt.get_width() + pad * 2
        bh = txt.get_height() + pad
        bx = GAME_W // 2 - bw // 2
        by = HEADER_H + 16
        box = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(box, (*self.color, alpha), (0, 0, bw, bh), border_radius=8)
        box.blit(txt, (pad, pad//2))
        surf.blit(box, (bx, by))


# ---------------------------------------------------------------------------
# Input box
# ---------------------------------------------------------------------------
class InputBox:
    def __init__(self, x, y, w, h, placeholder=""):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = ""
        self.placeholder = placeholder
        self.active = False

    def handle_event(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(ev.pos)
        if ev.type == pygame.KEYDOWN and self.active:
            if ev.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif ev.key not in (pygame.K_RETURN, pygame.K_TAB):
                if len(self.text) < 20:
                    self.text += ev.unicode

    def draw(self, surf):
        border = EMERALD if self.active else GRAY
        pygame.draw.rect(surf, DARK_GRAY, self.rect, border_radius=6)
        pygame.draw.rect(surf, border, self.rect, 2, border_radius=6)
        disp = self.text if self.text else self.placeholder
        col = WHITE if self.text else GRAY
        t = FONT_SM.render(disp, True, col)
        surf.blit(t, (self.rect.x + 10, self.rect.y + self.rect.h//2 - t.get_height()//2))


# ---------------------------------------------------------------------------
# Button
# ---------------------------------------------------------------------------
class Button:
    def __init__(self, x, y, w, h, text, color=EMERALD, text_color=BLACK):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.color = color
        self.text_color = text_color
        self.hovered = False

    def handle_event(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(ev.pos)
        if ev.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(ev.pos):
            return True
        return False

    def draw(self, surf, font=None):
        if font is None:
            font = FONT_SM
        col = tuple(min(255, c + 30) for c in self.color) if self.hovered else self.color
        pygame.draw.rect(surf, col, self.rect, border_radius=8)
        pygame.draw.rect(surf, WHITE, self.rect, 2, border_radius=8)
        t = font.render(self.text, True, self.text_color)
        surf.blit(t, (self.rect.centerx - t.get_width()//2,
                      self.rect.centery - t.get_height()//2))


# ---------------------------------------------------------------------------
# Message Write Dialog — Transport layer (WhiteHat types a message)
# ---------------------------------------------------------------------------
class MessageWriteDialog:
    """WhiteHat types a short message; it then splits into 3 network fragments."""
    def __init__(self):
        self.done = False
        self.message = ""
        cx, cy = W // 2 - 140, H // 2 - 120
        self.box_rect = pygame.Rect(cx, cy, 480, 260)
        self.input = InputBox(cx + 30, cy + 110, 420, 40, "Digite sua mensagem aqui...")
        self.input.active = True
        self.btn_send = Button(cx + 160, cy + 200, 160, 42, "ENVIAR MENSAGEM", CABLE_BLUE, WHITE)

    def handle_event(self, ev):
        self.input.handle_event(ev)
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.message = ""
            self.done = True
        if self.btn_send.handle_event(ev):
            self.message = self.input.text.strip()
            self.done = True

    def draw(self, surf):
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        surf.blit(ov, (0, 0))
        bx, by, bw, bh = self.box_rect
        pygame.draw.rect(surf, (5, 15, 40), self.box_rect, border_radius=12)
        pygame.draw.rect(surf, CABLE_BLUE, self.box_rect, 3, border_radius=12)
        t1 = FONT_LG.render("TERMINAL DE MENSAGEM", True, CABLE_BLUE)
        surf.blit(t1, (bx + bw//2 - t1.get_width()//2, by + 18))
        t2 = FONT_SM.render("Camada Transporte: sua mensagem sera", True, WHITE)
        t3 = FONT_SM.render("fragmentada em 3 pacotes TCP na rede.", True, CYAN)
        surf.blit(t2, (bx + bw//2 - t2.get_width()//2, by + 56))
        surf.blit(t3, (bx + bw//2 - t3.get_width()//2, by + 76))
        # Fragment preview
        for i in range(3):
            col_f = [(0,180,220),(0,140,200),(0,100,180)][i]
            fx = bx + 60 + i * 130
            pygame.draw.rect(surf, (0,20,50), (fx, by+160, 110, 28), border_radius=4)
            pygame.draw.rect(surf, col_f, (fx, by+160, 110, 28), 2, border_radius=4)
            lbl = FONT_TINY.render(f"FRAG {i+1}/3", True, col_f)
            surf.blit(lbl, (fx + 55 - lbl.get_width()//2, by + 167))
        self.input.draw(surf)
        self.btn_send.draw(surf)
        hint = FONT_TINY.render("ESC para cancelar", True, GRAY)
        surf.blit(hint, (bx + bw//2 - hint.get_width()//2, by + bh - 22))


# ---------------------------------------------------------------------------
# BlackHat: type intercepted phrase to confirm
# ---------------------------------------------------------------------------
class TypeConfirmDialog:
    """BlackHat must retype the intercepted phrase at the server to prove ownership."""
    def __init__(self, secret):
        self.secret  = secret.upper()
        self.done    = False
        self.success = False
        self.error   = False
        cx, cy = W // 2 - 210, H // 2 - 120
        self.box_rect = pygame.Rect(cx, cy, 420, 260)
        self.input = InputBox(cx + 30, cy + 145, 360, 40, "Digite a frase interceptada...")
        self.input.active = True
        self.btn_ok = Button(cx + 130, cy + 202, 160, 42, "CONFIRMAR", RED_HAT, WHITE)

    def handle_event(self, ev):
        self.input.handle_event(ev)
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.done = True
            elif ev.key == pygame.K_RETURN:
                self._check()
        if self.btn_ok.handle_event(ev):
            self._check()

    def _check(self):
        typed = self.input.text.strip().upper()
        if typed == self.secret:
            self.success = True
            self.done    = True
        else:
            self.error = True
            self.input.text = ""

    def draw(self, surf):
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 170))
        surf.blit(ov, (0, 0))
        bx, by, bw, bh = self.box_rect
        pygame.draw.rect(surf, (30, 5, 5), self.box_rect, border_radius=12)
        pygame.draw.rect(surf, RED_HAT, self.box_rect, 3, border_radius=12)
        t1 = FONT_LG.render("CONFIRMAR INTERCEPTAÇÃO", True, RED_HAT)
        surf.blit(t1, (bx + bw // 2 - t1.get_width() // 2, by + 16))
        t2 = FONT_SM.render("Frase interceptada:", True, GRAY)
        surf.blit(t2, (bx + 30, by + 58))
        ph = FONT_MED.render(f'"{self.secret}"', True, ORANGE)
        surf.blit(ph, (bx + bw // 2 - ph.get_width() // 2, by + 80))
        t3 = FONT_SM.render("Digite a frase acima para confirmar:", True, WHITE)
        surf.blit(t3, (bx + 30, by + 118))
        if self.error:
            err = FONT_XS.render("Frase incorreta! Tente novamente.", True, RED_HAT)
            surf.blit(err, (bx + bw // 2 - err.get_width() // 2, by + 136))
            self.error = False
        self.input.draw(surf)
        self.btn_ok.draw(surf)
        hint = FONT_TINY.render("ESC para cancelar", True, GRAY)
        surf.blit(hint, (bx + bw // 2 - hint.get_width() // 2, by + bh - 18))


# ---------------------------------------------------------------------------
# BlackHat: alter intercepted message (tampering)
# ---------------------------------------------------------------------------
class AlterMessageDialog:
    """BlackHat intercepts a message and alters its content before delivering."""
    def __init__(self, original):
        self.original = original
        self.done     = False
        self.altered  = ""
        self.error_msg = ""
        cx, cy = W // 2 - 220, H // 2 - 140
        self.box_rect = pygame.Rect(cx, cy, 440, 295)
        self.input = InputBox(cx + 30, cy + 172, 380, 40, "Digite a mensagem adulterada...")
        self.input.active = True
        self.btn_ok = Button(cx + 140, cy + 232, 160, 42, "ADULTERAR", PURPLE, WHITE)

    def handle_event(self, ev):
        self.input.handle_event(ev)
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.done = True
            elif ev.key == pygame.K_RETURN:
                self._confirm()
        if self.btn_ok.handle_event(ev):
            self._confirm()

    def _confirm(self):
        text = self.input.text.strip()
        if not text:
            self.error_msg = "Digite algo para adulterar!"
            return
        if text.upper() == self.original.upper():
            self.error_msg = "Deve ser DIFERENTE do original!"
            self.input.text = ""
            return
        self.altered = text
        self.done    = True

    def draw(self, surf):
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 170))
        surf.blit(ov, (0, 0))
        bx, by, bw, bh = self.box_rect
        pygame.draw.rect(surf, (20, 5, 30), self.box_rect, border_radius=12)
        pygame.draw.rect(surf, PURPLE, self.box_rect, 3, border_radius=12)
        t1 = FONT_LG.render("ADULTERAÇÃO DE MENSAGEM", True, PURPLE)
        surf.blit(t1, (bx + bw // 2 - t1.get_width() // 2, by + 16))
        t2 = FONT_SM.render("Mensagem original interceptada:", True, GRAY)
        surf.blit(t2, (bx + 30, by + 60))
        orig = FONT_MED.render(f'"{self.original}"', True, CYAN)
        surf.blit(orig, (bx + bw // 2 - orig.get_width() // 2, by + 83))
        sep = pygame.Surface((bw - 60, 1))
        sep.fill(GRAY)
        surf.blit(sep, (bx + 30, by + 120))
        t3 = FONT_SM.render("Digite a versão ADULTERADA para enviar:", True, WHITE)
        surf.blit(t3, (bx + 30, by + 130))
        t4 = FONT_XS.render("(deve ser diferente do original)", True, ORANGE)
        surf.blit(t4, (bx + 30, by + 152))
        if self.error_msg:
            err = FONT_XS.render(self.error_msg, True, RED_HAT)
            surf.blit(err, (bx + bw // 2 - err.get_width() // 2, by + 153))
            self.error_msg = ""
        self.input.draw(surf)
        self.btn_ok.draw(surf)
        hint = FONT_TINY.render("ESC para cancelar", True, GRAY)
        surf.blit(hint, (bx + bw // 2 - hint.get_width() // 2, by + bh - 18))


# ---------------------------------------------------------------------------
# César cipher mini-game
# ---------------------------------------------------------------------------
class CesarMiniGame:
    """WhiteHat encrypts (mode='encrypt'); BlackHat decrypts (mode='decrypt')."""
    def __init__(self, mode, encrypted_msg="", original_shift=0):
        self.mode = mode
        self.done = False
        self.result = {}
        self.encrypted_msg = encrypted_msg
        self.original_shift = original_shift
        self.input_text = ""
        self.shift_chosen = 0
        self.phase = "text"   # "text" | "shift" | "done"
        self.current_try = 1
        self.decrypted_preview = self._try_decrypt(1)

    @staticmethod
    def _cesar(text, shift):
        out = []
        for ch in text:
            if ch.isalpha():
                base = ord('A') if ch.isupper() else ord('a')
                out.append(chr((ord(ch) - base + shift) % 26 + base))
            else:
                out.append(ch)
        return "".join(out)

    def _try_decrypt(self, shift):
        if not self.encrypted_msg:
            return ""
        return self._cesar(self.encrypted_msg, 26 - shift)

    def handle_event(self, ev):
        if self.done or ev.type != pygame.KEYDOWN:
            return
        if self.mode == "encrypt":
            if self.phase == "text":
                if ev.key == pygame.K_RETURN and self.input_text.strip():
                    self.phase = "shift"
                elif ev.key == pygame.K_BACKSPACE:
                    self.input_text = self.input_text[:-1]
                elif ev.unicode.isprintable() and len(self.input_text) < 36:
                    self.input_text += ev.unicode
            elif self.phase == "shift":
                if ev.unicode in "123456789":
                    s = int(ev.unicode)
                    enc = self._cesar(self.input_text, s)
                    self.result = {"original": self.input_text, "shift": s, "encrypted": enc}
                    self.phase = "done"
                    self.done = True
        else:
            # Decrypt mode — uses ev.key (physical key code) to avoid NumLock
            # ambiguity where Numpad-2 with NumLock ON produces unicode "2".
            # Navigation keys checked FIRST so they can never be misread as numbers.
            if ev.key in (pygame.K_UP, pygame.K_KP8):
                self.current_try = (self.current_try - 2) % 9 + 1
                self.decrypted_preview = self._try_decrypt(self.current_try)
            elif ev.key in (pygame.K_DOWN, pygame.K_KP2):
                self.current_try = self.current_try % 9 + 1
                self.decrypted_preview = self._try_decrypt(self.current_try)
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                cracked = (self.current_try == self.original_shift)
                self.result = {
                    "cracked": cracked,
                    "shift": self.current_try,
                    "decrypted": self._try_decrypt(self.current_try),
                }
                self.done = True
            elif pygame.K_1 <= ev.key <= pygame.K_9:
                n = ev.key - pygame.K_0
                self.current_try = n
                self.decrypted_preview = self._try_decrypt(n)
                cracked = (n == self.original_shift)
                self.result = {
                    "cracked": cracked,
                    "shift": n,
                    "decrypted": self._try_decrypt(n),
                }
                self.done = True
            # ALL other keys (ESC, Shift, Alt, Win, numpad with NumLock, etc.) → ignored

    def draw(self, surf):
        ov = pygame.Surface((GAME_W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 210))
        surf.blit(ov, (0, 0))
        bw, bh = 600, 380
        bx = GAME_W // 2 - bw // 2
        by = H // 2 - bh // 2
        pygame.draw.rect(surf, (8, 18, 38), (bx, by, bw, bh), border_radius=14)
        border_c = CYAN if self.mode == "encrypt" else RED_HAT
        pygame.draw.rect(surf, border_c, (bx, by, bw, bh), 2, border_radius=14)

        if self.mode == "encrypt":
            t0 = FONT_MED.render("CIFRA DE CÉSAR — WhiteHat Cifra", True, EMERALD)
            surf.blit(t0, (bx + bw // 2 - t0.get_width() // 2, by + 12))
            if self.phase == "text":
                i1 = FONT_SM.render("Digite a mensagem e pressione ENTER:", True, WHITE)
                surf.blit(i1, (bx + 20, by + 56))
                pygame.draw.rect(surf, (15, 30, 55), (bx + 20, by + 88, bw - 40, 44), border_radius=6)
                pygame.draw.rect(surf, CYAN, (bx + 20, by + 88, bw - 40, 44), 2, border_radius=6)
                cursor = "|" if (pygame.time.get_ticks() // 500) % 2 == 0 else ""
                ts = FONT_SM.render(self.input_text + cursor, True, CYAN)
                surf.blit(ts, (bx + 30, by + 100))
                ex = FONT_XS.render('Ex: "O gato subiu no telhado"   →   ENTER para confirmar', True, GRAY)
                surf.blit(ex, (bx + 20, by + 142))
            elif self.phase == "shift":
                msg_t = FONT_SM.render(f'Mensagem: "{self.input_text[:30]}"', True, WHITE)
                surf.blit(msg_t, (bx + 20, by + 56))
                i2 = FONT_SM.render("Pressione 1–9 para escolher o deslocamento:", True, YELLOW)
                surf.blit(i2, (bx + 20, by + 88))
                for i in range(1, 10):
                    preview = self._cesar(self.input_text[:20], i)
                    col2 = EMERALD if i == (i % 9 + 1) else GRAY
                    row = FONT_XS.render(f"[{i}] → {preview}", True, GRAY)
                    surf.blit(row, (bx + 20 + (i - 1) % 3 * 190, by + 120 + (i - 1) // 3 * 22))
                hint2 = FONT_XS.render("Tecle o número (1-9) para cifrar e confirmar automaticamente", True, CYAN)
                surf.blit(hint2, (bx + 20, by + 340))
        else:
            t0 = FONT_MED.render("QUEBRAR CIFRA — BlackHat Decifra", True, RED_HAT)
            surf.blit(t0, (bx + bw // 2 - t0.get_width() // 2, by + 12))
            enc_t = FONT_XS.render(f'Cifrado: "{self.encrypted_msg[:40]}"', True, ORANGE)
            surf.blit(enc_t, (bx + 20, by + 50))
            i3 = FONT_XS.render("Pressione 1–9 para visualizar. ENTER = confirmar. ESC = sair.", True, WHITE)
            surf.blit(i3, (bx + 20, by + 76))
            for i in range(1, 10):
                preview = self._try_decrypt(i)[:32]
                is_cur = (i == self.current_try)
                col3 = YELLOW if is_cur else GRAY
                bg3 = (40, 20, 0) if is_cur else (12, 15, 28)
                ry = by + 106 + (i - 1) * 22
                pygame.draw.rect(surf, bg3, (bx + 18, ry, bw - 36, 20))
                rt = FONT_XS.render(f"[{i}] {preview}", True, col3)
                surf.blit(rt, (bx + 24, ry + 2))
            dec_t = FONT_SM.render(f"Tentativa [{self.current_try}]: {self.decrypted_preview[:32]}", True, CYAN)
            surf.blit(dec_t, (bx + 20, by + 318))
            hint3 = FONT_XS.render("↑↓ navegar  |  1-9 selecionar direto  |  ENTER confirmar", True, GRAY)
            surf.blit(hint3, (bx + 20, by + 354))


# ---------------------------------------------------------------------------
# SSH password dialog
# ---------------------------------------------------------------------------
class SSHPasswordDialog:
    def __init__(self):
        self.done = False
        self.password = ""
        self.skipped = False

    def handle_event(self, ev):
        if self.done or ev.type != pygame.KEYDOWN:
            return
        if ev.key == pygame.K_RETURN:
            self.done = True
        elif ev.key == pygame.K_ESCAPE:
            self.skipped = True
            self.done = True
        elif ev.key == pygame.K_BACKSPACE:
            self.password = self.password[:-1]
        elif ev.unicode.isprintable() and len(self.password) < 32:
            self.password += ev.unicode

    def draw(self, surf):
        ov = pygame.Surface((GAME_W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 210))
        surf.blit(ov, (0, 0))
        bw, bh = 520, 280
        bx = GAME_W // 2 - bw // 2
        by = H // 2 - bh // 2
        pygame.draw.rect(surf, (8, 20, 12), (bx, by, bw, bh), border_radius=12)
        pygame.draw.rect(surf, EMERALD, (bx, by, bw, bh), 2, border_radius=12)
        t1 = FONT_MED.render("SENHA SSH — WhiteHat Protege", True, EMERALD)
        surf.blit(t1, (bx + bw // 2 - t1.get_width() // 2, by + 14))
        t2 = FONT_XS.render("Digite senha para proteger o hash (ENTER confirma, ESC pula):", True, WHITE)
        surf.blit(t2, (bx + 20, by + 58))
        pygame.draw.rect(surf, (15, 30, 20), (bx + 20, by + 88, bw - 40, 44), border_radius=6)
        pygame.draw.rect(surf, EMERALD, (bx + 20, by + 88, bw - 40, 44), 2, border_radius=6)
        cursor = "|" if (pygame.time.get_ticks() // 500) % 2 == 0 else ""
        ts = FONT_SM.render("*" * len(self.password) + cursor, True, EMERALD)
        surf.blit(ts, (bx + 30, by + 100))
        h1 = FONT_XS.render("Senha definida = BlackHat NÃO consegue roubar o hash diretamente!", True, CYAN)
        surf.blit(h1, (bx + 20, by + 148))
        h2 = FONT_XS.render("Sem senha = hash vulnerável. BlackHat pode pegar direto.", True, ORANGE)
        surf.blit(h2, (bx + 20, by + 170))
        h3 = FONT_XS.render("ESC = pular (sem proteção SSH)", True, GRAY)
        surf.blit(h3, (bx + 20, by + 196))
        h4 = FONT_XS.render("ENTER = confirmar senha", True, EMERALD)
        surf.blit(h4, (bx + 20, by + 216))


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------
class Player:
    def __init__(self, char):
        self.char = char   # "white" or "black"
        self.x = 60.0
        self.y = 364.0
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.has_key = False
        self.has_hash = False
        self.has_cable = False
        self.packets = []
        self.facing = 1       # 1 = direita, -1 = esquerda
        self.anim_tick = 0    # contador de frames para animação
        self.anim_frame = 0   # frame atual da sprite walk

    def reset(self, spawn):
        self.x, self.y = float(spawn[0]), float(spawn[1])
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.has_key = False
        self.has_hash = False
        self.has_cable = False
        self.packets = []
        self.facing = 1
        self.anim_tick = 0
        self.anim_frame = 0

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), PW, PH)

    def update(self, actions: dict, platforms):
        # actions = {"left": bool, "right": bool, "jump": bool}
        self.vx = 0.0
        if actions.get("left"):
            self.vx = -SPEED
        if actions.get("right"):
            self.vx = SPEED

        # Jump
        if self.on_ground and actions.get("jump"):
            self.vy = JUMP
            self.on_ground = False

        # Gravity
        self.vy += GRAV
        self.vy = min(self.vy, 14)

        # Move X
        prev_x = self.x
        self.x += self.vx
        self.x = clamp(self.x, 0, GAME_W - PW)

        # Move Y — check platforms
        prev_bottom = self.y + PH
        self.y += self.vy

        self.on_ground = False

        for p in platforms:
            if p.get("kind") not in ("bridge", "brick"):
                continue
            pr = pygame.Rect(p["x"], p["y"], p["w"], p["h"])
            # Only land from above
            if (self.vy >= 0
                    and prev_bottom <= pr.top + 1
                    and self.x + PW > pr.left
                    and self.x < pr.right
                    and self.y + PH >= pr.top
                    and self.y < pr.bottom):
                self.y = pr.top - PH
                self.vy = 0
                self.on_ground = True

        # Facing & animation
        if self.vx < 0:
            self.facing = -1
        elif self.vx > 0:
            self.facing = 1

        if self.vx != 0 and self.on_ground:
            self.anim_tick += 1
            if self.anim_tick >= 8:   # troca de frame a cada 8 ticks (≈7.5fps @ 60fps)
                self.anim_tick = 0
                self.anim_frame += 1
        else:
            self.anim_tick = 0
            self.anim_frame = 0

    def draw(self, surf):
        draw_player(surf, int(self.x), int(self.y), self.char, self.facing, self.anim_frame)


# ---------------------------------------------------------------------------
# Enemy
# ---------------------------------------------------------------------------
class Enemy:
    def __init__(self, data):
        self.x = float(data["x"])
        self.y = float(data["y"])
        self.vx = float(data.get("vx", 1.5))
        self.min_x = data["minX"]
        self.max_x = data["maxX"]
        self.kind = data["kind"]
        self.chase = data.get("chase", False)

    def update(self, player_x=None):
        if self.chase and player_x is not None:
            # Chase the player horizontally within patrol bounds
            dx = player_x - self.x
            spd = abs(self.vx) * 1.6
            if abs(dx) > 8:
                move = spd if dx > 0 else -spd
                self.x += move
                self.vx = move  # update facing direction
            self.x = max(self.min_x, min(self.max_x, self.x))
        else:
            self.x += self.vx
            if self.x <= self.min_x:
                self.x = self.min_x
                self.vx = abs(self.vx)
            if self.x >= self.max_x:
                self.x = self.max_x
                self.vx = -abs(self.vx)

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), 32, 40)

    def draw(self, surf, player_char="white"):
        if self.kind == "opponent":
            opp = "black" if player_char == "white" else "white"
            facing = 1 if self.vx >= 0 else -1
            # Warning glow
            col = RED_HAT if opp == "black" else EMERALD
            draw_glow(surf, col, int(self.x) + 12, int(self.y) + 20, 24, 80)
            draw_player(surf, int(self.x), int(self.y), opp,
                        facing=facing, anim_frame=(pygame.time.get_ticks()//120) % 4)
            # Name tag
            now2 = pygame.time.get_ticks()
            lbl = FONT_TINY.render("OPONENTE!", True, col)
            surf.blit(lbl, (int(self.x)+16 - lbl.get_width()//2,
                            int(self.y) - 18 + int(2*math.sin(now2/200))))
        else:
            draw_enemy(surf, {"x": self.x, "y": self.y, "kind": self.kind})


# ---------------------------------------------------------------------------
# GameLevel — wraps one level's runtime state
# ---------------------------------------------------------------------------
class GameLevel:
    def __init__(self, level_data, char, control_slot: str = "P1"):
        self.data = level_data
        self.char = char
        self.control_slot = control_slot   # "P1" or "P2"
        self.player = Player(char)
        self.player.reset(level_data["spawn"])

        # Use character-specific data if available, else shared defaults
        if char == "black":
            raw_enemies  = level_data.get("enemies_black",  level_data.get("enemies", []))
            raw_pickups  = level_data.get("pickups_black",  level_data.get("pickups", []))
            self.goal_data = level_data.get("goal_black",   level_data["goal"])
            self.need      = level_data.get("need_black",   level_data.get("need", "none"))
        else:
            raw_enemies  = level_data.get("enemies", [])
            raw_pickups  = level_data.get("pickups", [])
            self.goal_data = level_data["goal"]
            self.need      = level_data.get("need", "none")

        self.enemies = [Enemy(e) for e in raw_enemies]
        self.pickups = [dict(p) for p in raw_pickups]
        for p in self.pickups:
            p["collected"] = False

        self.toasts = []
        self.state = "intro"  # intro | playing | win | fail
        self.thought_visible = False
        self.thought_idx = 0
        self.fail_reason = ""
        self.next_thought_timer = 0
        self.minigame = None          # active mini-game instance
        self.minigame_stage = 0       # tracks which sub-stages have fired
        self.cable_pickup_pos = None  # origin of cable for trail drawing
        self.spawned_pickups = []     # dynamically spawned (e.g. message fragments)
        self.msg_written = False      # transport layer: message typed at terminal
        self.intercept_phrase = ""    # BlackHat: phrase revealed on hash pickup
        self._pending_pickup = None   # pickup held back until dialog confirms
        # Multiplayer: remote player state
        self.remote_x: float | None = None
        self.remote_y: float | None = 0.0
        self.remote_facing: int = -1
        self.remote_frame: int = 0
        self.remote_char: str = "black" if char == "white" else "white"

    def add_toast(self, text, color=EMERALD):
        self.toasts.append(Toast(text, color=color))

    def _handle_pickup(self, p):
        pl = self.player
        p["collected"] = True
        t = p["type"]
        if t == "key":
            pl.has_key = True
            self.add_toast("Chave coletada! Acesso cifrado.", YELLOW)
        elif t in ("mac_cert",):
            pl.has_key = True
            self.add_toast("Certificado MAC coletado! Identidade de enlace verificada.", YELLOW)
        elif t in ("firewall_key",):
            pl.has_key = True
            self.add_toast("Regra de Firewall coletada! Rota criptografada.", CYAN)
        elif t in ("tls_cert",):
            pl.has_key = True
            self.add_toast("Certificado TLS coletado! Sessão autenticada.", EMERALD)
        elif t == "hash":
            if self.char == "black" and self.data.get("tamper_on_pickup"):
                # Tampering mechanic: show dialog before granting has_hash
                original = CESAR_STATE.get("original") or "DADOS SENSIVEIS"
                self.minigame = AlterMessageDialog(original)
                self._pending_pickup = p
                p["collected"] = False  # revert until dialog confirms
            elif self.char == "black" and self.data.get("confirm_phrase"):
                # Intercept-confirm mechanic: reveal phrase, must retype at goal
                phrase = CESAR_STATE.get("encrypted") or self.data["confirm_phrase"]
                self.intercept_phrase = phrase.upper()
                pl.has_hash = True
                self.add_toast(
                    f'Frase interceptada: "{self.intercept_phrase}" — confirme no servidor!',
                    RED_HAT,
                )
            else:
                pl.has_hash = True
                self.add_toast("Hash capturado! Integridade garantida.", EMERALD)
        elif t in ("dos_amp", "arp_spoofer", "ip_bomb", "cookie_grab"):
            pl.has_hash = True
            msgs = {
                "dos_amp":     ("Amplificador DDoS coletado! Plante no alvo.", RED_HAT),
                "arp_spoofer": ("ARP Spoofer ativo! Vai envenenar o switch.", ORANGE),
                "ip_bomb":     ("IP Bomb armada! Vai explodir o roteador.", RED_HAT),
                "cookie_grab": ("Cookie Stealer pronto! Roube a sessão.", PURPLE),
            }
            msg, col = msgs.get(t, ("Item coletado.", RED_HAT))
            self.add_toast(msg, col)
        elif t == "packet":
            pid = p.get("id", 1)
            expected = len(pl.packets) + 1
            if pid == expected:
                pl.packets.append(pid)
                self.add_toast(f"Pacote TCP {pid}/3 coletado!", CYAN)
            else:
                self.add_toast(f"Ordem errada! Esperado pacote {expected}.", ORANGE)
                p["collected"] = False
        elif t == "syn_packet":
            pid = p.get("id", 1)
            expected = len(pl.packets) + 1
            if pid == expected:
                pl.packets.append(pid)
                self.add_toast(f"SYN Flood {pid}/3 armado!", DARK_RED)
            else:
                self.add_toast(f"Pegue SYN {expected} primeiro!", ORANGE)
                p["collected"] = False
        elif t == "fragment":
            pid = p.get("id", 1)
            expected = len(pl.packets) + 1
            if pid == expected:
                pl.packets.append(pid)
                self.add_toast(f"Fragmento {pid}/3 da mensagem coletado!", CABLE_BLUE)
            else:
                self.add_toast(f"Pegue o fragmento {expected} primeiro!", ORANGE)
                p["collected"] = False
        elif t == "cable":
            pl.has_cable = True
            self.cable_pickup_pos = (p["x"], p["y"])
            self.add_toast("Cabo RJ45 coletado! Conecte na porta destino.", CABLE_BLUE)
        elif t == "terminal":
            if not self.msg_written:
                self.minigame = MessageWriteDialog()

    def check_pickups(self):
        pr = self.player.rect
        all_pickups = self.pickups + self.spawned_pickups
        for p in all_pickups:
            if p["collected"]:
                continue
            px, py = p["x"], p["y"]
            pr2 = pygame.Rect(px - 14, py - 14, 28, 28)
            if pr.colliderect(pr2):
                self._handle_pickup(p)

    def check_enemies(self):
        pr = self.player.rect
        pl = self.player
        for e in self.enemies:
            er = e.rect()
            if pr.colliderect(er):
                if self.char == "white":
                    if e.kind == "sniff":
                        if not pl.has_key:
                            self.state = "fail"
                            self.fail_reason = "Sniffer interceptou sua mensagem sem criptografia!"
                            return
                        else:
                            self.add_toast("Chave protegeu você do Sniffer!", EMERALD)
                    elif e.kind == "tamper":
                        if not pl.has_hash:
                            self.state = "fail"
                            self.fail_reason = "Tampering alterou sua mensagem sem hash!"
                            return
                        else:
                            self.add_toast("Hash detectou a adulteração!", EMERALD)
                    elif e.kind == "dos":
                        self.state = "fail"
                        self.fail_reason = "DoS bloqueou o caminho! Disponibilidade comprometida."
                        return
                    elif e.kind == "defender":
                        self.add_toast("Firewall bloqueou o ataque!", CYAN)
                    elif e.kind == "opponent":
                        self.state = "fail"
                        self.fail_reason = "BlackHat te interceptou! Seja mais rápido na próxima."
                        return
                else:
                    # BlackHat: dos/sniff/tamper are his tools — no damage
                    # Only "defender" and "opponent" block BlackHat
                    if e.kind == "defender":
                        self.state = "fail"
                        self.fail_reason = "Firewall detectou e bloqueou você! Tente pelo caminho inferior."
                        return
                    elif e.kind == "opponent":
                        self.state = "fail"
                        self.fail_reason = "WhiteHat te deteve! Encontre um caminho alternativo."
                        return

    def check_goal(self):
        g = self.goal_data
        gr = pygame.Rect(g["x"], g["y"], g["w"], g["h"])
        if not self.player.rect.colliderect(gr):
            return
        pl = self.player
        need = self.need
        if need == "none":
            self.state = "win"
        elif need in ("key", "mac_cert", "firewall_key", "tls_cert") and pl.has_key:
            self.state = "win"
        elif need in ("key", "mac_cert", "firewall_key", "tls_cert") and not pl.has_key:
            labels = {"mac_cert": "Certificado MAC", "firewall_key": "Regra de Firewall",
                      "tls_cert": "Certificado TLS"}
            self.add_toast(f"Pegue o {labels.get(need, 'chave')} primeiro!", ORANGE)
        elif need == "hash" and pl.has_hash:
            self.state = "win"
        elif need == "hash" and not pl.has_hash:
            self.add_toast("Pegue o hash antes de entregar!", ORANGE)
        elif need == "intercepted_phrase":
            if not pl.has_hash:
                self.add_toast("Intercepte a frase primeiro!", ORANGE)
            elif self.intercept_phrase and self.minigame is None:
                self.minigame = TypeConfirmDialog(self.intercept_phrase)
            elif not self.intercept_phrase:
                self.state = "win"
        elif need == "packets3" and len(pl.packets) == 3:
            self.state = "win"
        elif need == "packets3":
            self.add_toast(f"Pacotes: {len(pl.packets)}/3. Continue coletando!", ORANGE)
        elif need == "cable" and pl.has_cable:
            self.state = "win"
        elif need == "cable" and not pl.has_cable:
            self.add_toast("Pegue o cabo primeiro!", ORANGE)
        elif need == "syn_flood3" and len(pl.packets) == 3:
            self.state = "win"
        elif need == "syn_flood3":
            self.add_toast(f"SYN Flood: {len(pl.packets)}/3 pacotes. Continue!", ORANGE)
        elif need == "fragments3" and len(pl.packets) == 3:
            self.state = "win"
        elif need == "fragments3":
            if not self.msg_written:
                self.add_toast("Va ao terminal e escreva a mensagem primeiro!", ORANGE)
            else:
                self.add_toast(f"Fragmentos: {len(pl.packets)}/3. Continue coletando!", ORANGE)
        elif need in ("dos_amp", "arp_spoofer", "ip_bomb", "cookie_grab") and pl.has_hash:
            self.state = "win"
        elif need in ("dos_amp", "arp_spoofer", "ip_bomb", "cookie_grab") and not pl.has_hash:
            tools = {"arp_spoofer": "ARP Spoofer", "ip_bomb": "IP Bomb",
                     "cookie_grab": "Cookie Stealer", "dos_amp": "amplificador DDoS"}
            self.add_toast(f"Pegue o {tools.get(need, 'arma')} primeiro!", ORANGE)

    def check_fall(self):
        if self.player.y > GROUND_Y + 10:
            self.state = "fail"
            self.fail_reason = "Você caiu da rede! O cabo físico se rompeu."

    def _check_minigame_triggers(self):
        ld = self.data
        if not (ld.get("minigame_layer") or ld.get("ssh_layer")):
            return
        pl = self.player

        # WhiteHat at left terminal (x < 160, on ground) → cipher
        if (self.char == "white" and self.minigame_stage == 0
                and pl.x < 160 and pl.on_ground
                and not CESAR_STATE["original"]
                and ld.get("minigame_layer")):
            self.minigame = CesarMiniGame("encrypt")
            self.minigame_stage = 1
            return

        # WhiteHat has hash → SSH dialog (once)
        if (self.char == "white" and ld.get("ssh_layer")
                and pl.has_hash and self.minigame_stage < 2
                and not CESAR_STATE["ssh_locked"]):
            self.minigame = SSHPasswordDialog()
            self.minigame_stage = 2
            return

        # BlackHat near centre (350-560) → decrypt cipher (generate default if WhiteHat hasn't played)
        if (self.char == "black" and self.minigame_stage == 0
                and 340 < pl.x < 560 and pl.on_ground
                and ld.get("minigame_layer")):
            if not CESAR_STATE["encrypted"]:
                import random as _rnd
                _shift = _rnd.randint(2, 8)
                _words = ["REDE SEGURA", "PACOTE TCP", "FIREWALL", "PROTOCOLO", "CIFRA RSA"]
                _orig  = _rnd.choice(_words)
                def _enc(t, s):
                    return "".join(
                        chr((ord(c) - (65 if c.isupper() else 97) + s) % 26
                            + (65 if c.isupper() else 97))
                        if c.isalpha() else c for c in t)
                CESAR_STATE["shift"]     = _shift
                CESAR_STATE["encrypted"] = _enc(_orig, _shift)
            self.minigame = CesarMiniGame(
                "decrypt",
                CESAR_STATE["encrypted"],
                CESAR_STATE["shift"],
            )
            self.minigame_stage = 1
            return

        # BlackHat tries to grab SSH-locked hash
        if self.char == "black" and pl.has_hash and CESAR_STATE.get("ssh_locked"):
            pl.has_hash = False
            self.add_toast("Hash bloqueado por SSH! Quebre a cifra primeiro.", RED_HAT)

    def update(self, keys=None):
        if self.minigame is not None:
            return  # mini-game pauses all gameplay
        if self.state != "playing":
            return
        actions = get_actions(self.control_slot)
        self.player.update(actions, self.data["platforms"])
        for e in self.enemies:
            e.update(player_x=self.player.x)
        self.check_pickups()
        self.check_enemies()
        if self.state == "playing":
            self.check_goal()
        if self.state == "playing":
            self.check_fall()
        if self.state == "playing":
            self._check_minigame_triggers()
        self.toasts = [t for t in self.toasts if t.alive]
        for t in self.toasts:
            t.update()
        # Cycle thoughts
        now = pygame.time.get_ticks()
        if now - self.next_thought_timer > 6000:
            self.next_thought_timer = now
            thoughts = self.data.get("thoughts_text", [])
            if thoughts:
                self.thought_idx = (self.thought_idx + 1) % len(thoughts)

    def draw_playfield(self, surf):
        ld = self.data
        sky_top = hex_to_rgb(ld["sky"][0])
        sky_bot = hex_to_rgb(ld["sky"][1])
        ground_col = hex_to_rgb(ld["ground_color"])

        draw_background(surf, sky_top, sky_bot, ground_col)
        draw_connection_lines(surf, ld["centerpiece"], ld["platforms"])
        draw_centerpiece(surf, ld["centerpiece"])

        for p in ld["platforms"]:
            draw_device(surf, p)

        for p in self.pickups:
            draw_pickup(surf, p)
        for p in self.spawned_pickups:
            draw_pickup(surf, p)

        draw_goal(surf, self.goal_data)

        for e in self.enemies:
            e.draw(surf, player_char=self.char)

        # Multiplayer: draw remote player with label
        if self.remote_x is not None:
            rx, ry = int(self.remote_x), int(self.remote_y)
            rc = self.remote_char
            glow_col = RED_HAT if rc == "black" else EMERALD
            draw_glow(surf, glow_col, rx + PW // 2, ry + PH // 2, 20, 80)
            draw_player(surf, rx, ry, rc, facing=self.remote_facing, anim_frame=self.remote_frame)
            lbl_col = RED_HAT if rc == "black" else EMERALD
            lbl = FONT_TINY.render("OPONENTE", True, lbl_col)
            surf.blit(lbl, (rx + PW // 2 - lbl.get_width() // 2, ry - 16))

        self.player.draw(surf)

        # Cable trail — drawn from pickup origin to player centre
        if self.player.has_cable and self.cable_pickup_pos:
            ox, oy = self.cable_pickup_pos
            px = int(self.player.x + PW // 2)
            py = int(self.player.y + PH // 2)
            mid_x = (ox + px) // 2
            mid_y = max(oy, py) + 28
            pts = [(ox, oy), (mid_x, mid_y), (px, py)]
            pygame.draw.lines(surf, CABLE_BLUE, False, pts, 3)
            pygame.draw.lines(surf, (120, 180, 255), False, pts, 1)
            pygame.draw.circle(surf, CYAN, (px, py), 5)

        # Encrypted message floating label (cipher layers)
        if self.data.get("minigame_layer") and CESAR_STATE["encrypted"]:
            enc = CESAR_STATE["encrypted"][:28]
            now3 = pygame.time.get_ticks()
            gx3 = GAME_W // 2
            gy3 = 110 + int(5 * math.sin(now3 / 600))
            draw_glow(surf, ORANGE, gx3, gy3, 70, 55)
            et = FONT_SM.render(f'CIFRADO: "{enc}"', True, ORANGE)
            surf.blit(et, (gx3 - et.get_width() // 2, gy3 - 10))
            tag2 = FONT_TINY.render("BlackHat: chegue ao centro (x≈350-560) para decifrar", True, RED_HAT)
            surf.blit(tag2, (gx3 - tag2.get_width() // 2, gy3 + 14))

        # WhiteHat terminal hint (cipher / SSH layers)
        if self.char == "white" and (self.data.get("minigame_layer") or self.data.get("ssh_layer")):
            if not CESAR_STATE["original"] and self.data.get("minigame_layer"):
                hint_c = FONT_TINY.render("WhiteHat: vá para a esquerda (x<160) para cifrar!", True, EMERALD)
                surf.blit(hint_c, (10, HEADER_H + 60))

        # Thought bubble
        if self.thought_visible:
            thoughts = ld.get("thoughts_text", [])
            if thoughts:
                thought = thoughts[self.thought_idx % len(thoughts)]
                self._draw_thought_bubble(surf, thought)

        # Toasts
        for t in self.toasts:
            t.draw(surf)

        # Mini-game overlay (drawn on top of everything)
        if self.minigame is not None:
            self.minigame.draw(surf)

        # HUD
        self._draw_hud(surf)

    def _draw_thought_bubble(self, surf, text):
        px = int(self.player.x)
        py = int(self.player.y)
        lines = wrap_text(text, FONT_XS, 200)
        bw = 220
        bh = len(lines) * 20 + 16
        bx = min(px - 10, GAME_W - bw - 10)
        by = max(HEADER_H + 4, py - bh - 20)
        # Bubble
        pygame.draw.rect(surf, WHITE, (bx, by, bw, bh), border_radius=10)
        pygame.draw.rect(surf, CYAN, (bx, by, bw, bh), 2, border_radius=10)
        # Tail
        tail = [(px + PW//2, py - 2), (bx + 30, by + bh), (bx + 50, by + bh)]
        pygame.draw.polygon(surf, WHITE, tail)
        pygame.draw.polygon(surf, CYAN, tail, 2)
        for i, line in enumerate(lines):
            ts = FONT_XS.render(line, True, DARK_BG)
            surf.blit(ts, (bx + 8, by + 8 + i * 20))

    def _draw_hud(self, surf):
        pl = self.player
        need = self.need
        now = pygame.time.get_ticks()

        # HUD background bar
        hud_surf = pygame.Surface((260, 54), pygame.SRCALPHA)
        hud_surf.fill((0, 0, 0, 140))
        pygame.draw.rect(hud_surf, CYAN, (0, 0, 260, 54), 1, border_radius=6)
        surf.blit(hud_surf, (8, HEADER_H + 4))

        # Status text with animated icon
        pulse = int(200 + 55 * math.sin(now / 500))
        if need == "key":
            ok = pl.has_key
            col = EMERALD if ok else (255, pulse // 2, 0)
            status = "CRIPTO: ATIVA" if ok else "PEGUE A CHAVE"
            icon = "🔑"
        elif need == "hash":
            ok = pl.has_hash
            col = EMERALD if ok else (255, pulse // 2, 0)
            status = "HASH: VERIFICADO" if ok else "PEGUE O HASH"
            icon = "✅"
        elif need == "packets3":
            n = len(pl.packets)
            ok = n == 3
            col = EMERALD if ok else CYAN
            status = f"PACOTES: {n}/3"
            icon = "📦"
        elif need == "cable":
            ok = pl.has_cable
            col = (30, 140, 255) if ok else CYAN
            status = "CABO: PLUGADO!" if ok else "PEGUE O CABO RJ45"
            icon = "🔌"
        elif need == "dos_amp":
            ok = pl.has_hash
            col = RED_HAT if ok else ORANGE
            status = "AMP: PRONTO! PLANTE" if ok else "PEGUE O AMPLIFICADOR"
            icon = "⚡"
        else:
            ok = False
            col = CYAN
            status = "ENTREGUE O PACOTE"
            icon = "📬"

        # Icon
        ic = FONT_EMOJI.render(icon, True, col)
        surf.blit(ic, (14, HEADER_H + 10))

        # Status bar fill
        if need == "packets3":
            bar_w = int(180 * len(pl.packets) / 3)
            bar_col = EMERALD if ok else CYAN
        elif need != "none":
            bar_w = 180 if ok else 0
            bar_col = EMERALD
        else:
            bar_w = 180
            bar_col = EMERALD

        pygame.draw.rect(surf, (20, 20, 20), (40, HEADER_H + 8, 180, 10), border_radius=5)
        if bar_w > 0:
            pygame.draw.rect(surf, bar_col, (40, HEADER_H + 8, bar_w, 10), border_radius=5)
        pygame.draw.rect(surf, GRAY, (40, HEADER_H + 8, 180, 10), 1, border_radius=5)

        # Status label
        ts = FONT_XS.render(status, True, col)
        surf.blit(ts, (40, HEADER_H + 22))

        # I key hint
        hint = FONT_TINY.render("[I] pensamentos  [ESC] menu", True, (80, 80, 100))
        surf.blit(hint, (14, HEADER_H + 42))


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------
class ControlsScreen:
    """Lets each player rebind Left / Right / Jump keys."""

    _ACTIONS = [("left", "Esquerda"), ("right", "Direita"), ("jump", "Pular")]
    _SLOTS   = [("P1", "Jogador 1  (host / solo)", EMERALD),
                ("P2", "Jogador 2  (cliente)",      CYAN)]

    def __init__(self):
        self.result    = None       # "back"
        self.listening = None       # (slot, action) while waiting for a key press
        self.btn_back  = Button(W//2 - 90, 590, 180, 42, "Voltar", GRAY, WHITE)
        self.btn_reset = Button(W//2 + 110, 590, 180, 42, "Padrão", ORANGE, BLACK)
        self._error    = ""

    # ---- events ----

    def handle_event(self, ev):
        if self.listening:
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    self.listening = None
                else:
                    slot, action = self.listening
                    CONTROLS[slot][action] = ev.key
                    _save_controls()
                    self.listening = None
            return   # swallow all events while listening

        if ev.type == pygame.MOUSEBUTTONDOWN:
            mx, my = ev.pos
            # Check every rebind button
            for si, (slot, _, _col) in enumerate(self._SLOTS):
                for ai, (action, _lbl) in enumerate(self._ACTIONS):
                    bx, by = self._btn_pos(si, ai)
                    if pygame.Rect(bx, by, 130, 30).collidepoint(mx, my):
                        self.listening = (slot, action)
                        return

        if self.btn_back.handle_event(ev):
            self.result = "back"
        if self.btn_reset.handle_event(ev):
            for slot in CONTROLS:
                CONTROLS[slot].update(_DEFAULT_CONTROLS[slot])
            _save_controls()

    @staticmethod
    def _btn_pos(slot_idx, action_idx):
        col_x = 180 + slot_idx * 400
        row_y = 240 + action_idx * 90
        return col_x + 200, row_y + 2

    # ---- draw ----

    def draw(self, surf):
        surf.fill(DARK_BG)
        title = FONT_BIG.render("Configurar Controles", True, WHITE)
        surf.blit(title, (W//2 - title.get_width()//2, 50))

        if self.listening:
            slot, action = self.listening
            msg = FONT_MED.render(f"[{slot} — {action}]  Pressione uma tecla...", True, YELLOW)
            surf.blit(msg, (W//2 - msg.get_width()//2, 110))
        else:
            sub = FONT_SM.render("Clique em [Alterar] e pressione a tecla desejada.  ESC cancela.", True, GRAY)
            surf.blit(sub, (W//2 - sub.get_width()//2, 110))

        # Platform hint
        if not _IS_WINDOWS:
            warn = FONT_XS.render("Aviso: GetAsyncKeyState só funciona no Windows. No Linux/Mac, a janela precisa ter foco.", True, ORANGE)
            surf.blit(warn, (W//2 - warn.get_width()//2, 140))

        for si, (slot, label, col) in enumerate(self._SLOTS):
            col_x = 180 + si * 400

            # Column header
            pygame.draw.rect(surf, (10, 30, 20), (col_x, 170, 340, 44), border_radius=8)
            pygame.draw.rect(surf, col, (col_x, 170, 340, 44), 2, border_radius=8)
            hdr = FONT_MED.render(label, True, col)
            surf.blit(hdr, (col_x + 10, 180))

            for ai, (action, lbl) in enumerate(self._ACTIONS):
                row_y = 240 + ai * 90

                # Action label + current key
                pygame.draw.rect(surf, (15, 20, 35), (col_x, row_y, 340, 72), border_radius=6)
                pygame.draw.rect(surf, (40, 60, 100), (col_x, row_y, 340, 72), 1, border_radius=6)

                act_t = FONT_SM.render(lbl + ":", True, WHITE)
                surf.blit(act_t, (col_x + 10, row_y + 8))

                key_name = pygame.key.name(CONTROLS[slot][action]).upper()
                key_col  = YELLOW if self.listening == (slot, action) else CYAN
                key_t = FONT_MED.render(f"[ {key_name} ]", True, key_col)
                surf.blit(key_t, (col_x + 10, row_y + 34))

                # Alterar button
                bx, by = self._btn_pos(si, ai)
                hover = pygame.Rect(bx, by, 130, 30).collidepoint(pygame.mouse.get_pos())
                btn_col = ORANGE if hover else (60, 80, 120)
                pygame.draw.rect(surf, btn_col, (bx, by, 130, 30), border_radius=5)
                bt = FONT_XS.render("Alterar", True, WHITE)
                surf.blit(bt, (bx + 65 - bt.get_width()//2, by + 7))

        # Legend: who uses which slot
        leg_y = 510
        pygame.draw.rect(surf, (10, 25, 40), (W//2 - 300, leg_y, 600, 64), border_radius=8)
        pygame.draw.rect(surf, GRAY, (W//2 - 300, leg_y, 600, 64), 1, border_radius=8)
        l1 = FONT_XS.render("P1 = Modo Solo  |  Host do multiplayer (WhiteHat por padrão)", True, EMERALD)
        l2 = FONT_XS.render("P2 = Segundo jogador via rede (cliente / BlackHat por padrão)", True, CYAN)
        surf.blit(l1, (W//2 - l1.get_width()//2, leg_y + 8))
        surf.blit(l2, (W//2 - l2.get_width()//2, leg_y + 32))

        self.btn_back.draw(surf)
        self.btn_reset.draw(surf)


class MenuScreen:
    def __init__(self):
        self.btn_historia  = Button(W//2 - 140, 280, 280, 52, "Modo História", EMERALD, BLACK)
        self.btn_criar     = Button(W//2 - 140, 348, 280, 52, "Criar Sala", (30, 80, 160), WHITE)
        self.btn_entrar    = Button(W//2 - 140, 416, 280, 52, "Entrar em Sala", (60, 30, 100), WHITE)
        self.btn_controles = Button(W//2 - 140, 484, 280, 42, "Controles", (80, 60, 20), WHITE)
        self.result = None
        self.t = 0

    def handle_event(self, ev):
        if self.btn_historia.handle_event(ev):
            self.result = "historia"
        if self.btn_criar.handle_event(ev):
            self.result = "criar"
        if self.btn_entrar.handle_event(ev):
            self.result = "entrar"
        if self.btn_controles.handle_event(ev):
            self.result = "controles"

    def update(self):
        self.t += 1

    def draw(self, surf):
        surf.fill(DARK_BG)
        now = pygame.time.get_ticks()

        # Animated hex grid background
        hex_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        for gx in range(0, W, 50):
            for gy in range(0, H, 50):
                pulse = int(20 + 10 * math.sin(now / 1000 + gx * 0.03 + gy * 0.03))
                pygame.draw.circle(hex_surf, (*CYAN, pulse), (gx, gy), 2)
        for gx in range(0, W, 50):
            pygame.draw.line(hex_surf, (*CYAN, 12), (gx, 0), (gx, H))
        for gy in range(0, H, 50):
            pygame.draw.line(hex_surf, (*CYAN, 12), (0, gy), (W, gy))
        surf.blit(hex_surf, (0, 0))

        # Scanlines
        scan = pygame.Surface((W, H), pygame.SRCALPHA)
        for row in range(0, H, 3):
            scan.fill((0, 0, 0, 18), (0, row, W, 1))
        surf.blit(scan, (0, 0))

        # Floating data particles
        for i in range(40):
            px = (i * 137 + self.t * (1 + i % 4)) % W
            py = (i * 73 + self.t * (0.5 + i % 3)) % H
            r = 1 + i % 3
            a = 60 + (i % 5) * 20
            dot = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(dot, (*EMERALD, a), (r, r), r)
            surf.blit(dot, (int(px), int(py)))

        # Title glow
        draw_glow(surf, EMERALD, W // 2, 145, 120, 40)
        title_shadow = FONT_BIG.render("CyberLayerQuest", True, (0, 60, 40))
        surf.blit(title_shadow, (W//2 - title_shadow.get_width()//2 + 2, 122))
        title = FONT_BIG.render("CyberLayerQuest", True, EMERALD)
        surf.blit(title, (W//2 - title.get_width()//2, 120))

        # Subtitle with animated color
        pulse_c = int(128 + 127 * math.sin(now / 800))
        sub_col = (0, pulse_c, 255)
        sub = FONT_MED.render("WhiteHat  ⚔  BlackHat", True, sub_col)
        surf.blit(sub, (W//2 - sub.get_width()//2, 188))

        # OSI layer strip
        layers = ["FÍSICA","REDE","TRANSPORTE","SESSÃO","APRESENTAÇÃO","APLICAÇÃO"]
        strip_w = W // len(layers)
        layer_cols = [CYAN, EMERALD, YELLOW, ORANGE, PURPLE, RED_HAT]
        for i, (lname, lc) in enumerate(zip(layers, layer_cols)):
            lx = i * strip_w
            ly = 240
            draw_rect_alpha(surf, lc, (lx, ly, strip_w - 2, 28), 50)
            lt = FONT_TINY.render(lname, True, lc)
            surf.blit(lt, (lx + strip_w//2 - lt.get_width()//2, ly + 8))

        # Animated neon border on buttons
        blink = int(200 + 55 * math.sin(now / 400))
        border_col = (0, blink, blink // 2)

        # Buttons with neon style
        self.btn_historia.draw(surf, FONT_MED)
        draw_neon_rect(surf, EMERALD, (W//2 - 140, 280, 280, 52), 2, glow=True, radius=8)

        self.btn_criar.draw(surf, FONT_SM)
        draw_neon_rect(surf, border_col, (W//2 - 140, 348, 280, 52), 2, glow=True, radius=8)

        self.btn_entrar.draw(surf, FONT_SM)
        draw_neon_rect(surf, PURPLE, (W//2 - 140, 416, 280, 52), 2, glow=True, radius=8)

        self.btn_controles.draw(surf, FONT_SM)
        draw_neon_rect(surf, ORANGE, (W//2 - 140, 484, 280, 42), 2, glow=True, radius=8)

        # Mini character previews next to buttons
        tmp_w = pygame.Surface((50, 60), pygame.SRCALPHA)
        draw_player(tmp_w, 12, 16, "white")
        surf.blit(tmp_w, (W//2 - 140 - 60, 304))
        tmp_b = pygame.Surface((50, 60), pygame.SRCALPHA)
        draw_player(tmp_b, 12, 16, "black")
        surf.blit(tmp_b, (W//2 + 140 + 10, 304))

        # UTFPR badge
        badge_w, badge_h = 150, 38
        bx, by = W - badge_w - 12, H - badge_h - 12
        draw_rect_alpha(surf, BLACK, (bx, by, badge_w, badge_h), 200)
        pygame.draw.rect(surf, YELLOW, (bx, by, badge_w, badge_h), 2, border_radius=6)
        badge_t = FONT_XS.render("UTFPR-1ºLC", True, YELLOW)
        surf.blit(badge_t, (bx + badge_w//2 - badge_t.get_width()//2,
                            by + badge_h//2 - badge_t.get_height()//2))

        # ── CENA DO DATA CENTER (decorativa) ──────────────────────────────────
        scene_y = 510   # base Y da cena no menu

        # Chão da cena
        pygame.draw.rect(surf, (15, 20, 35), (0, scene_y, W, H - scene_y))
        pygame.draw.line(surf, CYAN, (0, scene_y), (W, scene_y), 1)

        # === Lado esquerdo: rack de servidores ===
        draw_server_rack_detailed(surf, 30, scene_y - 130, 90, 130, "RACK-01")
        draw_server_rack_detailed(surf, 130, scene_y - 100, 80, 100, "RACK-02")

        # Cabo aéreo conectando racks
        draw_cable_bundle(surf, 75, scene_y - 130, 170, scene_y - 100,
                          CABLE_BLUE, 3)

        # Personagem WhiteHat sentado (digitando no monitor)
        mon_x, mon_y = 230, scene_y - 80
        draw_monitor_detailed(surf, mon_x, mon_y, 70, 70, "PC")
        # Chão cadeira
        pygame.draw.rect(surf, STEEL, (mon_x + 20, scene_y - 12, 30, 12))
        # Personagem sentado (menor, posição sentada)
        tmp_seat = pygame.Surface((50, 55), pygame.SRCALPHA)
        draw_player(tmp_seat, 5, 10, "white", 1, (self.t // 16) % 4)
        surf.blit(pygame.transform.scale(tmp_seat, (35, 40)), (mon_x + 18, scene_y - 52))
        # Balão de fala
        bubble_txt = FONT_TINY.render("ssh root@srv", True, LED_GREEN)
        bubble_bg = pygame.Surface((bubble_txt.get_width() + 10, 18), pygame.SRCALPHA)
        bubble_bg.fill((10, 30, 10, 200))
        pygame.draw.rect(bubble_bg, LED_GREEN, (0, 0, bubble_bg.get_width(), 18), 1)
        surf.blit(bubble_bg, (mon_x - 10, scene_y - 72))
        surf.blit(bubble_txt, (mon_x - 5, scene_y - 70))

        # === Centro: roteador com cabos ===
        rtr_x = W // 2 - 30
        draw_router_detailed(surf, rtr_x, scene_y - 70, 60, 70, "ROUTER")
        # Cabos saindo do roteador para os lados
        draw_cable_bundle(surf, 300, scene_y - 35, rtr_x, scene_y - 35, CABLE_BLUE, 2)
        draw_cable_bundle(surf, rtr_x + 60, scene_y - 35, W - 300, scene_y - 35, (100, 30, 180), 2)

        # === Lado direito: monitor + personagem BlackHat ===
        mon2_x = W - 340
        draw_monitor_detailed(surf, mon2_x, scene_y - 90, 80, 80, "HACK")
        pygame.draw.rect(surf, STEEL, (mon2_x + 25, scene_y - 12, 30, 12))
        tmp_seat2 = pygame.Surface((50, 55), pygame.SRCALPHA)
        draw_player(tmp_seat2, 5, 10, "black", -1, (self.t // 16) % 4)
        surf.blit(pygame.transform.scale(tmp_seat2, (35, 40)), (mon2_x + 22, scene_y - 52))
        bubble_txt2 = FONT_TINY.render("sudo rm -rf /", True, (255, 80, 80))
        bubble_bg2 = pygame.Surface((bubble_txt2.get_width() + 10, 18), pygame.SRCALPHA)
        bubble_bg2.fill((30, 5, 5, 200))
        pygame.draw.rect(bubble_bg2, RED_HAT, (0, 0, bubble_bg2.get_width(), 18), 1)
        surf.blit(bubble_bg2, (mon2_x - 5, scene_y - 100))
        surf.blit(bubble_txt2, (mon2_x, scene_y - 98))

        # Segundo rack no lado direito
        draw_server_rack_detailed(surf, W - 130, scene_y - 120, 90, 120, "RACK-03")
        draw_cable_bundle(surf, W - 260, scene_y - 50, W - 130, scene_y - 60, (30, 80, 200), 3)

        # Cabos no chão
        draw_cable_bundle(surf, 0, scene_y + 10, W, scene_y + 10, (20, 40, 80), 5)
        draw_cable_bundle(surf, 0, scene_y + 20, W, scene_y + 20, (50, 20, 80), 3)

        # ── FIM DA CENA ──────────────────────────────────────────────────────

        # Controls hint
        ctrl = FONT_XS.render("Setas/WASD mover  •  Espaço/W pular  •  I pensamentos  •  ESC menu", True, GRAY)
        surf.blit(ctrl, (W//2 - ctrl.get_width()//2, H - 10))


class ModelSelectScreen:
    """Choose OSI (7 layers) or TCP/IP (4 layers) before character select."""
    def __init__(self):
        self.selected = "osi"   # "osi" | "tcpip"
        self.result = None      # "osi" | "tcpip" | "back"
        self.t = 0

    def handle_event(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN:
            mx, my = ev.pos
            if pygame.Rect(W // 2 - 340, 150, 280, 360).collidepoint(mx, my):
                self.selected = "osi"
            if pygame.Rect(W // 2 + 60, 150, 280, 360).collidepoint(mx, my):
                self.selected = "tcpip"
            if pygame.Rect(W // 2 - 140, 558, 280, 50).collidepoint(mx, my):
                self.result = self.selected
            if pygame.Rect(W // 2 - 60, 622, 120, 36).collidepoint(mx, my):
                self.result = "back"
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_RETURN:
                self.result = self.selected
            if ev.key == pygame.K_ESCAPE:
                self.result = "back"
            if ev.key == pygame.K_LEFT:
                self.selected = "osi"
            if ev.key == pygame.K_RIGHT:
                self.selected = "tcpip"

    def update(self):
        self.t += 1

    def draw(self, surf):
        surf.fill(DARK_BG)
        now = pygame.time.get_ticks()
        # Grid
        gs = pygame.Surface((W, H), pygame.SRCALPHA)
        for gx in range(0, W, 50):
            pygame.draw.line(gs, (*CYAN, 10), (gx, 0), (gx, H))
        for gy in range(0, H, 50):
            pygame.draw.line(gs, (*CYAN, 10), (0, gy), (W, gy))
        surf.blit(gs, (0, 0))

        title = FONT_BIG.render("Escolha o Modelo de Rede", True, WHITE)
        surf.blit(title, (W // 2 - title.get_width() // 2, 50))
        sub = FONT_SM.render("Cada modelo define quantas camadas você vai explorar", True, GRAY)
        surf.blit(sub, (W // 2 - sub.get_width() // 2, 112))

        # OSI card
        osi_border = EMERALD if self.selected == "osi" else GRAY
        pygame.draw.rect(surf, (10, 25, 20), (W // 2 - 340, 150, 280, 360), border_radius=12)
        pygame.draw.rect(surf, osi_border, (W // 2 - 340, 150, 280, 360), 3, border_radius=12)
        if self.selected == "osi":
            draw_glow(surf, EMERALD, W // 2 - 200, 330, 80, 28)
        t1 = FONT_MED.render("Modelo OSI", True, EMERALD)
        surf.blit(t1, (W // 2 - 340 + 140 - t1.get_width() // 2, 166))
        t2 = FONT_SM.render("7 Camadas", True, CYAN)
        surf.blit(t2, (W // 2 - 340 + 140 - t2.get_width() // 2, 204))
        osi_layers = ["7. Aplicação", "6. Apresentação", "5. Sessão",
                      "4. Transporte", "3. Rede", "2. Enlace", "1. Física"]
        osi_cols   = [RED_HAT, ORANGE, YELLOW, EMERALD, CYAN, PURPLE, STEEL]
        for i, (lyr, lc) in enumerate(zip(osi_layers, osi_cols)):
            ly = 238 + i * 30
            pygame.draw.rect(surf, (*lc, 55), (W // 2 - 330, ly, 260, 24))
            lt = FONT_XS.render(lyr, True, lc)
            surf.blit(lt, (W // 2 - 330 + 8, ly + 5))

        # TCP/IP card
        tcp_border = CYAN if self.selected == "tcpip" else GRAY
        pygame.draw.rect(surf, (10, 20, 30), (W // 2 + 60, 150, 280, 360), border_radius=12)
        pygame.draw.rect(surf, tcp_border, (W // 2 + 60, 150, 280, 360), 3, border_radius=12)
        if self.selected == "tcpip":
            draw_glow(surf, CYAN, W // 2 + 200, 330, 80, 28)
        t3 = FONT_MED.render("Modelo TCP/IP", True, CYAN)
        surf.blit(t3, (W // 2 + 60 + 140 - t3.get_width() // 2, 166))
        t4 = FONT_SM.render("4 Camadas", True, EMERALD)
        surf.blit(t4, (W // 2 + 60 + 140 - t4.get_width() // 2, 204))
        tcp_layers = [
            ("4. Aplicação", "HTTP, SSH, DNS..."),
            ("3. Transporte", "TCP / UDP"),
            ("2. Internet", "IP, ICMP, roteamento"),
            ("1. Acesso à Rede", "Ethernet, Wi-Fi"),
        ]
        tcp_cols = [RED_HAT, EMERALD, CYAN, STEEL]
        for i, ((ln, ls), lc) in enumerate(zip(tcp_layers, tcp_cols)):
            ly = 248 + i * 56
            pygame.draw.rect(surf, (*lc, 55), (W // 2 + 70, ly, 260, 46))
            lt1 = FONT_XS.render(ln, True, lc)
            lt2 = FONT_TINY.render(ls, True, tuple(max(0, c - 40) for c in lc))
            surf.blit(lt1, (W // 2 + 78, ly + 5))
            surf.blit(lt2, (W // 2 + 78, ly + 24))

        # Confirm button
        bc = EMERALD if self.selected == "osi" else CYAN
        pygame.draw.rect(surf, bc, (W // 2 - 140, 558, 280, 50), border_radius=8)
        pygame.draw.rect(surf, WHITE, (W // 2 - 140, 558, 280, 50), 2, border_radius=8)
        bt = FONT_MED.render("Confirmar ▶", True, BLACK)
        surf.blit(bt, (W // 2 - bt.get_width() // 2, 573))

        # Back button
        pygame.draw.rect(surf, GRAY, (W // 2 - 60, 622, 120, 36), border_radius=6)
        back_t = FONT_SM.render("Voltar", True, WHITE)
        surf.blit(back_t, (W // 2 - back_t.get_width() // 2, 631))

        hint = FONT_XS.render("← → para alternar  |  ENTER para confirmar", True, GRAY)
        surf.blit(hint, (W // 2 - hint.get_width() // 2, 665))


class SelectScreen:
    def __init__(self):
        self.selected = "white"
        self.btn_back  = Button(W//2 - 240, 570, 180, 44, "Voltar", GRAY, WHITE)
        self.btn_cont  = Button(W//2 + 60,  570, 180, 44, "Continuar", EMERALD, BLACK)
        self.result = None
        self.char_result = None

    def handle_event(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN:
            mx, my = ev.pos
            # White card
            if pygame.Rect(W//2 - 340, 130, 260, 380).collidepoint(mx, my):
                self.selected = "white"
            # Black card
            if pygame.Rect(W//2 + 80, 130, 260, 380).collidepoint(mx, my):
                self.selected = "black"
        if self.btn_back.handle_event(ev):
            self.result = "back"
        if self.btn_cont.handle_event(ev):
            self.result = "play"
            self.char_result = self.selected

    def draw(self, surf):
        surf.fill(DARK_BG)
        title = FONT_BIG.render("Escolha seu personagem", True, WHITE)
        surf.blit(title, (W//2 - title.get_width()//2, 50))

        # White card
        wborder = EMERALD if self.selected == "white" else GRAY
        pygame.draw.rect(surf, (20, 40, 30), (W//2 - 340, 130, 260, 380), border_radius=14)
        pygame.draw.rect(surf, wborder, (W//2 - 340, 130, 260, 380), 3, border_radius=14)
        # Sprite preview
        tmp = pygame.Surface((80, 80), pygame.SRCALPHA)
        draw_player(tmp, 27, 22, "white")
        surf.blit(tmp, (W//2 - 340 + 90, 170))
        draw_text_centered(surf, "WhiteHat", FONT_MED, EMERALD, W//2 - 210, 290)
        draw_text_centered(surf, "Defensor", FONT_SM, CYAN, W//2 - 210, 326)
        for i, line in enumerate([
            "Protege a rede contra",
            "ataques cibernéticos.",
            "Usa criptografia,",
            "hash e boas práticas.",
        ]):
            draw_text_centered(surf, line, FONT_XS, WHITE, W//2 - 210, 360 + i * 22)

        # Black card
        bborder = RED_HAT if self.selected == "black" else GRAY
        pygame.draw.rect(surf, (30, 10, 10), (W//2 + 80, 130, 260, 380), border_radius=14)
        pygame.draw.rect(surf, bborder, (W//2 + 80, 130, 260, 380), 3, border_radius=14)
        tmp2 = pygame.Surface((80, 80), pygame.SRCALPHA)
        draw_player(tmp2, 27, 22, "black")
        surf.blit(tmp2, (W//2 + 80 + 90, 170))
        draw_text_centered(surf, "BlackHat", FONT_MED, RED_HAT, W//2 + 210, 290)
        draw_text_centered(surf, "Invasor", FONT_SM, ORANGE, W//2 + 210, 326)
        for i, line in enumerate([
            "Testa as defesas da rede",
            "simulando ataques reais.",
            "Usa sniff, DoS e",
            "Tampering.",
        ]):
            draw_text_centered(surf, line, FONT_XS, WHITE, W//2 + 210, 360 + i * 22)

        self.btn_back.draw(surf)
        self.btn_cont.draw(surf)


class RoomScreen:
    """
    Handles room creation / joining with real TCP+UDP networking.
    - Host:   starts TCP server + UDP broadcast; waits for peer; shows [Iniciar] when connected.
    - Client: discovers host via UDP broadcast; connects; waits for host to start.
    result values: "back" | "start_multiplayer"
    """
    _MODEL_LABELS = [("OSI (7 camadas)", "osi"), ("TCP/IP (4 camadas)", "tcpip")]

    def __init__(self, mode: str):
        self.mode = mode           # "criar" | "entrar"
        self.result = None
        self.net = NetworkManager() if _NET_AVAILABLE else None

        # Form widgets (shown before connecting)
        lbl = "Código da sala" if mode == "criar" else "Código da sala (igual ao host)"
        self.code_box = InputBox(W//2 - 170, 210, 340, 44, lbl)
        self.pass_box = InputBox(W//2 - 170, 285, 340, 44, "Senha")
        if mode == "criar":
            self.btn_action = Button(W//2 - 130, 355, 260, 48, "Criar e aguardar", EMERALD, BLACK)
        else:
            self.btn_action = Button(W//2 - 130, 355, 260, 48, "Procurar e entrar", CYAN, BLACK)
        self.btn_back = Button(W//2 - 90, 500, 180, 40, "Voltar", GRAY, WHITE)

        # Host-only: model + level selector + start button (shown after peer connects)
        self.model_choice = "osi"
        self.level_choice = 0        # which level index to start
        self.btn_osi   = Button(W//2 - 190, 300, 170, 36, "OSI  (7 cam.)",  CABLE_BLUE, WHITE)
        self.btn_tcpip = Button(W//2 +  20, 300, 170, 36, "TCP/IP (4 cam.)", CABLE_BLUE, WHITE)
        self.btn_start = Button(W//2 - 100, 570, 200, 44, "INICIAR JOGO", EMERALD, BLACK)

        self.phase = "form"        # "form" | "waiting" | "connected" | "starting"
        self.pulse_t = 0
        self.my_char = "white" if mode == "criar" else "black"
        self.status_msg = ""

    # ---- events ----

    def handle_event(self, ev):
        if self.phase == "form":
            self.code_box.handle_event(ev)
            self.pass_box.handle_event(ev)
            if self.btn_action.handle_event(ev):
                self._start_network()
            if self.btn_back.handle_event(ev):
                self.result = "back"

        elif self.phase in ("waiting", "connected"):
            if self.btn_back.handle_event(ev):
                if self.net:
                    self.net.close()
                self.result = "back"
            if self.phase == "connected" and self.mode == "criar":
                if self.btn_osi.handle_event(ev):
                    self.model_choice = "osi"
                    self.level_choice = 0
                if self.btn_tcpip.handle_event(ev):
                    self.model_choice = "tcpip"
                    self.level_choice = 0
                # Level selector clicks
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    levels = LEVELS_OSI if self.model_choice == "osi" else LEVELS_TCPIP
                    for i, lvd in enumerate(levels):
                        bx, by = self._level_btn_pos(i, len(levels))
                        if pygame.Rect(bx, by, self._level_btn_w(len(levels)), 38).collidepoint(ev.pos):
                            self.level_choice = i
                if self.btn_start.handle_event(ev):
                    self._send_start()

    def _start_network(self):
        code = self.code_box.text.strip()
        pw   = self.pass_box.text.strip()
        if not code or not pw:
            self.status_msg = "Preencha o código e a senha!"
            return
        if not self.net:
            self.status_msg = "Rede não disponível (netplay.py ausente)"
            return
        self.phase = "waiting"
        if self.mode == "criar":
            self.net.host(code, pw)
            self.status_msg = f"Aguardando jogador... (IP: {self.net.my_ip})"
        else:
            self.net.join(code, pw)
            self.status_msg = "Procurando a sala na rede..."

    def _send_start(self):
        if self.net:
            self.net.send({"type": "start", "model": self.model_choice,
                           "level": self.level_choice})
        self.phase = "starting"
        self.result = "start_multiplayer"

    @staticmethod
    def _level_btn_w(n: int) -> int:
        return max(80, min(124, (W - 120) // n))

    @staticmethod
    def _level_btn_pos(i: int, n: int) -> tuple[int, int]:
        bw  = RoomScreen._level_btn_w(n)
        gap = 6
        total = n * bw + (n - 1) * gap
        x0 = W // 2 - total // 2
        return x0 + i * (bw + gap), 355

    # ---- update ----

    def update(self):
        self.pulse_t += 1
        if not self.net or self.phase not in ("waiting",):
            return

        # Check peer messages while waiting
        for msg in self.net.poll():
            if msg.get("type") == "start":
                # Client received start from host
                self.model_choice = msg.get("model", "osi")
                self.phase = "starting"
                self.result = "start_multiplayer"

        st = self.net.status
        if st == "connected" and self.phase == "waiting":
            self.phase = "connected"
            if self.mode == "criar":
                self.status_msg = "Jogador conectou! Escolha o modelo e inicie."
            else:
                self.status_msg = "Conectado! Aguardando o host iniciar..."
        elif st == "error":
            self.status_msg = f"ERRO: {self.net.error_msg}"
            self.phase = "form"
            self.net = NetworkManager() if _NET_AVAILABLE else None

    # ---- draw ----

    def draw(self, surf):
        surf.fill(DARK_BG)
        col = EMERALD if self.mode == "criar" else CYAN
        title_txt = "Criar Sala" if self.mode == "criar" else "Entrar em Sala"
        title = FONT_BIG.render(title_txt, True, col)
        surf.blit(title, (W//2 - title.get_width()//2, 60))

        if self.phase == "form":
            self._draw_form(surf)
        elif self.phase in ("waiting", "connected"):
            self._draw_waiting(surf)

        # Status message
        if self.status_msg:
            col_s = RED_HAT if "ERRO" in self.status_msg else GRAY
            sm = FONT_XS.render(self.status_msg, True, col_s)
            surf.blit(sm, (W//2 - sm.get_width()//2, 560))

        self.btn_back.draw(surf)

        if not _NET_AVAILABLE:
            warn = FONT_XS.render("netplay.py não encontrado — multiplayer desativado", True, ORANGE)
            surf.blit(warn, (W//2 - warn.get_width()//2, 600))

    def _draw_form(self, surf):
        lbl1 = FONT_SM.render("Código da sala:", True, WHITE)
        surf.blit(lbl1, (W//2 - 170, 185))
        self.code_box.draw(surf)
        lbl2 = FONT_SM.render("Senha:", True, WHITE)
        surf.blit(lbl2, (W//2 - 170, 260))
        self.pass_box.draw(surf)
        self.btn_action.draw(surf)
        if self.mode == "criar" and self.net:
            ip_t = FONT_XS.render(f"Seu IP: {self.net.my_ip}", True, GRAY)
            surf.blit(ip_t, (W//2 - ip_t.get_width()//2, 415))
        elif self.mode == "entrar":
            hint = FONT_XS.render("Dica: use o mesmo código e senha que o host digitou.", True, GRAY)
            surf.blit(hint, (W//2 - hint.get_width()//2, 415))

    def _draw_waiting(self, surf):
        # Connection status box
        box_col = EMERALD if self.phase == "connected" else GRAY
        pygame.draw.rect(surf, (10, 30, 20), (W//2 - 200, 130, 400, 90), border_radius=10)
        pygame.draw.rect(surf, box_col, (W//2 - 200, 130, 400, 90), 2, border_radius=10)

        if self.phase == "connected":
            st_t = FONT_MED.render("CONECTADO!", True, EMERALD)
        else:
            st_t = FONT_SM.render("Aguardando...", True, GRAY)
        surf.blit(st_t, (W//2 - st_t.get_width()//2, 148))

        # Pulsing dot
        r = 7 + int(3 * math.sin(self.pulse_t / 10))
        pygame.draw.circle(surf, box_col, (W//2 + 160, 175), r)

        # IP info
        if self.net and self.mode == "criar":
            ip_t = FONT_SM.render(f"Seu IP: {self.net.my_ip}", True, CYAN)
            surf.blit(ip_t, (W//2 - ip_t.get_width()//2, 240))
            share = FONT_XS.render("Compartilhe este IP ou use o mesmo código para o outro jogador encontrar.", True, GRAY)
            surf.blit(share, (W//2 - share.get_width()//2, 268))

        if self.phase == "connected" and self.mode == "criar":
            # --- Model selector ---
            mdl_lbl = FONT_SM.render("Modelo de rede:", True, WHITE)
            surf.blit(mdl_lbl, (W//2 - 190, 268))
            self.btn_osi.color   = EMERALD if self.model_choice == "osi"   else CABLE_BLUE
            self.btn_tcpip.color = EMERALD if self.model_choice == "tcpip" else CABLE_BLUE
            self.btn_osi.draw(surf)
            self.btn_tcpip.draw(surf)

            # --- Level selector ---
            levels = LEVELS_OSI if self.model_choice == "osi" else LEVELS_TCPIP
            lv_lbl = FONT_SM.render("Fase inicial:", True, WHITE)
            surf.blit(lv_lbl, (W//2 - self._level_btn_w(len(levels)) * len(levels) // 2, 334))
            bw = self._level_btn_w(len(levels))
            for i, lvd in enumerate(levels):
                bx, by = self._level_btn_pos(i, len(levels))
                is_sel = (i == self.level_choice)
                bg_col = EMERALD if is_sel else (30, 50, 80)
                border  = EMERALD if is_sel else (60, 100, 140)
                pygame.draw.rect(surf, bg_col, (bx, by, bw, 38), border_radius=6)
                pygame.draw.rect(surf, border, (bx, by, bw, 38), 2, border_radius=6)
                # Short level label
                short = lvd["name"].split("—")[-1].strip()
                # Two lines: number + name
                num_t = FONT_TINY.render(f"L{i+1}", True, WHITE if not is_sel else BLACK)
                nm_t  = FONT_TINY.render(short[:10], True, WHITE if not is_sel else BLACK)
                surf.blit(num_t, (bx + bw//2 - num_t.get_width()//2, by + 4))
                surf.blit(nm_t,  (bx + bw//2 - nm_t.get_width()//2,  by + 20))

            # Selected level name
            sel_name = levels[self.level_choice]["name"]
            sn_t = FONT_XS.render(f"Selecionado: {sel_name}", True, YELLOW)
            surf.blit(sn_t, (W//2 - sn_t.get_width()//2, 400))

            # Start button
            self.btn_start.draw(surf)

        elif self.phase == "connected" and self.mode == "entrar":
            wait_t = FONT_SM.render("Aguardando o host escolher a fase e iniciar...", True, CYAN)
            surf.blit(wait_t, (W//2 - wait_t.get_width()//2, 360))


# ---------------------------------------------------------------------------
# Main game state machine
# ---------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.screen_state = "menu"
        self.menu         = MenuScreen()
        self.model_screen = ModelSelectScreen()
        self.select        = SelectScreen()
        self.room          = None
        self.controls_scr  = None
        self.char          = "white"
        self.model_choice  = "osi"        # "osi" | "tcpip"
        self.active_levels = LEVELS_OSI   # set on model confirm
        self.level_idx     = 0
        self.game_level: GameLevel | None = None
        self.person_name   = "Jogador"
        # Multiplayer
        self.net: "NetworkManager | None" = None
        self._net_send_t: int = 0    # last time we sent a position update (ms)

    # ---- screen transitions ----
    def start_level(self, idx):
        self.level_idx = idx
        ld = self.active_levels[idx]
        # P2 slot for multiplayer client, P1 for everything else
        slot = "P2" if (self.net and getattr(self.net, "mode", "") == "client") else "P1"
        self.game_level = GameLevel(ld, self.char, control_slot=slot)
        self.screen_state = "game"
        # Reset César state when entering a cipher/SSH level
        if ld.get("minigame_layer") or ld.get("ssh_layer"):
            CESAR_STATE.update({"original": "", "encrypted": "", "shift": 0,
                                "ssh_locked": False, "ssh_password": ""})

    def _finish_minigame(self, gl):
        """Called when the active mini-game completes."""
        mg = gl.minigame
        gl.minigame = None
        if isinstance(mg, CesarMiniGame):
            if mg.mode == "encrypt" and mg.result:
                CESAR_STATE["original"]  = mg.result["original"]
                CESAR_STATE["encrypted"] = mg.result["encrypted"]
                CESAR_STATE["shift"]     = mg.result["shift"]
                gl.add_toast(f"Mensagem cifrada! Deslocamento: {mg.result['shift']}", EMERALD)
            elif mg.mode == "decrypt":
                if mg.result.get("cracked"):
                    gl.add_toast(f"Cifra quebrada! Msg: {mg.result['decrypted'][:24]}", RED_HAT)
                    gl.player.has_hash = True
                else:
                    if not mg.result.get("aborted"):
                        gl.add_toast("Deslocamento errado — tente novamente!", ORANGE)
                    gl.minigame_stage = 0   # allow retry
        elif isinstance(mg, SSHPasswordDialog):
            if not mg.skipped and mg.password:
                CESAR_STATE["ssh_locked"]   = True
                CESAR_STATE["ssh_password"] = mg.password
                gl.add_toast("Senha SSH definida! Hash protegido.", EMERALD)
            else:
                CESAR_STATE["ssh_locked"] = False
                gl.add_toast("Sem senha SSH — hash vulnerável!", ORANGE)
        elif isinstance(mg, MessageWriteDialog):
            if mg.message:
                gl.msg_written = True
                # Spawn 3 message fragments at level-defined positions
                frag_positions = gl.data.get("fragment_positions",
                    [(200, 185), (460, 250), (780, 185)])
                for i, (fx, fy) in enumerate(frag_positions):
                    gl.spawned_pickups.append(
                        {"x": fx, "y": fy, "type": "fragment", "id": i+1, "collected": False}
                    )
                gl.add_toast(
                    f'Mensagem "{mg.message[:16]}" fragmentada em 3 partes na rede!',
                    CABLE_BLUE
                )
            else:
                gl.add_toast("Digite uma mensagem no terminal!", ORANGE)
        elif isinstance(mg, TypeConfirmDialog):
            if mg.success:
                gl.state = "win"
                gl.add_toast("Interceptação confirmada! Dados entregues.", RED_HAT)
            # If ESC/aborted: return to game without winning, player retries at goal
        elif isinstance(mg, AlterMessageDialog):
            if mg.altered:
                # Mark the pending pickup collected, grant has_hash
                if gl._pending_pickup is not None:
                    gl._pending_pickup["collected"] = True
                    gl._pending_pickup = None
                gl.player.has_hash = True
                gl.add_toast(
                    f'Mensagem adulterada: "{mg.altered[:20]}" — entregue no servidor!',
                    PURPLE,
                )
            else:
                # Dialog cancelled — reset pickup so player can try again
                if gl._pending_pickup is not None:
                    gl._pending_pickup["collected"] = False
                    gl._pending_pickup = None
                gl.add_toast("Adulteração cancelada. Colete novamente.", ORANGE)

    # ---- main loop ----
    def run(self):
        running = True
        while running:
            dt = clock.tick(FPS)
            events = pygame.event.get()

            for ev in events:
                if ev.type == pygame.QUIT:
                    running = False
                    continue

                if self.screen_state == "menu":
                    self.menu.handle_event(ev)
                elif self.screen_state == "controls":
                    if self.controls_scr:
                        self.controls_scr.handle_event(ev)
                elif self.screen_state == "model_select":
                    self.model_screen.handle_event(ev)
                elif self.screen_state == "select":
                    self.select.handle_event(ev)
                    if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                        self.screen_state = "model_select"
                        self.select = SelectScreen()
                elif self.screen_state in ("crear_sala", "entrar_sala"):
                    self.room.handle_event(ev)
                    if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                        self.screen_state = "menu"
                elif self.screen_state == "game":
                    gl = self.game_level
                    if gl and gl.minigame is not None:
                        # Minigame active: it gets the event exclusively
                        gl.minigame.handle_event(ev)
                        if gl.minigame and gl.minigame.done:
                            self._finish_minigame(gl)
                    else:
                        # No minigame: normal game event handling
                        self._handle_game_event(ev)
                elif self.screen_state == "complete":
                    if ev.type == pygame.MOUSEBUTTONDOWN or \
                       (ev.type == pygame.KEYDOWN and ev.key == pygame.K_RETURN):
                        self.screen_state = "menu"
                        self.menu = MenuScreen()
                        self.select = SelectScreen()

            # Updates
            if self.screen_state == "menu":
                self.menu.update()
                if self.menu.result == "historia":
                    self.screen_state = "model_select"
                    self.model_screen = ModelSelectScreen()
                    self.menu.result = None
                elif self.menu.result in ("criar", "entrar"):
                    mode = self.menu.result
                    self.room = RoomScreen(mode)
                    self.screen_state = "crear_sala" if mode == "criar" else "entrar_sala"
                    self.menu.result = None
                elif self.menu.result == "controles":
                    self.controls_scr = ControlsScreen()
                    self.screen_state = "controls"
                    self.menu.result = None

            elif self.screen_state == "controls":
                if self.controls_scr and self.controls_scr.result == "back":
                    self.controls_scr = None
                    self.screen_state = "menu"

            elif self.screen_state == "model_select":
                self.model_screen.update()
                if self.model_screen.result in ("osi", "tcpip"):
                    self.model_choice  = self.model_screen.result
                    self.active_levels = LEVELS_OSI if self.model_choice == "osi" else LEVELS_TCPIP
                    self.screen_state  = "select"
                    self.model_screen.result = None
                elif self.model_screen.result == "back":
                    self.screen_state = "menu"
                    self.model_screen = ModelSelectScreen()

            elif self.screen_state == "select":
                if self.select.result == "play":
                    self.char = self.select.char_result
                    self.select.result = None
                    self.start_level(0)
                elif self.select.result == "back":
                    self.screen_state = "model_select"
                    self.select = SelectScreen()

            elif self.screen_state in ("crear_sala", "entrar_sala"):
                if self.room:
                    self.room.update()
                    if self.room.result == "back":
                        if self.room.net:
                            self.room.net.close()
                        self.screen_state = "menu"
                        self.room = None
                    elif self.room.result == "start_multiplayer":
                        # Transition to game with network
                        level_start = self.room.level_choice
                        self.net = self.room.net
                        self.char = self.room.my_char
                        model = self.room.model_choice
                        self.active_levels = LEVELS_OSI if model == "osi" else LEVELS_TCPIP
                        self.room = None
                        self.start_level(level_start)

                # Client side: also poll net for start message if room still waiting
                if self.room and self.room.net and self.room.phase == "connected" \
                        and self.room.mode == "entrar":
                    for msg in self.room.net.poll():
                        if msg.get("type") == "start":
                            self.net = self.room.net
                            self.char = self.room.my_char
                            model = msg.get("model", "osi")
                            self.active_levels = LEVELS_OSI if model == "osi" else LEVELS_TCPIP
                            self.room = None
                            self.start_level(msg.get("level", 0))
                            break

            elif self.screen_state == "game":
                self._update_game()

            # Draw
            self._draw()
            pygame.display.flip()

        pygame.quit()
        sys.exit()

    def _handle_game_event(self, ev):
        gl = self.game_level
        # Safety guard: never process game events when a minigame is active
        if gl and gl.minigame is not None:
            return
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.screen_state = "menu"
                self.menu = MenuScreen()
            elif ev.key == pygame.K_i and gl and gl.state == "playing":
                gl.thought_visible = not gl.thought_visible
            elif ev.key == pygame.K_RETURN:
                if gl:
                    if gl.state == "intro":
                        gl.state = "playing"
                    elif gl.state == "win":
                        self._next_level()
                    elif gl.state == "fail":
                        self.start_level(self.level_idx)

        if ev.type == pygame.MOUSEBUTTONDOWN:
            mx, my = ev.pos
            gl = self.game_level
            if gl:
                if gl.state == "intro":
                    # Check JOGAR button click
                    bx = GAME_W//2 - 80
                    by = H//2 + 80
                    if pygame.Rect(bx, by, 160, 44).collidepoint(mx, my):
                        gl.state = "playing"
                elif gl.state == "win":
                    # Next button
                    if pygame.Rect(GAME_W//2 - 80, H//2 + 30, 160, 44).collidepoint(mx, my):
                        self._next_level()
                    # Repeat
                    if pygame.Rect(GAME_W//2 - 80, H//2 + 84, 160, 44).collidepoint(mx, my):
                        self.start_level(self.level_idx)
                elif gl.state == "fail":
                    # Repeat
                    if pygame.Rect(GAME_W//2 - 90, H//2 + 20, 180, 44).collidepoint(mx, my):
                        self.start_level(self.level_idx)
                    # Menu
                    if pygame.Rect(GAME_W//2 - 90, H//2 + 74, 180, 44).collidepoint(mx, my):
                        self.screen_state = "menu"
                        self.menu = MenuScreen()

            # Level nav buttons (dynamic)
            if gl and gl.state in ("playing", "intro"):
                n_lvls = len(self.active_levels)
                btn_w = min(104, (GAME_W - 240) // n_lvls)
                btn_x0 = GAME_W - n_lvls * (btn_w + 4) - 4
                for i in range(n_lvls):
                    bx = btn_x0 + i * (btn_w + 4)
                    by = 6
                    if pygame.Rect(bx, by, btn_w, 36).collidepoint(mx, my):
                        self.start_level(i)

        if ev.type == pygame.KEYDOWN:
            # F-key level jump (up to F7 for OSI)
            fkeys = [pygame.K_F1, pygame.K_F2, pygame.K_F3, pygame.K_F4,
                     pygame.K_F5, pygame.K_F6, pygame.K_F7]
            for i, fk in enumerate(fkeys):
                if ev.key == fk and i < len(self.active_levels):
                    self.start_level(i)

    def _next_level(self):
        nxt = self.level_idx + 1
        if nxt >= len(self.active_levels):
            self.screen_state = "complete"
        else:
            # In multiplayer host controls level transitions
            if self.net and self.net.mode == "host":
                self.net.send({"type": "next", "level": nxt})
            self.start_level(nxt)

    def _update_game(self):
        gl = self.game_level
        if not gl:
            return
        gl.update()
        self._net_update(gl)

    def _net_update(self, gl):
        """Send local position and process incoming network messages."""
        net = self.net
        if not net or net.status != "connected":
            return

        # Send own position at ~20 Hz
        now = pygame.time.get_ticks()
        if now - self._net_send_t >= 50:
            pl = gl.player
            net.send({
                "type":   "pos",
                "x":      round(pl.x, 1),
                "y":      round(pl.y, 1),
                "facing": pl.facing,
                "frame":  pl.anim_frame,
            })
            self._net_send_t = now

        # Broadcast win/fail once
        if gl.state == "win" and not getattr(gl, "_net_win_sent", False):
            net.send({"type": "win"})
            gl._net_win_sent = True
        elif gl.state == "fail" and not getattr(gl, "_net_fail_sent", False):
            net.send({"type": "fail"})
            gl._net_fail_sent = True

        # Process incoming
        for msg in net.poll():
            t = msg.get("type")
            if t == "pos":
                gl.remote_x      = msg.get("x", gl.remote_x)
                gl.remote_y      = msg.get("y", 0)
                gl.remote_facing = msg.get("facing", -1)
                gl.remote_frame  = msg.get("frame", 0)
            elif t == "win":
                # Opponent finished first — we lose
                if gl.state == "playing":
                    opp_char = gl.remote_char
                    opp_msg  = compute_win_msg(gl.data, opp_char)
                    gl.fail_reason = (
                        "Oponente completou o objetivo primeiro!\n" + opp_msg
                    )
                    gl.state = "fail"
            elif t == "fail":
                gl.add_toast("Oponente falhou!", GRAY)
            elif t == "next":
                # Host sent next-level command
                idx = msg.get("level", self.level_idx + 1)
                if idx < len(self.active_levels):
                    self.start_level(idx)
            elif t == "peer_disconnect":
                gl.add_toast("Oponente desconectou!", RED_HAT)
                self.net = None

    def _draw(self):
        if self.screen_state == "menu":
            self.menu.draw(screen)
        elif self.screen_state == "controls":
            if self.controls_scr:
                self.controls_scr.draw(screen)
        elif self.screen_state == "model_select":
            self.model_screen.draw(screen)
        elif self.screen_state == "select":
            self.select.draw(screen)
        elif self.screen_state in ("crear_sala", "entrar_sala"):
            if self.room:
                self.room.draw(screen)
        elif self.screen_state == "game":
            self._draw_game()
        elif self.screen_state == "complete":
            self._draw_complete()

    # ---- Game drawing ----
    def _draw_game(self):
        gl = self.game_level
        if not gl:
            return
        ld = gl.data

        # --- Playfield surface (left portion) ---
        game_surf = pygame.Surface((GAME_W, H))
        gl.draw_playfield(game_surf)

        # --- Header bar ---
        pygame.draw.rect(game_surf, (8, 14, 28), (0, 0, GAME_W, HEADER_H))
        pygame.draw.line(game_surf, CYAN, (0, HEADER_H), (GAME_W, HEADER_H), 1)
        char_label = "WhiteHat" if self.char == "white" else "BlackHat"
        col_label = EMERALD if self.char == "white" else RED_HAT
        title_t = FONT_SM.render(f"Cyber Quest — {char_label}", True, col_label)
        game_surf.blit(title_t, (10, HEADER_H//2 - title_t.get_height()//2))

        # Level nav buttons — dynamic based on active_levels count
        n_lvls = len(self.active_levels)
        btn_w = min(104, (GAME_W - 240) // n_lvls)
        btn_x0 = GAME_W - n_lvls * (btn_w + 4) - 4
        for i, lvd in enumerate(self.active_levels):
            short = lvd["name"].split("—")[-1].strip()[:10]
            bx = btn_x0 + i * (btn_w + 4)
            by = 6
            is_cur = (i == self.level_idx)
            bg = EMERALD if is_cur else (25, 40, 60)
            pygame.draw.rect(game_surf, bg, (bx, by, btn_w, 36), border_radius=6)
            pygame.draw.rect(game_surf, CYAN if is_cur else DARK_GRAY,
                             (bx, by, btn_w, 36), 1, border_radius=6)
            lt = FONT_TINY.render(f"F{i+1} {short}", True, BLACK if is_cur else WHITE)
            game_surf.blit(lt, (bx + btn_w // 2 - lt.get_width() // 2, by + 18 - lt.get_height() // 2))

        screen.blit(game_surf, (0, 0))

        # --- Side panel ---
        self._draw_panel(ld)

        # --- Overlays ---
        if gl.state == "intro":
            self._draw_intro_overlay(ld)
        elif gl.state == "win":
            self._draw_win_overlay()
        elif gl.state == "fail":
            self._draw_fail_overlay(gl.fail_reason)

    def _draw_panel(self, ld):
        px = GAME_W
        pygame.draw.rect(screen, PANEL_BG, (px, 0, PANEL_W, H))
        pygame.draw.line(screen, CYAN, (px, 0), (px, H), 2)

        y = 12
        # Level name
        lname = FONT_XS.render(ld["name"], True, CYAN)
        screen.blit(lname, (px + 10, y))
        y += lname.get_height() + 8

        pygame.draw.line(screen, (30, 50, 80), (px + 8, y), (px + PANEL_W - 8, y), 1)
        y += 10

        # Tasks header
        char_label = "WhiteHat" if self.char == "white" else "BlackHat"
        th = FONT_XS.render(f"Tarefas — {char_label}:", True, WHITE)
        screen.blit(th, (px + 10, y))
        y += th.get_height() + 6

        tasks = ld["tasks_white"] if self.char == "white" else ld["tasks_black"]
        for task in tasks:
            lines = wrap_text(task, FONT_TINY, PANEL_W - 20)
            for line in lines:
                lt = FONT_TINY.render(line, True, (180, 200, 220))
                screen.blit(lt, (px + 10, y))
                y += lt.get_height() + 2
            y += 4

        pygame.draw.line(screen, (30, 50, 80), (px + 8, y), (px + PANEL_W - 8, y), 1)
        y += 10

        # Thoughts header
        tp = FONT_XS.render("Dicas / Pensamentos:", True, YELLOW)
        screen.blit(tp, (px + 10, y))
        y += tp.get_height() + 6

        gl = self.game_level
        thoughts = ld.get("thoughts_text", [])
        for i, thought in enumerate(thoughts):
            lines = wrap_text(thought, FONT_TINY, PANEL_W - 24)
            active = gl and (gl.thought_idx % max(1, len(thoughts))) == i
            col = EMERALD if active else (120, 160, 180)
            prefix = "▶ " if active else "  "
            for j, line in enumerate(lines):
                disp = (prefix + line) if j == 0 else ("  " + line)
                lt = FONT_TINY.render(disp, True, col)
                screen.blit(lt, (px + 10, y))
                y += lt.get_height() + 2
            y += 3

        pygame.draw.line(screen, (30, 50, 80), (px + 8, y), (px + PANEL_W - 8, y), 1)
        y += 10

        # Lesson
        ll = FONT_XS.render("Lição:", True, ORANGE)
        screen.blit(ll, (px + 10, y))
        y += ll.get_height() + 4
        for line in wrap_text(ld["lesson"], FONT_TINY, PANEL_W - 18):
            lt = FONT_TINY.render(line, True, (220, 200, 160))
            screen.blit(lt, (px + 10, y))
            y += lt.get_height() + 2

        # Controls reminder at bottom
        ctrl_y = H - 88
        pygame.draw.line(screen, (30, 50, 80), (px + 8, ctrl_y - 8), (px + PANEL_W - 8, ctrl_y - 8), 1)
        for i, line in enumerate([
            "Setas / WASD: mover",
            "Espaço/W/↑: pular",
            "I: pensamentos",
            "ESC: menu | F1-F4: nível",
        ]):
            lt = FONT_TINY.render(line, True, GRAY)
            screen.blit(lt, (px + 10, ctrl_y + i * 16))

        # UTFPR badge
        badge_w, badge_h = 130, 28
        pygame.draw.rect(screen, YELLOW,
                         (px + PANEL_W - badge_w - 8, H - badge_h - 8,
                          badge_w, badge_h), border_radius=5)
        bt = FONT_TINY.render("UTFPR-1ºLC", True, BLACK)
        screen.blit(bt, (px + PANEL_W - badge_w - 8 + badge_w//2 - bt.get_width()//2,
                         H - badge_h - 8 + badge_h//2 - bt.get_height()//2))

    def _draw_intro_overlay(self, ld):
        overlay = pygame.Surface((GAME_W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        name_t = FONT_BIG.render(ld["name"], True, EMERALD)
        screen.blit(name_t, (GAME_W//2 - name_t.get_width()//2, H//2 - 120))

        lesson_lines = wrap_text(ld["lesson"], FONT_SM, GAME_W - 80)
        for i, line in enumerate(lesson_lines):
            lt = FONT_SM.render(line, True, WHITE)
            screen.blit(lt, (GAME_W//2 - lt.get_width()//2, H//2 - 50 + i * 32))

        # JOGAR button
        bx = GAME_W//2 - 80
        by = H//2 + 80
        pygame.draw.rect(screen, EMERALD, (bx, by, 160, 44), border_radius=8)
        pygame.draw.rect(screen, WHITE, (bx, by, 160, 44), 2, border_radius=8)
        bt = FONT_MED.render("▶ JOGAR", True, BLACK)
        screen.blit(bt, (bx + 80 - bt.get_width()//2, by + 22 - bt.get_height()//2))

        hint = FONT_XS.render("ou pressione ENTER", True, GRAY)
        screen.blit(hint, (GAME_W//2 - hint.get_width()//2, by + 54))

    def _draw_win_overlay(self):
        gl = self.game_level
        is_mp   = self.net is not None
        is_last = self.level_idx == len(self.active_levels) - 1
        char_col = EMERALD if self.char == "white" else RED_HAT

        overlay = pygame.Surface((GAME_W, H), pygame.SRCALPHA)
        overlay.fill((0, 20, 0, 195))
        screen.blit(overlay, (0, 0))

        # Glow behind title
        draw_glow(screen, char_col, GAME_W // 2, H // 2 - 90, 160, 60)

        # Title
        if is_mp:
            title_txt = "VITÓRIA!" if not is_last else "MISSÃO COMPLETA!"
        else:
            title_txt = "NÍVEL COMPLETO!" if not is_last else "MISSÃO COMPLETA!"
        mt = FONT_BIG.render(title_txt, True, char_col)
        screen.blit(mt, (GAME_W // 2 - mt.get_width() // 2, H // 2 - 118))

        # Contextual achievement line
        if gl:
            achievement = compute_win_msg(gl.data, self.char)
            # Word-wrap if needed
            lines = wrap_text(achievement, FONT_SM, GAME_W - 80)
            for i, line in enumerate(lines):
                lt = FONT_SM.render(line, True, WHITE)
                screen.blit(lt, (GAME_W // 2 - lt.get_width() // 2, H // 2 - 62 + i * 26))

        # Divider
        pygame.draw.line(screen, char_col,
                         (GAME_W // 2 - 180, H // 2 + 10),
                         (GAME_W // 2 + 180, H // 2 + 10), 1)

        # Multiplayer badge
        if is_mp:
            badge = FONT_XS.render("Você completou antes do oponente!", True, YELLOW)
            screen.blit(badge, (GAME_W // 2 - badge.get_width() // 2, H // 2 + 18))

        # Buttons
        bx = GAME_W // 2 - 80
        by = H // 2 + (46 if is_mp else 36)
        pygame.draw.rect(screen, char_col, (bx, by, 160, 44), border_radius=8)
        nt = FONT_SM.render("Próxima fase" if not is_last else "Ver resultado", True, BLACK)
        screen.blit(nt, (bx + 80 - nt.get_width() // 2, by + 22 - nt.get_height() // 2))

        by2 = by + 54
        pygame.draw.rect(screen, GRAY, (bx, by2, 160, 44), border_radius=8)
        rt = FONT_SM.render("Repetir", True, WHITE)
        screen.blit(rt, (bx + 80 - rt.get_width() // 2, by2 + 22 - rt.get_height() // 2))

        hint = FONT_XS.render("ENTER = próxima fase", True, GRAY)
        screen.blit(hint, (GAME_W // 2 - hint.get_width() // 2, by2 + 56))

    def _draw_fail_overlay(self, reason):
        now = pygame.time.get_ticks()
        char = getattr(self, "char", "white")

        # Dark red overlay
        overlay = pygame.Surface((GAME_W, H), pygame.SRCALPHA)
        overlay.fill((30, 0, 0, 200))
        screen.blit(overlay, (0, 0))

        # Static / glitch lines
        for _ in range(18):
            import random
            gy = random.randint(0, H)
            ga = random.randint(20, 80)
            gw = random.randint(40, GAME_W)
            gx = random.randint(0, GAME_W - gw)
            gl2 = pygame.Surface((gw, 3), pygame.SRCALPHA)
            gl2.fill((255, 20, 20, ga))
            screen.blit(gl2, (gx, gy))

        # GAME OVER — retro flicker
        flicker = int(200 + 55 * math.sin(now / 80))
        go_col = (255, flicker // 4, flicker // 4)
        go_shadow = FONT_BIG.render("GAME  OVER", True, (80, 0, 0))
        go_text   = FONT_BIG.render("GAME  OVER", True, go_col)
        gx2 = GAME_W // 2 - go_text.get_width() // 2
        screen.blit(go_shadow, (gx2 + 4, H // 2 - 154))
        screen.blit(go_text,   (gx2,     H // 2 - 158))
        draw_glow(screen, RED_HAT, GAME_W // 2, H // 2 - 140, 140, 50)

        # Fallen character (rotated 90°)
        fallen = pygame.Surface((PH + 20, PW + 20), pygame.SRCALPHA)
        draw_player(fallen, 10, 10, char, 1, 0)
        rotated = pygame.transform.rotate(fallen, 90)
        screen.blit(rotated, (GAME_W // 2 - rotated.get_width() // 2, H // 2 - 100))

        # Reason
        lines = wrap_text(reason, FONT_SM, GAME_W - 100)
        for i, line in enumerate(lines):
            lt = FONT_SM.render(line, True, (255, 180, 180))
            screen.blit(lt, (GAME_W // 2 - lt.get_width() // 2, H // 2 - 20 + i * 28))

        # Buttons
        bx = GAME_W // 2 - 110
        by = H // 2 + 60
        # Repetir
        pygame.draw.rect(screen, (180, 40, 40), (bx, by, 200, 46), border_radius=8)
        pygame.draw.rect(screen, RED_HAT, (bx, by, 200, 46), 2, border_radius=8)
        rt = FONT_SM.render("▶  Repetir nível", True, WHITE)
        screen.blit(rt, (bx + 100 - rt.get_width() // 2, by + 23 - rt.get_height() // 2))
        # Menu
        by2 = by + 58
        pygame.draw.rect(screen, (40, 40, 60), (bx, by2, 200, 46), border_radius=8)
        pygame.draw.rect(screen, GRAY, (bx, by2, 200, 46), 2, border_radius=8)
        mt2 = FONT_SM.render("⬅  Menu", True, WHITE)
        screen.blit(mt2, (bx + 100 - mt2.get_width() // 2, by2 + 23 - mt2.get_height() // 2))

    def _draw_complete(self):
        screen.fill(DARK_BG)
        if self.char == "white":
            title = FONT_BIG.render("MISSAO COMPLETA!", True, EMERALD)
            sub_t = FONT_MED.render("A rede foi protegida!", True, CYAN)
        else:
            title = FONT_BIG.render("INVASAO TOTAL!", True, RED_HAT)
            sub_t = FONT_MED.render("Todas as camadas foram comprometidas!", True, ORANGE)

        screen.blit(title, (W//2 - title.get_width()//2, H//2 - 130))
        screen.blit(sub_t, (W//2 - sub_t.get_width()//2, H//2 - 60))

        n = len(self.active_levels)
        model_name = "OSI (7 camadas)" if self.model_choice == "osi" else "TCP/IP (4 camadas)"
        desc = FONT_SM.render(f"Você completou todos os {n} níveis — Modelo {model_name}!", True, WHITE)
        screen.blit(desc, (W//2 - desc.get_width()//2, H//2 - 10))

        # Trophy / skull
        icon = "MISSAO CUMPRIDA" if self.char == "white" else "FIM DO JOGO"
        icon_t = FONT_BIG.render(icon, True, YELLOW)
        screen.blit(icon_t, (W//2 - icon_t.get_width()//2, H//2 + 50))

        # Replay button
        bx = W//2 - 110
        by = H//2 + 130
        pygame.draw.rect(screen, EMERALD, (bx, by, 220, 52), border_radius=10)
        pygame.draw.rect(screen, WHITE, (bx, by, 220, 52), 2, border_radius=10)
        bt = FONT_MED.render("Jogar de novo", True, BLACK)
        screen.blit(bt, (bx + 110 - bt.get_width()//2, by + 26 - bt.get_height()//2))

        hint = FONT_XS.render("Clique ou ENTER para voltar ao menu", True, GRAY)
        screen.blit(hint, (W//2 - hint.get_width()//2, by + 66))

        # UTFPR badge
        badge_w, badge_h = 140, 36
        pygame.draw.rect(screen, YELLOW, (W - badge_w - 12, H - badge_h - 12,
                                          badge_w, badge_h), border_radius=6)
        bt2 = FONT_XS.render("UTFPR-1ºLC", True, BLACK)
        screen.blit(bt2, (W - badge_w - 12 + badge_w//2 - bt2.get_width()//2,
                          H - badge_h - 12 + badge_h//2 - bt2.get_height()//2))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    game = Game()
    game.run()
