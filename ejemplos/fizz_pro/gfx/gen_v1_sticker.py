"""Gráficos superpuestos del unboxing Redragon Fizz Pro (10/11/2026), estilo zk_style del canal en modo overlay.
Cada gráfico: PNG 1920x1080 con alfa (cuadro ya asentado) y, si anima, MOV qtrle argb con la entrada, el reposo y
una salida de 0,25 s. Todo se dibuja en capas aparte y se compone con alpha_composite (lección del Carrito, v030).
Uso: python gen_v1_sticker.py [id ...]   (sin argumentos, todos)"""
import os, sys, math, json, subprocess, functools
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "graficos"))   # gfx.py y zk_style.py de la suite
import gfx, zk_style as Z
from gfx import ease
from PIL import Image, ImageDraw, ImageFilter

Z.OVER = True
cv = gfx.Canvas(1.0)
W, H, FPS = 1920, 1080, 30
OUT = Path(os.environ.get("ZK_GFX_OUT", "10_work/gfx"))
FF = os.environ.get("ZK_FFMPEG", "ffmpeg")
THUMB = OUT / "_ref" / "miniatura.jpg"
PANEL = Z.NAVY + (232,)
GLOWS = [(255, 40, 40), (245, 166, 35), (40, 200, 255), (220, 60, 255), (255, 40, 40)]


def layer(w=W, h=H): return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def card_bg(w, h, r=30):
    """Panel oscuro translúcido con borde negro y sombra corrida (misma familia que la etiqueta de la miniatura)."""
    m = 34; L = layer(w + 2 * m, h + 2 * m)
    sh = layer(w + 2 * m, h + 2 * m); ImageDraw.Draw(sh).rounded_rectangle((m + 10, m + 14, m + w + 10, m + h + 14), r, fill=(0, 0, 0, 120))
    L.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
    top = layer(w + 2 * m, h + 2 * m); ImageDraw.Draw(top).rounded_rectangle((m, m, m + w, m + h), r, fill=PANEL, outline=Z.INK + (255,), width=5)
    L.alpha_composite(top)
    return L, m


def put(img, L, cx, cy, t, start=0.0, rot=-1.5):
    p = (t - start) / 0.4
    if p > 0: Z._place(cv, img, L, cx, cy, Z._back(p), rot, min(1, p * 2))


def shape(w, h, fn):
    """Dibuja con ImageDraw en una capa propia y la devuelve (nunca directo sobre el cuadro con alfa)."""
    L = layer(w, h); fn(ImageDraw.Draw(L)); return L


def ftext(d, xy, s, spec, size, fill, anchor="mm", stroke=0, sfill=Z.INK):
    d.text(xy, s, font=Z._f(spec, size), fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=sfill)


def text_left(img, x, y, s, size, fill, t, start, font=None, rot=-2.0):
    """Z.text centra; esto lo alinea a la izquierda en x."""
    f = Z._f(font or Z.IMPACT, size); w = ImageDraw.Draw(img).textlength(s, font=f)
    Z.text(cv, img, (x + w / 2, y), s, size, fill, t, start, rot=rot, font=font)


# ---------------------------------------------------------------------------------------------------- 1. 60 %
U = 34
def _kb_keys():
    """Teclado completo en unidades: (x, y, w, h, zona). zona: main / frow / nav / num."""
    k = []
    rows = [[1] * 13 + [2], [1.5] + [1] * 12 + [1.5], [1.75] + [1] * 11 + [2.25], [2.25] + [1] * 10 + [2.75], [1.25] * 3 + [6.25] + [1.25] * 4]
    for r, ws in enumerate(rows):
        x = 0
        for w in ws: k.append((x, 1.5 + r, w, 1, "main")); x += w
    x = 0
    for w, gap in [(1, 1)] + [(1, 0)] * 3 + [(1, .5)] + [(1, 0)] * 3 + [(1, .5)] + [(1, 0)] * 3 + [(1, 0)]:
        k.append((x, 0, w, 1, "frow")); x += w + gap
    for c in range(3):
        k.append((15.5 + c, 0, 1, 1, "nav")); k.append((15.5 + c, 1.5, 1, 1, "nav")); k.append((15.5 + c, 2.5, 1, 1, "nav"))
        k.append((15.5 + c, 5.5, 1, 1, "nav"))
    k.append((16.5, 4.5, 1, 1, "nav"))
    for r in range(5):
        for c in range(4):
            if c == 3 and r in (2, 4): continue          # + y Enter ocupan dos filas
            if r == 4 and c == 1: continue               # el 0 es doble
            w = 2 if (r == 4 and c == 0) else 1; h = 2 if (c == 3 and r in (1, 3)) else 1
            k.append((19 + c, 1.5 + r, w, h, "num"))
    return k
