"""Motor de gráficos (base Nokia, adaptado a «autos»): escenas dibujadas cuadro a cuadro con PIL.
Estilo: documental sobrio. Fondo carbón con viñeta y grano, una tipografía (Poppins),
años y citas en Georgia itálica, acento ámbar. Clips de video tech como base. Nada de cajas ni tarjetas tipo web."""
import math, os, random, functools
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONTS = os.environ.get("ZK_FUENTES_DIR", "fonts")          # Poppins-Bold/Medium + georgiai/georgiaz
W0, H0 = 1920, 1080
BG = (11, 14, 19); BG2 = (24, 30, 40)
TX = (242, 241, 236); DIM = (138, 144, 154); ACC = (255, 176, 46); RED = (229, 72, 77)
LCD = (151, 178, 92); LCD_D = (40, 52, 26)
CROSSFADE = True   # el build funde escenas entre sí: fotos y clips no pasan por negro

def ease(x):  # ease-out cúbica, recortada
    x = min(max(x, 0.0), 1.0); return 1 - (1 - x) ** 3
def ein(t, a, d=0.45): return ease((t - a) / d)

class Canvas:
    def __init__(self, scale=0.5):
        self.s = scale; self.W = int(W0 * scale); self.H = int(H0 * scale)
        self._bg = self._make_bg(); self._grain = [self._make_grain(i) for i in range(6)]
    def px(self, v): return int(round(v * self.s))
    @functools.lru_cache(maxsize=None)
    def font(self, name, size):
        f = {"b": "Poppins-Bold.ttf", "m": "Poppins-Medium.ttf", "gi": "georgiai.ttf", "gz": "georgiaz.ttf"}[name]
        return ImageFont.truetype(os.path.join(FONTS, f), max(8, self.px(size)))
    def _make_bg(self):
        y, x = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
        d = np.sqrt(((x - self.W * .5) / self.W) ** 2 + ((y - self.H * .45) / self.H) ** 2)
        k = np.clip(1 - d * 1.5, 0, 1)[..., None]
        img = np.array(BG, np.float32) * (1 - k) + np.array(BG2, np.float32) * k
        return Image.fromarray(img.astype(np.uint8))
    def _make_grain(self, seed):
        r = np.random.default_rng(seed).normal(0, 7, (self.H, self.W, 1)).astype(np.float32)
        return r
    def new(self): return self._bg.copy()
    def finish(self, img, fi):
        a = np.asarray(img, np.float32) + self._grain[fi % 6]
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

def alpha_col(c, a): return tuple(int(v) for v in c) + (int(255 * max(0, min(1, a))),)

def text(cv, img, xy, s, font, size, col=TX, a=1.0, anchor="mm", dy=0.0, spacing=0):
    if a <= 0: return
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    x, y = xy; d.text((cv.px(x), cv.px(y + dy)), s, font=cv.font(font, size), fill=alpha_col(col, a), anchor=anchor)
    img.alpha_composite(lay) if img.mode == "RGBA" else img.paste(Image.alpha_composite(img.convert("RGBA"), lay).convert("RGB"))

def text_w(cv, s, font, size):
    return cv.font(font, size).getlength(s) / cv.s

def wrap(cv, s, font, size, maxw):
    out, cur = [], ""
    for w in s.split():
        t = (cur + " " + w).strip()
        if text_w(cv, t, font, size) > maxw and cur: out.append(cur); cur = w
        else: cur = t
    if cur: out.append(cur)
    return out

def rrect(d, cv, box, r, fill=None, outline=None, width=1):
    x0, y0, x1, y1 = [cv.px(v) for v in box]
    d.rounded_rectangle((x0, y0, x1, y1), radius=cv.px(r), fill=fill, outline=outline, width=max(1, cv.px(width)))

