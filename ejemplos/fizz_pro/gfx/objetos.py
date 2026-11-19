"""Gráficos-objeto (v3, 10/11/2026). Sobre el g04 de la v1 (teclas Fn y F9 en 3D con brillo naranja): «ESTO ME
ENCANTÓ!!!!». Lo rechazado era el texto suelto con contorno grueso y el sello rojo; el dato dibujado como objeto grande
(YANPOL) va. g04 sale tal cual de gen_v1_sticker.py; g01/g02/g03 se dibujan en esa misma línea: pieza con relieve
(falda oscura + cara), brillo naranja suave detrás, entrada con pop y el texto corto abajo como «cambia las luces»."""
import math
from PIL import Image, ImageDraw, ImageFilter
import gen_v1_sticker as v1
from gen_v1_sticker import Z, cv, ease, layer, put

ORANGE = (248, 129, 36)          # el brillo del g04 en su cuadro de reposo (rojo → ámbar a 1,2 s)
FACE, SKIRT, EDGE = (40, 40, 46, 255), (14, 14, 16, 255), (70, 70, 80, 255)


def glow(L, box, r=26, a=200, blur=16, col=ORANGE):
    g = layer(*L.size); ImageDraw.Draw(g).rounded_rectangle(box, r, fill=col + (a,)); L.alpha_composite(g.filter(ImageFilter.GaussianBlur(blur)))


def sub(img, xy, s, t, start, size=46):
    """El texto chico de abajo, igual que «cambia las luces» del g04."""
    Z.text(cv, img, xy, s, size, Z.WHITE, t, start, rot=-2, font=Z.POP)


# ------------------------------------------------------------------------------------------------- g01 · 60 %
KU = 26                                              # unidad de tecla en px
def _keyboard(t):
    keys, zones = v1.KB, {"frow": 1.0, "nav": 1.15, "num": 1.3}   # cuándo se apaga cada zona
    o, pad = 40, 22; bw, bh = 23 * KU, 6.5 * KU; W_, H_ = int(bw + 2 * pad), int(bh + 2 * pad)
    L = layer(W_ + 2 * o, H_ + 2 * o + 14)
    glow(L, (o - 6, o + 6, o + W_ + 6, o + H_ + 20), a=150, blur=18)
    d = ImageDraw.Draw(L)
    d.rounded_rectangle((o, o + 12, o + W_, o + H_ + 14), 22, fill=SKIRT, outline=Z.INK + (255,), width=4)       # falda
    d.rounded_rectangle((o + 6, o, o + W_ - 6, o + H_), 20, fill=(26, 26, 30, 255), outline=EDGE, width=3)        # cara de la carcasa
    x0, y0 = o + pad, o + pad
    lit = []
    for (x, y, w, h, z) in keys:
        on = ease((t - 0.35 - 0.02 * x) / 0.3)                           # se prenden de izquierda a derecha
        if z != "main": on *= 1 - ease((t - zones[z]) / 0.3)             # el numérico, las flechas y las F se apagan
        lit.append(on)
    bl = layer(*L.size); bd = ImageDraw.Draw(bl)                          # luz que se escapa entre teclas
    for (x, y, w, h, z), on in zip(keys, lit):
        if on > 0: bd.rounded_rectangle((x0 + x * KU - 2, y0 + y * KU - 2, x0 + (x + w) * KU + 2, y0 + (y + h) * KU + 2), 5, fill=ORANGE + (int(230 * on),))
    L.alpha_composite(bl.filter(ImageFilter.GaussianBlur(4)))
    kl = layer(*L.size); kd = ImageDraw.Draw(kl)
    for (x, y, w, h, z), on in zip(keys, lit):
        f = tuple(int(28 + (46 - 28) * on) for _ in range(3)) + (255,)
        kd.rounded_rectangle((x0 + x * KU + 2, y0 + y * KU + 2, x0 + (x + w) * KU - 2, y0 + (y + h) * KU - 2), 5, fill=f,
                             outline=tuple(int(48 + 40 * on) for _ in range(3)) + (255,), width=2)
    L.alpha_composite(kl)
    return L


def g60(t):
    img = layer()
    put(img, _keyboard(t), 385, 158, t, 0.0, rot=-2)
    Z.text(cv, img, (385, 312), "60 %", 80, Z.WHITE, t, 1.35, rot=-2, font=Z.PRICE)
    sub(img, (385, 375), "sin numérico ni flechas", t, 1.55, size=42)
    return img


