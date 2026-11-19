"""Gráficos en pantalla (títulos, precios, etiquetas) renderizados como PNG con transparencia.

Se dibujan con Pillow a resolución 1080p, se cachean por hash y se usan igual en:
  * el LIVE PREVIEW del navegador (<img>), y
  * el render (overlay de ffmpeg con animación de entrada/salida),
así lo que ves en el visor es exactamente lo que sale en el video.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .util import sha256_text

S = 1.0  # escala base: 1080p
FONT_DIRS = ["04_graphics/fonts"]
FALLBACK = ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def _font(prj, weight: str, size: int):
    names = {"bold": ["Poppins-Bold.ttf"], "medium": ["Poppins-Medium.ttf", "Poppins-Regular.ttf"]}[weight]
    for d in FONT_DIRS:
        for n in names:
            p = prj.p(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    for f in FALLBACK:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def _hex(c, a=255):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def _shadowed(card: Image.Image, radius=18, offset=(0, 10), alpha=110) -> Image.Image:
    pad = radius * 3
    W, H = card.size
    out = Image.new("RGBA", (W + pad * 2, H + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    m = card.split()[3].point(lambda v: alpha if v > 0 else 0)
    sh.paste((0, 0, 0, 255), (pad + offset[0], pad + offset[1]), m)
    sh = sh.filter(ImageFilter.GaussianBlur(radius))
    out = Image.alpha_composite(out, sh)
    out.alpha_composite(card, (pad, pad))
    return out


def _price_card(prj, d: dict) -> Image.Image:
    """Tarjeta oscura con barra de color: etiqueta chica + valor grande (+ chip opcional)."""
    label, value = d.get("label", "").upper(), d.get("value", "")
    accent = _hex(d.get("accent", "#facc15"))
    fl, fv, fc = _font(prj, "medium", 30), _font(prj, "bold", 64), _font(prj, "bold", 28)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    wl = tmp.textlength(label, font=fl)
    wv = tmp.textlength(value, font=fv)
    chip = d.get("chip")
    wc = tmp.textlength(chip, font=fc) + 36 if chip else 0
    W = int(max(wl, wv + (wc + 18 if chip else 0)) + 36 + 44)
    H = 150
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(card)
    g.rounded_rectangle((0, 0, W - 1, H - 1), radius=22, fill=(14, 17, 23, 232))
    g.rounded_rectangle((0, 0, 12, H - 1), radius=6, fill=accent)
    g.text((36, 18), label, font=fl, fill=(170, 178, 195, 255))
    g.text((36, 52), value, font=fv, fill=(255, 255, 255, 255))
    if chip:
        cx = 36 + wv + 18
        ccol = _hex(d.get("chip_color", "#e11d2e"))
        g.rounded_rectangle((cx, 70, cx + wc, 118), radius=24, fill=ccol)
        g.text((cx + 18, 76), chip, font=fc, fill=(255, 255, 255, 255))
    return _shadowed(card)


def _section(prj, d: dict) -> Image.Image:
    """Título de sección: 'SETUP 1' chico sobre 'PC COMÚN' grande, con acento de color."""
    small, big = d.get("kicker", "").upper(), d.get("title", "").upper()
    accent = _hex(d.get("accent", "#1f6fff"))
    fs, fb = _font(prj, "bold", 34), _font(prj, "bold", 96)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    wb = tmp.textlength(big, font=fb)
    ws = tmp.textlength(small, font=fs)
    W, H = int(max(wb, ws + 40) + 90), 226
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(card)
    g.rounded_rectangle((0, 40, W - 1, H - 1), radius=26, fill=(14, 17, 23, 236))
    g.rounded_rectangle((28, 0, 28 + ws + 40, 70), radius=18, fill=accent)
    g.text((48, 10), small, font=fs, fill=(255, 255, 255, 255))
    g.text((45, 78), big, font=fb, fill=(255, 255, 255, 255))
    g.rectangle((45, H - 16, 45 + min(wb, 220), H - 9), fill=accent)
    return _shadowed(card, radius=22)


def _tag(prj, d: dict) -> Image.Image:
    """Etiqueta tipo miniatura (COMÚN / GAMER / CREADOR)."""
    txt = d.get("text", "").upper()
    col = _hex(d.get("accent", "#1f6fff"))
    f = _font(prj, "bold", int(d.get("size", 74)))
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    w = tmp.textlength(txt, font=f)
    W, H = int(w + 70), int(f.size * 1.55)
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(card)
    g.rounded_rectangle((0, 0, W - 1, H - 1), radius=20, fill=col)
    g.text((35, int(H * 0.1)), txt, font=f, fill=_hex(d.get("color", "#ffffff")), stroke_width=3,
           stroke_fill=(0, 0, 0, 90))
    return _shadowed(card, radius=14, offset=(0, 8))


TEMPLATES = {"price": _price_card, "section": _section, "tag": _tag}


def build(prj, e: dict) -> str:
    """Devuelve la ruta relativa del PNG del gráfico (lo genera si no está en caché)."""
    spec = {"t": e["template"], "d": e.get("data", {}), "v": 3}
    key = sha256_text(json.dumps(spec, sort_keys=True, ensure_ascii=False))[:20]
    out = prj.cache_dir / "graphics" / f"{e['template']}_{key}.png"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        img = TEMPLATES[e["template"]](prj, e.get("data", {}))
        img.save(out)
    return prj.rel(out)


def build_all(prj, tl: dict) -> int:
    n = 0
    for e in tl.get("effects", []):
        if e.get("type") == "graphic":
            e["png"] = build(prj, e)
            with Image.open(prj.p(e["png"])) as im:
                e["png_size"] = list(im.size)
            n += 1
    return n
