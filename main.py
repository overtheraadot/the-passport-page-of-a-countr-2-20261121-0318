#!/usr/bin/env python3
"""The Passport Page of a Country That Isn't There.

Draws one uncaptioned open passport spread for the invented alpine
Republic of Tarnovia (capital Velgrad) and writes it to /output/entry.png.

Pure Python standard library only: no PIL, no third-party imports at all.
The rasteriser, the bitmap font and the PNG encoder are all implemented
here by hand, so the program runs in a bare sandbox. No network, no
external fonts, no randomness: the output is fully deterministic.
"""

import hashlib
import math
import os
import struct
import zlib

W, H = 1024, 1024
OUT = "/output/entry.png"

PAPER = (247, 243, 232)
INK = (28, 32, 48)
INK_SOFT = (70, 74, 96)
RULE = (120, 110, 88)
GREEN = (31, 74, 54)
GOLD = (150, 112, 38)
RED = (158, 32, 32)
BLUE = (28, 62, 140)
PURPLE = (96, 44, 120)
NOTE_BLUE = (60, 60, 110)


# ---------------------------------------------------------------- canvas

class Canvas:
    """An RGB pixel buffer with small drawing primitives."""

    def __init__(self, w, h, bg=(0, 0, 0)):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def _idx(self, x, y):
        return (y * self.w + x) * 3

    def set_px(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = self._idx(x, y)
            self.buf[i] = color[0]
            self.buf[i + 1] = color[1]
            self.buf[i + 2] = color[2]

    def fill_rect(self, x0, y0, x1, y1, color):
        x0 = max(0, int(x0))
        y0 = max(0, int(y0))
        x1 = min(self.w, int(x1))
        y1 = min(self.h, int(y1))
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        for y in range(y0, y1):
            i = self._idx(x0, y)
            self.buf[i:i + len(row)] = row

    def hline(self, x0, x1, y, color, width=1):
        half = width // 2
        for dy in range(-half, width - half):
            self.fill_rect(x0, y + dy, x1 + 1, y + dy + 1, color)

    def vline(self, x, y0, y1, color, width=1):
        half = width // 2
        for dx in range(-half, width - half):
            self.fill_rect(x + dx, y0, x + dx + 1, y1 + 1, color)

    def _brush(self, x, y, color, width):
        r = width // 2
        if width <= 1:
            self.set_px(x, y, color)
        else:
            self.fill_rect(x - r, y - r, x + r + 1, y + r + 1, color)

    def line(self, x0, y0, x1, y1, color, width=1):
        """Bresenham line with a square brush."""
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self._brush(x0, y0, color, width)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def polyline(self, pts, color, width=1, closed=False):
        n = len(pts)
        if n < 2:
            return
        for i in range(n - 1):
            self.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                      color, width)
        if closed:
            self.line(pts[-1][0], pts[-1][1], pts[0][0], pts[0][1],
                      color, width)

    def fill_polygon(self, pts, color):
        """Scanline polygon fill."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y_min = max(0, int(math.ceil(min(ys))))
        y_max = min(self.h - 1, int(math.floor(max(ys))))
        n = len(pts)
        for y in range(y_min, y_max + 1):
            xs = []
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    if y1 != y0:
                        t = (y + 0.5 - y0) / (y1 - y0)
                        xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.fill_rect(int(math.ceil(xs[i])),
                               y, int(math.floor(xs[i + 1])) + 1, y + 1,
                               color)

    def fill_ellipse(self, cx, cy, rx, ry, color):
        rx = float(rx)
        ry = float(ry)
        for y in range(int(cy - ry), int(cy + ry) + 1):
            t = (y + 0.5 - cy) / ry
            if abs(t) >= 1.0:
                continue
            hw = rx * math.sqrt(1.0 - t * t)
            self.fill_rect(int(cx - hw), y, int(cx + hw) + 1, y + 1, color)

    def ellipse_outline(self, cx, cy, rx, ry, color, width=1):
        pts = []
        steps = max(48, int(2 * math.pi * max(rx, ry)))
        for i in range(steps + 1):
            a = 2 * math.pi * i / steps
            pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
        self.polyline(pts, color, width, closed=True)

    def arc_points(self, cx, cy, rx, ry, a0_deg, a1_deg, step=4):
        pts = []
        a = a0_deg
        while a <= a1_deg:
            r = math.radians(a)
            pts.append((cx + rx * math.cos(r), cy + ry * math.sin(r)))
            a += step
        r = math.radians(a1_deg)
        pts.append((cx + rx * math.cos(r), cy + ry * math.sin(r)))
        return pts

    def rect_outline(self, x0, y0, x1, y1, color, width=1):
        self.hline(x0, x1, y0, color, width)
        self.hline(x0, x1, y1, color, width)
        self.vline(x0, y0, y1, color, width)
        self.vline(x1, y0, y1, color, width)


# ------------------------------------------------------------- bitmap font
# Hand-drawn 5x7 glyphs, one string per row, "1" = ink.

_FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "a": ("00000", "00000", "01110", "00001", "01111", "10001", "01111"),
    "b": ("10000", "10000", "10110", "11001", "10001", "10001", "11110"),
    "c": ("00000", "00000", "01110", "10000", "10000", "10001", "01110"),
    "d": ("00001", "00001", "01101", "10011", "10001", "10001", "01111"),
    "e": ("00000", "00000", "01110", "10001", "11111", "10000", "01110"),
    "f": ("00110", "01001", "01000", "11110", "01000", "01000", "01000"),
    "g": ("00000", "01111", "10001", "10001", "01111", "00001", "01110"),
    "h": ("10000", "10000", "10110", "11001", "10001", "10001", "10001"),
    "i": ("00100", "00000", "01100", "00100", "00100", "00100", "01110"),
    "j": ("00010", "00000", "00110", "00010", "00010", "10010", "01100"),
    "k": ("10000", "10000", "10010", "10100", "11000", "10100", "10010"),
    "l": ("01100", "00100", "00100", "00100", "00100", "00100", "01110"),
    "m": ("00000", "00000", "11010", "10101", "10101", "10101", "10101"),
    "n": ("00000", "00000", "10110", "11001", "10001", "10001", "10001"),
    "o": ("00000", "00000", "01110", "10001", "10001", "10001", "01110"),
    "p": ("00000", "00000", "11110", "10001", "11110", "10000", "10000"),
    "q": ("00000", "00000", "01101", "10011", "01111", "00001", "00001"),
    "r": ("00000", "00000", "10110", "11001", "10000", "10000", "10000"),
    "s": ("00000", "00000", "01111", "10000", "01110", "00001", "11110"),
    "t": ("01000", "01000", "11100", "01000", "01000", "01001", "00110"),
    "u": ("00000", "00000", "10001", "10001", "10001", "10011", "01101"),
    "v": ("00000", "00000", "10001", "10001", "10001", "01010", "00100"),
    "w": ("00000", "00000", "10001", "10101", "10101", "10101", "01010"),
    "x": ("00000", "00000", "10001", "01010", "00100", "01010", "10001"),
    "y": ("00000", "00000", "10001", "10001", "01111", "00001", "01110"),
    "z": ("00000", "00000", "11111", "00010", "00100", "01000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    ";": ("00000", "01100", "01100", "00000", "01100", "00100", "01000"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "<": ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    ">": ("01000", "00100", "00010", "00001", "00010", "00100", "01000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '"': ("01010", "01010", "00000", "00000", "00000", "00000", "00000"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "%": ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "·": ("00000", "00000", "00000", "01100", "01100", "00000", "00000"),
}

# Aliases for lookalike punctuation.
_FONT["—"] = _FONT["-"]
_FONT["–"] = _FONT["-"]
_FONT["’"] = _FONT["'"]
_FONT["‘"] = _FONT["'"]
_FONT["•"] = _FONT["·"]
_FONT["«"] = _FONT['"']
_FONT["»"] = _FONT['"']

_BLANK = ("00000",) * 7


def text_width(s, size=14, spacing=0, sx=None):
    """Pixel width of s at the given size."""
    if sx is None:
        sx = size / 8.0
    if not s:
        return 0
    return len(s) * 5 * sx + (len(s) - 1) * (sx + spacing)


def draw_text(cv, x, y, s, size=14, color=INK, anchor="la", spacing=0,
              sx=None, sy=None):
    """Draw s with the bitmap font. (x, y) is the top-left for anchor la,
    the top-centre for ma, the top-right for ra."""
    base = size / 8.0
    if sx is None:
        sx = base
    if sy is None:
        sy = base
    w = text_width(s, size, spacing, sx)
    if anchor == "ma":
        x = x - w / 2.0
    elif anchor == "ra":
        x = x - w
    cx = float(x)
    for ch in s:
        glyph = _FONT.get(ch, _BLANK)
        for r in range(7):
            row = glyph[r]
            y0 = int(round(y + r * sy))
            y1 = int(round(y + (r + 1) * sy))
            for c in range(5):
                if row[c] == "1":
                    x0 = int(round(cx + c * sx))
                    x1 = int(round(cx + (c + 1) * sx))
                    cv.fill_rect(x0, y0, max(x1, x0 + 1), max(y1, y0 + 1),
                                 color)
        cx += 5 * sx + sx + spacing


def centred(cv, cx, y, s, size=14, color=INK, spacing=0):
    draw_text(cv, cx, y, s, size=size, color=color, anchor="ma",
              spacing=spacing)


def rule(cv, x0, x1, y, color=RULE, width=1):
    cv.hline(x0, x1, y, color, width)


def field(cv, x, y, label, value, vsize=17, label_size=11):
    # Labels use a condensed horizontal scale so long bilingual labels
    # never collide with the next field.
    draw_text(cv, x, y, label, size=label_size, color=INK_SOFT, sx=1.0)
    draw_text(cv, x, y + 14, value, size=vsize, color=INK)


# ------------------------------------------------------------------- ICAO

def check_digit(s):
    """ICAO 9303 check digit (weights 7, 3, 1)."""
    vals = {}
    for i, c in enumerate("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        vals[c] = i
    vals["<"] = 0
    total = 0
    for i, ch in enumerate(s):
        total += vals[ch] * (7, 3, 1)[i % 3]
    return str(total % 10)


def mrz_lines():
    line1 = "P<TNO" + "KOVAC<<ELENA<MARIA"
    line1 = line1 + "<" * (44 - len(line1))
    doc = "TN4829137"
    dob = "880407"
    exp = "340312"
    pers = "<" * 14
    line2 = (
        doc + check_digit(doc)
        + "TNO"
        + dob + check_digit(dob)
        + "F"
        + exp + check_digit(exp)
        + pers + check_digit(pers)
    )
    line2 += check_digit(line2)
    assert len(line1) == 44 and len(line2) == 44
    return line1, line2


# ------------------------------------------------------------------ emblem

def mountain_emblem(cv, cx, cy, s, fill=GREEN):
    """Coat of arms: three peaks under a sun, inside a thin ring."""
    r = s
    cv.ellipse_outline(cx, cy, r, r, fill, 2)
    cv.ellipse_outline(cx, cy, r - 4, r - 4, fill, 1)
    cv.fill_ellipse(cx, cy - r + 14, 5, 5, GOLD)  # sun
    base = cy + r * 0.55
    cv.fill_polygon([(cx - r + 8, base), (cx - r * 0.28, cy - r * 0.28),
                     (cx - 2, base)], fill)
    cv.fill_polygon([(cx - r * 0.42, base), (cx, cy - r * 0.62),
                     (cx + r * 0.42, base)], fill)
    cv.fill_polygon([(cx + 2, base), (cx + r * 0.28, cy - r * 0.28),
                     (cx + r - 8, base)], fill)
    # Snow caps
    cv.fill_polygon([(cx - r * 0.28 - 4, cy - r * 0.28 + 7),
                     (cx - r * 0.28, cy - r * 0.28),
                     (cx - r * 0.28 + 4, cy - r * 0.28 + 7)], PAPER)
    cv.fill_polygon([(cx - 5, cy - r * 0.62 + 8), (cx, cy - r * 0.62),
                     (cx + 5, cy - r * 0.62 + 8)], PAPER)
    cv.fill_polygon([(cx + r * 0.28 - 4, cy - r * 0.28 + 7),
                     (cx + r * 0.28, cy - r * 0.28),
                     (cx + r * 0.28 + 4, cy - r * 0.28 + 7)], PAPER)


# ---------------------------------------------------------------- portrait

def draw_portrait(cv, box):
    """Stylised dignified profile bust, drawn with primitives only."""
    x0, y0, x1, y1 = box
    # Guilloche-style background
    for i in range(0, (x1 - x0), 7):
        cv.line(x0 + i, y0, x0 + i + 14, y1, (214, 206, 186), 1)
    cv.rect_outline(x0, y0, x1, y1, INK, 2)
    cx = (x0 + x1) // 2
    skin = (214, 178, 140)
    skin_dark = (196, 158, 120)
    hair = (58, 44, 34)
    coat = (44, 62, 74)
    # Shoulders / coat
    cv.fill_polygon([(cx - 52, y1), (cx - 46, y1 - 58), (cx - 18, y1 - 74),
                     (cx + 18, y1 - 74), (cx + 46, y1 - 58),
                     (cx + 52, y1)], coat)
    # Collar and shirt
    cv.fill_polygon([(cx - 18, y1 - 74), (cx, y1 - 52), (cx + 18, y1 - 74)],
                    (240, 236, 224))
    cv.fill_polygon([(cx - 8, y1 - 66), (cx, y1 - 52), (cx + 8, y1 - 66)],
                    (120, 40, 40))
    # Neck
    cv.fill_rect(cx - 13, y1 - 96, cx + 13, y1 - 68, skin_dark)
    # Head, profile facing left: cranium + jaw + nose
    cv.fill_ellipse(cx - 2, y1 - 132, 32, 36, skin)
    cv.fill_polygon([(cx - 34, y1 - 138), (cx - 44, y1 - 122),
                     (cx - 32, y1 - 116)], skin)  # nose
    cv.fill_polygon([(cx - 34, y1 - 116), (cx - 26, y1 - 104),
                     (cx - 16, y1 - 104)], skin)  # chin / jaw
    # Eye (closed, dignified) and brow
    cv.line(cx - 26, y1 - 138, cx - 12, y1 - 138, INK, 2)
    cv.line(cx - 27, y1 - 144, cx - 11, y1 - 145, hair, 2)
    # Ear
    cv.fill_ellipse(cx + 21, y1 - 130, 5, 8, skin_dark)
    # Hair: swept back bun (pie-slice fan over the cranium + bun)
    ccx, ccy, rx, ry = cx - 2, y1 - 144, 34, 28
    fan = [(ccx, ccy)] + cv.arc_points(ccx, ccy, rx, ry, 90, 350)
    cv.fill_polygon(fan, hair)
    cv.fill_ellipse(cx + 20, y1 - 162, 14, 14, hair)
    cv.polyline(cv.arc_points(ccx, ccy, rx, ry, 100, 340), (30, 22, 16), 2)
    # Small earring
    cv.fill_ellipse(cx + 20, y1 - 118, 3, 3, GOLD)
    # Photo corner marks
    for (mx, my, dx, dy) in [(x0, y0, 1, 1), (x1, y0, -1, 1),
                             (x0, y1, 1, -1), (x1, y1, -1, -1)]:
        cv.line(mx, my + 10 * dy, mx, my, INK, 2)
        cv.line(mx, my, mx + 10 * dx, my, INK, 2)


# ------------------------------------------------------------------ stamps

class Stamp:
    """A rubber stamp drawn on its own RGBA layer, pasted rotated."""

    def __init__(self, w, h, color):
        self.w = w + 40
        self.h = h + 40
        self.px = bytearray(self.w * self.h * 4)
        self.color = color

    def set_px(self, x, y, color, alpha):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 4
            self.px[i] = color[0]
            self.px[i + 1] = color[1]
            self.px[i + 2] = color[2]
            self.px[i + 3] = alpha

    def fill_rect_a(self, x0, y0, x1, y1, color, alpha):
        for y in range(max(0, y0), min(self.h, y1)):
            for x in range(max(0, x0), min(self.w, x1)):
                self.set_px(x, y, color, alpha)

    def line_a(self, x0, y0, x1, y1, color, alpha, width=1):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            r = width // 2
            self.fill_rect_a(x0 - r, y0 - r, x0 + r + 1, y0 + r + 1,
                             color, alpha)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def ellipse_outline_a(self, cx, cy, rx, ry, color, alpha, width=1):
        steps = max(48, int(2 * math.pi * max(rx, ry)))
        prev = None
        for i in range(steps + 1):
            a = 2 * math.pi * i / steps
            pt = (int(cx + rx * math.cos(a)), int(cy + ry * math.sin(a)))
            if prev is not None:
                self.line_a(prev[0], prev[1], pt[0], pt[1], color, alpha,
                            width)
            prev = pt

    def text_a(self, x, y, s, size, color, alpha, anchor="la"):
        sx = size / 8.0
        sy = sx
        w = text_width(s, size, 0, sx)
        if anchor == "ma":
            x = x - w / 2.0
        elif anchor == "ra":
            x = x - w
        cx = float(x)
        for ch in s:
            glyph = _FONT.get(ch, _BLANK)
            for r in range(7):
                row = glyph[r]
                y0 = int(round(y + r * sy))
                y1 = int(round(y + (r + 1) * sy))
                for c in range(5):
                    if row[c] == "1":
                        x0 = int(round(cx + c * sx))
                        x1 = int(round(cx + (c + 1) * sx))
                        self.fill_rect_a(x0, y0, max(x1, x0 + 1),
                                         max(y1, y0 + 1), color, alpha)
            cx += 6 * sx


def make_stamp(text_lines, w, h, color, shape="rect", size=15, border=3):
    """Build a stamp layer with a border and centred lines."""
    st = Stamp(w, h, color)
    if shape == "oval":
        st.ellipse_outline_a(20 + w / 2, 20 + h / 2, w / 2, h / 2,
                             color, 235, border)
        st.ellipse_outline_a(20 + w / 2, 20 + h / 2, w / 2 - 6, h / 2 - 6,
                             color, 235, 1)
    else:
        st.fill_rect_a(20, 20, 20 + w, 20 + h, color, 0)  # no-op, keep clear
        # Border: two nested rectangles.
        for (bx0, by0, bx1, by1, al, wd) in [
                (20, 20, 20 + w, 20 + h, 235, border),
                (25, 25, 15 + w, 15 + h, 200, 1)]:
            st.line_a(bx0, by0, bx1, by0, color, al, wd)
            st.line_a(bx0, by1, bx1, by1, color, al, wd)
            st.line_a(bx0, by0, bx0, by1, color, al, wd)
            st.line_a(bx1, by0, bx1, by1, color, al, wd)
    cx, cy = st.w // 2, st.h // 2
    line_h = size + 4
    y = cy - (len(text_lines) * line_h) // 2 + 2
    for line in text_lines:
        st.text_a(cx, y, line, size, color, 235, anchor="ma")
        y += line_h
    return st


def paste_stamp(cv, stamp, x, y, angle_deg):
    """Paste the stamp rotated by angle_deg, top-left of the rotated
    bounding box landing at (x, y). Nearest-neighbour sampling."""
    th = math.radians(angle_deg)
    cos_t, sin_t = math.cos(th), math.sin(th)
    w, h = stamp.w, stamp.h
    corners = [(-w / 2, -h / 2), (w / 2, -h / 2),
               (w / 2, h / 2), (-w / 2, h / 2)]
    rot = [(cx * cos_t - cy * sin_t, cx * sin_t + cy * cos_t)
           for cx, cy in corners]
    min_x = min(p[0] for p in rot)
    max_x = max(p[0] for p in rot)
    min_y = min(p[1] for p in rot)
    max_y = max(p[1] for p in rot)
    dw = int(math.ceil(max_x - min_x))
    dh = int(math.ceil(max_y - min_y))
    ccx, ccy = w / 2.0, h / 2.0
    for dy in range(dh):
        for dx in range(dw):
            # Destination offset from rotated bbox centre.
            rx = (x + dx) - (x + dw / 2.0)
            ry = (y + dy) - (y + dh / 2.0)
            # Inverse rotation back into stamp space.
            sx = rx * cos_t + ry * sin_t + ccx
            sy = -rx * sin_t + ry * cos_t + ccy
            ix, iy = int(sx), int(sy)
            if 0 <= ix < w and 0 <= iy < h:
                i = (iy * w + ix) * 4
                a = stamp.px[i + 3]
                if a == 0:
                    continue
                tx, ty = x + dx, y + dy
                if 0 <= tx < cv.w and 0 <= ty < cv.h:
                    j = cv._idx(tx, ty)
                    if a >= 255:
                        cv.buf[j] = stamp.px[i]
                        cv.buf[j + 1] = stamp.px[i + 1]
                        cv.buf[j + 2] = stamp.px[i + 2]
                    else:
                        cv.buf[j] = (stamp.px[i] * a
                                     + cv.buf[j] * (255 - a)) // 255
                        cv.buf[j + 1] = (stamp.px[i + 1] * a
                                         + cv.buf[j + 1] * (255 - a)) // 255
                        cv.buf[j + 2] = (stamp.px[i + 2] * a
                                         + cv.buf[j + 2] * (255 - a)) // 255


# -------------------------------------------------------------------- PNG

def png_bytes(w, h, buf):
    def chunk(typ, data):
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))

    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)  # filter: None
        raw += buf[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


# ------------------------------------------------------------------- build

def build():
    cv = Canvas(W, H, PAPER)

    # ---- Spread frame -------------------------------------------------
    cv.rect_outline(16, 16, W - 17, H - 17, RULE, 2)
    cv.rect_outline(22, 22, W - 23, H - 23, (170, 158, 128), 1)
    # Centre fold
    for y in range(30, H - 30, 12):
        cv.vline(512, y, y + 6, (150, 138, 108), 1)
    # Page numbers
    draw_text(cv, 40, H - 46, "4", size=12, color=INK_SOFT)
    draw_text(cv, W - 40, H - 46, "5", size=12, color=INK_SOFT, anchor="ra")

    # ================= LEFT PAGE: DATA PAGE ============================
    mountain_emblem(cv, 268, 92, 34)
    centred(cv, 268, 132, "REPUBLIC OF TARNOVIA", size=25, color=GREEN,
            spacing=2)
    centred(cv, 268, 162, "REPUBLIKA TARNOVIJA", size=12, color=INK_SOFT,
            spacing=3)
    centred(cv, 268, 182, "PASSPORT", size=19, color=INK, spacing=6)
    centred(cv, 268, 206, "PASPORT  ·  PASSEPORT", size=11, color=INK_SOFT,
            spacing=2)
    rule(cv, 48, 488, 228, GREEN, 2)

    # Top row: type / country code / passport number
    field(cv, 48, 244, "TYPE / TIP", "P", vsize=17)
    field(cv, 128, 244, "CODE / KOD", "TNO", vsize=17)
    field(cv, 300, 244, "PASSPORT No. / BROJ PASOSA", "TN 4829137",
          vsize=17)

    # Portrait
    draw_portrait(cv, (48, 300, 208, 492))
    draw_text(cv, 48, 500, "SIGNATURE / POTPIS", size=11, color=INK_SOFT,
              sx=1.0)
    draw_text(cv, 48, 514, "Elena M. Kovac", size=16, color=INK)

    # Data fields, right of portrait
    fx = 232
    field(cv, fx, 300, "SURNAME / PREZIME", "KOVAC", vsize=18)
    field(cv, fx, 344, "GIVEN NAMES / IME", "ELENA MARIA", vsize=18)
    field(cv, fx, 388, "NATIONALITY / DRZAVLJANSTVO", "TARNOVIAN",
          vsize=18)
    field(cv, fx, 432, "DATE OF BIRTH / DATUM RODJENJA", "07 APR 1988",
          vsize=18)
    field(cv, fx, 476, "PLACE OF BIRTH / MJESTO RODJENJA", "VELGRAD",
          vsize=18)

    # Lower data row
    field(cv, 48, 556, "SEX / SPOL", "F", vsize=17)
    field(cv, 128, 556, "DATE OF ISSUE / DATUM IZDAVANJA", "12 MAR 2024",
          vsize=17)
    field(cv, 330, 556, "DATE OF EXPIRY / VAZI DO", "12 MAR 2034",
          vsize=17)
    field(cv, 48, 600, "AUTHORITY / ORGAN",
          "MINISTRY OF THE INTERIOR - VELGRAD", vsize=16)
    field(cv, 48, 644, "HOLDER'S ADDRESS / ADRESA",
          "14 ULICA PLANINA, VELGRAD", vsize=16)

    # Personal number / height, small print (size 9: stays inside the page)
    draw_text(cv, 48, 700,
              "PERSONAL No.  880407-512  ·  HEIGHT  168 cm  ·  EYES  BROWN",
              size=9, color=INK_SOFT)
    draw_text(cv, 48, 720,
              "THIS PASSPORT REMAINS THE PROPERTY OF THE REPUBLIC OF "
              "TARNOVIA.",
              size=9, color=INK_SOFT)

    # MRZ
    rule(cv, 48, 488, 756, INK, 1)
    l1, l2 = mrz_lines()
    draw_text(cv, 48, 768, l1, size=17, color=INK, sx=1.55, sy=2.4)
    draw_text(cv, 48, 792, l2, size=17, color=INK, sx=1.55, sy=2.4)
    draw_text(cv, 48, 824, "P<TNOKOVAC<<ELENA<MARIA - MACHINE READABLE ZONE",
              size=10, color=INK_SOFT)

    # Small mountain watermark, in the clear strip between the small
    # print and the MRZ rule.
    mountain_emblem(cv, 462, 744, 10)

    # ================= RIGHT PAGE: VISAS & STAMPS ======================
    centred(cv, 756, 52, "VISAS", size=20, color=INK, spacing=6)
    centred(cv, 756, 78, "VIZE  ·  VISAS", size=11, color=INK_SOFT,
            spacing=2)
    rule(cv, 536, 976, 102, GREEN, 2)

    # Stamps - all dated AFTER the passport issue date 12 MAR 2024.
    paste_stamp(cv, make_stamp(
        ["ALPENMARK", "ENTRY - 14 JUN 2024", "BORDER POST KLAUSEN"],
        260, 84, BLUE, shape="oval", size=15), 560, 130, -7)
    paste_stamp(cv, make_stamp(
        ["ALPENMARK", "EXIT - 28 JUN 2024", "BORDER POST KLAUSEN"],
        260, 84, BLUE, shape="oval", size=15), 690, 250, 6)
    paste_stamp(cv, make_stamp(
        ["DRAVSKA", "ENTRY - 03 SEP 2025", "DRAVSKA BORDER"],
        250, 84, RED, shape="rect", size=15), 556, 380, 5)
    paste_stamp(cv, make_stamp(
        ["DRAVSKA", "EXIT - 19 SEP 2025", "DRAVSKA BORDER"],
        250, 84, RED, shape="rect", size=15), 700, 500, -6)
    paste_stamp(cv, make_stamp(
        ["VELGRAD", "DEPARTURE - 02 FEB 2026", "TARNOVIA"],
        250, 78, PURPLE, shape="oval", size=14), 566, 620, -4)

    # Fee stamp, small, overlapping the visa-condition box edge
    paste_stamp(cv, make_stamp(
        ["FEE PAID", "40 TVD"],
        120, 56, GREEN, shape="rect", size=14), 830, 760, 8)

    # Visa condition box - the telling paperwork detail
    cv.rect_outline(556, 760, 976, 884, INK, 2)
    cv.rect_outline(560, 764, 972, 880, RULE, 1)
    draw_text(cv, 576, 776, "VISA CONDITION / UVJET VIZE", size=12,
              color=INK_SOFT, sx=1.0)
    draw_text(cv, 576, 798, "HOLDER MAY NOT CROSS THE", size=16, color=RED)
    draw_text(cv, 576, 820, "VELGRAD PASS NOV-MAR", size=16, color=RED)
    draw_text(cv, 576, 842, "WITHOUT CHAIN PERMIT.", size=16, color=RED)
    draw_text(cv, 576, 864, "SEE PAGE 12 FOR MOUNTAIN PASS REGULATIONS.",
              size=11, color=INK_SOFT)

    # Handwritten-style travel note, bottom of right page (condensed
    # horizontally so both lines stay inside the page).
    draw_text(cv, 556, 908,
              "Holder travelled by rail: Velgrad - Klausen - Dravska.",
              size=12, color=NOTE_BLUE, sx=1.0, sy=1.5)
    draw_text(cv, 556, 928,
              "No visa required for stays under 90 days (Alpenmark, Dravska).",
              size=12, color=NOTE_BLUE, sx=1.0, sy=1.5)

    # Faint mountain watermark on the right page
    mountain_emblem(cv, 920, 160, 22)

    os.makedirs("/output", exist_ok=True)
    data = png_bytes(W, H, cv.buf)
    with open(OUT, "wb") as f:
        f.write(data)
    return OUT


if __name__ == "__main__":
    path = build()
    data = open(path, "rb").read()
    print(path, len(data), "bytes")
    print("sha256:", hashlib.sha256(data).hexdigest())
    w, h = struct.unpack(">II", data[16:24])
    print("size:", (w, h))