# ------------------------------------------------------------------------------------------- g02 · switch red
def _switch(t):
    press = max(0.0, math.sin(min(1, max(0, (t - 0.8) / 0.35)) * math.pi)); dy = 16 * press
    L = layer(360, 330); cx = 180
    glow(L, (cx - 120, 70, cx + 120, 260), r=40, a=170, blur=22)
    d = ImageDraw.Draw(L); INK = Z.INK + (255,)
    gold = (206, 164, 70, 255)
    d.rectangle((cx - 64, 250, cx - 54, 292), fill=gold, outline=INK, width=2); d.rectangle((cx + 40, 250, cx + 48, 284), fill=gold, outline=INK, width=2)
    d.rounded_rectangle((cx - 122, 196, cx + 122, 258), 10, fill=SKIRT, outline=INK, width=4)                      # carcasa de abajo
    d.line((cx - 112, 206, cx + 112, 206), fill=(40, 40, 46, 255), width=3)
    # vástago rojo (atrás de la carcasa de arriba): cruz vista de frente
    sy = 58 + dy
    d.rectangle((cx - 36, sy, cx + 36, 132), fill=(222, 30, 36, 255), outline=INK, width=4)
    d.rectangle((cx - 9, sy + 4, cx + 9, 130), fill=(170, 18, 24, 255))
    d.rectangle((cx - 32, sy + 4, cx + 32, sy + 14), fill=(255, 92, 92, 255))
    d.polygon([(cx - 116, 202), (cx - 88, 118), (cx + 88, 118), (cx + 116, 202)], fill=(58, 58, 66, 255), outline=INK, width=4)  # carcasa de arriba
    d.line((cx - 84, 124, cx + 84, 124), fill=(118, 118, 128, 255), width=3)
    for sx in (-1, 1): d.rectangle((cx + sx * 104 - 6, 150, cx + sx * 104 + 6, 176), fill=(40, 40, 46, 255))       # trabas
    return L


def gswitch(t):
    img = layer()
    put(img, _switch(t), 330, 165, t, 0.0, rot=-3)
    Z.text(cv, img, (330, 325), "Switch red", 64, Z.WHITE, t, 0.3, rot=-2, font=Z.PRICE)
    sub(img, (330, 388), "menos ruidoso que el blue", t, 0.5, size=40)
    return img


# --------------------------------------------------------------------------------------------- g03 · modos
def _tile(icon, w=190, h=170):
    o = 40; L = layer(w + 80, h + 90)
    glow(L, (o - 6, o + 6, o + w + 6, o + h + 22))
    d = ImageDraw.Draw(L)
    d.rounded_rectangle((o, o + 10, o + w, o + h + 14), 24, fill=SKIRT, outline=Z.INK + (255,), width=4)
    d.rounded_rectangle((o + 12, o, o + w - 12, o + h - 18), 20, fill=FACE, outline=EDGE, width=3)
    ic = layer(*L.size); icon(ImageDraw.Draw(ic), o + w / 2, o + (h - 18) / 2); L.alpha_composite(ic)
    return L


def gmodos(t):
    img = layer()
    for i, (lab, ic) in enumerate([("2.4G", v1.icon_dongle), ("BT", v1.icon_bt), ("Cable", v1.icon_cable)]):
        put(img, _tile(ic), 175 + i * 250, 190, t, 0.25 * i, rot=(-3, 2, -2)[i])
        sub(img, (175 + i * 250, 352), lab, t, 0.3 + 0.25 * i, size=50)
    return img


# ------------------------------------------------------------------------------- g12 · like + suscribite (cierre)
def _piece(w, h, face=FACE, dy=0, r=24):
    """Pieza con relieve (falda + cara) y brillo naranja, como las teclas del g04. Devuelve la capa y la caja de la cara."""
    o = 40; L = layer(w + 80, h + 90)
    glow(L, (o - 6, o + 6, o + w + 6, o + h + 22))
    d = ImageDraw.Draw(L)
    d.rounded_rectangle((o, o + 10, o + w, o + h + 14), r, fill=SKIRT, outline=Z.INK + (255,), width=4)
    box = (o + 12, o + dy, o + w - 12, o + h - 18 + dy)
    d.rounded_rectangle(box, r - 4, fill=face, outline=EDGE, width=3)
    return L, box