# ---------------------------------------------------------------- teléfonos dibujados
def draw_phone(cv, img, cx, cy, kind="3310", sc=1.0, a=1.0, lcd=None, t=0.0):
    """Dibuja un Nokia estilizado. lcd: función(draw, box_px, t) para animar la pantalla."""
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    A = lambda c, k=1.0: alpha_col(c, a * k)
    def R(x0, y0, x1, y1): return (cx + x0 * sc, cy + y0 * sc, cx + x1 * sc, cy + y1 * sc)
    if kind in ("3310", "1100", "3210", "2110", "1011"):
        body = {"3310": (28, 50, 78), "1100": (70, 76, 84), "3210": (150, 40, 45), "2110": (35, 37, 42), "1011": (30, 31, 34)}[kind]
        hw, hh = (125, 300) if kind != "2110" else (110, 330)
        if kind == "1011": hw, hh = 105, 340
        # sombra
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
        rrect(sd, cv, R(-hw + 14, -hh + 30, hw + 14, hh + 30), 70 * sc, fill=(0, 0, 0, int(140 * a)))
        lay.alpha_composite(sh.filter(ImageFilter.GaussianBlur(cv.px(28))))
        if kind in ("2110", "1011"):  # antena
            rrect(d, cv, R(hw - 55, -hh - 70, hw - 25, -hh + 10), 12 * sc, fill=A((22, 22, 24)))
        rrect(d, cv, R(-hw, -hh, hw, hh), (75 if kind == "3310" else 40) * sc, fill=A(body))
        rrect(d, cv, R(-hw + 8, -hh + 8, hw - 8, hh - 8), (68 if kind == "3310" else 34) * sc, outline=A((255, 255, 255), .10), width=3)
        # marco de pantalla
        rrect(d, cv, R(-hw + 22, -hh + 55, hw - 22, -hh + 225), 22 * sc, fill=A((205, 210, 212) if kind == "3310" else (40, 42, 46)))
        text(cv, lay, (cx, cy + (-hh + 75) * sc), "NOKIA", "b", 20 * sc, (30, 34, 40) if kind == "3310" else (200, 200, 200), a)
        sx0, sy0, sx1, sy1 = R(-hw + 42, -hh + 92, hw - 42, -hh + 205)
        rrect(d, cv, (sx0, sy0, sx1, sy1), 6 * sc, fill=A(LCD))
        if lcd: lcd(d, [cv.px(v) for v in (sx0, sy0, sx1, sy1)], t, a)
        # tecla navi / teclado
        if kind == "3310":
            d.ellipse([cv.px(v) for v in R(-62, -hh + 245, 62, -hh + 300)], fill=A((215, 220, 224)))
        ky0 = -hh + (325 if kind == "3310" else 255)
        kw, kh, gx, gy = 58, 34, 74, 48
        for r_ in range(4):
            for c_ in range(3):
                x = (c_ - 1) * gx; y = ky0 + r_ * gy
                rrect(d, cv, R(x - kw / 2, y, x + kw / 2, y + kh), 16 * sc, fill=A((225, 228, 230) if kind == "3310" else (95, 100, 108)))
    elif kind == "cityman":
        rrect(d, cv, R(-90, -330, 90, 330), 18 * sc, fill=A((32, 33, 36)))
        rrect(d, cv, R(40, -470, 62, -320), 8 * sc, fill=A((25, 25, 27)))
        rrect(d, cv, R(-60, -280, 60, -200), 6 * sc, fill=A((90, 30, 28)))
        for r_ in range(5):
            for c_ in range(3):
                x = (c_ - 1) * 48; y = -150 + r_ * 62
                rrect(d, cv, R(x - 18, y, x + 18, y + 34), 6 * sc, fill=A((150, 152, 156)))
        text(cv, lay, (cx, cy - 300 * sc), "MOBIRA", "b", 18 * sc, (170, 170, 170), a)
    elif kind == "smart":
        rrect(d, cv, R(-150, -300, 150, 300), 42 * sc, fill=A((20, 21, 24)))
        rrect(d, cv, R(-138, -288, 138, 288), 34 * sc, fill=A((60, 90, 160)))
        for i_ in range(4):
            for j_ in range(5):
                x = -90 + i_ * 60; y = -220 + j_ * 70
                rrect(d, cv, R(x - 20, y - 20, x + 20, y + 20), 10 * sc, fill=A((240, 240, 245), .85))
    elif kind == "communicator":
        rrect(d, cv, R(-330, -40, 330, 190), 30 * sc, fill=A((50, 54, 60)))
        for r_ in range(4):
            for c_ in range(11):
                x = -270 + c_ * 54; y = 10 + r_ * 42
                rrect(d, cv, R(x - 22, y, x + 22, y + 30), 6 * sc, fill=A((170, 175, 180)))
        rrect(d, cv, R(-330, -280, 330, -50), 30 * sc, fill=A((44, 47, 52)))
        rrect(d, cv, R(-250, -250, 250, -80), 8 * sc, fill=A((175, 195, 150)))
    elif kind == "ngage":
        d.ellipse([cv.px(v) for v in R(-330, -120, 330, 120)], fill=A((55, 60, 66)))
        rrect(d, cv, R(-110, -80, 110, 80), 10 * sc, fill=A(LCD))
        d.ellipse([cv.px(v) for v in R(-270, -40, -190, 40)], fill=A((110, 115, 120)))
        for k in range(4):
            d.ellipse([cv.px(v) for v in R(190 + (k % 2) * 45, -45 + (k // 2) * 45, 225 + (k % 2) * 45, -10 + (k // 2) * 45)], fill=A((110, 115, 120)))
    img.alpha_composite(lay)

def lcd_text(lines):
    def f(d, box, t, a):
        x0, y0, x1, y1 = box; h = y1 - y0
        fnt = ImageFont.truetype(os.path.join(FONTS, "Poppins-Bold.ttf"), max(8, int(h * 0.22)))
        for i, s in enumerate(lines):
            d.text(((x0 + x1) / 2, y0 + h * (0.3 + 0.36 * i)), s, font=fnt, fill=alpha_col(LCD_D, a), anchor="mm")
    return f

def lcd_snake(d, box, t, a):
    x0, y0, x1, y1 = box; cols, rows = 20, 10
    cw = (x1 - x0) / cols; ch = (y1 - y0) / rows
    path = [(2 + i, 5) for i in range(14)] + [(15, 5 - i) for i in range(1, 4)] + [(15 - i, 2) for i in range(1, 10)]
    head = int(t * 7) % len(path); L = 6
    for k in range(L):
        c, r = path[(head - k) % len(path)]
        d.rectangle((x0 + c * cw + 1, y0 + r * ch + 1, x0 + (c + 1) * cw - 1, y0 + (r + 1) * ch - 1), fill=alpha_col(LCD_D, a))
    fc, fr = (12, 7)
    d.rectangle((x0 + fc * cw + cw * .25, y0 + fr * ch + ch * .25, x0 + (fc + .75) * cw, y0 + (fr + .75) * ch), fill=alpha_col(LCD_D, a))

def lcd_torch(d, box, t, a):
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=alpha_col((200, 220, 140), a))

# ---------------------------------------------------------------- escenas
def sc_title(cv, t, dur, big, sub=None, kicker=None, col=TX):
    img = cv.new().convert("RGBA")
    fo = 1 - ein(t, dur - 0.35, 0.35)
    if kicker: text(cv, img, (960, 400), kicker.upper(), "m", 34, (175, 181, 190), ein(t, 0) * fo, dy=(1 - ein(t, 0)) * 18)
    lines = wrap(cv, big, "b", 92, 1500)
    y0 = 540 - (len(lines) - 1) * 56
    for i, l in enumerate(lines):
        e = ein(t, 0.08 + i * 0.1)
        text(cv, img, (960, y0 + i * 112), l, "b", 92, col, e * fo, dy=(1 - e) * 26)
    if sub:
        e = ein(t, 0.45); text(cv, img, (960, y0 + len(lines) * 112 + 14), sub, "m", 42, (190, 195, 202), e * fo, dy=(1 - e) * 16)
    return img

def sc_year(cv, t, dur, year, label, sub=None):
    img = cv.new().convert("RGBA"); fo = 1 - ein(t, dur - 0.35, 0.35)
    e = ein(t, 0, 0.7); text(cv, img, (960, 470), str(year), "gi", 260, TX, e * fo, dy=(1 - e) * 30)
    d = ImageDraw.Draw(img); w = 120 * ein(t, 0.35, 0.6)
    d.line((cv.px(960 - w / 2), cv.px(640), cv.px(960 + w / 2), cv.px(640)), fill=alpha_col(DIM, .6 * fo), width=max(1, cv.px(2)))
    e2 = ein(t, 0.55); text(cv, img, (960, 700), label, "b", 46, TX, e2 * fo, dy=(1 - e2) * 14)
    if sub: e3 = ein(t, 0.8); text(cv, img, (960, 770), sub, "m", 42, (190, 195, 202), e3 * fo)
    return img

def sc_counter(cv, t, dur, value, label, prefix="", suffix="", decimals=0, sub=None, col=TX):
    img = cv.new().convert("RGBA"); fo = 1 - ein(t, dur - 0.35, 0.35)
    v = value * ease(min(1, t / 0.8))
    s = f"{v:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    text(cv, img, (960, 480), prefix + s + suffix, "b", 190, col, ein(t, 0) * fo)
    e = ein(t, 0.4); text(cv, img, (960, 650), label, "m", 44, DIM, e * fo, dy=(1 - e) * 14)
    if sub: e = ein(t, 0.7); text(cv, img, (960, 730), sub, "m", 40, (190, 195, 202), e * fo)
    return img

def sc_phone(cv, t, dur, kind, name, note=None, lcd=None, side="center"):
    img = cv.new().convert("RGBA"); fo = 1 - ein(t, dur - 0.35, 0.35)
    e = ein(t, 0, 0.8); zoom = 1.0 + 0.04 * (t / max(dur, .1))
    px_ = 660 if side == "left" else 960
    draw_phone(cv, img, px_, 560 + (1 - e) * 60, kind, 1.05 * zoom, e * fo, lcd, t)
    if side == "left":
        e2 = ein(t, 0.35); text(cv, img, (1100, 500), name, "b", 84, TX, e2 * fo, anchor="lm", dy=(1 - e2) * 18)
        if note: e3 = ein(t, 0.6); text(cv, img, (1104, 585), note, "m", 36, DIM, e3 * fo, anchor="lm")
    else:
        e2 = ein(t, 0.35); text(cv, img, (960, 990), name, "b", 44, TX, e2 * fo)
        if note: text(cv, img, (960, 1040), note, "m", 26, DIM, ein(t, .6) * fo)
    return img

def sc_lineup(cv, t, dur, items):
    img = cv.new().convert("RGBA"); fo = 1 - ein(t, dur - 0.35, 0.35)
    n = len(items); gap = 1700 / n
    for i, (k, name) in enumerate(items):
        e = ein(t, 0.15 + i * 0.22, 0.6); x = 110 + gap * (i + .5)
        draw_phone(cv, img, x, 520 + (1 - e) * 50, k, 0.62, e * fo, lcd_text([name.split()[-1]]) if k in ("3310", "1100", "3210", "2110", "1011") else None)
        text(cv, img, (x, 860), name, "m", 30, DIM, e * fo)
    return img

def sc_grid(cv, t, dur, total=50, on=25, label="1 de cada 2 celulares vendidos era Nokia", year="2007"):
    img = cv.new().convert("RGBA"); d = ImageDraw.Draw(img); fo = 1 - ein(t, dur - 0.35, 0.35)
    cols = 10; rows = total // cols; w, h, gx, gy = 64, 104, 104, 150
    x0 = 960 - (cols - 1) * gx / 2; y0 = 300
    for i in range(total):
        c, r = i % cols, i // cols; x = x0 + c * gx; y = y0 + r * gy * .85
        lit = (i % 2 == 0) and t > 0.6 + (i / total) * 1.4
        e = ein(t, i * 0.012, .4)
        col = ACC if lit else (58, 64, 74)
        rrect(d, cv, (x - w / 2, y - h / 2, x + w / 2, y + h / 2), 16, fill=alpha_col(col, e * fo))
    text(cv, img, (960, 180), year, "gi", 70, TX, ein(t, 0) * fo)
    e = ein(t, 1.6); text(cv, img, (960, 990), label, "b", 46, TX, e * fo, dy=(1 - e) * 14)
    return img

def sc_bars(cv, t, dur, a_name, a_vals, b_name, b_vals, years, title):
    img = cv.new().convert("RGBA"); d = ImageDraw.Draw(img); fo = 1 - ein(t, dur - 0.35, 0.35)
    text(cv, img, (960, 150), title, "b", 50, TX, ein(t, 0) * fo)
    n = len(years); bx = 360; bw = 1200 / n; base = 860; mx = max(a_vals + b_vals)
    for i, yv in enumerate(years):
        e = ein(t, 0.3 + i * 0.12, .7); x = bx + i * bw
        for j, (vals, col) in enumerate(((a_vals, ACC), (b_vals, (120, 126, 136)))):
            hgt = 560 * vals[i] / mx * e; xx = x + 30 + j * 70
            rrect(d, cv, (xx, base - hgt, xx + 60, base), 6, fill=alpha_col(col, fo))
        text(cv, img, (x + 95, 905), str(yv), "m", 28, DIM, fo)
    for j, (nm, col) in enumerate(((a_name, ACC), (b_name, (120, 126, 136)))):
        x = 760 + j * 300
        rrect(d, cv, (x, 235, x + 26, 261), 4, fill=alpha_col(col, fo * ein(t, .2)))
        text(cv, img, (x + 40, 248), nm, "m", 30, TX, fo * ein(t, .2), anchor="lm")
    return img

def sc_line(cv, t, dur, pts, title, ylab="%"):
    img = cv.new().convert("RGBA"); d = ImageDraw.Draw(img); fo = 1 - ein(t, dur - 0.35, 0.35)
    text(cv, img, (960, 150), title, "b", 50, TX, ein(t, 0) * fo)
    x0, x1, y0, y1 = 300, 1620, 880, 300; mx = max(v for _, v in pts)
    d.line((cv.px(x0), cv.px(y0), cv.px(x1), cv.px(y0)), fill=alpha_col(DIM, .5 * fo), width=max(1, cv.px(2)))
    P = [(x0 + (x1 - x0) * i / (len(pts) - 1), y0 - (y0 - y1) * v / mx) for i, (_, v) in enumerate(pts)]
    prog = ease(min(1, t / 2.2)) * (len(P) - 1)
    k = int(prog); fr = prog - k
    seg = P[:k + 1] + ([(P[k][0] + (P[k + 1][0] - P[k][0]) * fr, P[k][1] + (P[k + 1][1] - P[k][1]) * fr)] if k + 1 < len(P) else [])
    if len(seg) > 1: d.line([(cv.px(x), cv.px(y)) for x, y in seg], fill=alpha_col(RED if pts[-1][1] < pts[0][1] else ACC, fo), width=max(2, cv.px(7)), joint="curve")
    for i, ((lab, v), (x, y)) in enumerate(zip(pts, P)):
        if i <= prog + 0.01:
            r = 9; d.ellipse((cv.px(x - r), cv.px(y - r), cv.px(x + r), cv.px(y + r)), fill=alpha_col(TX, fo))
            text(cv, img, (x, y - 45), f"{v:g}{ylab}", "b", 36, TX, fo)
        text(cv, img, (x, 930), str(lab), "m", 28, DIM, fo)
    return img

def sc_quote(cv, t, dur, q, who=None, stamp=None):
    img = cv.new().convert("RGBA"); fo = 1 - ein(t, dur - 0.35, 0.35)
    lines = wrap(cv, q, "gi", 66, 1400); y0 = 520 - (len(lines) - 1) * 44
    text(cv, img, (960, y0 - 120), "“", "gz", 160, DIM, ein(t, 0) * fo)
    for i, l in enumerate(lines):
        e = ein(t, 0.15 + i * 0.12); text(cv, img, (960, y0 + i * 88), l, "gi", 66, TX, e * fo, dy=(1 - e) * 14)
    if who: text(cv, img, (960, y0 + len(lines) * 88 + 30), who, "m", 32, DIM, ein(t, .6) * fo)
    if stamp: stamp_on(cv, img, t - 1.2, stamp, fo)
    return img

def stamp_on(cv, img, t, s, fo=1.0, xy=(1440, 300), col=RED):
    if t <= 0: return
    e = ein(t, 0, 0.18); k = 1.6 - 0.6 * e
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    f = cv.font("b", 64 * k); bb = d.textbbox((0, 0), s, font=f)
    w_, h_ = bb[2] - bb[0] + cv.px(60), bb[3] - bb[1] + cv.px(44)
    st = Image.new("RGBA", (w_, h_), (0, 0, 0, 0)); sd = ImageDraw.Draw(st)
    sd.rectangle((2, 2, w_ - 3, h_ - 3), outline=alpha_col(col, .9 * e * fo), width=max(2, cv.px(7 * k)))
    sd.text((w_ / 2, h_ / 2), s, font=f, fill=alpha_col(col, .92 * e * fo), anchor="mm")
    st = st.rotate(-8, expand=True, resample=Image.BICUBIC)
    lay.alpha_composite(st, (cv.px(xy[0]) - st.width // 2, cv.px(xy[1]) - st.height // 2))
    img.alpha_composite(lay)

def sc_strike(cv, t, dur, title, items, every=0.7):
    img = cv.new().convert("RGBA"); d = ImageDraw.Draw(img); fo = 1 - ein(t, dur - 0.35, 0.35)
    text(cv, img, (960, 230), title, "b", 60, TX, ein(t, 0) * fo)
    for i, s in enumerate(items):
        y = 400 + i * 120; e = ein(t, 0.3 + i * every * .5)
        text(cv, img, (960, y), s, "m", 52, TX, e * fo, dy=(1 - e) * 12)
        k = ein(t, 0.9 + i * every, 0.3)
        if k > 0:
            w = text_w(cv, s, "m", 52) + 40
            d.line((cv.px(960 - w / 2), cv.px(y), cv.px(960 - w / 2 + w * k), cv.px(y)), fill=alpha_col(RED, fo), width=max(2, cv.px(6)))
    return img

def sc_pyramid(cv, t, dur):
    img = cv.new().convert("RGBA"); d = ImageDraw.Draw(img); fo = 1 - ein(t, dur - 0.35, 0.35)
    rows = [("Directivos", "miedo a Apple", 0.0), ("Mandos medios", "miedo a los de arriba", 0.9), ("Resultado", "fechas que nadie iba a cumplir", 1.8)]
    for i, (who, what, at) in enumerate(rows):
        e = ein(t, at, .5); w = 520 + i * 300; y = 300 + i * 200
        rrect(d, cv, (960 - w / 2, y, 960 + w / 2, y + 140), 10, fill=alpha_col((36, 42, 54), e * fo))
        text(cv, img, (960, y + 50), who, "b", 46, TX, e * fo)
        text(cv, img, (960, y + 102), what, "m", 32, RED if i < 2 else DIM, e * fo)
    return img

def sc_logo_crack(cv, t, dur, word="NOKIA"):
    img = cv.new().convert("RGBA"); fo = 1 - ein(t, dur - 0.35, 0.35)
    e = ein(t, 0, .6); text(cv, img, (960, 540), word, "b", 240, ACC, e * fo, dy=(1 - e) * 20)
    k = ein(t, 1.0, .5)
    if k > 0:
        d = ImageDraw.Draw(img); rnd = random.Random(3); x, y = 860, 380
        pts = [(x, y)]
        for i in range(9): x += rnd.uniform(-35, 50); y += 36; pts.append((x, y))
        n = max(2, int(len(pts) * k)); d.line([(cv.px(a), cv.px(b)) for a, b in pts[:n]], fill=alpha_col(BG, fo), width=max(2, cv.px(9)))
    return img

def sc_split(cv, t, dur, left, right, ltitle, rtitle, mid="vs"):
    img = cv.new().convert("RGBA"); fo = 1 - ein(t, dur - 0.35, 0.35)
    for x, k, nm, at in ((560, left, ltitle, 0), (1360, right, rtitle, .35)):
        e = ein(t, at, .6); draw_phone(cv, img, x, 520 + (1 - e) * 40, k, .82, e * fo,
                                        lcd_text(["MENÚ"]) if k in ("3310", "1100") else None)
        text(cv, img, (x, 930), nm, "b", 42, TX, e * fo)
    text(cv, img, (960, 520), mid, "gi", 70, DIM, ein(t, .6) * fo)
    return img

def sc_blackline(cv, t, dur, s, col=TX):
    img = Image.new("RGBA", (cv.W, cv.H), (5, 6, 8, 255)); fo = 1 - ein(t, dur - 0.3, 0.3)
    text(cv, img, (960, 540), s, "b", 70, col, ein(t, .15, .5) * fo)
    return img

def sc_words(cv, t, dur, words, title=None, every=0.45):
    """Palabras que entran de a una, alineadas al centro (enumeraciones)."""
    img = cv.new().convert("RGBA"); fo = 1 - ein(t, dur - 0.35, 0.35)
    if title: text(cv, img, (960, 260), title, "m", 34, ACC, ein(t, 0) * fo)
    n = len(words); y0 = 540 - (n - 1) * 52
    for i, w in enumerate(words):
        e = ein(t, 0.2 + i * every, .35); last = i == n - 1
        text(cv, img, (960, y0 + i * 104), w, "b", 78 if not last else 84, ACC if last else TX, e * fo, dy=(1 - e) * 18)
    return img

def sc_flow(cv, t, dur, a, b, strike=None, title=None):
    """A → B, con una opción tachada debajo (decisiones)."""
    img = cv.new().convert("RGBA"); d = ImageDraw.Draw(img); fo = 1 - ein(t, dur - 0.35, 0.35)
    if title: text(cv, img, (960, 250), title, "m", 34, DIM, ein(t, 0) * fo)
    fs = 80 if max(text_w(cv, a, "b", 80), text_w(cv, b, "b", 80)) < 640 else 64
    e1 = ein(t, 0.1); text(cv, img, (820, 480), a, "b", fs, DIM, e1 * fo, anchor="rm")
    k = ein(t, 0.5, .5); d.line((cv.px(860), cv.px(480), cv.px(860 + 200 * k), cv.px(480)), fill=alpha_col(ACC, fo), width=max(2, cv.px(6)))
    if k > .95: d.polygon([(cv.px(1075), cv.px(480)), (cv.px(1045), cv.px(462)), (cv.px(1045), cv.px(498))], fill=alpha_col(ACC, fo))
    e2 = ein(t, 0.9); text(cv, img, (1110, 480), b, "b", fs, TX, e2 * fo, anchor="lm")
    if strike:
        e3 = ein(t, 1.4); text(cv, img, (960, 720), strike, "b", 64, DIM, e3 * fo)
        ks = ein(t, 1.9, .3); w = text_w(cv, strike, "b", 64) + 40
        if ks > 0: d.line((cv.px(960 - w / 2), cv.px(720), cv.px(960 - w / 2 + w * ks), cv.px(720)), fill=alpha_col(RED, fo), width=max(2, cv.px(7)))
    return img

def sc_drawer(cv, t, dur, label="Prototipo táctil · 2004"):
    img = cv.new().convert("RGBA"); d = ImageDraw.Draw(img); fo = 1 - ein(t, dur - 0.35, 0.35)
    # cajón visto de frente: el teléfono baja y el frente sube para taparlo
    rrect(d, cv, (560, 560, 1360, 900), 8, fill=alpha_col((44, 38, 32), fo))
    rrect(d, cv, (920, 690, 1000, 712), 6, fill=alpha_col((160, 150, 135), fo))
    k = ein(t, 0.9, .7)
    draw_phone(cv, img, 960, 380 + k * 260, "smart", 0.55, fo * (1 - k * .9))
    rrect(d2 := ImageDraw.Draw(img), cv, (560, 560, 1360, 900), 8, fill=alpha_col((44, 38, 32), fo * k))
    rrect(d2, cv, (920, 690, 1000, 712), 6, fill=alpha_col((160, 150, 135), fo * k))
    text(cv, img, (960, 980), label, "m", 34, DIM, ein(t, 0) * fo)
    stamp_on(cv, img, t - 1.7, "RECHAZADO", fo, xy=(1380, 360))
    return img

def sc_antenna(cv, t, dur, title="Nokia hoy: redes y 5G", sub="compró Alcatel-Lucent en 2016"):
    img = cv.new().convert("RGBA"); d = ImageDraw.Draw(img); fo = 1 - ein(t, dur - 0.35, 0.35)
    e = ein(t, 0, .6); cx = 600; col = alpha_col((200, 205, 212), e * fo); w = max(2, cv.px(6))
    d.line((cv.px(cx - 120), cv.px(950), cv.px(cx), cv.px(250)), fill=col, width=w)
    d.line((cv.px(cx + 120), cv.px(950), cv.px(cx), cv.px(250)), fill=col, width=w)
    for y in range(350, 950, 100):
        k = (y - 250) / 700 * 120
        d.line((cv.px(cx - k), cv.px(y), cv.px(cx + k), cv.px(y + 100 - 2)), fill=col, width=max(1, w // 2))
    for side in (-1, 1):
        rrect(d, cv, (cx + side * 40 - 18, 280, cx + side * 40 + 18, 420), 6, fill=alpha_col((230, 232, 236), e * fo))
    for r in range(3):  # ondas
        k = ((t * 0.8 + r / 3) % 1.0); rad = 60 + k * 420
        d.arc((cv.px(cx - rad), cv.px(330 - rad), cv.px(cx + rad), cv.px(330 + rad)), -40, 40, fill=alpha_col(ACC, (1 - k) * fo), width=max(2, cv.px(5)))
    e2 = ein(t, .4); text(cv, img, (1130, 520), title, "b", 66, TX, e2 * fo, anchor="lm", dy=(1 - e2) * 14)
    text(cv, img, (1134, 600), sub, "m", 34, DIM, ein(t, .7) * fo, anchor="lm")
    return img

def sc_cam(cv, t, dur, frame):
    """Toma de cámara con borde negro fino y viñeta: solo para reacciones."""
    img = frame.convert("RGBA").resize((cv.W, cv.H))
    return img

def tracked(cv, img, xy, s, font, size, col, a, track=0.15):
    """Texto con espaciado entre letras (PIL no lo trae)."""
    if a <= 0: return
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay); f = cv.font(font, size)
    x = cv.px(xy[0]); y = cv.px(xy[1]); gap = f.size * track
    for ch in s:
        d.text((x, y), ch, font=f, fill=alpha_col(col, a), anchor="lm"); x += f.getlength(ch) + gap
    img.alpha_composite(lay)

BROLL = os.environ.get("ZK_FOTOS", "06_material_usuario")
_photo_cache = {}
def _load_photo(cv, name):
    k = (name, cv.s)
    if k not in _photo_cache:
        im = Image.open(f"{BROLL}/{name}").convert("RGB")
        # fondo: la misma foto, cubriendo, desenfocada y oscurecida
        r = max(cv.W / im.width, cv.H / im.height) * 1.1
        bg = im.resize((int(im.width * r), int(im.height * r)), Image.BILINEAR)
        bg = bg.crop(((bg.width - cv.W) // 2, (bg.height - cv.H) // 2, (bg.width - cv.W) // 2 + cv.W, (bg.height - cv.H) // 2 + cv.H))
        bg = bg.filter(ImageFilter.GaussianBlur(cv.px(40)))
        bg = Image.blend(bg, Image.new("RGB", bg.size, BG), 0.62)
        # primer plano: entera (contain) en alta para el zoom
        r2 = min(cv.W * 1.12 / im.width, cv.H * 1.12 / im.height)
        fg = im.resize((max(1, int(im.width * r2)), max(1, int(im.height * r2))), Image.LANCZOS)
        cover = abs(im.width / im.height - 16 / 9) < 0.25
        _photo_cache[k] = (bg, fg, cover, im)
    return _photo_cache[k]

def sc_photo(cv, t, dur, file, caption=None, sub=None, credit=None, zoom=(1.0, 1.08), pan=(0, 0)):
    bg, fg, cover, im = _load_photo(cv, file)
    fo = 1 - ein(t, dur - 0.3, 0.3); fi = ein(t, 0, 0.35)
    p = t / max(dur, .1); z = zoom[0] + (zoom[1] - zoom[0]) * p
    if cover:  # foto apaisada: a pantalla completa
        r = max(cv.W / im.width, cv.H / im.height) * z
        big = im.resize((int(im.width * r), int(im.height * r)), Image.BILINEAR)
        ox = (big.width - cv.W) // 2 + int(pan[0] * cv.W * p); oy = (big.height - cv.H) // 2 + int(pan[1] * cv.H * p)
        frame = big.crop((ox, oy, ox + cv.W, oy + cv.H))
    else:
        frame = bg.copy()
        s = z * 0.80; f2 = fg.resize((int(fg.width * s), int(fg.height * s)), Image.BILINEAR)
        frame.paste(f2, ((cv.W - f2.width) // 2, (cv.H - f2.height) // 2))
    img = (frame if CROSSFADE else Image.blend(Image.new("RGB", frame.size, BG), frame, fi * fo)).convert("RGBA")
    if caption:  # rótulo editorial: bajada en versalitas espaciadas + nombre, sin barras ni cajas
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
        sd.rectangle((0, cv.px(820), cv.W, cv.H), fill=(0, 0, 0, 110)); img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(cv.px(70))))
        e = ein(t, 0.35) * fo
        if sub: tracked(cv, img, (110, 900), sub.upper(), "m", 34, (220, 222, 226), e, 0.12)
        text(cv, img, (108, 968), caption, "b", 52, TX, e, anchor="lm", dy=(1 - e) * 8)
    if credit: text(cv, img, (1860, 1046), credit, "m", 22, (200, 200, 200), 0.85 * fo * fi, anchor="rm")
    return img

def sc_collage(cv, t, dur, files, labels=None, title=None):
    """Fotos reales en columnas que entran escalonadas (alineación de productos)."""
    img = cv.new().convert("RGBA"); fo = 1 - ein(t, dur - 0.35, 0.35)
    n = len(files); colw = 1640 / n; top = 200 if title else 140
    if title: text(cv, img, (960, 120), title, "b", 46, TX, ein(t, 0) * fo)
    for i, f in enumerate(files):
        _, _, _, im = _load_photo(cv, f)
        e = ein(t, 0.15 + i * 0.18, .5); bw, bh = cv.px(colw - 40), cv.px(720)
        r = min(bw / im.width, bh / im.height); ph = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.BILINEAR)
        ph = Image.blend(Image.new("RGB", ph.size, BG), ph, e * fo)
        cx = cv.px(140 + colw * (i + .5)); cy = cv.px(top + 360) + int((1 - e) * cv.px(30))
        img.paste(ph, (cx - ph.width // 2, cy - ph.height // 2))
        if labels: tracked(cv, img, (140 + colw * (i + .5) - text_w(cv, labels[i].upper(), "m", 22) * 0.6, top + 770), labels[i].upper(), "m", 22, DIM, e * fo, 0.15)
    return img

def sc_sequence(cv, t, dur, files, labels=None, subs=None):
    """Montaje de fotos a pantalla completa con cortes secos (en vez de collage)."""
    n = len(files); d = dur / n; i = min(n - 1, int(t / d)); tt = t - i * d
    return sc_photo(cv, tt + (0.4 if i else 0), d + (0.4 if i else 0) + (0 if i == n - 1 else 9), files[i],
                    caption=labels[i] if labels else None, sub=subs[i] if subs else None, zoom=(1.0, 1.05))

def sc_snakescreen(cv, t, dur, label="Snake"):
    """Pantalla LCD a cuadro completo con el Snake jugándose (pixel art, no un dibujo de teléfono)."""
    img = Image.new("RGBA", (cv.W, cv.H), LCD + (255,)); d = ImageDraw.Draw(img); fo = 1 - ein(t, dur - 0.3, 0.3)
    cols, rows = 48, 27; cw = cv.W / cols; ch = cv.H / rows
    for c in range(cols):  # grilla de píxeles del LCD, muy sutil
        d.line((c * cw, 0, c * cw, cv.H), fill=(140, 166, 84, 255))
    for r in range(rows):
        d.line((0, r * ch, cv.W, r * ch), fill=(140, 166, 84, 255))
    path = [(6 + i, 14) for i in range(30)] + [(35, 14 - i) for i in range(1, 8)] + [(35 - i, 7) for i in range(1, 25)] + [(11, 7 + i) for i in range(1, 7)]
    head = int(t * 9) % len(path); L = 9 + int(t * 1.2)
    for k in range(L):
        c, r = path[(head - k) % len(path)]
        d.rectangle((c * cw + 2, r * ch + 2, (c + 1) * cw - 2, (r + 1) * ch - 2), fill=LCD_D)
    fc, fr = path[(head + 12) % len(path)]
    d.rectangle((fc * cw + cw * .25, fr * ch + ch * .25, (fc + .75) * cw, (fr + .75) * ch), fill=LCD_D)
    d.rectangle((0, 0, cv.W, ch * 2), fill=LCD_D)
    text(cv, img, (60, 54), f"{int(t * 7) * 10:04d}", "b", 40, LCD, 1, anchor="lm")
    if fo < 1: img = Image.blend(Image.new("RGBA", img.size, BG + (255,)), img, fo)
    return img


# ---------------------------------------------------------------- clips de video (autos)
import subprocess as _sp
CLIPS = os.environ.get("ZK_CLIPS", "06_material_usuario/broll_oficial")
_procs = {}   # varios decodificadores a la vez (para fundidos entre clips)
_last = {}
def _clip_open(cv, file, ss, key, vf=None):
    if key in _procs: _procs[key].kill()
    vf = vf or f"scale={cv.W}:{cv.H}:force_original_aspect_ratio=increase,crop={cv.W}:{cv.H},fps=30"
    _procs[key] = _sp.Popen(["ffmpeg", "-v", "error", "-ss", f"{ss:.2f}", "-i", file if ":" in file else f"{CLIPS}/{file}", "-an", "-vf", vf,
                             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=_sp.PIPE)
    while len(_procs) > 3:
        k0 = next(iter(_procs)); _procs.pop(k0).kill(); _last.pop(k0, None)
def _clip_frame(cv, file, ss, key, vf=None):
    if key not in _procs: _clip_open(cv, file, ss, key, vf)
    n = cv.W * cv.H * 3; raw = _procs[key].stdout.read(n)
    if len(raw) < n:  # se terminó el clip: vuelve a arrancar desde ss
        _clip_open(cv, file, ss, key, vf); raw = _procs[key].stdout.read(n)
    if len(raw) == n: _last[key] = Image.frombytes("RGB", (cv.W, cv.H), raw)
    return _last.get(key) or Image.new("RGB", (cv.W, cv.H), BG)

def _darken(img, k):
    return Image.blend(img, Image.new("RGB", img.size, (6, 8, 11)), k) if k > 0 else img

def sc_clip(cv, t, dur, file, ss=0.0, caption=None, sub=None, big=None, bigsub=None, bigcol=None, dark=None, key=None):
    """Clip de video a pantalla completa. Opcional: rótulo editorial (caption/sub) o número/palabra grande (big)."""
    fr = _clip_frame(cv, file, ss, key or (file, ss, round(dur, 2)))
    fi = ein(t, 0, 0.18); fo = 1 - ein(t, dur - 0.18, 0.18)
    k = dark if dark is not None else (0.64 if big else 0.0)
    img = (_darken(fr, k * ein(t, 0.1, 0.4)) if CROSSFADE else Image.blend(Image.new("RGB", fr.size, BG), _darken(fr, k * ein(t, 0.1, 0.4)), max(fi, 0.0) * fo)).convert("RGBA")
    if big:
        e = ein(t, 0.15, 0.5)
        fs = 320 if len(big) <= 4 else (220 if len(big) <= 10 else 150)
        lines = wrap(cv, big, "b", fs, 1700); lh = int(fs * 1.12); y0 = 520 - (len(lines) - 1) * lh / 2
        for i, l in enumerate(lines): text(cv, img, (960, y0 + i * lh), l, "b", fs, bigcol or TX, e * fo, dy=(1 - e) * 24)
        if bigsub: e2 = ein(t, 0.5); text(cv, img, (960, y0 + (len(lines) - 1) * lh + fs * 0.62 + 40), bigsub, "m", 44, (225, 226, 230), e2 * fo, dy=(1 - e2) * 12)
    if caption:
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
        sd.rectangle((0, cv.px(820), cv.W, cv.H), fill=(0, 0, 0, 120)); img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(cv.px(70))))
        e = ein(t, 0.35) * fo
        if sub: tracked(cv, img, (110, 900), sub.upper(), "m", 34, (220, 222, 226), e, 0.12)
        text(cv, img, (108, 968), caption, "b", 52, TX, e, anchor="lm", dy=(1 - e) * 8)
    return img

def sc_versus(cv, t, dur, a, b, la, lb, file=None, ss=0.0, title=None):
    """Dos números grandes comparados (A arriba en ámbar, B abajo), sobre clip oscurecido o fondo."""
    base = _darken(_clip_frame(cv, file, ss, (file, ss, "vs", round(dur, 2))), 0.72) if file else cv.new()
    img = base.convert("RGBA"); fo = 1 - ein(t, dur - 0.25, 0.25)
    if title: text(cv, img, (960, 190), title, "m", 38, (225, 226, 230), ein(t, 0) * fo)
    e1 = ein(t, 0.1, 0.5); text(cv, img, (960, 390), a, "b", 150, ACC, e1 * fo, dy=(1 - e1) * 20)
    text(cv, img, (960, 500), la, "m", 40, TX, e1 * fo)
    text(cv, img, (960, 610), "vs", "gi", 64, DIM, ein(t, 0.6) * fo)
    e2 = ein(t, 0.9, 0.5); text(cv, img, (960, 760), b, "b", 120, TX, e2 * fo, dy=(1 - e2) * 20)
    text(cv, img, (960, 860), lb, "m", 40, DIM, e2 * fo)
    return img

def sc_equation(cv, t, dur, parts, result, file=None, ss=0.0, sub=None):
    """«MOTOR + OLA = MOTOROLA»: piezas que entran de a una y el resultado en ámbar."""
    base = _darken(_clip_frame(cv, file, ss, (file, ss, "eq", round(dur, 2))), 0.7) if file else cv.new()
    img = base.convert("RGBA"); fo = 1 - ein(t, dur - 0.25, 0.25)
    toks = []
    for i, p_ in enumerate(parts):
        if i: toks.append(("+", DIM))
        toks.append((p_, TX))
    widths = [text_w(cv, s_, "b", 110) for s_, _ in toks]; gap = 50; tot = sum(widths) + gap * (len(toks) - 1); x = 960 - tot / 2
    for i, ((s_, c_), w_) in enumerate(zip(toks, widths)):
        e = ein(t, 0.15 + i * 0.25, 0.4); text(cv, img, (x + w_ / 2, 420), s_, "b", 110, c_, e * fo, dy=(1 - e) * 16); x += w_ + gap
    e = ein(t, 0.25 + len(toks) * 0.25, 0.5)
    text(cv, img, (960, 600), "=", "b", 90, DIM, e * fo)
    text(cv, img, (960, 760), result, "b", 170, ACC, e * fo, dy=(1 - e) * 20)
    if sub: text(cv, img, (960, 900), sub, "m", 38, (225, 226, 230), ein(t, 1.6) * fo)
    return img


# ---------------------------------------------------------------- Moto G: producto recortado y datos (nuevo)
CUT = os.environ.get("ZK_RECORTES", "02_broll/cut")          # PNG de productos recortados
GLOW = (36, 150, 190)   # foco cian (serie «historia»)
_cut_cache = {}
def _cut(cv, name, h):
    k = (name, h, cv.s)
    if k not in _cut_cache:
        im = Image.open(f"{CUT}/{name}").convert("RGBA"); bb = im.getbbox(); im = im.crop(bb)
        r = cv.px(h) / im.height; _cut_cache[k] = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
    return _cut_cache[k]

def _glow_bg(cv, cx, cy, rad, col=GLOW, k=0.55):
    img = cv.new()
    y, x = np.mgrid[0:cv.H, 0:cv.W].astype(np.float32)
    d = np.sqrt((x - cv.px(cx)) ** 2 + (y - cv.px(cy)) ** 2) / cv.px(rad)
    g = np.clip(1 - d, 0, 1) ** 2 * k
    a = np.asarray(img, np.float32) * (1 - g[..., None]) + np.array(col, np.float32) * g[..., None]
    return Image.fromarray(a.astype(np.uint8)).convert("RGBA")
_glow_cache = {}
def glow_bg(cv, cx, cy, rad, col=GLOW, k=0.55):
    key = (cx, cy, rad, col, k, cv.s)
    if key not in _glow_cache: _glow_cache[key] = _glow_bg(cv, cx, cy, rad, col, k)
    return _glow_cache[key].copy()

def put_cut(cv, img, name, cx, cy, h, a=1.0, t=0.0, float_=True, shadow=True):
    ph = _cut(cv, name, round(h / 10) * 10)
    if float_: cy = cy + 7 * math.sin(t * 1.1)
    if shadow:
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(sh); w = ph.width * 0.42 / cv.s
        d.ellipse((cv.px(cx - w), cv.px(cy + h / 2 + 18), cv.px(cx + w), cv.px(cy + h / 2 + 44)), fill=(0, 0, 0, int(150 * a)))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(cv.px(14))))
    if a <= 0: return
    if a < 1: ph = ph.copy(); ph.putalpha(ph.getchannel("A").point(lambda v: int(v * a)))
    img.alpha_composite(ph, (int(cv.px(cx) - ph.width / 2), int(cv.px(cy) - ph.height / 2)))

def _rev(reveal, i, default):
    return reveal[i] if reveal and i < len(reveal) and reveal[i] is not None else default

def sc_hero(cv, t, dur, file, name=None, kicker=None, rows=None, reveal=None, side="left", h=800, col=GLOW, sub=None):
    """Producto recortado sobre negro con foco de color, flotando, y datos que entran al terminar de decirlos."""
    px_ = 640 if side == "left" else (1280 if side == "right" else 960)
    img = glow_bg(cv, px_, 540, 620, col); fo = 1 - ein(t, dur - 0.3, 0.3)
    e = ein(t, 0, 0.7); z = 1.0 + 0.035 * (t / max(dur, .1))
    put_cut(cv, img, file, px_, 545 + (1 - e) * 50, h * z, e, t)
    tx = 1130 if side == "left" else (200 if side == "right" else None)
    if tx is None:
        if name: e2 = ein(t, 0.3); text(cv, img, (960, 1000), name, "b", 46, TX, e2 * fo)
        return img
    y = 330 if rows else 470
    if kicker: tracked(cv, img, (tx, y - 70), kicker.upper(), "m", 30, (175, 181, 190), ein(t, 0.2) * fo, 0.2)
    if name: e2 = ein(t, 0.3); text(cv, img, (tx - 4, y), name, "b", 84, TX, e2 * fo, anchor="lm", dy=(1 - e2) * 16)
    if sub: e3 = ein(t, 0.55); text(cv, img, (tx, y + 70), sub, "m", 40, (190, 195, 202), e3 * fo, anchor="lm")
    for i, (lab, val) in enumerate(rows or []):
        r0 = _rev(reveal, i, 0.6 + 0.7 * i); er = ein(t, r0, 0.4) * fo; yy = y + 130 + i * 112
        tracked(cv, img, (tx, yy - 28), lab.upper(), "m", 26, (175, 181, 190), er, 0.2)
        text(cv, img, (tx - 2, yy + 22), val, "b", 58, ACC if "US$" in val else TX, er, anchor="lm", dy=(1 - er) * 10)
    return img

_tl_cam = {}
def sc_timeline(cv, t, dur, items, reveal=None, title=None, col=GLOW, key=None):
    """Línea de tiempo de generaciones: cada celular (recortado) entra con su año; la cámara acompaña hacia la derecha."""
    n = len(items); gap = min(330, 1480 / max(1, n - 1)); total = gap * (n - 1)
    shown = [_rev(reveal, i, 0.02 + i * (dur - 1.2) / max(1, n)) for i in range(n)]
    last = max([i for i in range(n) if t >= shown[i]] or [0])
    target = min(max(0.0, last * gap - 1920 + 520), max(0.0, total - 1920 + 520))
    cam = _tl_cam.get(key, 0.0); cam += (target - cam) * 0.07; _tl_cam[key] = cam
    img = glow_bg(cv, 960, 470, 900, col, 0.35); fo = 1 - ein(t, dur - 0.3, 0.3)
    if title: text(cv, img, (960, 110), title, "b", 44, TX, ein(t, 0) * fo)
    d = ImageDraw.Draw(img); x0 = 260 - cam
    d.line((cv.px(x0 - 200), cv.px(800), cv.px(x0 + total + 200), cv.px(800)), fill=alpha_col(DIM, .5 * fo), width=max(1, cv.px(2)))
    for i, (yr, f, lab) in enumerate(items):
        e = ein(t, shown[i], 0.5) * fo; cx = x0 + i * gap
        if cx < -300 or cx > 2220 or e <= 0: continue
        iw, ih = Image.open(f"{CUT}/{f}").size
        put_cut(cv, img, f, cx, 520 + (1 - e) * 40, min(430, (gap - 40) * ih / iw), e, t + i, shadow=False)
        d = ImageDraw.Draw(img)
        d.ellipse((cv.px(cx - 7), cv.px(793), cv.px(cx + 7), cv.px(807)), fill=alpha_col(ACC if i == last else TX, e))
        text(cv, img, (cx, 862), str(yr), "gi", 52, TX, e)
        text(cv, img, (cx, 925), lab, "m", 28, DIM, e)
    return img

def sc_drop(cv, t, dur, a=12500, b=2910, la="Google la compra", lb="Lenovo la compra", ya="2012", yb="2014", unit="millones de dólares", reveal=None, note=None):
    """Dos barras: lo que pagó Google y lo que cobró al venderla. La segunda cae en rojo."""
    img = cv.new().convert("RGBA"); fo = 1 - ein(t, dur - 0.3, 0.3)
    ra, rb = _rev(reveal, 0, 0.2), _rev(reveal, 1, 1.6)
    base = 820; hmax = 520; bw = 300
    for i, (v, lab, yr, c, r0) in enumerate([(a, la, ya, TX, ra), (b, lb, yb, RED, rb)]):
        d = ImageDraw.Draw(img)
        cx = 700 + i * 520; e = ease((t - r0) / 1.1) if t > r0 else 0
        hh = hmax * v / a * e
        if e > 0: d.rectangle((cv.px(cx - bw / 2), cv.px(base - hh), cv.px(cx + bw / 2), cv.px(base)), fill=alpha_col(c, 0.92 * fo * min(1, e * 3)))
        val = f"{int(round(v * e / 10) * 10):,}".replace(",", ".")
        text(cv, img, (cx, base - hh - 60), "US$ " + val, "b", 64, c, min(1, e * 3) * fo)
        text(cv, img, (cx, base + 60), yr, "gi", 46, TX, ein(t, r0) * fo)
        text(cv, img, (cx, base + 118), lab, "m", 30, DIM, ein(t, r0) * fo)
    text(cv, img, (960, 120), unit.upper(), "m", 24, DIM, ein(t, 0) * fo)
    if note: e = ein(t, _rev(reveal, 2, rb + 1.2), 0.5); text(cv, img, (1250, 560), note, "gi", 50, RED, e * fo, anchor="lm")
    return img

def _person(d, cv, cx, cy, sc, col):
    d.ellipse((cv.px(cx - 22 * sc), cv.px(cy - 92 * sc), cv.px(cx + 22 * sc), cv.px(cy - 48 * sc)), fill=col)
    d.rounded_rectangle((cv.px(cx - 36 * sc), cv.px(cy - 38 * sc), cv.px(cx + 36 * sc), cv.px(cy + 60 * sc)), radius=cv.px(26 * sc), fill=col)

def sc_people(cv, t, dur, on=4, total=10, big="38,5 %", label="de los celulares vendidos en Argentina", sub=None, reveal=None, credit=None, title=None):
    """«Casi cuatro de cada diez»: diez personas, se prenden las de Motorola."""
    img = glow_bg(cv, 960, 520, 900, GLOW, 0.25); fo = 1 - ein(t, dur - 0.3, 0.3)
    if title: e0 = ein(t, 0); text(cv, img, (960, 170), title, "b", 52, TX, e0 * fo, dy=(1 - e0) * 12)
    d = ImageDraw.Draw(img)
    r0 = _rev(reveal, 0, 0.4)
    for i in range(total):
        cx = 960 + (i - (total - 1) / 2) * 150
        e = ein(t, r0 + i * 0.45, 0.3) if i < on else 0
        c = tuple(int(DIM[k] * 0.7 * (1 - e) + ACC[k] * e) for k in range(3))
        _person(d, cv, cx, 420, 1.25, alpha_col(c, fo))
    eb = ein(t, _rev(reveal, 1, r0 + on * 0.45), 0.5)
    text(cv, img, (960, 700), big, "b", 150, ACC, eb * fo, dy=(1 - eb) * 18)
    text(cv, img, (960, 820), label, "m", 40, TX, eb * fo)
    if sub: text(cv, img, (960, 880), sub, "m", 30, DIM, ein(t, _rev(reveal, 1, r0 + on * 0.45) + 0.4) * fo)
    if credit: text(cv, img, (1860, 1040), credit, "m", 26, (170, 170, 170), 0.8 * fo, anchor="rm")
    return img

def sc_compare(cv, t, dur, left, right, lname, rname, rows, reveal=None, lyear=None, ryear=None):
    """Moto G 2013 vs G06: los dos recortados a los costados y los datos en el medio; el que gana va en ámbar."""
    img = glow_bg(cv, 960, 520, 1100, GLOW, 0.22); fo = 1 - ein(t, dur - 0.3, 0.3)
    e = ein(t, 0, 0.6)
    for f_, x_, tt_ in ((left, 330, t), (right, 1590, t + 1.3)):
        iw, ih = Image.open(f"{CUT}/{f_}").size; put_cut(cv, img, f_, x_, 500 + (1 - e) * 40, min(600, 470 * ih / iw), e, tt_)
    text(cv, img, (330, 890), lname, "b", 44, TX, e * fo); text(cv, img, (1590, 890), rname, "b", 44, TX, e * fo)
    if lyear: text(cv, img, (330, 945), lyear, "gi", 34, DIM, e * fo)
    if ryear: text(cv, img, (1590, 945), ryear, "gi", 34, DIM, e * fo)
    y0 = 300
    for i, (lab, lv, rv, win) in enumerate(rows):
        er = ein(t, _rev(reveal, i, 0.6 + i * 0.8), 0.4) * fo; yy = y0 + i * 150
        tracked(cv, img, (960 - text_w(cv, lab.upper(), "m", 28) * 0.6, yy - 44), lab.upper(), "m", 28, (175, 181, 190), er, 0.2)
        text(cv, img, (900, yy + 20), lv, "b", 54, ACC if win == "l" else (TX if win == "=" else (120, 126, 136)), er, anchor="rm")
        text(cv, img, (960, yy + 20), "·", "b", 54, DIM, er)
        text(cv, img, (1020, yy + 20), rv, "b", 54, ACC if win == "r" else (TX if win == "=" else (120, 126, 136)), er, anchor="lm")
    return img


def _fit_vf(cv, w, h):
    """El clip entra completo en w×h, centrado sobre una copia desenfocada y oscura de sí mismo (para verticales y archivo)."""
    W, H = cv.W, cv.H; w, h = cv.px(w) // 2 * 2, cv.px(h) // 2 * 2
    return (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:3,eq=brightness=-0.32:saturation=0.7[bg];"
            f"[b]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,fps=30")

def sc_vertical(cv, t, dur, file, ss=0.0, caption=None, sub=None, key=None, crop_top=None):
    """Clip vertical del celular (videos propios del canal) centrado sobre su propio fondo desenfocado."""
    vf = _fit_vf(cv, 1920, 1080)
    if crop_top:   # desenfoca la franja de subtítulos quemados del video viejo (sin recortar el cuadro)
        y0, y1 = crop_top
        vf = (f"split[o][c];[c]crop=iw:ih*{y1 - y0:.3f}:0:ih*{y0:.3f},boxblur=18:2[bl];[o][bl]overlay=0:H*{y0:.3f},") + vf
    fr = _clip_frame(cv, file, ss, key or (file, ss, "v"), vf)
    img = fr.convert("RGBA"); fo = 1 - ein(t, dur - 0.18, 0.18)
    if caption:
        e = ein(t, 0.35) * fo
        if sub: tracked(cv, img, (110, 900), sub.upper(), "m", 34, (220, 222, 226), e, 0.12)
        text(cv, img, (108, 968), caption, "b", 52, TX, e, anchor="lm", dy=(1 - e) * 8)
    return img

def sc_archive(cv, t, dur, file, ss=0.0, label=None, key=None, big=None, bigsub=None):
    """Material de archivo (comercial viejo en baja): más chico, con rótulo de fecha, como en un documental."""
    fr = _clip_frame(cv, file, ss, key or (file, ss, "arch"), _fit_vf(cv, 1500, 844))
    img = fr.convert("RGBA"); fo = 1 - ein(t, dur - 0.25, 0.25)
    if label: tracked(cv, img, (210, 1010), label.upper(), "m", 22, (215, 216, 220), ein(t, 0.3) * fo, 0.2)
    if big:
        sh = Image.new("RGBA", img.size, (0, 0, 0, int(150 * ein(t, 0.1, 0.4)))); img.alpha_composite(sh)
        e = ein(t, 0.2, 0.5); text(cv, img, (960, 500), big, "b", 170 if len(big) < 12 else 120, TX, e * fo, dy=(1 - e) * 20)
        if bigsub: text(cv, img, (960, 630), bigsub, "m", 44, (225, 226, 230), ein(t, 0.5) * fo)
    return img


def sc_names(cv, t, dur, words, title=None, every=0.3, said=5, reveal=None):
    """Los nombres de los Moto G se multiplican en una grilla: los que se nombran en blanco grande, el resto en gris."""
    img = glow_bg(cv, 960, 560, 900, GLOW, 0.2); fo = 1 - ein(t, dur - 0.3, 0.3)
    if title: text(cv, img, (960, 150), title, "b", 52, TX, ein(t, 0) * fo)
    cols = 5; rows = (len(words) + cols - 1) // cols; t0 = _rev(reveal, 0, 0.3)
    for i, w in enumerate(words):
        last = _rev(reveal, said - 1, t0 + (said - 1) * every) if reveal and len(reveal) >= said else t0 + (said - 1) * every
        ti = (max(0.0, _rev(reveal, i, t0 + i * every) - 0.4) if reveal and len(reveal) >= said else t0 + i * every) if i < said else last + 0.2 + (i - said) * 0.15
        e = ein(t, ti, 0.35) * fo
        cx = 960 + (i % cols - (cols - 1) / 2) * 330; cy = 360 + (i // cols) * 170
        text(cv, img, (cx, cy), w, "b", 100 if i < said else 80, TX if i < said else (110, 118, 130), e, dy=(1 - e) * 20)
    return img

def sc_trio(cv, t, dur, files, labels, title=None, sub=None, h=560):
    """Tres celulares recortados en fila (la comparativa), entrando escalonados."""
    img = glow_bg(cv, 960, 560, 1000, GLOW, 0.3); fo = 1 - ein(t, dur - 0.3, 0.3)
    if title: e = ein(t, 0); text(cv, img, (960, 120), title, "b", 56, TX, e * fo, dy=(1 - e) * 12)
    if sub: text(cv, img, (960, 185), sub, "m", 32, DIM, ein(t, 0.3) * fo)
    n = len(files)
    for i, (f, lab) in enumerate(zip(files, labels)):
        e = ein(t, 0.2 + i * 0.25, 0.5) * fo; cx = 960 + (i - (n - 1) / 2) * 580
        iw, ih = Image.open(f"{CUT}/{f}").size; hh = min(h, 500 * ih / iw)   # que entre en una caja de 500 × h
        put_cut(cv, img, f, cx, 580 + (1 - e) * 40, hh, e, t + i * 1.7)
        text(cv, img, (cx, 960), lab, "b", 44, TX, e)
    return img


def sc_camz(cv, t, dur, file, ss=0.0, z=1.0, key=None, flip=False, cx=0.5):
    """Toma a cámara sincronizada con la voz. z > 1 = plano apretado (alterna en cada corte, estilo jump cut). flip = espejada.
    cx = dónde está la nariz en el primer cuadro (fracción del ancho): el recorte la deja en el centro."""
    W, H = cv.W, cv.H
    x = f"min(max(iw*{cx:.4f}-iw/{z:.3f}/2\\,0)\\,iw-iw/{z:.3f})"   # las comas de la expresión van escapadas: si no, ffmpeg corta el filtro y el plano sale negro
    vf = f"crop=iw/{z:.3f}:ih/{z:.3f}:{x}:(ih-ih/{z:.3f})*0.35,scale={W}:{H},fps=30" + (",hflip" if flip else "")
    return _clip_frame(cv, file, ss, key or (file, round(ss, 2), "cam"), vf).convert("RGBA")