KB = _kb_keys()
ZONES = {"frow": (0, 0, 14.4, 1), "nav": (15.5, 0, 18.5, 6.5), "num": (19, 1.5, 23, 6.5)}


def g60(t):
    img = layer(); cw, ch = 900, 400
    L, m = card_bg(cw, ch); ox, oy = m + 58, m + 44
    strike = {"frow": 0.75, "nav": 1.05, "num": 1.35}; amber_on = 1.75
    keys = layer(*L.size); d = ImageDraw.Draw(keys)
    for (x, y, w, h, z) in KB:
        p = ease((t - 0.15 - 0.012 * (x + y)) / 0.25)
        if p <= 0: continue
        a = p
        if z != "main": a *= 1 - 0.72 * ease((t - strike[z]) / 0.3)
        col = Z.WHITE
        if z == "main" and t >= amber_on: col = Z.AMBER; a *= 1
        box = (ox + x * U + 3, oy + y * U + 3, ox + (x + w) * U - 3, oy + (y + h) * U - 3)
        d.rounded_rectangle(box, 6, outline=col + (int(255 * a),), width=3)
    L.alpha_composite(keys)
    for z, s in strike.items():                       # tachado rojo que se dibuja
        p = ease((t - s) / 0.28)
        if p <= 0: continue
        x0, y0, x1, y1 = ZONES[z]; x0, y0, x1, y1 = ox + x0 * U - 8, oy + y0 * U + 6, ox + x1 * U + 8, oy + y1 * U - 6
        if z == "frow": y0, y1 = oy + 0.5 * U, oy + 0.5 * U
        ln = layer(*L.size); dd = ImageDraw.Draw(ln); xe, ye = x0 + (x1 - x0) * p, y0 + (y1 - y0) * p
        dd.line((x0, y0, xe, ye), fill=Z.INK + (255,), width=18); dd.line((x0, y0, xe, ye), fill=Z.RED + (255,), width=11)
        L.alpha_composite(ln)
    Z.text(cv, L, (m + cw / 2, m + ch - 72), "60 %", 128, Z.AMBER, t, amber_on - 0.05, rot=-2)
    put(img, L, 500, 250, t)
    return img


# ---------------------------------------------------------------------------------------------- 2. switch red
def switch_icon(press):
    s = 170; L = layer(s + 40, s + 40); d = ImageDraw.Draw(L); o = 20
    d.rounded_rectangle((o, o, o + s, o + s), 26, fill=Z.WHITE + (255,))
    d.rounded_rectangle((o + 9, o + 9, o + s - 9, o + s - 9), 20, fill=(34, 34, 40, 255), outline=Z.INK + (255,), width=4)
    d.rounded_rectangle((o + 30, o + 30, o + s - 30, o + s - 30), 14, outline=(90, 90, 100, 255), width=4)
    c = o + s / 2; k = 1 - 0.12 * press; a, b = 44 * k, 11 * k
    d.rounded_rectangle((c - a - 4, c - b - 4, c + a + 4, c + b + 4), 6, fill=Z.INK + (255,)); d.rounded_rectangle((c - b - 4, c - a - 4, c + b + 4, c + a + 4), 6, fill=Z.INK + (255,))
    d.rounded_rectangle((c - a, c - b, c + a, c + b), 5, fill=(230, 30, 36, 255)); d.rounded_rectangle((c - b, c - a, c + b, c + a), 5, fill=(230, 30, 36, 255))
    return L


def gswitch(t):
    img = layer()
    press = max(0.0, math.sin(min(1, max(0, (t - 0.7) / 0.3)) * math.pi))
    put(img, switch_icon(press), 175, 195, t, 0.0, rot=-5)
    text_left(img, 300, 150, "Switch red", 116, Z.AMBER, t, 0.15)
    text_left(img, 304, 258, "menos ruidoso que el blue", 46, Z.WHITE, t, 0.45, font=Z.POP)
    return img


