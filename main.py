#!/usr/bin/env python3
"""The Passport Page of a Country That Isn't There.

Draws one uncaptioned open passport spread for the invented alpine
Republic of Tarnovia (capital Velgrad) and writes it to /output/entry.png.

Pure local drawing with PIL only. No network, no external fonts, no
randomness: the output is fully deterministic.
"""

import hashlib
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1024, 1024
OUT = "/output/entry.png"

PAPER = (247, 243, 232)
PAPER_DARK = (238, 232, 214)
INK = (28, 32, 48)
INK_SOFT = (70, 74, 96)
RULE = (120, 110, 88)
GREEN = (31, 74, 54)
GOLD = (150, 112, 38)
RED = (158, 32, 32)
BLUE = (28, 62, 140)
PURPLE = (96, 44, 120)


def font(size):
    return ImageFont.load_default(size=size)


def text(draw, xy, s, size=14, fill=INK, anchor="la", spacing=None):
    f = font(size)
    if spacing is None:
        draw.text(xy, s, font=f, fill=fill, anchor=anchor)
    else:
        # Manual letter-spacing for headers.
        x, y = xy
        for ch in s:
            draw.text((x, y), ch, font=f, fill=fill)
            x += draw.textlength(ch, font=f) + spacing
    return f


def text_w(draw, s, size=14):
    return draw.textlength(s, font=font(size))


def centred(draw, cx, y, s, size=14, fill=INK, spacing=None):
    if spacing is None:
        draw.text((cx, y), s, font=font(size), fill=fill, anchor="ma")
    else:
        w = sum(draw.textlength(c, font=font(size)) + spacing for c in s) - spacing
        text(draw, (cx - w / 2, y), s, size=size, fill=fill, spacing=spacing)


def rule(draw, x0, x1, y, fill=RULE, width=1):
    draw.line([(x0, y), (x1, y)], fill=fill, width=width)


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


def mountain_emblem(draw, cx, cy, s, fill=GREEN):
    """Small coat of arms: three peaks under a sun, inside a thin ring."""
    r = s
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=fill, width=2)
    draw.ellipse([cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4],
                 outline=fill, width=1)
    # Sun
    draw.ellipse([cx - 5, cy - r + 9, cx + 5, cy - r + 19], fill=GOLD)
    # Peaks
    base = cy + r * 0.55
    draw.polygon([(cx - r + 8, base), (cx - r * 0.28, cy - r * 0.28),
                  (cx - 2, base)], fill=fill)
    draw.polygon([(cx - r * 0.42, base), (cx, cy - r * 0.62),
                  (cx + r * 0.42, base)], fill=fill)
    draw.polygon([(cx + 2, base), (cx + r * 0.28, cy - r * 0.28),
                  (cx + r - 8, base)], fill=fill)
    # Snow caps
    draw.polygon([(cx - r * 0.28 - 4, cy - r * 0.28 + 7),
                  (cx - r * 0.28, cy - r * 0.28),
                  (cx - r * 0.28 + 4, cy - r * 0.28 + 7)], fill=PAPER)
    draw.polygon([(cx - 5, cy - r * 0.62 + 8), (cx, cy - r * 0.62),
                  (cx + 5, cy - r * 0.62 + 8)], fill=PAPER)
    draw.polygon([(cx + r * 0.28 - 4, cy - r * 0.28 + 7),
                  (cx + r * 0.28, cy - r * 0.28),
                  (cx + r * 0.28 + 4, cy - r * 0.28 + 7)], fill=PAPER)


def draw_portrait(draw, box):
    """Stylised dignified profile bust, drawn with PIL shapes only."""
    x0, y0, x1, y1 = box
    # Guilloche-style background
    for i in range(0, (x1 - x0), 7):
        draw.line([(x0 + i, y0), (x0 + i + 14, y1)], fill=(214, 206, 186), width=1)
    draw.rectangle(box, outline=INK, width=2)
    cx = (x0 + x1) // 2
    skin = (214, 178, 140)
    skin_dark = (196, 158, 120)
    hair = (58, 44, 34)
    coat = (44, 62, 74)
    # Shoulders / coat
    draw.polygon([(cx - 52, y1), (cx - 46, y1 - 58), (cx - 18, y1 - 74),
                  (cx + 18, y1 - 74), (cx + 46, y1 - 58), (cx + 52, y1)],
                 fill=coat)
    # Collar and shirt
    draw.polygon([(cx - 18, y1 - 74), (cx, y1 - 52), (cx + 18, y1 - 74)],
                 fill=(240, 236, 224))
    draw.polygon([(cx - 8, y1 - 66), (cx, y1 - 52), (cx + 8, y1 - 66)],
                 fill=(120, 40, 40))
    # Neck
    draw.rectangle([cx - 13, y1 - 96, cx + 13, y1 - 68], fill=skin_dark)
    # Head, profile facing left: cranium + jaw + nose
    draw.ellipse([cx - 34, y1 - 168, cx + 30, y1 - 96], fill=skin)
    draw.polygon([(cx - 34, y1 - 138), (cx - 44, y1 - 122),
                  (cx - 32, y1 - 116)], fill=skin)  # nose
    draw.polygon([(cx - 34, y1 - 116), (cx - 26, y1 - 104),
                  (cx - 16, y1 - 104)], fill=skin)  # chin / jaw
    # Eye (closed, dignified) and brow
    draw.line([(cx - 26, y1 - 138), (cx - 12, y1 - 138)], fill=INK, width=2)
    draw.line([(cx - 27, y1 - 144), (cx - 11, y1 - 145)], fill=hair, width=2)
    # Ear
    draw.ellipse([cx + 16, y1 - 138, cx + 26, y1 - 122], fill=skin_dark)
    # Hair: swept back bun
    draw.pieslice([cx - 36, y1 - 172, cx + 32, y1 - 116], 90, 350, fill=hair)
    draw.ellipse([cx + 6, y1 - 176, cx + 34, y1 - 148], fill=hair)
    draw.arc([cx - 36, y1 - 172, cx + 32, y1 - 116], 100, 340,
             fill=(30, 22, 16), width=2)
    # Small earring
    draw.ellipse([cx + 18, y1 - 120, cx + 23, y1 - 115], fill=GOLD)
    # Photo corner marks
    for (mx, my, dx, dy) in [(x0, y0, 1, 1), (x1, y0, -1, 1),
                             (x0, y1, 1, -1), (x1, y1, -1, -1)]:
        draw.line([(mx, my + 10 * dy), (mx, my), (mx + 10 * dx, my)],
                  fill=INK, width=2)


