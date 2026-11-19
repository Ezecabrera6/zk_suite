#!/usr/bin/env python3
"""vedit — edición asistida de video para YouTube (Claude = orquestador).

Comandos principales:
  python main.py check                         detecta hardware real → 12_project/hardware.json
  python main.py proxy [--max-chunks N]        proxy 720p30 incremental (se puede cortar y retomar)
  python main.py watch [--port 8765]           LIVE PREVIEW en el navegador (se actualiza solo)
  python main.py timeline list|show|undo|restore N
  python main.py preview --from 120 --to 160   render parcial (tiempo de la fuente original)
  python main.py preview --around 561 --duration 20
  python main.py preview --full                preview completo de la timeline actual
  python main.py transcribe                    faster-whisper (CUDA si está disponible) → transcript.json
  python main.py subtitles                     transcript.json → SRT / VTT / ASS
  python main.py render --confirm              render FINAL desde los originales (requiere confirmación)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _s in (sys.stdout, sys.stderr):  # consola de Windows (cp1252) no imprime →, ñ, etc.
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from vedit import hw, proxy, render, subtitles, timeline  # noqa: E402
from vedit.project import find_project  # noqa: E402
from vedit.util import fmt_tc, save_json  # noqa: E402


def cmd_check(prj, a):
    info = hw.detect()
    save_json(prj.project_dir / "hardware.json", info)
    print(json.dumps(info, indent=2, ensure_ascii=False))


def cmd_proxy(prj, a):
    prj.ensure_dirs()
    h = json.loads((prj.project_dir / "hardware.json").read_text("utf-8")) if (prj.project_dir / "hardware.json").exists() else {}
    enc = a.encoder or h.get("recommended_encoder", "libx264")
    print(proxy.build_proxy(prj, "main", enc, a.max_chunks))


def cmd_watch(prj, a):
    from vedit.server import serve
    serve(prj, a.port, not a.no_browser)


def cmd_timeline(prj, a):
    cur = timeline.load_current(prj) or {}
    if cur.get("track") == "enhanced" and a.action in ("list", "undo", "restore"):
        if a.action == "list":
            for v in timeline.list_enhanced(prj):
                print(f"enhanced v{v['version']:03d}  {fmt_tc(v['duration']):>10}  {v['created_at']}  {v['changes']} cambios  {v['note']}")
        elif a.action == "undo":
            if not cur.get("parent_version"):
                sys.exit("No hay versión anterior")
            print("OK →", timeline.restore_enhanced(prj, cur["parent_version"])["version"])
        else:
            print("OK →", timeline.restore_enhanced(prj, int(a.n))["version"])
        return
    if a.action == "list":
        for v in timeline.list_versions(prj):
            print(f"v{v['version']:03d}  {fmt_tc(v['duration']):>10}  {v['created_at']}  {v['note']}")
    elif a.action == "show":
        tl = timeline.load_current(prj)
        print(f"v{tl['version']:03d} — {tl['note']}\nduración editada {fmt_tc(timeline.edited_duration(tl))}")
        for c in tl["sequence"]:
            print(f"  {c['kind']:<8} {c['source']:<6} {fmt_tc(c['in'])} → {fmt_tc(c['out'])}")
    elif a.action == "undo":
        print("OK →", timeline.undo(prj)["version"])
    elif a.action == "restore":
        print("OK →", timeline.restore(prj, int(a.n))["version"])


def cmd_preview(prj, a):
    lo, hi = a.from_, a.to
    if a.around is not None:
        lo, hi = max(0.0, a.around - a.duration / 2), a.around + a.duration / 2
    if not a.full and lo is None and hi is None and a.edit_from is None and a.edit_to is None:
        sys.exit("Indicá --from/--to, --around o --full")
    r = render.render(prj, "preview", lo, hi, burn_subs=True if a.burn_subtitles else None,
                      encoder=a.encoder, max_seconds=a.max_seconds, raw=a.raw,
                      edit_from=a.edit_from, edit_to=a.edit_to)
    print(json.dumps(r, indent=2, ensure_ascii=False))


def cmd_render(prj, a):
    if not a.confirm:
        sys.exit("El render FINAL requiere --confirm (aprobá antes el preview).")
    r = render.render(prj, a.profile, burn_subs=True if a.burn_subtitles else None, encoder=a.encoder,
                      max_seconds=a.max_seconds)
    print(json.dumps(r, indent=2, ensure_ascii=False))


def cmd_transcribe(prj, a):
    d = subtitles.transcribe(prj, model=a.model)
    print(f"{len(d['segments'])} segmentos · {d['engine']} · {d.get('device')}/{d.get('compute_type')}")


def cmd_subtitles(prj, a):
    tl = timeline.load_current(prj) or {}
    print(subtitles.write_subtitles(prj, style=tl.get("subtitles", {}).get("style")))


def main():
    ap = argparse.ArgumentParser(prog="vedit", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", help="carpeta del proyecto (por defecto se detecta)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("check")
    p = sp.add_parser("proxy"); p.add_argument("--max-chunks", type=int); p.add_argument("--encoder")
    p = sp.add_parser("watch"); p.add_argument("--port", type=int, default=8765); p.add_argument("--no-browser", action="store_true")
    p = sp.add_parser("timeline"); p.add_argument("action", choices=["list", "show", "undo", "restore"]); p.add_argument("n", nargs="?")
    for name in ("preview", "render"):
        p = sp.add_parser(name)
        p.add_argument("--burn-subtitles", action="store_true")
        p.add_argument("--encoder")
        p.add_argument("--max-seconds", type=float, help="corta tras N s y retoma desde caché al re-ejecutar")
        if name == "preview":
            p.add_argument("--from", dest="from_", type=float); p.add_argument("--to", type=float)
            p.add_argument("--around", type=float); p.add_argument("--duration", type=float, default=20.0)
            p.add_argument("--full", action="store_true")
            p.add_argument("--raw", action="store_true", help="ignora los cortes: para revisar blur/overlays en un tramo")
            p.add_argument("--edit-from", type=float, help="inicio en tiempo de la EDICIÓN (lo que ves en el visor)")
            p.add_argument("--edit-to", type=float, help="fin en tiempo de la EDICIÓN")
        else:
            p.add_argument("--confirm", action="store_true")
            p.add_argument("--profile", default="final", choices=["final", "final1440", "final4k"])
    p = sp.add_parser("transcribe"); p.add_argument("--model", default="auto")
    sp.add_parser("subtitles")
    a = ap.parse_args()
    prj = find_project(a.project)
    prj.ensure_dirs()
    {"check": cmd_check, "proxy": cmd_proxy, "watch": cmd_watch, "timeline": cmd_timeline, "preview": cmd_preview,
     "render": cmd_render, "transcribe": cmd_transcribe, "subtitles": cmd_subtitles}[a.cmd](prj, a)


if __name__ == "__main__":
    main()