# ---------------------------------------------------------------------------------------------- 3. modos
def icon_dongle(d, cx, cy):
    d.rounded_rectangle((cx - 26, cy - 10, cx + 26, cy + 46), 8, outline=Z.WHITE, width=7)
    d.rectangle((cx - 16, cy + 46, cx + 16, cy + 66), outline=Z.WHITE, width=6)
    for r in (22, 40):
        d.arc((cx - r, cy - 24 - r, cx + r, cy - 24 + r), 220, 320, fill=Z.WHITE, width=7)


def icon_bt(d, cx, cy):
    h = 44; w = 24
    pts = [(cx - w, cy - h / 2), (cx + w, cy + h / 2 - 4), (cx, cy + h + 4), (cx, cy - h - 4), (cx + w, cy - h / 2 + 4), (cx - w, cy + h / 2)]
    d.line(pts, fill=Z.WHITE, width=7, joint="curve")


def icon_cable(d, cx, cy):
    d.rounded_rectangle((cx - 18, cy - 50, cx + 18, cy - 10), 6, outline=Z.WHITE, width=7)
    d.rectangle((cx - 9, cy - 66, cx + 9, cy - 50), fill=Z.WHITE)
    d.rounded_rectangle((cx - 26, cy - 12, cx + 26, cy + 18), 8, fill=Z.WHITE)
    d.line([(cx, cy + 18), (cx, cy + 40), (cx - 30, cy + 64)], fill=Z.WHITE, width=8, joint="curve")


def gmodos(t):
    img = layer()
    for i, (lab, ic) in enumerate([("2.4G", icon_dongle), ("BT", icon_bt), ("Cable", icon_cable)]):
        L, m = card_bg(240, 210, 28); d = ImageDraw.Draw(L)
        ic(d, m + 120, m + 72); ftext(d, (m + 120, m + 168), lab, Z.PRICE, 58, Z.AMBER + (255,), stroke=3)
        put(img, L, 660 + i * 300, 200, t, 0.0 + 0.35 * i, rot=(-3, 1.5, -1.5)[i])
    return img


# ---------------------------------------------------------------------------------------------- 4. Fn + F9
def keycap(label, w, press, glow):
    s = 150; Wd = int(s * w); L = layer(Wd + 80, s + 90); d = ImageDraw.Draw(L); o = 40; dy = 12 * press
    g = layer(*L.size); ImageDraw.Draw(g).rounded_rectangle((o - 6, o + 6, o + Wd + 6, o + s + 22), 26, fill=glow + (200,))
    L.alpha_composite(g.filter(ImageFilter.GaussianBlur(16)))
    d = ImageDraw.Draw(L)
    d.rounded_rectangle((o, o + 10, o + Wd, o + s + 14), 22, fill=(14, 14, 16, 255), outline=Z.INK + (255,), width=4)       # falda
    d.rounded_rectangle((o + 12, o + dy, o + Wd - 12, o + s - 18 + dy), 18, fill=(40, 40, 46, 255), outline=(70, 70, 80, 255), width=3)  # cara
    ftext(d, (o + Wd / 2, o + (s - 18) / 2 + dy), label, Z.PRICE, 62, Z.WHITE + (255,))
    return L


def gfn(t):
    img = layer()
    press = max(0.0, math.sin(min(1, max(0, (t - 0.8) / 0.35)) * math.pi))
    k = min(1, max(0, (t - 0.95) / 1.4)) * (len(GLOWS) - 1); i = int(k); f = k - i; j = min(i + 1, len(GLOWS) - 1)
    glow = tuple(int(GLOWS[i][c] * (1 - f) + GLOWS[j][c] * f) for c in range(3))
    put(img, keycap("Fn", 1.25, press, glow), 230, 190, t, 0.0, rot=-3)
    Z.text(cv, img, (420, 190), "+", 110, Z.AMBER, t, 0.2, rot=0)
    put(img, keycap("F9", 1.0, press, glow), 590, 190, t, 0.3, rot=2)
    Z.text(cv, img, (420, 345), "cambia las luces", 50, Z.WHITE, t, 0.6, rot=-2, font=Z.POP)
    return img