def stamp_layer(text_lines, w, h, ink, shape="rect", size=15, border=3):
    """A rubber stamp on its own transparent layer, ready to rotate."""
    layer = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = (w + 40) // 2, (h + 40) // 2
    if shape == "oval":
        d.ellipse([20, 20, 20 + w, 20 + h], outline=ink + (235,),
                  width=border)
        d.ellipse([26, 26, 14 + w, 14 + h], outline=ink + (235,), width=1)
    else:
        d.rounded_rectangle([20, 20, 20 + w, 20 + h], radius=8,
                            outline=ink + (235,), width=border)
        d.rounded_rectangle([25, 25, 15 + w, 15 + h], radius=6,
                            outline=ink + (200,), width=1)
    y = cy - (len(text_lines) * (size + 4)) // 2 + 2
    for line in text_lines:
        d.text((cx, y), line, font=font(size), fill=ink + (235,),
               anchor="ma")
        y += size + 4
    return layer


def paste_stamp(img, layer, x, y, angle):
    rotated = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    img.paste(rotated, (x, y), rotated)


def field(draw, x, y, label, value, vsize=17, label_size=11):
    text(draw, (x, y), label, size=label_size, fill=INK_SOFT)
    text(draw, (x, y + 14), value, size=vsize, fill=INK)


