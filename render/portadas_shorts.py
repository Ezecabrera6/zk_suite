"""Portadas de los Shorts de shorts_partidos.py (estilo aprobado el 10/11/2026): un cuadro elegido a mano del base.mp4 (sin
subtítulos), con la cara mirando y el producto entero, y 1-2 palabras en amarillo con contorno negro, en cursiva, sobre la
unión de las dos cámaras para no tapar ni la cara ni el producto.
uso: python render/portadas_shorts.py ejemplos/m999/shorts.json [n]
config: en cada Short del JSON, "portada": [segundo_del_base, "TEXTO"].
Salida: <ZK_PROYECTO>/11_exports/shorts/short_NN_slug_portada.jpg"""
import json, os, pathlib, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

CFG = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
R = pathlib.Path(os.environ["ZK_PROYECTO"])
FF = os.environ.get("ZK_FFMPEG", "ffmpeg")
FONT = os.environ.get("ZK_FUENTE_PORTADA", r"C:\Windows\Fonts\impact.ttf")
TOP_H = 680


def portada(slug, t, txt):
    wk = R / "10_work/shorts_vertical" / slug; raw = wk / "portada_cruda.png"
    subprocess.run([FF, "-v", "error", "-y", "-ss", str(t), "-i", str(wk / "base.mp4"), "-frames:v", "1", str(raw)], check=True)
    im = Image.open(raw).convert("RGBA"); W = im.width; size = 170
    while True:                                                 # el texto entra con 45 px de margen a cada lado
        f = ImageFont.truetype(FONT, size)
        if ImageDraw.Draw(im).textbbox((0, 0), txt, font=f, stroke_width=12)[2] < W - 90 or size < 90: break
        size -= 6
    lay = Image.new("RGBA", (W, size + 80), (0, 0, 0, 0))
    ImageDraw.Draw(lay).text((W // 2, lay.height // 2), txt, font=f, fill=(255, 214, 10, 255), anchor="mm", stroke_width=12, stroke_fill=(0, 0, 0, 255))
    lay = lay.transform(lay.size, Image.AFFINE, (1, 0.18, -0.09 * lay.height, 0, 1, 0), Image.BICUBIC)   # cursiva
    sh = Image.new("RGBA", lay.size, (0, 0, 0, 0)); sh.paste((0, 0, 0, 170), (0, 0), lay.getchannel("A")); sh = sh.filter(ImageFilter.GaussianBlur(10))
    y = TOP_H - lay.height // 2 + 10
    im.alpha_composite(sh, (0, y + 8)); im.alpha_composite(lay, (0, y))
    out = R / "11_exports/shorts" / f"{slug}_portada.jpg"; im.convert("RGB").save(out, quality=92); print("ok", out.name)


if __name__ == "__main__":
    for s in CFG["shorts"]:
        if "portada" in s and (len(sys.argv) < 3 or str(s["n"]) == sys.argv[2]):
            portada(f"short_{s['n']:02d}_{s['slug']}", *s["portada"])