# ---------------------------------------------------------------------------------------------- 5. precio
def gprecio(t):
    img = layer()
    Z.text(cv, img, (470, 95), "precio actual", 48, Z.WHITE, t, 0.3, rot=-2, font=Z.POP)
    Z.tag(cv, img, 470, 225, "$60.000 – $70.000", t=t, start=0.0, scale=0.62, rot=-3)
    return img


# ---------------------------------------------------------------------------------------------- 6. no es publicidad
def gnopubli(t):
    img = layer()
    Z.stamp(cv, img, (960, 140), "NO ES PUBLICIDAD", t, 0.0, size=74, rot=-4)
    Z.text(cv, img, (960, 275), "Lo compré yo", 100, Z.AMBER, t, 0.45, rot=-2)
    return img


# ---------------------------------------------------------------------------------------------- 7. lo malo
def gmalo(t):
    img = layer()
    for i, s in enumerate(["Sin flechas", "Sin F1–F12"]):
        p = (t - 0.5 * i) / 0.35
        if p <= 0: continue
        L = layer(640, 130); d = ImageDraw.Draw(L)
        d.rounded_rectangle((0, 0, 639, 129), 26, fill=(255, 255, 255, 242), outline=Z.INK + (255,), width=5)
        d.ellipse((24, 22, 110, 108), fill=Z.RED + (255,), outline=Z.INK + (255,), width=4)
        d.line((48, 46, 86, 84), fill=Z.WHITE, width=11); d.line((86, 46, 48, 84), fill=Z.WHITE, width=11)
        ftext(d, (140, 65), s, Z.PRICE, 66, Z.INK + (255,), anchor="lm")
        L = L.rotate(-1.5, resample=Image.BICUBIC, expand=True)
        img.alpha_composite(Z._fade(L, ease(p)), (int(60 - 110 * (1 - ease(p))), 70 + i * 160))
    return img


# ---------------------------------------------------------------------------------------------- 8. tiempo real
def gtiempo(t):
    img = layer(); L = layer(470, 120); d = ImageDraw.Draw(L)
    d.rounded_rectangle((8, 8, 462, 112), 52, fill=PANEL, outline=Z.INK + (255,), width=5)
    on = (t % 1.0) < 0.6
    d.ellipse((40, 38, 84, 82), fill=(Z.RED if on else (110, 30, 30)) + (255,))
    ftext(d, (106, 60), "TIEMPO REAL", Z.PRICE, 54, Z.WHITE + (255,), anchor="lm")
    p = t / 0.3
    if p > 0: Z._place(cv, img, L, 290, 105, Z._back(p), 0, min(1, p * 2))
    return img


# ---------------------------------------------------------------------------------------------- 9. títulos de sección
def gsec(name):
    def f(t):
        img = layer(); size = 124
        text_left(img, 70, 150, name, size, Z.AMBER, t, 0.0)
        w = ImageDraw.Draw(img).textlength(name, font=Z._f(Z.IMPACT, size))
        p = ease((t - 0.2) / 0.35)
        if p > 0:
            bar = shape(int(w) + 20, 30, lambda d: (d.rounded_rectangle((0, 0, int((w + 10) * p) + 9, 25), 8, fill=Z.INK + (255,)),
                                                      d.rounded_rectangle((4, 4, int((w + 10) * p) + 5, 21), 6, fill=Z.WHITE + (255,))))
            img.alpha_composite(bar, (82, 230))
        return img
    return f


# ---------------------------------------------------------------------------------------------- 10. tarjeta Cyber Monday
@functools.lru_cache(maxsize=1)
def _card():
    tw, th, sh, b = 512, 288, 112, 10
    C = layer(tw + 2 * b, th + sh + 2 * b); d = ImageDraw.Draw(C)
    d.rounded_rectangle((0, 0, C.width - 1, C.height - 1), 18, fill=Z.WHITE + (255,))
    th_img = Image.open(THUMB).convert("RGBA").resize((tw, th), Image.LANCZOS); C.alpha_composite(th_img, (b, b))
    d.rectangle((b, b + th, b + tw, b + th + sh), fill=(14, 18, 24, 255))
    f = Z._f(Z.POP, 40); y1, y2 = b + th + 34, b + th + 80; x = b + 22
    for s, col in [("Así te ", Z.WHITE), ("ESTAFAN", Z.AMBER), (" en el", Z.WHITE)]:
        d.text((x, y1), s, font=f, fill=col, anchor="lm"); x += d.textlength(s, font=f)
    d.text((b + 22, y2), "CyberMonday 2026", font=f, fill=Z.WHITE, anchor="lm")
    px, py = b + tw - 92, b + th - 64                                                         # botón play, abajo a la derecha
    d.rounded_rectangle((px, py, px + 78, py + 50), 14, fill=(230, 30, 36, 255), outline=Z.WHITE, width=3)
    d.polygon([(px + 30, py + 11), (px + 30, py + 39), (px + 54, py + 25)], fill=Z.WHITE)
    M = 30; O = layer(C.width + 2 * M, C.height + 2 * M)
    s_ = layer(*O.size); ImageDraw.Draw(s_).rounded_rectangle((M + 12, M + 16, M + C.width + 12, M + C.height + 16), 18, fill=(0, 0, 0, 140))
    O.alpha_composite(s_.filter(ImageFilter.GaussianBlur(12))); O.alpha_composite(C, (M, M))
    return O


