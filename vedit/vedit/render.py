"""Render de la timeline: preview (desde el proxy) y final (desde los originales).

Estrategia rápida e incremental:
  * Cada clip de la secuencia se renderiza como un segmento independiente y queda en caché
    (10_work/cache/segments/<hash>.mkv). El hash incluye fuente, in/out, efectos, subtítulos y perfil,
    así que al cambiar un corte solo se regeneran los segmentos afectados.
  * Los segmentos llevan audio PCM y duraciones alineadas a 1/30 s → al unirlos no hay deriva A/V.
  * La unión final es sin recomprimir el video (concat demuxer + copy); solo se codifica el audio a AAC.
  * Render parcial: --from/--to (tiempo de la fuente) o --around/--duration.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
import time
from pathlib import Path

from .hw import encoder_args
from .proxy import loudnorm_measure
from .timeline import clip_dur, load_current
from .util import ffmpeg_bin, ffprobe_json, file_fingerprint, fmt_tc, load_json, run, sha256_text, snap

PROFILES = {
    "preview": {"w": 1280, "h": 720, "fps": 30, "quality": "preview", "use_proxy": True},
    "final": {"w": 1920, "h": 1080, "fps": 30, "quality": "final", "use_proxy": False},
    "final1440": {"w": 2560, "h": 1440, "fps": 30, "quality": "final", "use_proxy": False},
    "final4k": {"w": 3840, "h": 2160, "fps": 30, "quality": "final", "use_proxy": False},
}
LOGO_OUTRO_LUFS = -16.0


# ------------------------------------------------------------------ subtítulos
def parse_vtt(path: Path) -> list[dict]:
    cues, cur = [], None
    if not path or not path.exists():
        return cues

    def ts(s):
        p = s.strip().replace(",", ".").split(":")
        p = [float(x) for x in p]
        return p[0] * 3600 + p[1] * 60 + p[2] if len(p) == 3 else p[0] * 60 + p[1]

    for line in path.read_text(encoding="utf-8").splitlines():
        if "-->" in line:
            a, b = line.split("-->")
            cur = {"start": ts(a), "end": ts(b.split()[0]), "text": ""}
            cues.append(cur)
        elif cur is not None and line.strip():
            cur["text"] = (cur["text"] + "\n" + line.strip()).strip()
        elif not line.strip():
            cur = None
    return cues


def _srt_time(t: float) -> str:
    t = max(0, t)
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ass_color(hexcolor: str) -> str:
    h = hexcolor.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}".upper()


def force_style(st: dict, out_h: int) -> str:
    # libass trabaja en una grilla de 288 px de alto por defecto → escalamos tamaños
    k = 288.0 / 1080.0
    align = {"bottom": 2, "top": 8, "middle": 5}.get(st.get("position", "bottom"), 2)
    parts = [f"FontName={st.get('font', 'Arial')}", f"FontSize={max(8, round(st.get('size', 46) * k))}",
             f"PrimaryColour={_ass_color(st.get('color', '#FFFFFF'))}",
             f"OutlineColour={_ass_color(st.get('outline_color', '#000000'))}",
             f"Outline={st.get('outline', 3) * k * 1.5:.1f}", f"Shadow={st.get('shadow', 1)}",
             f"Bold={-1 if st.get('bold', True) else 0}", f"Alignment={align}",
             f"MarginV={round(st.get('margin_v', 60) * k)}"]
    bg = st.get("background", "")
    if bg and not bg.endswith(",0)") and bg not in ("none", "transparent"):
        parts.append("BorderStyle=3")
    return ",".join(parts)


# ------------------------------------------------------------------ segmento
def _font() -> str:
    """Fuente bold para títulos (drawtext). Configurable con VEDIT_FONT."""
    cands = [os.environ.get("VEDIT_FONT", ""), "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
             "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
    for c in cands:
        if c and os.path.exists(c):
            return c.replace("\\", "/").replace(":", "\\:")
    return ""


def _zoom_vf(z, W, H) -> str:
    if not z or float(z.get("scale", 1)) <= 1.0:
        return ""
    k = float(z["scale"]); cx = float(z.get("cx", 0.5)); cy = float(z.get("cy", 0.5))
    cw, ch = int(W / k) // 2 * 2, int(H / k) // 2 * 2
    x, y = int((W - cw) * cx), int((H - ch) * cy)
    return f",crop={cw}:{ch}:{x}:{y},scale={W}:{H}:flags=lanczos"


def _push_vf(pi, W, H, FPS=30) -> str:
    """Zoom de empuje: arranca en 'from' (p.ej. 1.07) y vuelve a 1.0 en 'dur' s con ease-out cúbico (zoompan, tamaño fijo)."""
    if not pi:
        return ""
    z0, d = float(pi.get("from", 1.07)), float(pi.get("dur", 0.4))
    z = f"1+{z0 - 1:.4f}*pow(1-min(it/{d:.3f},1),3)"
    return (f",zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
            f"setsar=1,format=yuv420p")


def _norm_af(prj, src_key: str, target_I: float | None, TP: float, from_proxy: bool) -> str:
    if target_I is None:
        return ""  # timeline sin normalización (finishing: la base se escucha tal cual)
    if from_proxy and src_key == "main":
        return ""  # el audio del proxy ya está normalizado
    meas = loudnorm_measure(prj, src_key, I=target_I, TP=TP)
    gain = target_I - float(meas["measured"]["input_i"])
    lim = 10 ** (TP / 20.0)
    return f"volume={gain:.2f}dB,alimiter=limit={lim:.4f}:level=disabled,"


def render_segment(prj, tl: dict, clip: dict, profile: str, encoder: str, cut_in: float | None = None,
                   cut_out: float | None = None, burn_subs: bool = False, log=print) -> Path:
    P = PROFILES[profile]
    W, H, FPS = P["w"], P["h"], P["fps"]
    src_key = clip["source"]
    s_info = prj.source(src_key)
    use_proxy = P["use_proxy"] and s_info.get("proxy") and prj.p(s_info["proxy"]).exists()
    src = prj.p(s_info["proxy"] if use_proxy else s_info["path"])
    a = snap(clip["in"] if cut_in is None else max(clip["in"], cut_in))
    b = snap(clip["out"] if cut_out is None else min(clip["out"], cut_out))
    dur = b - a
    if dur < 1 / FPS:
        return None
    effects = [e for e in tl.get("effects", []) if e.get("source", "main") == src_key
               and e["start"] < b and (e.get("end", e["start"] + e.get("duration", 0))) > a and e.get("enabled", True)
               and (e.get("clip") == clip.get("id") or (e.get("clip") is None and
                    (clip.get("kind") != "HOOK" or e["type"] == "privacy_blur")))]
    subs = []
    st = tl.get("subtitles", {})
    if burn_subs and src_key == "main" and st.get("enabled") and st.get("file"):
        subs = [c for c in parse_vtt(prj.p(st["file"])) if c["start"] < b and c["end"] > a]
    norm = tl.get("audio", {}).get("normalize", {})
    if norm is None:                                  # finishing: sin normalizar; ajuste de ganancia por clip
        tI, norm = None, {}
    else:
        tI = norm.get("I", -14.0) if src_key == "main" else LOGO_OUTRO_LUFS
        tI = float(clip.get("audio_lufs", tI))          # nivel propio del clip (p.ej. logo más bajo)
    extra_af = clip.get("audio_af", "")               # filtros extra del clip (p.ej. lowpass)
    zoom = clip.get("zoom")                           # {"scale":1.15,"cx":0.5,"cy":0.4} punch-in
    tTP = norm.get("TP", -1.0)
    spec = {"src": str(src), "fp": file_fingerprint(src), "a": a, "b": b, "W": W, "H": H, "FPS": FPS,
            "enc": encoder, "q": P["quality"], "fx": effects, "subs": subs, "style": st.get("style") if subs else None,
            "tI": tI, "tTP": tTP, "v": 4}
    for k2, v2 in (("af", extra_af), ("mute", clip.get("mute")), ("zoom", zoom), ("tr", clip.get("transition_in")), ("gain", clip.get("gain_db")), ("push", clip.get("push_in")), ("pip", clip.get("pip_reframe")), ("trk", clip.get("track"))):
        if v2:
            spec[k2] = v2
    key = sha256_text(json.dumps(spec, sort_keys=True))[:24]
    out = prj.cache_dir / "segments" / f"{key}.mkv"
    if out.exists() and out.stat().st_size > 0:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)

    tmpdir = tempfile.mkdtemp(prefix="vedit_")
    inputs = ["-ss", f"{a:.6f}", "-t", f"{dur:.6f}", "-i", str(src)]
    has_audio = any(s.get("codec_type") == "audio" for s in ffprobe_json(src).get("streams", []))
    trk = clip.get("track")
    track_vf = ""
    if trk and trk.get("kind") == "full":
        k = float(trk["k"]); cw, ch = int(W / k) // 2 * 2, int(H / k) // 2 * 2
        lines = []
        for ts, fx, fy in trk["keys"]:
            rel = ts - a
            if -0.5 <= rel <= dur + 0.5:
                x = min(max(0, fx * W - cw / 2), W - cw); y = min(max(0, fy * H - ch / 2), H - ch)
                lines.append(f"{max(0.0, rel):.3f} crop@trk x {x:.1f}, crop@trk y {y:.1f};")
        Path(tmpdir, "trk.txt").write_text("\n".join(lines) or "0 crop@trk x 0;", encoding="utf-8")
        x0 = min(max(0, trk["keys"][0][1] * W - cw / 2), W - cw); y0 = min(max(0, trk["keys"][0][2] * H - ch / 2), H - ch)
        track_vf = f",sendcmd=f=trk.txt,crop@trk=w={cw}:h={ch}:x={x0:.1f}:y={y0:.1f},scale={W}:{H}:flags=lanczos,setsar=1"
        zoom = None
    fc = [f"[0:v]fps={FPS},scale={W}:{H}:force_original_aspect_ratio=decrease,"
          f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p" + track_vf + _zoom_vf(zoom, W, H) + _push_vf(clip.get("push_in"), W, H, FPS) + "[v0]"]
    last, n_in = "v0", 1
    pr = clip.get("pip_reframe")
    if pr:
        # reencuadre del PIP de la webcam: zoom k y desplazamiento para llevar la cara (fx,fy) al punto (tx,ty)
        r = pr["rect"]
        pw, ph = int(r["w"] * W) // 2 * 2, int(r["h"] * H) // 2 * 2
        px, py = int(round(r["x"] * W)), int(round(r["y"] * H))
        k = float(pr.get("k", 1.2))
        cw, ch = int(pw / k) // 2 * 2, int(ph / k) // 2 * 2
        cx = min(max(0, pr["fx"] * pw - pr.get("tx", 0.5) * cw), pw - cw)
        cy = min(max(0, pr["fy"] * ph - pr.get("ty", 0.5) * ch), ph - ch)
        inner = f"crop={cw}:{ch}:{int(cx)}:{int(cy)}"
        if trk and trk.get("kind") == "pip":
            lines = []
            for ts, fx, fy in trk["keys"]:
                rel = ts - a
                if -0.5 <= rel <= dur + 0.5:
                    x = min(max(0, fx * pw - pr.get("tx", 0.5) * cw), pw - cw); y = min(max(0, fy * ph - pr.get("ty", 0.5) * ch), ph - ch)
                    lines.append(f"{max(0.0, rel):.3f} crop@pip x {x:.1f}, crop@pip y {y:.1f};")
            Path(tmpdir, "pip.txt").write_text("\n".join(lines) or "0 crop@pip x 0;", encoding="utf-8")
            inner = f"sendcmd=f=pip.txt,crop@pip=w={cw}:h={ch}:x={int(cx)}:y={int(cy)}"
        fc.append(f"[v0]split[pra][prb];[prb]crop={pw}:{ph}:{px}:{py},{inner},"
                  f"scale={pw}:{ph}:flags=lanczos,setsar=1[prc];[pra][prc]overlay={px}:{py}[vpr]")
        last = "vpr"
    for i, e in enumerate(effects):
        es, ee = e["start"] - a, e.get("end", e["start"] + e.get("duration", 0)) - a
        if e["type"] == "privacy_blur":
            r = e["rect"]
            cw, ch = max(2, int(r["w"] * W) // 2 * 2), max(2, int(r["h"] * H) // 2 * 2)
            cx, cy = int(r["x"] * W), int(r["y"] * H)
            sig = float(e.get("strength", 24)) * W / 1280.0
            fc.append(f"[{last}]split[b{i}a][b{i}b];[b{i}b]crop={cw}:{ch}:{cx}:{cy},gblur=sigma={sig:.1f}:steps=3[b{i}c];"
                      f"[b{i}a][b{i}c]overlay={cx}:{cy}:enable='between(t,{max(0, es):.3f},{ee:.3f})'[v{i + 1}]")
            last = f"v{i + 1}"
        elif e["type"] == "overlay" and not e.get("on_top"):
            asset = prj.p(e["path"]) if e.get("path") else prj.p(prj.source(e["asset"])["path"])
            off_in = float(e.get("asset_offset", 0)) + max(0.0, -es)
            dec = ["-c:v", "libvpx-vp9"] if str(asset).lower().endswith(".webm") else []
            inputs += ["-ss", f"{off_in:.3f}", *dec, "-i", str(asset)]
            r = e.get("rect", {"x": 0, "y": 0, "w": 1, "h": 1})
            ow, oh = int(r["w"] * W) // 2 * 2, int(r["h"] * H) // 2 * 2
            fc.append(f"[{n_in}:v]scale={ow}:{oh},format=yuva420p,setpts=PTS+{max(0, es):.3f}/TB[o{i}];"
                      f"[{last}][o{i}]overlay={int(r['x'] * W)}:{int(r['y'] * H)}:eof_action=pass[v{i + 1}]")
            n_in += 1
            last = f"v{i + 1}"
    # parche con el original: tapa una zona de la base con la misma zona de otra fuente (p.ej. main)
    # {"type":"source_patch","source":"base","start","end","from":"main","offset":88.1,"rect":{x,y,w,h}}
    def patch(i, e):
        nonlocal last, n_in, inputs
        es, ee = e["start"] - a, e["end"] - a
        f_info = prj.source(e["from"])
        f_path = prj.p(f_info["proxy"] if use_proxy and f_info.get("proxy") and prj.p(f_info["proxy"]).exists()
                       else f_info["path"])
        t_from = a + float(e["offset"])
        inputs += ["-ss", f"{max(0.0, t_from):.6f}", "-t", f"{dur:.6f}", "-i", str(f_path)]
        r = e["rect"]
        cw, ch = max(2, int(r["w"] * W) // 2 * 2), max(2, int(r["h"] * H) // 2 * 2)
        cx, cy = int(r["x"] * W), int(r["y"] * H)
        shift = f",setpts=PTS+{-t_from:.6f}/TB" if t_from < 0 else ""   # la fuente del parche empieza más tarde que el tramo
        fd = float(e.get("fade", 0))
        fades = ""
        if fd > 0:   # fundido de entrada/salida (alfa); no se repite si el parche ya venía de un tramo anterior
            fades = ",format=yuva420p"
            if es >= 0 and e.get("fade_in", True):
                fades += f",fade=t=in:st={es:.3f}:d={fd}:alpha=1"
            if ee <= dur + 1e-3 and e.get("fade_out", True):
                fades += f",fade=t=out:st={max(0.0, ee - fd):.3f}:d={max(0.01, min(fd, ee)):.3f}:alpha=1"
        fc.append(f"[{n_in}:v]fps={FPS},scale={W}:{H},setsar=1,format=yuv420p,crop={cw}:{ch}:{cx}:{cy}{shift}{fades}[p{i}];"
                  f"[{last}][p{i}]overlay={cx}:{cy}:eof_action=pass:enable='between(t,{max(0, es):.3f},{ee:.3f})'[pv{i}]")
        n_in += 1
        last = f"pv{i}"

    for i, e in enumerate(effects):
        if e["type"] == "source_patch" and not e.get("on_top"):
            patch(i, e)
    # gráficos PNG (tarjetas de precio, títulos, etiquetas) con entrada deslizante + fundido
    for i, e in enumerate(effects):
        if e["type"] != "graphic" or not e.get("png"):
            continue
        es = e["start"] - a
        ee = es + float(e.get("duration", 3.0))
        k = W / 1920.0
        gw, gh = [int(v * k) // 2 * 2 for v in e.get("png_size", [600, 200])]
        pos = e.get("pos", {"x": 0.98, "y": 0.1, "anchor": "tr"})
        anc = pos.get("anchor", "tr")
        X = pos["x"] * W - (gw if anc.endswith("r") else gw / 2 if anc.endswith("c") else 0)
        Y = pos["y"] * H - (gh if anc.startswith("b") else gh / 2 if anc.startswith("m") else 0)
        slide = float(e.get("slide_px", 60)) * k * (1 if anc.endswith("r") else -1)
        tin, tout = float(e.get("fade_in", 0.28)), float(e.get("fade_out", 0.22))
        inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(prj.p(e["png"]))]
        # si el gráfico ya estaba en pantalla antes de este tramo (corte en el medio), no se repite la entrada
        fin = f"fade=t=in:st={es:.3f}:d={tin}:alpha=1," if es >= 0 and tin > 0 else ""
        fout = f"fade=t=out:st={max(0.0, ee - tout):.3f}:d={max(0.01, min(tout, ee)):.3f}:alpha=1," if ee <= dur + 1e-3 and tout > 0 else ""
        ease = f"max(0,1-(t-{es:.3f})/{tin})*max(0,1-(t-{es:.3f})/{tin})"
        anim = es >= 0 and slide and tin > 0
        if e.get("slide_axis") == "y":   # sube desde abajo
            xexpr, yexpr = f"{X:.1f}", (f"{Y:.1f}+{abs(slide):.1f}*{ease}" if anim else f"{Y:.1f}")
        else:
            xexpr, yexpr = (f"{X:.1f}+{slide:.1f}*{ease}" if anim else f"{X:.1f}"), f"{Y:.1f}"
        fc.append(f"[{n_in}:v]scale={gw}:{gh},format=rgba,{fin}{fout}format=rgba[g{i}];"
                  f"[{last}][g{i}]overlay=x='{xexpr}':y='{yexpr}':enable='between(t,{max(0, es):.3f},{ee:.3f})'[gv{i}]")
        n_in += 1
        last = f"gv{i}"
    for i, e in enumerate(effects):
        if e["type"] != "counter":
            continue
        # placa (PNG) + número con conteo animado (ease-out cúbico) usando drawtext/eif; t del filtro = fuente - a
        es, ee = e["start"] - a, e["end"] - a
        k = W / 1920.0
        pw, ph = [int(v * k) // 2 * 2 for v in e["plate_size"]]
        px, py = e["pos"]["x"] * W, e["pos"]["y"] * H
        tin, tout = 0.25, 0.22
        inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(prj.p(e["plate"]))]
        fin = f"fade=t=in:st={es:.3f}:d={tin}:alpha=1," if es >= 0 else ""
        fout = f"fade=t=out:st={max(0.0, ee - tout):.3f}:d={max(0.01, min(tout, ee)):.3f}:alpha=1," if ee <= dur + 1e-3 else ""
        fc.append(f"[{n_in}:v]scale={pw}:{ph},format=rgba,{fin}{fout}format=rgba[cp{i}];"
                  f"[{last}][cp{i}]overlay={px:.1f}:{py:.1f}:enable='between(t,{max(0, es):.3f},{ee:.3f})'[cv{i}]")
        n_in += 1
        last = f"cv{i}"
        st = e["steps"]; D = float(e.get("roll", 0.7))
        V = f"{st[0]['v']}"
        for j in range(1, len(st)):
            tj = st[j]["t"] - a
            V += f"+{st[j]['v'] - st[j - 1]['v']}*(1-pow(1-clip((t-{tj:.3f})/{D}\\,0\\,1)\\,3))"
        A = (f"if(lt(t\\,{es:.3f})\\,0\\,if(lt(t\\,{es + tin:.3f})\\,(t-{es:.3f})/{tin}\\,"
             f"if(gt(t\\,{ee - tout:.3f})\\,max(0\\,({ee:.3f}-t)/{tout})\\,1)))")
        vf = V.replace("\\", "")  # para textfile (sin escapes de filtergraph)
        big = f"$ %{{eif:floor(({vf})/1000000):d}}.%{{eif:mod(floor(({vf})/1000),1000):d:3}}.%{{eif:mod(floor({vf}),1000):d:3}}"
        small = f"$ %{{eif:floor(({vf})/1000):d}}.%{{eif:mod(floor({vf}),1000):d:3}}"
        Path(tmpdir, f"cb{i}.txt").write_text(big, encoding="utf-8")
        Path(tmpdir, f"cs{i}.txt").write_text(small, encoding="utf-8")
        fsz = int(round(float(e.get("font_size", 50)) * k))
        tx, ty = px + e.get("text_x", 28) * k, py + e.get("text_y", 50) * k
        font = e.get("font", "C:/Windows/Fonts/seguisb.ttf").replace(":", "\\:")
        for nm, f_, cond in ((f"cb{i}", f"cb{i}.txt", f"gte({V}\\,1000000)"), (f"cs{i}", f"cs{i}.txt", f"lt({V}\\,1000000)")):
            fc.append(f"[{last}]drawtext=fontfile='{font}':textfile={f_}:fontsize={fsz}:fontcolor=white:"
                      f"x={tx:.1f}:y={ty:.1f}:alpha=if({cond}\\,{A}\\,0):"
                      f"enable='between(t,{max(0, es):.3f},{ee:.3f})'[{nm}]")
            last = nm
    for i, e in enumerate(effects):
        if e["type"] != "magnify":
            continue
        # lupa: recorta una zona del cuadro y la muestra ampliada con filete de acento
        es, ee = e["start"] - a, e["start"] + float(e.get("duration", 3.0)) - a
        r, dst = e["rect"], e["dst"]
        cw, ch = int(r["w"] * W) // 2 * 2, int(r["h"] * H) // 2 * 2
        dw = int(dst["w"] * W) // 2 * 2
        dh = int(dw * ch / cw) // 2 * 2
        bw = max(2, int(4 * W / 1920))
        col = e.get("border", "0x2F7DE1")
        tin, tout = 0.3, 0.22
        fin = f"fade=t=in:st={es:.3f}:d={tin}:alpha=1," if es >= 0 else ""
        fout = f"fade=t=out:st={max(0.0, ee - tout):.3f}:d={max(0.01, min(tout, ee)):.3f}:alpha=1," if ee <= dur + 1e-3 else ""
        X, Y = dst["x"] * W, dst["y"] * H
        fc.append(f"[{last}]split[mg{i}a][mg{i}b];[mg{i}b]crop={cw}:{ch}:{int(r['x'] * W)}:{int(r['y'] * H)},"
                  f"scale={dw}:{dh}:flags=lanczos,pad={dw + 2 * bw}:{dh + 2 * bw}:{bw}:{bw}:color={col},format=rgba,"
                  f"{fin}{fout}format=rgba[mg{i}c];"
                  f"[mg{i}a][mg{i}c]overlay=x='{X:.1f}':y={Y:.1f}+18*{W / 1920:.3f}*max(0\\,1-(t-{es:.3f})/{tin}):"
                  f"enable='between(t,{max(0, es):.3f},{ee:.3f})'[mgv{i}]")
        last = f"mgv{i}"
    for i, e in enumerate(effects):
        if e["type"] == "source_patch" and e.get("on_top"):
            patch(i, e)
        elif e["type"] == "overlay" and e.get("on_top"):
            es = e["start"] - a
            asset = prj.p(e["path"]) if e.get("path") else prj.p(prj.source(e["asset"])["path"])
            off_in = float(e.get("asset_offset", 0)) + max(0.0, -es)
            dec = ["-c:v", "libvpx-vp9"] if str(asset).lower().endswith(".webm") else []
            inputs += ["-ss", f"{off_in:.3f}", *dec, "-i", str(asset)]
            r = e.get("rect", {"x": 0, "y": 0, "w": 1, "h": 1})
            ow, oh = int(r["w"] * W) // 2 * 2, int(r["h"] * H) // 2 * 2
            fc.append(f"[{n_in}:v]fps={FPS},scale={ow}:{oh},format=yuva420p,setpts=PTS-STARTPTS+{max(0, es):.3f}/TB[ot{i}];"
                      f"[{last}][ot{i}]overlay={int(r['x'] * W)}:{int(r['y'] * H)}:eof_action=pass[otv{i}]")
            n_in += 1
            last = f"otv{i}"
    for i, e in enumerate(effects):
        if e["type"] != "text":
            continue
        es, ee = e["start"] - a, e["start"] + e.get("duration", 2.5) - a
        stl = e.get("style", {})
        Path(tmpdir, f"t{i}.txt").write_text(e["text"], encoding="utf-8")
        fsz = int(H * float(stl.get("size", 0.06)))
        xs = stl.get("x", "center")
        xexpr = "(w-tw)/2" if xs == "center" else f"{float(xs) * W:.0f}"
        yexpr = f"{float(stl.get('y', 0.12)) * H:.0f}"
        fin = 0.18
        alpha = (f"if(lt(t,{es:.3f}+{fin}),(t-{es:.3f})/{fin},if(gt(t,{ee:.3f}-{fin}),({ee:.3f}-t)/{fin},1))")
        bg = stl.get("bg", "#1f6fff").lstrip("#")
        fg = stl.get("color", "#ffffff").lstrip("#")
        fc.append(f"[{last}]drawtext=fontfile='{_font()}':textfile=t{i}.txt:fontsize={fsz}:fontcolor=0x{fg}:"
                  f"box=1:boxcolor=0x{bg}@0.96:boxborderw={max(6, fsz // 3)}:x={xexpr}:y={yexpr}:"
                  f"shadowcolor=black@0.5:shadowx=3:shadowy=3:alpha='{alpha}':"
                  f"enable='between(t,{max(0, es):.3f},{ee:.3f})'[tx{i}]")
        last = f"tx{i}"
    tr = clip.get("transition_in")
    if tr and tr.get("type") == "flash":
        fc.append(f"[{last}]fade=t=in:st=0:d={float(tr.get('duration', 0.22)):.3f}:color=white[trn]")
        last = "trn"
    if subs:
        lines = []
        for k, c in enumerate(subs, 1):
            lines += [str(k), f"{_srt_time(c['start'] - a)} --> {_srt_time(c['end'] - a)}", c["text"], ""]
        Path(tmpdir, "s.srt").write_text("\n".join(lines), encoding="utf-8")
        fs = force_style(st.get("style", {}), H).replace(",", "\\,")
        fc.append(f"[{last}]subtitles=s.srt:force_style={fs}[vs]")
        last = "vs"
    af = _norm_af(prj, src_key, tI, tTP, bool(use_proxy) and "audio_lufs" not in clip)
    if clip.get("gain_db"):
        af += f"volume={float(clip['gain_db']):.2f}dB,"
    if extra_af:
        af += extra_af.rstrip(",") + ","
    if clip.get("mute"):
        af = "volume=0,"
    if has_audio:
        fc.append(f"[0:a]{af}aresample=48000,aformat=channel_layouts=stereo,"
                  f"afade=t=in:d=0.012,afade=t=out:st={max(0, dur - 0.012):.3f}:d=0.012,apad[a0]")
    else:
        inputs += ["-f", "lavfi", "-t", f"{dur:.6f}", "-i", "anullsrc=r=48000:cl=stereo"]
        fc.append(f"[{n_in}:a]anull[a0]")
        n_in += 1
    # efectos de sonido (whoosh en transiciones/títulos) mezclados sin normalizar
    sfx = [e for e in effects if e["type"] == "sfx"]
    alast = "a0"
    for j, e in enumerate(sfx):
        inputs += ["-i", str(prj.p(prj.source(e["asset"])["path"]))]
        dly = int(max(0.0, e["start"] - a) * 1000)
        fc.append(f"[{n_in}:a]aresample=48000,aformat=channel_layouts=stereo,volume={e.get('gain_db', -6)}dB,"
                  f"adelay={dly}|{dly}[sx{j}];[{alast}][sx{j}]amix=inputs=2:duration=first:normalize=0[am{j}]")
        alast = f"am{j}"
        n_in += 1
    amap = ["-map", f"[{alast}]"]
    cmd = [ffmpeg_bin(), "-hide_banner", "-nostdin", "-loglevel", "error", *inputs,
           "-filter_complex", ";".join(fc), "-map", f"[{last}]", *amap,
           *encoder_args(encoder, P["quality"]), "-g", str(FPS), "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-c:a", "pcm_s16le", "-ar", "48000", "-t", f"{dur:.6f}", "-y", str(out.with_suffix(".tmp.mkv"))]
    t0 = time.time()
    cwd = os.getcwd()
    try:
        os.chdir(tmpdir)
        run(cmd)
    finally:
        os.chdir(cwd)
    os.replace(out.with_suffix(".tmp.mkv"), out)
    log(f"  segmento {src_key} {fmt_tc(a)}→{fmt_tc(b)} ({dur:.1f}s) en {time.time() - t0:.1f}s")
    return out


# ------------------------------------------------------------------ render de timeline
def render(prj, profile: str = "preview", src_from: float | None = None, src_to: float | None = None,
           burn_subs: bool | None = None, encoder: str | None = None, max_seconds: float | None = None,
           include_bumpers: bool | None = None, raw: bool = False, edit_from: float | None = None,
           edit_to: float | None = None, log=print) -> dict:
    tl = load_current(prj)
    if not tl:
        raise SystemExit("No hay timeline_current.json")
    hw = load_json(prj.project_dir / "hardware.json", {}) or {}
    encoder = encoder or hw.get("recommended_encoder") or "libx264"
    if burn_subs is None:
        burn_subs = bool(tl.get("subtitles", {}).get("burn"))
    partial = src_from is not None or src_to is not None
    if include_bumpers is None:
        include_bumpers = not partial
    lo = -math.inf if src_from is None else src_from
    hi = math.inf if src_to is None else src_to
    t_start = time.time()
    segs, pending = [], 0
    sequence = tl["sequence"]
    if raw:  # revisar efectos (blur, overlays) en un tramo del original, ignorando los cortes
        sequence = [{"id": "raw", "source": "main", "in": snap(max(0.0, lo)), "out": snap(hi), "kind": "RAW"}]
    if edit_from is not None or edit_to is not None:
        ef, et = edit_from or 0.0, edit_to if edit_to is not None else math.inf
        acc, jobs = 0.0, []
        for c in sequence:
            d = clip_dur(c)
            if acc + d > ef and acc < et:
                sp = float(c.get("speed") or 1.0)
                jobs.append((c, c["in"] + max(0.0, ef - acc) * sp, c["in"] + min(d, et - acc) * sp))
            acc += d
        for c, ci, co in jobs:
            if max_seconds and time.time() - t_start > max_seconds:
                pending += 1
                continue
            seg = render_segment(prj, tl, c, profile, encoder, ci, co, burn_subs, log)
            if seg:
                segs.append(seg)
        sequence, partial = [], True
        lo, hi = ef, et
    for c in sequence:
        if c["source"] != "main":
            if not include_bumpers:
                continue
            ci, co = None, None
        else:
            if c["out"] <= lo or c["in"] >= hi:
                continue
            ci, co = max(c["in"], lo), min(c["out"], hi)
        if max_seconds and time.time() - t_start > max_seconds:
            pending += 1
            continue
        seg = render_segment(prj, tl, c, profile, encoder, ci, co, burn_subs, log)
        if seg:
            segs.append(seg)
    if pending:
        return {"status": "partial", "pending_segments": pending, "hint": "volvé a ejecutar el mismo comando; continúa desde el caché"}
    if not segs:
        raise SystemExit("El rango pedido no contiene material conservado")
    outdir = prj.previews_dir if profile == "preview" else prj.final_dir
    outdir.mkdir(parents=True, exist_ok=True)
    tag = (f"enh_v{tl['version']:03d}" if tl.get("track") == "enhanced" else
           "base" if tl.get("track") == "preedited_base" else f"v{tl['version']:03d}")
    if partial:
        pre = "_edit" if (edit_from is not None or edit_to is not None) else "_src"
        tag += f"{pre}{int(lo if lo > -math.inf else 0)}-{int(hi if hi < math.inf else 0)}" + ("_raw" if raw else "")
    name = ("preview_" if profile == "preview" else "final_") + tag + ".mp4"
    out = outdir / name
    if os.environ.get("VEDIT_STAGE_DIR"):  # discos lentos: se escribe en local y luego se copia
        out = Path(os.environ["VEDIT_STAGE_DIR"]) / name
    lst = prj.cache_dir / f"concat_{tag}.txt"
    lst.write_text("".join(f"file '{s.as_posix()}'\n" for s in segs), encoding="utf-8")
    total = sum(float(ffprobe_json(s)["format"]["duration"]) for s in segs)
    au = tl.get("audio", {})
    # limitador de seguridad al final: margen de 1 dB bajo el True Peak objetivo (el AAC genera sobrepicos)
    tp = float((au.get("normalize") or {}).get("TP", -1.0))
    afx = [f"alimiter=limit={10 ** ((tp - 1.0) / 20):.4f}:level=disabled"]
    if not partial:
        if au.get("fade_in"):
            afx.append(f"afade=t=in:d={au['fade_in']}")
        if au.get("fade_out"):
            afx.append(f"afade=t=out:st={max(0, total - au['fade_out']):.3f}:d={au['fade_out']}")
    norm = au.get("normalize") or {}
    if not partial and norm.get("I") is not None and au.get("master_normalize", True):
        # master: medición de loudness de la mezcla completa → ganancia lineal exacta + limitador de pico
        p = run([ffmpeg_bin(), "-hide_banner", "-nostdin", "-f", "concat", "-safe", "0", "-i", str(lst), "-vn",
                 "-af", "loudnorm=print_format=json", "-f", "null", "-"])
        import re as _re
        m = json.loads(_re.findall(r"\{[^{}]*\}", p.stderr, _re.S)[-1])
        gain = float(norm["I"]) - float(m["input_i"])
        lim = 10 ** ((float(norm.get("TP", -1.0)) - 0.6) / 20)
        afx = [f"volume={gain:.2f}dB", f"alimiter=limit={lim:.4f}:attack=3:release=60:level=disabled"] + afx[1:]
        log(f"  master: medido {m['input_i']} LUFS / TP {m['input_tp']} → ganancia {gain:+.2f} dB")
    cmd = [ffmpeg_bin(), "-hide_banner", "-nostdin", "-loglevel", "error", "-f", "concat", "-safe", "0",
           "-i", str(lst), "-map", "0:v", "-map", "0:a", "-c:v", "copy"]
    if afx:
        cmd += ["-af", ",".join(afx)]
    cmd += ["-c:a", "aac", "-b:a", "128k" if profile == "preview" else "256k", "-ar", "48000",
            "-movflags", "+faststart", "-y", str(out)]
    run(cmd)
    info = ffprobe_json(out)
    return {"status": "done", "output": str(out) if os.environ.get("VEDIT_STAGE_DIR") else prj.rel(out), "duration": float(info["format"]["duration"]),
            "segments": len(segs), "encoder": encoder, "seconds": round(time.time() - t_start, 1)}
