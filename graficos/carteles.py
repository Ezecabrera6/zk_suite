"""Genera los carteles de un video con el estilo oficial (lower_third.py: caja oscura mate, sin línea de color,
Consolas Bold). Cada cartel: PNG 1920x1080 con alfa + MOV qtrle con fundido de 0,15 s al entrar y al salir.
Si en la carpeta de salida hay un catalogo.json ({"graficos": [...]}), reemplaza ahí las entradas «lt_*».

uso: python carteles.py carteles.json CARPETA_SALIDA
     carteles.json = [["lt_precio", "PRECIO", "$80.000 en la tienda", 3.5], ...]   (id, rótulo, dato, duración en s)
     Ejemplo real: ejemplos/m999/carteles.json"""
import json, subprocess, sys
from pathlib import Path
from lower_third import lower_third

LISTA, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
LT = json.load(open(LISTA, encoding="utf-8"))
cat_f = OUT / "catalogo.json"
cat = json.load(open(cat_f, encoding="utf-8")) if cat_f.exists() else {"graficos": []}
cat["graficos"] = [g for g in cat["graficos"] if not g["id"].startswith("lt_")]
for gid, r, dato, dur in LT:
    lower_third(1920, 1080, r, dato).save(OUT / f"{gid}.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "30", "-t", str(dur), "-i", str(OUT / f"{gid}.png"),
                    "-vf", f"format=argb,fade=in:st=0:d=0.15:alpha=1,fade=out:st={dur - 0.15}:d=0.15:alpha=1",
                    "-c:v", "qtrle", "-pix_fmt", "argb", str(OUT / f"{gid}.mov")], check=True)
    cat["graficos"].append({"id": gid, "archivo": f"{gid}.mov", "png": f"{gid}.png", "dur_sugerida": dur, "sfx": []})
    print("ok", gid, flush=True)
cat_f.write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