@__import__("functools").lru_cache(maxsize=1)
def _thumb_mask(h=88):
    """Pulgar de «me gusta»: el glifo Like (E8E1) de Segoe MDL2 relleno (es de contorno) + el puño a la izquierda.
    Se arma a 4x y se achica para que los bordes queden limpios. (el pulgar armado con rectángulos «está feo».)"""
    S = 400; f = __import__("PIL.ImageFont", fromlist=["x"]).truetype("C:/Windows/Fonts/segmdl2.ttf", S)
    m = Image.new("L", (S + 160, S + 80), 0); ImageDraw.Draw(m).text((S // 2 + 140, (S + 80) // 2), chr(0xE8E1), font=f, fill=255, anchor="mm")
    m = m.point(lambda v: 255 if v > 100 else 0); ImageDraw.floodfill(m, (0, 0), 128)
    m = m.point(lambda v: 0 if v == 128 else 255).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    x0, y0, x1, y1 = m.getbbox()
    cols = [x for x in range(x0, x1) if m.getpixel((x, y1 - 8))]                     # base de la palma
    py0 = next(y for y in range(y0, y1) if m.getpixel((x0 + 2, y)))                 # arriba de la palma, borde izquierdo
    d = ImageDraw.Draw(m); gap, cw = 26, 70
    d.rounded_rectangle((x0 - gap - cw, py0, x0 - gap, y1), 14, fill=255)           # puño
    m = m.crop(m.getbbox())
    return m.resize((int(m.width * h / m.height), h), Image.LANCZOS)


def _thumb(L, cx, cy, col=Z.WHITE):
    M = _thumb_mask(); G = Image.new("RGBA", M.size, col + (255,)); G.putalpha(M)
    L.alpha_composite(G, (int(cx - M.width / 2), int(cy - M.height / 2)))


def _cursor(sc=1.0):
    pts = [(0, 0), (0, 44), (11, 34), (19, 52), (27, 48), (19, 31), (33, 31)]
    L = layer(60, 80); ImageDraw.Draw(L).polygon([(6 + x * 1.3 * sc, 6 + y * 1.3 * sc) for x, y in pts], fill=Z.WHITE + (255,), outline=Z.INK + (255,), width=4)
    return L


def glike(t):
    img = layer(); CLICK_T = 1.35
    press = max(0.0, math.sin(min(1, max(0, (t - CLICK_T) / 0.3)) * math.pi)); done = t >= CLICK_T + 0.1
    T, box = _piece(190, 170); _thumb(T, (box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
    put(img, T, 175, 180, t, 0.0, rot=-3)
    B, box = _piece(380, 120, face=((76, 76, 84, 255) if done else (206, 24, 30, 255)), dy=10 * press, r=22)
    d = ImageDraw.Draw(B); cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    if done:
        d.line([(cx - 152, cy), (cx - 140, cy + 12), (cx - 118, cy - 12)], fill=(214, 214, 220, 255), width=7, joint="curve")
        d.text((cx + 22, cy), "SUSCRIPTO", font=Z._f(Z.PRICE, 42), fill=(214, 214, 220, 255), anchor="mm")
    else:
        d.text((cx, cy), "SUSCRIBIRSE", font=Z._f(Z.PRICE, 46), fill=Z.WHITE + (255,), anchor="mm")
    put(img, B, 520, 180, t, 0.2, rot=2)
    if 0.55 < t < 2.4:                                                        # cursor: entra, hace clic y se va
        a = ease((t - 0.55) / 0.7); x = 760 + (556 - 760) * a; y = 390 + (160 - 390) * a
        if t > CLICK_T + 0.35: x += 60 * ease((t - CLICK_T - 0.35) / 0.5); y += 40 * ease((t - CLICK_T - 0.35) / 0.5)
        fo = min(1, (t - 0.55) / 0.15) * (1 - ease((t - 2.0) / 0.4))
        C = Z._fade(_cursor(1 - 0.12 * press), fo); img.alpha_composite(C, (int(x), int(y)))
    return img


# ------------------------------------------------------------------------------- g13 · vamos por los 3.000 (cierre)
def g3000(t):
    img = layer()
    K, box = _piece(430, 150, r=24); ImageDraw.Draw(K).text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2 - 4), "3.000", font=Z._f(Z.PRICE, 104), fill=Z.WHITE + (255,), anchor="mm")
    put(img, K, 390, 140, t, 0.0, rot=-2)
    p = (t - 0.35) / 0.3
    if p > 0:                                                                  # barra de progreso con relieve, casi llena
        bw, bh = 560, 34; o = 30; L = layer(bw + 2 * o, bh + 2 * o + 10)
        fill = 0.92 * ease((t - 0.5) / 1.1); fx = o + 6 + (bw - 12) * fill
        if fill > 0: glow(L, (o, o, fx + 6, o + bh), r=17, a=160, blur=12)
        d = ImageDraw.Draw(L)
        d.rounded_rectangle((o, o + 6, o + bw, o + bh + 8), 17, fill=SKIRT, outline=Z.INK + (255,), width=4)
        d.rounded_rectangle((o + 4, o, o + bw - 4, o + bh), 15, fill=(30, 30, 34, 255), outline=EDGE, width=3)
        if fill > 0.02:
            d.rounded_rectangle((o + 6, o + 5, fx, o + bh - 5), 12, fill=ORANGE + (255,))
            d.line((o + 16, o + 10, fx - 10, o + 10), fill=(255, 190, 120, 255), width=3)
        Z._place(cv, img, L, 390, 262, 1, -2, min(1, p * 2))
    sub(img, (390, 322), "vamos por los tres mil", t, 0.8, size=44)
    return img