def build():
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img, "RGBA")

    # ---- Spread frame -------------------------------------------------
    d.rectangle([16, 16, W - 17, H - 17], outline=RULE, width=2)
    d.rectangle([22, 22, W - 23, H - 23], outline=(170, 158, 128), width=1)
    # Centre fold
    for y in range(30, H - 30, 12):
        d.line([(512, y), (512, y + 6)], fill=(150, 138, 108), width=1)
    # Page numbers
    text(d, (40, H - 46), "4", size=12, fill=INK_SOFT)
    text(d, (W - 40, H - 46), "5", size=12, fill=INK_SOFT, anchor="ra")

    # ================= LEFT PAGE: DATA PAGE ============================
    mountain_emblem(d, 268, 92, 34)
    centred(d, 268, 132, "REPUBLIC OF TARNOVIA", size=25, fill=GREEN,
            spacing=2)
    centred(d, 268, 162, "REPUBLIKA TARNOVIJA", size=12, fill=INK_SOFT,
            spacing=3)
    centred(d, 268, 182, "PASSPORT", size=19, fill=INK, spacing=6)
    centred(d, 268, 206, "PASPORT  ·  PASSEPORT", size=11, fill=INK_SOFT,
            spacing=2)
    rule(d, 48, 488, 228, fill=GREEN, width=2)

    # Top row: type / country code / passport number
    field(d, 48, 244, "TYPE / TIP", "P", vsize=17)
    field(d, 128, 244, "CODE / KOD", "TNO", vsize=17)
    field(d, 300, 244, "PASSPORT No. / BROJ PASOSA", "TN 4829137", vsize=17)

    # Portrait
    draw_portrait(d, (48, 300, 208, 492))
    text(d, (48, 500), "SIGNATURE / POTPIS", size=11, fill=INK_SOFT)
    text(d, (48, 514), "Elena M. Kovac", size=16, fill=INK)

    # Data fields, right of portrait
    fx = 232
    field(d, fx, 300, "SURNAME / PREZIME", "KOVAC", vsize=18)
    field(d, fx, 344, "GIVEN NAMES / IME", "ELENA MARIA", vsize=18)
    field(d, fx, 388, "NATIONALITY / DRZAVLJANSTVO", "TARNOVIAN",
          vsize=18)
    field(d, fx, 432, "DATE OF BIRTH / DATUM RODJENJA", "07 APR 1988",
          vsize=18)
    field(d, fx, 476, "PLACE OF BIRTH / MJESTO RODJENJA", "VELGRAD",
          vsize=18)

    # Lower data row
    field(d, 48, 556, "SEX / SPOL", "F", vsize=17)
    field(d, 128, 556, "DATE OF ISSUE / DATUM IZDAVANJA", "12 MAR 2024",
          vsize=17)
    field(d, 330, 556, "DATE OF EXPIRY / VAZI DO", "12 MAR 2034",
          vsize=17)
    field(d, 48, 600, "AUTHORITY / ORGAN", "MINISTRY OF THE INTERIOR - VELGRAD",
          vsize=16)
    field(d, 48, 644, "HOLDER'S ADDRESS / ADRESA", "14 ULICA PLANINA, VELGRAD",
          vsize=16)

    # Personal number / height, small print
    text(d, (48, 700), "PERSONAL No.  880407-512  ·  HEIGHT  168 cm  ·  EYES  BROWN",
         size=12, fill=INK_SOFT)
    text(d, (48, 720), "THIS PASSPORT REMAINS THE PROPERTY OF THE REPUBLIC OF TARNOVIA.",
         size=12, fill=INK_SOFT)

    # MRZ
    rule(d, 48, 488, 756, fill=INK, width=1)
    l1, l2 = mrz_lines()
    text(d, (48, 768), l1, size=17, fill=INK)
    text(d, (48, 792), l2, size=17, fill=INK)
    text(d, (48, 824), "P<TNOKOVAC<<ELENA<MARIA - MACHINE READABLE ZONE",
         size=10, fill=INK_SOFT)

    # Small mountain watermark, lower left corner of data page
    mountain_emblem(d, 452, 700, 16)

    # ================= RIGHT PAGE: VISAS & STAMPS ======================
    centred(d, 756, 52, "VISAS", size=20, fill=INK, spacing=6)
    centred(d, 756, 78, "VIZE  ·  VISAS", size=11, fill=INK_SOFT, spacing=2)
    rule(d, 536, 976, 102, fill=GREEN, width=2)

    # Stamps - all dated AFTER the passport issue date 12 MAR 2024.
    paste_stamp(img, stamp_layer(
        ["ALPENMARK", "ENTRY - 14 JUN 2024", "BORDER POST KLAUSEN"],
        260, 84, BLUE, shape="oval", size=15),
        560, 130, -7)
    paste_stamp(img, stamp_layer(
        ["ALPENMARK", "EXIT - 28 JUN 2024", "BORDER POST KLAUSEN"],
        260, 84, BLUE, shape="oval", size=15),
        690, 250, 6)
    paste_stamp(img, stamp_layer(
        ["DRAVSKA", "ENTRY - 03 SEP 2025", "DRAVSKA BORDER"],
        250, 84, RED, shape="rect", size=15),
        556, 380, 5)
    paste_stamp(img, stamp_layer(
        ["DRAVSKA", "EXIT - 19 SEP 2025", "DRAVSKA BORDER"],
        250, 84, RED, shape="rect", size=15),
        700, 500, -6)
    paste_stamp(img, stamp_layer(
        ["VELGRAD", "DEPARTURE - 02 FEB 2026", "TARNOVIA"],
        250, 78, PURPLE, shape="oval", size=14),
        566, 620, -4)

    # Fee stamp, small, overlapping the visa-condition box edge
    paste_stamp(img, stamp_layer(
        ["FEE PAID", "40 TVD"],
        120, 56, GREEN, shape="rect", size=14),
        830, 760, 8)

    # Visa condition box - the telling paperwork detail
    d.rectangle([556, 760, 976, 884], outline=INK, width=2)
    d.rectangle([560, 764, 972, 880], outline=RULE, width=1)
    text(d, (576, 776), "VISA CONDITION / UVJET VIZE", size=12, fill=INK_SOFT)
    text(d, (576, 798),
         "HOLDER MAY NOT CROSS THE", size=16, fill=RED)
    text(d, (576, 820),
         "VELGRAD PASS NOV-MAR", size=16, fill=RED)
    text(d, (576, 842),
         "WITHOUT CHAIN PERMIT.", size=16, fill=RED)
    text(d, (576, 864), "SEE PAGE 12 FOR MOUNTAIN PASS REGULATIONS.",
         size=11, fill=INK_SOFT)

    # Handwritten-style travel note, bottom of right page
    text(d, (556, 908), "Holder travelled by rail: Velgrad - Klausen - Dravska.",
         size=12, fill=(60, 60, 110))
    text(d, (556, 928), "No visa required for stays under 90 days (Alpenmark, Dravska).",
         size=12, fill=(60, 60, 110))

    # Faint mountain watermark on the right page
    mountain_emblem(d, 920, 160, 22)

    os.makedirs("/output", exist_ok=True)
    img.save(OUT, format="PNG", optimize=True)
    return OUT


if __name__ == "__main__":
    path = build()
    data = open(path, "rb").read()
    print(path, len(data), "bytes")
    print("sha256:", hashlib.sha256(data).hexdigest())
    print("size:", Image.open(path).size)