def gcard(t):
    img = layer(); p = ease(t / 0.45)
    if p > 0:
        L = _card().rotate(-1.5, resample=Image.BICUBIC, expand=True)
        cx = 1612 + 520 * (1 - p); img.alpha_composite(Z._fade(L.copy(), min(1, p * 1.6)), (int(cx - L.width / 2), int(262 - L.height / 2)))
    return img


# ---------------------------------------------------------------------------------------------- 11. idea KVM
def gkvm(t):
    img = layer(); cw, ch = 940, 396
    L, m = card_bg(cw, ch); d = ImageDraw.Draw(L); cx = m + cw / 2; iy = m + 72
    lit = 0 if t < 1.35 else 1
    for k, x in enumerate((cx - 250, cx + 250)):                     # dos PC
        fill = Z.AMBER + (230,) if k == lit else None
        d.rounded_rectangle((x - 70, iy - 46, x + 70, iy + 40), 10, fill=fill, outline=Z.WHITE, width=6)
        d.line((x, iy + 40, x, iy + 58), fill=Z.WHITE, width=6); d.line((x - 30, iy + 60, x + 30, iy + 60), fill=Z.WHITE, width=6)
    for x0, x1 in ((cx - 170, cx - 60), (cx + 60, cx + 170)):
        for xx in range(int(x0), int(x1), 22): d.line((xx, iy, xx + 11, iy), fill=Z.WHITE + (200,), width=5)
    pr = max(0.0, math.sin(min(1, max(0, (t - 1.15) / 0.3)) * math.pi))
    d.rounded_rectangle((cx - 56, iy - 28, cx + 56, iy + 28), 10, fill=(34, 34, 40, 255), outline=Z.WHITE, width=5)
    r = 15 - 4 * pr; d.ellipse((cx - r, iy - r, cx + r, iy + r), fill=Z.AMBER)
    Z.text(cv, L, (cx, m + 188), "¿Un switch para pasar", 70, Z.AMBER, t, 0.25, rot=0)
    Z.text(cv, L, (cx, m + 258), "de PC con un botón?", 70, Z.AMBER, t, 0.35, rot=0)
    p = (t - 1.9) / 0.35
    if p > 0:
        B = layer(330, 96); bd = ImageDraw.Draw(B)
        bd.rounded_rectangle((0, 0, 329, 95), 46, fill=Z.WHITE + (255,), outline=Z.INK + (255,), width=5)
        bd.rounded_rectangle((34, 26, 84, 62), 9, fill=Z.INK); bd.polygon([(44, 60), (44, 76), (60, 61)], fill=Z.INK)   # globito de comentario
        ftext(bd, (102, 48), "Comentá", Z.PRICE, 52, Z.INK + (255,), anchor="lm")
        Z._place(cv, L, B, cx, m + ch - 56, Z._back(p), 0, min(1, p * 2))
    put(img, L, 960, 232, t)
    return img


