"""ESTILO PROPIO DEL CANAL (02/11/2026). Se rechazó las placas oscuras genéricas («demasiado IA, todos iguales, nada que
identifique a mi canal»). Todo sale del banner y de la miniatura del canal: pizarra azul con rayos e íconos de línea,
Impact ámbar con borde negro y sombra corrida, la etiqueta de precio de la miniatura (tachado gris + raya roja + «% OFF»
verde), el sello rojo «FALSO», productos como stickers con borde blanco y capturas reales de Mercado Libre con un óvalo
rojo hecho a mano. build.py junta estas escenas (sc_zk_*) con las de gfx."""
import math, random, functools
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import gfx
from gfx import ease

NAVY, SLATE, STEEL = (22, 31, 40), (46, 61, 72), (120, 140, 156)   # tomados del BANNER_FINAL
AMBER, AMBER2, INK = (245, 166, 35), (255, 196, 92), (12, 8, 7)
GREEN, RED, WHITE, RED2 = (0, 166, 80), (226, 35, 26), (255, 255, 255), (255, 82, 70)
# Tipografía: Bahnschrift, la de los rótulos del canal (pedido 02/11: Poppins «es la típica que usan todos»)
BAHN = "C:/Windows/Fonts/bahnschrift.ttf"
IMPACT = (BAHN, b"Bold Condensed"); POP = (BAHN, b"SemiBold SemiCondensed"); PRICE = (BAHN, b"Bold")
FOTOS = None   # carpeta de fotos: la setea el script que arma las escenas (CFG["fotos"])
OVER = False   # True: sin fondo, para ir encima de la cámara (build.py)

@functools.lru_cache(maxsize=None)
def _f(spec, size):
    f = ImageFont.truetype(spec[0], max(8, int(size))); f.set_variation_by_name(spec[1]); return f

def _icon(d, kind, cx, cy, s, col, w):
    if kind == "phone":
        d.rounded_rectangle((cx - s * .32, cy - s * .55, cx + s * .32, cy + s * .55), radius=s * .1, outline=col, width=w)
        d.line((cx - s * .08, cy - s * .45, cx + s * .08, cy - s * .45), fill=col, width=w)
    elif kind == "head":
        d.arc((cx - s * .5, cy - s * .55, cx + s * .5, cy + s * .45), 180, 360, fill=col, width=w)
        for sx in (-1, 1):
            d.rounded_rectangle((cx + sx * s * .5 - s * .14, cy - s * .05, cx + sx * s * .5 + s * .14, cy + s * .4), radius=s * .08, outline=col, width=w)
    elif kind == "tag":
        d.polygon([(cx - s * .5, cy - s * .3), (cx + s * .25, cy - s * .3), (cx + s * .5, cy), (cx + s * .25, cy + s * .3), (cx - s * .5, cy + s * .3)], outline=col, width=w)
        d.ellipse((cx + s * .12, cy - s * .07, cx + s * .26, cy + s * .07), outline=col, width=w)
    elif kind == "star":
        d.polygon([(cx + (s * .5 if k % 2 == 0 else s * .14) * math.cos(k * math.pi / 4 - math.pi / 2),
                    cy + (s * .5 if k % 2 == 0 else s * .14) * math.sin(k * math.pi / 4 - math.pi / 2)) for k in range(8)], fill=col)

