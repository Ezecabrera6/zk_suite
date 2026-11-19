"""Cartel tipo lower third, el ESTILO OFICIAL de carteles del canal (aprobado el 18/11/2026): abajo a la izquierda,
rectángulo oscuro mate con esquinas apenas redondeadas, SIN línea ni barra de color, rótulo chico en mayúsculas arriba
y el dato abajo, en Consolas Bold. Para generar los carteles de un video, ver carteles.py.
uso: python lower_third.py   → 6_lt_*.jpg sobre dos cuadros de muestra (_cara.png, _caja.png) + HOJA_LOWER_THIRD.jpg"""
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

D = Path(__file__).parent
CONSOLAS = os.environ.get("ZK_FUENTE_CARTEL", "C:/Windows/Fonts/consolab.ttf")
BG, WHITE, SUBW = (18, 19, 22, 225), (255, 255, 255, 255), (235, 237, 240, 255)


def lower_third(W, H, rotulo, dato, esc=1.0, fuentes=(CONSOLAS, CONSOLAS)):
    """Capa RGBA de WxH con el cartel. esc=1 para 1920x1080."""
    s = lambda v: int(v * esc)
    fr, fd = ImageFont.truetype(fuentes[0], s(25)), ImageFont.truetype(fuentes[1], s(46))
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    rot = " ".join(rotulo.upper())[:0] or rotulo.upper()
    w = max(tmp.textlength(rot, font=fr) + s(3) * len(rot), tmp.textlength(dato, font=fd)) + s(28 + 6 + 26)
    h = s(118); x0, y0 = s(64), H - s(64) - h
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle((x0, y0 + s(6), x0 + w, y0 + h + s(6)), s(8), fill=(0, 0, 0, 90))
    L.alpha_composite(sh.filter(ImageFilter.GaussianBlur(s(12))))
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(top)
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), s(8), fill=BG)
    # sin barra celeste: pedido 18/11 «esa línea que le ponés es demasiado IA»
    x = x0 + s(6 + 22)
    for ch in rot:                                            # mayúsculas chicas con un poco de aire entre letras
        d.text((x, y0 + s(36)), ch, font=fr, fill=SUBW, anchor="lm"); x += tmp.textlength(ch, font=fr) + s(3)
    d.text((x0 + s(6 + 22), y0 + s(80)), dato, font=fd, fill=WHITE, anchor="lm")
    L.alpha_composite(top)
    return L


if __name__ == "__main__":
    ej = [("_cara.png", "PESO", "54 g • según Redragon"), ("_caja.png", "SENSOR", "45.000 DPI • Redragon 3953"),
          ("_cara.png", "PRECIO", "$80.000 • precio de ejemplo")]
    out = []
    for i, (fondo, r, dt) in enumerate(ej):
        img = Image.open(D / fondo).convert("RGBA"); img.alpha_composite(lower_third(*img.size, r, dt))
        p = D / f"6_lt_{i + 1}_{r.lower()}.jpg"; img.convert("RGB").save(p, quality=90); out.append(img)
    hoja = Image.new("RGB", (1920, 1080 * 3 // 2 + 0), (14, 15, 18))
    for i, im in enumerate(out): hoja.paste(im.convert("RGB").resize((960, 540)), ((i % 2) * 960, (i // 2) * 540))
    hoja.crop((0, 0, 1920, 1080 if len(out) < 3 else 1620)).save(D / "HOJA_LOWER_THIRD.jpg", quality=88); print("ok")