# ---------------------------------------------------------------------------------------------- catálogo
S = lambda f, t, v: {"archivo": f"sfx/{f}", "t": t, "vol": v}
WH = ["fast_whoosh_1490.mp3", "air_woosh_1489.mp3", "cinematic_whoosh_fast_1492.mp3"]
SECS = ["Unboxing", "Accesorios", "Luces", "Conexiones", "Prueba de sonido", "Lo malo", "Veredicto"]
G = [  # id, función, dur, hold (cuadro del PNG), posición, sfx
    ("g01_60_por_ciento", g60, 4.5, 2.4, "arriba a la izquierda (x 50–950, y 40–460)",
     [S(WH[0], -0.2, 0.22), S("dry_pop_2356.mp3", 0.75, 0.30), S("dry_pop_2356.mp3", 1.05, 0.30), S("dry_pop_2356.mp3", 1.35, 0.30), S("hard_pop_click_2364.mp3", 1.7, 0.30)]),
    ("g02_switch_red", gswitch, 4.0, 1.4, "arriba a la izquierda (x 80–900, y 90–300)",
     [S(WH[1], -0.2, 0.22), S("classic_click_1117.mp3", 0.75, 0.35), S("explainer_pop_3005.mp3", 0.45, 0.30)]),
    ("g03_modos", gmodos, 4.0, 1.5, "arriba al centro (x 510–1410, y 70–330)",
     [S("explainer_pop_3005.mp3", 0.0, 0.30), S("dry_pop_2356.mp3", 0.35, 0.30), S("explainer_pop_3005.mp3", 0.7, 0.30)]),
    ("g04_fn_f9", gfn, 4.5, 1.2, "arriba a la izquierda (x 60–760, y 70–380)",
     [S("explainer_pop_3005.mp3", 0.0, 0.30), S("dry_pop_2356.mp3", 0.3, 0.30), S("classic_click_1117.mp3", 0.85, 0.40)]),
    ("g05_precio", gprecio, 4.0, 1.0, "arriba a la izquierda (x 90–850, y 60–310)",
     [S(WH[2], -0.2, 0.22), S("hard_pop_click_2364.mp3", 0.1, 0.30)]),
    ("g06_no_es_publicidad", gnopubli, 3.5, 1.0, "arriba al centro (x 560–1360, y 70–330)",
     [S("movie_whoosh_impact_2903.mp3", -0.25, 0.28), S("explainer_pop_3005.mp3", 0.45, 0.30)]),
    ("g07_lo_malo", gmalo, 4.0, 1.0, "arriba a la izquierda (x 60–720, y 70–380)",
     [S(WH[0], -0.2, 0.22), S("dry_pop_2356.mp3", 0.0, 0.30), S("dry_pop_2356.mp3", 0.5, 0.30)]),
    ("g08_tiempo_real", gtiempo, 10.0, 0.5, "arriba a la izquierda (x 60–530, y 45–165); el punto rojo titila, se puede cortar en cualquier momento",
     [S("hard_pop_click_2364.mp3", 0.0, 0.25)]),
] + [(f"g09_seccion_{i + 1}_{n.lower().replace(' ', '_')}", gsec(n), 2.2, 0.8, "arriba a la izquierda (x 60–800, y 70–260)",
      [S("movie_whoosh_impact_2903.mp3", -0.25, 0.28)]) for i, n in enumerate(SECS)] + [
    ("g10_tarjeta_cybermonday", gcard, 5.0, 1.0, "arriba a la derecha (x 1340–1890, y 40–490), libre del recuadro de cara",
     [S(WH[1], -0.15, 0.22), S("bell_notification_933.mp3", 0.4, 0.25)]),
    ("g11_idea_kvm", gkvm, 5.5, 2.5, "arriba al centro (x 470–1450, y 20–480)",
     [S(WH[2], -0.2, 0.22), S("classic_click_1117.mp3", 1.2, 0.40), S("confirmation_tone_2867.mp3", 1.9, 0.22)]),
]


def render(gid, fn, dur, hold):
    fn(hold).save(OUT / f"{gid}.png")
    p = subprocess.Popen([FF, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "qtrle", "-pix_fmt", "argb", str(OUT / f"{gid}.mov")], stdin=subprocess.PIPE)
    n = int(dur * FPS)
    for i in range(n):
        t = i / FPS; im = fn(t); k = min(1, (dur - t) / 0.25)      # salida: fundido de 0,25 s
        if k < 1: im = Z._fade(im, k)
        p.stdin.write(im.tobytes())
    p.stdin.close(); assert p.wait() == 0, gid


if __name__ == "__main__":
    want = set(sys.argv[1:])
    for gid, fn, dur, hold, pos, sfx in G:
        if want and not any(gid.startswith(w) for w in want): continue
        render(gid, fn, dur, hold); print("ok", gid, flush=True)