_bg = {}
def bg(cv, t):
    """Pizarra del banner: degradé navy → azul, 28 rayos que giran despacio, íconos de línea y destellos ámbar."""
    W, H = cv.W, cv.H
    if cv.s not in _bg:
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((x - W / 2) / (W * .75)) ** 2 + ((y - H / 2) / (H * .75)) ** 2); k = (np.clip(1 - r, 0, 1) ** .8)[..., None]
        base = Image.fromarray((np.array(NAVY) * (1 - k) + np.array(SLATE) * k).astype(np.uint8)).convert("RGBA")
        R = int(math.hypot(W, H)) + 4; rays = Image.new("RGBA", (R, R), (0, 0, 0, 0)); d = ImageDraw.Draw(rays)
        for i in range(28):
            a0 = i * 2 * math.pi / 28; a1 = a0 + math.pi / 56
            d.polygon([(R / 2, R / 2), (R / 2 + R * math.cos(a0), R / 2 + R * math.sin(a0)), (R / 2 + R * math.cos(a1), R / 2 + R * math.sin(a1))], fill=STEEL + (26,))
        ic = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ic)
        for kind, fx, fy, s, amb in [("head", .07, .30, 150, 1), ("phone", .27, .14, 120, 0), ("tag", .91, .17, 130, 1), ("phone", .94, .72, 140, 0),
                                     ("head", .79, .92, 120, 0), ("tag", .08, .84, 120, 0), ("star", .2, .1, 46, 1), ("star", .86, .45, 40, 1), ("star", .55, .95, 34, 1)]:
            _icon(d, kind, fx * W, fy * H, cv.px(s), AMBER + (70,) if amb else (170, 186, 198, 45), max(2, cv.px(7)))
        _bg[cv.s] = (base, rays, ic)
    if OVER: return Image.new("RGBA", (W, H), (0, 0, 0, 0))   # modo overlay: los datos van encima de la cámara
    base, rays, ic = _bg[cv.s]; R = rays.size[0]
    img = base.copy(); rr = rays.rotate(t * 2.0, resample=Image.BILINEAR)
    img.alpha_composite(rr.crop(((R - W) // 2, (R - H) // 2, (R - W) // 2 + W, (R - H) // 2 + H))); img.alpha_composite(ic)
    return img

def _back(x):   # pop con rebote (0 → 1,08 → 1)
    x = min(max(x, 0.0), 1.0); c1 = 1.9; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2

def _fade(L, a):
    if a < 1: L.putalpha(L.getchannel("A").point(lambda v: int(v * max(0, a))))
    return L

def _place(cv, img, L, cx, cy, sc=1.0, rot=0.0, a=1.0):
    if rot: L = L.rotate(rot, resample=Image.BICUBIC, expand=True)
    if sc != 1: L = L.resize((max(1, int(L.width * sc)), max(1, int(L.height * sc))), Image.BICUBIC)
    img.alpha_composite(_fade(L, a), (int(cv.px(cx) - L.width / 2), int(cv.px(cy) - L.height / 2)))

def text(cv, img, xy, s, size, fill=AMBER, t=1.0, start=0.0, rot=-2.0, font=None, shadow=True, fo=1.0):
    """Texto sticker del banner: relleno, borde negro grueso y sombra corrida; entra con pop."""
    p = (t - start) / 0.35
    if p <= 0: return
    f = _f(font or IMPACT, cv.px(size)); st = max(2, cv.px(size * (.09 if font is None else .07)))
    bb = ImageDraw.Draw(img).textbbox((0, 0), s, font=f, stroke_width=st)
    L = Image.new("RGBA", (bb[2] - bb[0] + cv.px(size * .5), bb[3] - bb[1] + cv.px(size * .5)), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    o = (L.width / 2, L.height / 2)
    if shadow: d.text((o[0] + cv.px(size * .06), o[1] + cv.px(size * .08)), s, font=f, fill=(0, 0, 0, 150), anchor="mm", stroke_width=st, stroke_fill=(0, 0, 0, 150))
    d.text(o, s, font=f, fill=fill, anchor="mm", stroke_width=st, stroke_fill=INK)
    _place(cv, img, L, xy[0], xy[1], _back(p), rot, min(1, p * 2) * fo)

@functools.lru_cache(maxsize=64)
def _sticker(path, h):
    """Recorte de producto con borde blanco y sombra (los stickers del banner)."""
    im = Image.open(path).convert("RGBA")
    from scipy import ndimage
    al = np.asarray(im.getchannel("A")) > 40; lab, n = ndimage.label(al)
    if n > 1:
        sz = ndimage.sum(al, lab, range(1, n + 1)); chico = [i + 1 for i, v in enumerate(sz) if v < sz.max() * 0.05]   # solo restos (esquinas blancas sueltas)
        a2 = np.asarray(im.getchannel("A")).copy(); a2[np.isin(lab, chico)] = 0; im.putalpha(Image.fromarray(a2))
    im = im.crop(im.getbbox())
    im = im.resize((max(1, int(im.width * h / im.height)), h), Image.LANCZOS)
    pad = int(h * .05) + 4; big = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0)); big.alpha_composite(im, (pad, pad))
    a = big.getchannel("A").point(lambda v: 255 if v > 40 else 0).filter(ImageFilter.MaxFilter(2 * (pad // 2) + 1))
    out = Image.new("RGBA", big.size, (0, 0, 0, 0)); sh = Image.new("RGBA", big.size, (0, 0, 0, 0))
    sh.putalpha(a.point(lambda v: int(v * .45))); sh = sh.filter(ImageFilter.GaussianBlur(pad * .6))
    out.alpha_composite(sh, (pad // 3, pad // 2)); wl = Image.new("RGBA", big.size, WHITE + (255,)); wl.putalpha(a)
    out.alpha_composite(wl); out.alpha_composite(big)
    return out

def sticker(cv, img, file, cx, cy, h, t, start=0.0, rot=-4.0, fo=1.0):
    p = (t - start) / 0.45
    if p <= 0: return
    st = _sticker(f"{gfx.CUT}/{file}", cv.px(h))
    _place(cv, img, st.copy(), cx, cy + 8 * math.sin(t * 1.1), _back(p), rot + 1.5 * math.sin(t * 1.3), min(1, p * 2) * fo)

def stamp(cv, img, xy, s, t, start, size=90, rot=-8):
    """Sello rojo «FALSO» de la miniatura: entra grande y golpea."""
    p = (t - start) / 0.25
    if p <= 0: return
    f = _f(IMPACT, cv.px(size)); bb = ImageDraw.Draw(img).textbbox((0, 0), s, font=f)
    pad = cv.px(size * .35); L = Image.new("RGBA", (bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.rounded_rectangle((cv.px(6), cv.px(6), L.width - cv.px(6), L.height - cv.px(6)), radius=cv.px(18), fill=RED + (255,), outline=(110, 8, 6, 255), width=max(2, cv.px(7)))
    d.text((L.width / 2, L.height / 2 - cv.px(size * .05)), s, font=f, fill=WHITE, anchor="mm")
    _place(cv, img, L, xy[0], xy[1], 1 + 1.4 * (1 - ease(p)), rot, min(1, p * 1.5))

def circle(img, box, t, start, w, dur=0.55, col=RED):
    """Óvalo rojo dibujado a mano alrededor de box (px de img); el trazo se completa en dur s."""
    p = (t - start) / dur
    if p <= 0: return
    p = ease(p); x0, y0, x1, y1 = box; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; rx, ry = (x1 - x0) / 2 + w * 2, (y1 - y0) / 2 + w * 1.6
    n = 90; pts = []
    for k in range(int(n * 1.12 * p)):
        a = -2.2 + k / n * 2 * math.pi; j = 1 + 0.04 * math.sin(k * .7) + 0.03 * k / n
        pts.append((cx + rx * j * math.cos(a), cy + ry * j * math.sin(a) + k / n * w * .8))
    if len(pts) > 1: ImageDraw.Draw(img).line(pts, fill=col + (255,), width=max(2, int(w)), joint="curve")

def arrow(cv, img, a, b, t, start, col=AMBER, width=14):
    """Flecha dibujada (curva y con punta), no un glifo de la fuente."""
    p = (t - start) / 0.4
    if p <= 0: return
    p = ease(p); (x0, y0), (x1, y1) = [(cv.px(x), cv.px(y)) for x, y in (a, b)]
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2 - cv.px(70); pts = []
    for k in range(int(40 * p) + 1):
        u = k / 40; pts.append(((1 - u) ** 2 * x0 + 2 * (1 - u) * u * mx + u * u * x1, (1 - u) ** 2 * y0 + 2 * (1 - u) * u * my + u * u * y1))
    d = ImageDraw.Draw(img); w = max(2, cv.px(width))
    if len(pts) > 1:
        d.line(pts, fill=INK + (255,), width=w + max(2, cv.px(8)), joint="curve"); d.line(pts, fill=col + (255,), width=w, joint="curve")
    if p > .95 and len(pts) > 2:
        (ax, ay), (bx, by) = pts[-3], pts[-1]; ang = math.atan2(by - ay, bx - ax); L_ = cv.px(44)
        d.polygon([(bx + cv.px(12) * math.cos(ang), by + cv.px(12) * math.sin(ang)), (bx - L_ * math.cos(ang - .5), by - L_ * math.sin(ang - .5)),
                   (bx - L_ * math.cos(ang + .5), by - L_ * math.sin(ang + .5))], fill=col + (255,), outline=INK + (255,))

def tag(cv, img, cx, cy, new, old=None, off=None, t=1.0, start=0.0, scale=1.0, rot=-3, fo=1.0):
    """La etiqueta de precio de la miniatura: tarjeta blanca, tachado gris con raya roja, precio grande y «% OFF» verde,
    cada renglón centrado en vertical."""
    p = (t - start) / 0.4
    if p <= 0: return
    s = cv.s * scale; fn = _f(PRICE, 120 * s); fo_ = _f(PRICE, 66 * s); dd = ImageDraw.Draw(img)
    pw = dd.textlength(new, font=fn); bw = int(180 * s) if off else 0
    W_ = int(pw + bw + (110 if off else 80) * s); H_ = int((300 if old else 190) * s)
    L = Image.new("RGBA", (W_ + int(40 * s), H_ + int(40 * s)), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.rounded_rectangle((int(16 * s), int(22 * s), W_ + int(16 * s), H_ + int(22 * s)), radius=int(34 * s), fill=(0, 0, 0, 110))
    d.rounded_rectangle((0, 0, W_, H_), radius=int(34 * s), fill=WHITE + (255,), outline=INK + (255,), width=max(2, int(6 * s)))
    x0 = int(40 * s); yp = H_ * (0.64 if old else 0.5)
    if old:
        yo = H_ * 0.25; d.text((x0, yo), old, font=fo_, fill=(150, 150, 150), anchor="lm")
        bb = d.textbbox((x0, yo), old, font=fo_, anchor="lm")
        d.line((bb[0] - int(6 * s), yo + int(4 * s), bb[2] + int(6 * s), yo - int(4 * s)), fill=RED, width=max(2, int(11 * s)))
    d.text((x0, yp), new, font=fn, fill=INK, anchor="lm")
    if off:
        fx = int(x0 + pw + 30 * s); a_, b_ = (off.split(" ", 1) + ["OFF"])[:2]
        d.rounded_rectangle((fx, yp - int(72 * s), fx + bw, yp + int(72 * s)), radius=int(16 * s), fill=GREEN, outline=INK, width=max(2, int(5 * s)))
        d.text((fx + bw / 2, yp - int(28 * s)), a_, font=_f(IMPACT, 64 * s), fill=WHITE, anchor="mm")
        d.text((fx + bw / 2, yp + int(34 * s)), b_, font=_f(IMPACT, 52 * s), fill=WHITE, anchor="mm")
    _place(cv, img, L, cx, cy, _back(p), rot, min(1, p * 2) * fo)

def _foto(file): return Image.open(f"{FOTOS}/{file}").convert("RGB")

def _rv(reveal, i, default):
    return reveal[i] if reveal and i < len(reveal) and reveal[i] is not None else default

# ---------------------------------------------------------------------------------------------- escenas
def sc_zk_title(cv, t, dur, big, sub=None, col="amber", stamp_txt=None, stamp_at=0.8):
    img = bg(cv, t); fo = 1 - ease((t - (dur - 0.25)) / 0.25); fill = {"amber": AMBER, "white": WHITE, "red": RED2}[col]
    lines = big.split("\n"); n = len(lines)
    for i, ln in enumerate(lines):
        text(cv, img, (960, 520 - (n - 1) * 75 + i * 150 - (50 if sub else 0)), ln, 150 if len(ln) < 15 else 118, fill, t, i * 0.12, rot=-2.5, fo=fo)
    if sub: text(cv, img, (960, 520 + (n - 1) * 75 + 100), sub, 50, WHITE, t, 0.35, rot=-2.5, font=POP, fo=fo)
    if stamp_txt: stamp(cv, img, (1460, 290), stamp_txt, t, stamp_at)
    return img

def sc_zk_capture(cv, t, dur, file, focus=None, circ=None, circ_at=0.8, stamp_txt=None, stamp_xy=(1500, 250), stamp_at=1.2, caption=None, sub=None):
    """Captura real como tarjeta inclinada con borde blanco sobre la pizarra; zoom lento hacia focus (x0,y0,x1,y1 en px
    de la captura), óvalo rojo a mano en circ (px de la captura) y sello opcional."""
    img = bg(cv, t); im = _foto(file)
    fx0, fy0, fx1, fy1 = focus or (0, 0, im.width, im.height)
    z = 1 + 0.07 * min(1, t / max(dur, .1)); maxw, maxh = cv.px(1560), cv.px(780 if caption else 900)
    r = min(maxw / (fx1 - fx0), maxh / (fy1 - fy0)) * z; vw, vh = int(min(maxw, (fx1 - fx0) * r)), int(min(maxh, (fy1 - fy0) * r))
    sx0 = min(max(0, (fx0 + fx1) / 2 - vw / r / 2), max(0, im.width - vw / r)); sy0 = min(max(0, (fy0 + fy1) / 2 - vh / r / 2), max(0, im.height - vh / r))
    crop = im.crop((int(sx0), int(sy0), int(sx0 + vw / r), int(sy0 + vh / r))).resize((vw, vh), Image.LANCZOS).convert("RGBA")
    b = cv.px(14); card = Image.new("RGBA", (vw + 2 * b, vh + 2 * b), WHITE + (255,)); card.alpha_composite(crop, (b, b))
    if circ:
        x0, y0, x1, y1 = circ; circle(card, ((x0 - sx0) * r + b, (y0 - sy0) * r + b, (x1 - sx0) * r + b, (y1 - sy0) * r + b), t, circ_at, cv.px(10))
    sh = Image.new("RGBA", (card.width + cv.px(70), card.height + cv.px(70)), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle((cv.px(35), cv.px(45), card.width + cv.px(35), card.height + cv.px(45)), fill=(0, 0, 0, 140))
    sh = sh.filter(ImageFilter.GaussianBlur(cv.px(18))); sh.alpha_composite(card, (cv.px(25), cv.px(25)))
    _place(cv, img, sh, 960, 455 if caption else 540, _back(t / 0.45), -1.5)
    if stamp_txt: stamp(cv, img, stamp_xy, stamp_txt, t, stamp_at)
    if caption: text(cv, img, (960, 960), caption, 72, AMBER, t, 0.3, rot=-1.5)
    if sub: text(cv, img, (960, 1035), sub, 34, WHITE, t, 0.45, rot=-1.5, font=POP)
    return img

def sc_zk_price(cv, t, dur, file, name=None, new=None, old=None, off=None, stamp_txt=None, stamp_at=1.0, date=None, kicker=None, reveal=None):
    """Producto sticker a la izquierda y la etiqueta de precio de la miniatura a la derecha."""
    img = bg(cv, t); r0 = _rv(reveal, 0, 0.5)
    sticker(cv, img, file, 520, 560, 640, t, 0.0, rot=-6)
    if kicker: text(cv, img, (1310, 170), kicker, 44, WHITE, t, 0.2, rot=-2, font=POP)
    if name: text(cv, img, (1310, 265), name, 92 if len(name) < 15 else 74, AMBER, t, 0.15, rot=-2)
    if new: tag(cv, img, 1310, 590, new, old, off, t, r0)
    if stamp_txt: stamp(cv, img, (1450, 430), stamp_txt, t, _rv(reveal, 1, r0 + 0.6), size=80)
    if date: text(cv, img, (1310, 880), date, 40, WHITE, t, r0 + 0.3, rot=-2, font=POP)
    return img

def sc_zk_jump(cv, t, dur, file, name, d0, p0, d1, p1, delta, col="red", reveal=None):
    """Antes → después: dos etiquetas con fecha, flecha dibujada y la diferencia en grande."""
    img = bg(cv, t); r1 = _rv(reveal, 0, 1.0); r2 = _rv(reveal, 1, r1 + 0.6)
    text(cv, img, (960, 120), name, 92, AMBER, t, 0.0, rot=-2)
    sticker(cv, img, file, 960, 760, 420, t, 0.1, rot=3)
    text(cv, img, (420, 290), d0, 46, WHITE, t, 0.25, rot=-3, font=POP); tag(cv, img, 420, 420, p0, t=t, start=0.3, scale=.72, rot=-4)
    text(cv, img, (1500, 290), d1, 46, WHITE, t, r1, rot=2, font=POP); tag(cv, img, 1500, 420, p1, t=t, start=r1, scale=.72, rot=3)
    arrow(cv, img, (720, 420), (1200, 420), t, r1 - 0.1)
    text(cv, img, (1500, 700), delta, 130, GREEN if col == "green" else RED2, t, r2, rot=-4)
    return img

def sc_zk_list(cv, t, dur, title, rows, reveal=None, file=None):
    """Filas blancas tipo etiqueta (veredicto, tachados): cada una entra al decirla; el valor en ámbar oscuro."""
    img = bg(cv, t); text(cv, img, (960, 125), title, 100, AMBER, t, 0.0, rot=-2)
    if file: sticker(cv, img, file, 290, 610, 520, t, 0.1, rot=-5)
    x0 = 600 if file else 300; n = len(rows); y0 = 300 if n > 3 else 350; step = 172 if n > 3 else 200
    for i, (lab, val) in enumerate(rows):
        p = (t - _rv(reveal, i, 0.5 + 0.7 * i)) / 0.35
        if p <= 0: continue
        y = y0 + i * step; L = Image.new("RGBA", (cv.px(1860 - x0), cv.px(140)), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
        d.rounded_rectangle((0, 0, L.width - 1, L.height - 1), radius=cv.px(24), fill=(255, 255, 255, 240), outline=INK + (255,), width=max(2, cv.px(5)))
        d.text((cv.px(40), L.height / 2), lab, font=_f(POP, cv.px(46)), fill=INK, anchor="lm")
        d.text((L.width - cv.px(36), L.height / 2), val, font=_f(PRICE, cv.px(72)), fill=(206, 110, 0), anchor="rm")
        img.alpha_composite(_fade(L, ease(p)), (int(cv.px(x0) + cv.px(90) * (1 - ease(p))), int(cv.px(y) - L.height / 2)))
    return img

def sc_zk_product(cv, t, dur, file, name, kicker=None, rows=None, reveal=None):
    """Producto sticker + nombre en Impact + datos (auriculares, Edge 60 Fusion)."""
    img = bg(cv, t)
    sticker(cv, img, file, 560, 580, 700, t, 0.0, rot=-5)
    if kicker: text(cv, img, (1340, 185), kicker, 44, WHITE, t, 0.2, rot=-2, font=POP)
    text(cv, img, (1340, 290), name, 92 if len(name) < 16 else 74, AMBER, t, 0.1, rot=-2)
    for i, (lab, val) in enumerate(rows or []):
        r = _rv(reveal, i, 0.7 + 0.6 * i)
        text(cv, img, (1340, 460 + i * 200), lab, 40, WHITE, t, r, rot=-2, font=POP)
        text(cv, img, (1340, 540 + i * 200), val, 98, AMBER2 if i == 0 else WHITE, t, r + 0.1, rot=-2)
    return img
