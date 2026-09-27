"""Medição automática do PNG de referência: faixas, foto, logo e blocos de texto.

Só MEDE pixels do PNG aprovado e propõe coordenadas para validação humana; não desenha nada.
Saídas: `report.json` (medidas), `overlay.png` (caixas sobre a referência) e
`layout-spec.proposed.json` (sempre PENDING_REFERENCE, proposal=true).
Caixas, cores e alinhamento são medidos; "suggested_role" é palpite a confirmar no overlay.
"""
import hashlib
import json
import os
import unicodedata
from statistics import median

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat

INK_DIFF = 60


def _flat(im):
    return list(getattr(im, "get_flattened_data", im.getdata)())


# --------------------------------------------------------------------------- faixas
def _runs(flags, max_gap):
    runs, start, last, gap = [], None, None, 0
    for i, on in enumerate(flags):
        if on:
            if start is None:
                start = i
            last, gap = i, 0
        elif start is not None:
            gap += 1
            if gap > max_gap:
                runs.append((start, last + 1))
                start, gap = None, 0
    if start is not None:
        runs.append((start, last + 1))
    return runs


def _hard_bands(gray):
    """Bordas retas que atravessam a largura toda: (fundo do cabeçalho, topo do rodapé) ou None."""
    W, H = gray.size
    diff = ImageChops.difference(gray.crop((0, 0, W, H - 1)), gray.crop((0, 1, W, H))).point(lambda v: 255 if v > 22 else 0)
    vals = [v / 255 for v in _flat(diff.resize((1, H - 1), Image.Resampling.BOX))]
    groups = []
    for y, v in enumerate(vals):
        if v >= 0.6:
            if groups and y + 1 - groups[-1][-1] <= 6:
                groups[-1].append(y + 1)
            else:
                groups.append([y + 1])
    top = [g for g in groups if g[0] < 0.35 * H]
    bottom = [g for g in groups if g[-1] > 0.7 * H]
    return (top[-1][-1], bottom[0][0]) if top and bottom else None


def _panel_top(img, header_bottom, footer_top, tol=26, max_gap=70, quantile=0.35):
    """Sobe do rodapé enquanto a cor da linha (percentil escuro, imune a texto claro) é a do painel de texto."""
    W = img.width
    cache = {}

    def row(y):
        if y not in cache:
            px = _flat(img.crop((0, y, W, y + 1)))
            k = int(len(px) * quantile)
            cache[y] = tuple(sorted(p[c] for p in px)[k] for c in range(3))
        return cache[y]

    lo = int(header_bottom + 0.75 * (footer_top - header_bottom))
    samples = [row(y) for y in range(lo, footer_top - 8, 4)]
    panel = [sorted(s[c] for s in samples)[len(samples) // 2] for c in range(3)]
    top, gap = footer_top - 8, 0
    for y in range(footer_top - 8, header_bottom, -1):
        if max(abs(row(y)[c] - panel[c]) for c in range(3)) <= tol:
            top, gap = y, 0
        else:
            gap += 1
            if gap > max_gap:
                break
    return top, tuple(round(v) for v in panel)


def _row_diff(gray, y, x0, x1):
    return ImageStat.Stat(ImageChops.difference(gray.crop((x0, y, x1, y + 1)), gray.crop((x0, y + 1, x1, y + 2)))).mean[0]


def _refine_edge(gray, approx, window, span):
    lo, hi = max(0, approx - window), min(gray.height - 2, approx + window)
    return max(range(lo, hi + 1), key=lambda y: _row_diff(gray, y, *span)) + 1


def _fallback_photo(img, gray, B):
    """Sem bordas retas de largura total: maior trecho alto de linhas com variação horizontal."""
    W, H = img.size
    row_std = [ImageStat.Stat(gray.crop((0, y, W, y + 1))).stddev[0] for y in range(H)]
    runs = [r for r in _runs([v > 12 for v in row_std], 3 * B) if r[1] - r[0] >= 0.12 * H]
    if not runs:
        return None
    top, bottom = max(runs, key=lambda r: r[1] - r[0])
    span = (int(W * 0.1), int(W * 0.9))
    top = _refine_edge(gray, top, 2 * B, span) if top > 0 else 0
    bottom = _refine_edge(gray, bottom - 1, 2 * B, span) if bottom < H else H
    left, right = 0, W
    if top >= 6:
        bg = ImageStat.Stat(img.crop((0, top - 4, W, top - 2))).median[:3]
        cols = _flat(img.crop((0, top + 2, W, bottom - 2)).resize((W, 1), Image.Resampling.BOX))
        far = [max(abs(cols[x][c] - bg[c]) for c in range(3)) > 25 for x in range(W)]
        col_runs = [r for r in _runs(far, 3 * B) if r[1] - r[0] >= 0.3 * W]
        if col_runs:
            left, right = max(col_runs, key=lambda r: r[1] - r[0])
    return [left, top, right - left, bottom - top]


# --------------------------------------------------------------------------- texto
def _mask_rect(size, rect):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rectangle((rect[0], rect[1], rect[2] - 1, rect[3] - 1), fill=255)
    return m


def _bbox_in(mask, rect):
    """bbox (no espaço da imagem) dos pixels ligados de `mask` dentro de `rect` = (x0, y0, x1, y1)."""
    if rect[2] <= rect[0] or rect[3] <= rect[1]:
        return None
    bb = mask.crop(rect).getbbox()
    return (rect[0] + bb[0], rect[1] + bb[1], rect[0] + bb[2], rect[1] + bb[3]) if bb else None


def _blue(img, thr):
    r, _, b = img.split()
    return ImageChops.subtract(b, r).point(lambda v: 255 if v > thr else 0)


def _dense_bbox(mask, rect, min_frac=0.08):
    """bbox só das colunas/linhas com massa de pixels ligados (ignora respingos isolados)."""
    x0, y0, x1, y1 = rect
    if x1 <= x0 or y1 <= y0:
        return None
    crop = mask.crop(rect)
    cols = _flat(crop.resize((crop.width, 1), Image.Resampling.BOX))
    rows = _flat(crop.resize((1, crop.height), Image.Resampling.BOX))
    cx = [i for i, v in enumerate(cols) if v / 255 * crop.height >= min_frac * crop.height]
    ry = [i for i, v in enumerate(rows) if v / 255 * crop.width >= min_frac * crop.width]
    if not cx or not ry:
        return None
    return (x0 + cx[0], y0 + ry[0], x0 + cx[-1] + 1, y0 + ry[-1] + 1)


def _measure_header(img, hb):
    """Logo (claro à esquerda), chip azul (linhas com muito azul), texto do chip e data (escura sobre branco)."""
    W = img.width
    head = img.crop((0, 0, W, hb))
    gray = head.convert("L")
    out = {}
    out["logo"] = _bbox_in(gray.point(lambda v: 255 if v > 110 else 0), (0, 0, int(0.52 * W), hb - 8))
    blue = ImageChops.multiply(_blue(head, 90), _mask_rect((W, hb), (int(0.58 * W), 0, W, hb)))
    rows = _flat(blue.resize((1, hb), Image.Resampling.BOX))
    chip_rows = [r for r in _runs([v / 255 * W >= 0.12 * W for v in rows], 3) if r[1] - r[0] >= 0.02 * W]
    chip = None
    if chip_rows:
        ra, rb = max(chip_rows, key=lambda r: r[1] - r[0])
        chip = _bbox_in(blue, (int(0.58 * W), ra, W, rb))
    out["chip"] = chip
    if chip:
        mid = (chip[1] + chip[3]) // 2
        row = _flat(blue.crop((0, mid, W, mid + 1)))
        x_fill = next((x for x in range(chip[0], chip[2]) if row[x]), chip[0]) + int(0.04 * W)
        white = gray.point(lambda v: 255 if v > 215 else 0)
        band = (x_fill, chip[1] + 8, chip[2], chip[3] - 8)
        cols = _flat(white.crop(band).resize((band[2] - band[0], 1), Image.Resampling.BOX))
        xruns = _runs([v > 0 for v in cols], int(0.045 * W))
        if xruns:
            xa, xb = max(xruns, key=lambda r: sum(1 for v in cols[r[0]:r[1]] if v > 0))
            out["category"] = _bbox_in(white, (band[0] + xa, band[1], band[0] + xb, band[3]))
    out["date"] = _bbox_in(gray.point(lambda v: 255 if v < 100 else 0), (int(0.64 * W), 0, W, (chip[1] - 4) if chip else hb))
    return out


def _vertical_bars(ink, y0, y1, min_run, max_w):
    """Barras verticais finas: (x0, ya, x1, yb) de sequências verticais contínuas longas em colunas vizinhas."""
    data = ink.load()
    cols = []
    for x in range(ink.width):
        run = start = 0
        best = None
        for y in range(y0, y1):
            if data[x, y]:
                if run == 0:
                    start = y
                run += 1
                if run >= min_run and (best is None or run > best[1] - best[0]):
                    best = (start, y + 1)
            else:
                run = 0
        cols.append(best)
    bars = []
    x = 0
    while x < len(cols):
        if cols[x]:
            xe = x
            while xe + 1 < len(cols) and cols[xe + 1]:
                xe += 1
            if xe - x + 1 <= max_w:
                ya, yb = min(c[0] for c in cols[x:xe + 1]), max(c[1] for c in cols[x:xe + 1])
                bars.append((x, ya, xe + 1, yb))
            x = xe + 1
        else:
            x += 1
    return bars


def _measure_panel(img, pt, fb, panel_color):
    """Painel escuro com texto claro: chip da categoria, linhas de texto, barras de destaque e elemento decorativo."""
    W, H = img.size
    lum_panel = _lum(panel_color)
    r, g, b = img.split()
    gray = img.convert("L")
    out = {"chip": None, "chip_text": None, "decor": None, "bars": [], "lines": []}
    out["decor"] = _dense_bbox(_blue(img, 100), (int(0.6 * W), pt, W, fb), 0.3)
    win = (0, max(0, pt - int(0.07 * H)), int(0.4 * W), min(fb, pt + int(0.05 * H)))
    out["chip"] = _dense_bbox(_blue(img, 120), win, 0.15)
    if out["chip"]:
        c = out["chip"]
        out["chip_text"] = _bbox_in(gray.point(lambda v: 255 if v > 225 else 0), (c[0] + int(0.03 * W), c[1] + 6, c[2], c[3] - 4))
    y0 = max(pt, out["chip"][3] + 4 if out["chip"] else pt)
    warm = ImageChops.subtract(r, b).point(lambda v: 255 if v > 60 else 0)
    bright = gray.point(lambda v, lp=lum_panel: 255 if v > lp + 100 else 0)
    ink = ImageChops.subtract(bright, warm)
    y1 = fb - max(12, int(0.016 * H))            # o brilho da borda do rodapé sangra para cima
    keep = _mask_rect((W, H), (0, y0, W, y1))
    if out["decor"]:
        d = out["decor"]
        grow = int(0.012 * W)
        keep = ImageChops.subtract(keep, _mask_rect((W, H), (max(0, d[0] - grow), max(0, d[1] - grow), min(W, d[2] + grow), min(H, d[3] + grow))))
    ink = ImageChops.multiply(ink, keep)
    for bar in _vertical_bars(ink, y0, y1, int(0.05 * H), int(0.02 * W)):
        out["bars"].append(bar)
        ImageDraw.Draw(ink).rectangle((bar[0] - 1, bar[1] - 1, bar[2], bar[3]), fill=0)
    counts = _flat(ink.crop((0, y0, W, y1)).resize((1, y1 - y0), Image.Resampling.BOX))
    for ra, rb in _runs([c > 1 for c in counts], 2):
        if rb - ra < 8:
            continue
        line = ink.crop((0, y0 + ra, W, y0 + rb))
        colv = _flat(line.resize((W, 1), Image.Resampling.BOX))
        xruns = _runs([v > 0 for v in colv], int(0.045 * W))     # separa respingos da foto do texto de verdade
        if not xruns:
            continue
        xa, xb = max(xruns, key=lambda r: sum(1 for v in colv[r[0]:r[1]] if v > 0))
        if xb - xa >= 12:
            sub = line.crop((xa, 0, xb, line.height)).getbbox()
            out["lines"].append((xa + sub[0], y0 + ra + sub[1], xa + sub[2], y0 + ra + sub[3]))
    return out


def _ink_info(img, bbox):
    """Cor de fundo (anel), cor dominante da tinta e cor de destaque dentro da caixa."""
    x0, y0, x1, y1 = bbox
    pad = 6
    box = (max(0, x0 - pad), max(0, y0 - pad), min(img.width, x1 + pad), min(img.height, y1 + pad))
    crop = img.crop(box)
    ring = Image.new("L", crop.size, 0)
    ImageDraw.Draw(ring).rectangle((0, 0, crop.width - 1, crop.height - 1), outline=255, width=2)
    bg = tuple(round(v) for v in ImageStat.Stat(crop, ring).median[:3])
    inner = img.crop(bbox)
    diff = ImageChops.difference(inner, Image.new("RGB", inner.size, bg)).convert("L").point(lambda v: 255 if v > INK_DIFF else 0)
    ink = [p for p, on in zip(_flat(inner), _flat(diff)) if on]
    if not ink:
        return {"bg": bg, "ink": bg, "accent": None}
    bins = {}
    for r, g, b in ink:
        bins.setdefault((r // 32, g // 32, b // 32), []).append((r, g, b))
    ranked = sorted(bins.values(), key=len, reverse=True)

    def mean(pts):
        return tuple(round(sum(p[c] for p in pts) / len(pts)) for c in range(3))

    accent = mean(ranked[1]) if len(ranked) > 1 and len(ranked[1]) >= 0.15 * len(ink) else None
    return {"bg": bg, "ink": mean(ranked[0]), "accent": accent}


def _lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _group_lines(lines, W):
    """Junta linhas vizinhas de mesmo alinhamento e altura parecida em blocos (título, resumo...)."""
    blocks = []
    for ln in sorted(lines, key=lambda b: b[1]):
        h = ln[3] - ln[1]
        for blk in blocks:
            bx0, by0, bx1, by1 = blk["bbox"]
            bh = blk["line_h"]
            same_left = abs(ln[0] - blk["left"]) <= 0.02 * W
            close = 0 <= ln[1] - by1 <= 1.1 * max(h, bh)
            similar = 0.55 <= h / max(1, bh) <= 1.8
            if same_left and close and similar:
                blk["bbox"] = (min(bx0, ln[0]), by0, max(bx1, ln[2]), ln[3])
                blk["lines"].append(ln)
                break
        else:
            blocks.append({"bbox": ln, "lines": [ln], "left": ln[0], "line_h": h})
    return blocks


def measure_reference(path, out_dir=None):
    src = Image.open(path)
    src_format = src.format
    src.load()
    img = src.convert("RGB")
    W, H = img.size
    gray = img.convert("L")
    B = max(8, round(W / 135))
    notes, photo, panel_info, header, footer = [], None, None, None, None

    bands = _hard_bands(gray)
    if bands:
        hb, fb = bands
        pt, panel_color = _panel_top(img, hb, fb)
        photo = [0, hb, W, pt - hb]
        panel_info = {"rect": [0, pt, W, fb - pt], "color": list(panel_color)}
        header, footer = [0, 0, W, hb], [0, fb, W, H - fb]
        notes.append("Bordas retas de largura total (cabeçalho e rodapé) medidas no pixel. A borda foto/painel é uma transição suave: y do painel com margem de ±20 px.")
    else:
        photo = _fallback_photo(img, gray, B)
        if photo:
            header = [0, 0, W, photo[1]] if photo[1] > 0 else None
            notes.append("Bordas retas não encontradas; foto detectada por variação de linhas (menos precisa).")
        else:
            notes.append("Foto não detectada com confiança.")

    photo_bottom = photo[1] + photo[3] if photo else 0
    logo, accents, decor, lines, header_items, shapes = None, [], [], [], [], {}
    if bands:
        head = _measure_header(img, hb)
        logo = head["logo"]
        for role, key in (("data", "date"), ("categoria (cabeçalho)", "category")):
            if head.get(key):
                header_items.append((role, head[key]))
        shapes["header_chip"] = head.get("chip")
        panel = _measure_panel(img, pt, fb, panel_color)
        lines = panel["lines"]
        accents = list(panel["bars"])
        shapes["panel_chip"] = panel["chip"]
        shapes["panel_globe"] = panel["decor"]
        panel_chip = (panel["chip"], panel["chip_text"])
    else:
        panel_chip = (None, None)
        notes.append("Sem bordas retas de largura total: texto não medido automaticamente (informe as zonas).")

    blocks = []
    if bands:
        for role, bb in header_items:
            info = _ink_info(img, bb)
            blocks.append({
                "ink_bbox": [bb[0], bb[1], bb[2] - bb[0], bb[3] - bb[1]], "lines": 1, "line_height_px": bb[3] - bb[1], "line_pitch_px": 0,
                "ink_color": list(info["ink"]), "accent_color": None, "bg_color": list(info["bg"]),
                "align": "center" if abs((bb[0] + bb[2]) / 2 - W / 2) <= 0.02 * W else ("right" if bb[2] >= 0.92 * W else "left"),
                "suggested_role": role, "confidence": "média",
            })
        if panel_chip[1]:
            bb = panel_chip[1]
            info = _ink_info(img, bb)
            blocks.append({
                "ink_bbox": [bb[0], bb[1], bb[2] - bb[0], bb[3] - bb[1]], "lines": 1, "line_height_px": bb[3] - bb[1], "line_pitch_px": 0,
                "ink_color": list(info["ink"]), "accent_color": None, "bg_color": list(info["bg"]), "align": "left",
                "suggested_role": "categoria (chip)", "confidence": "média",
                "chip_shape": [panel_chip[0][0], panel_chip[0][1], panel_chip[0][2] - panel_chip[0][0], panel_chip[0][3] - panel_chip[0][1]],
            })
    for blk in _group_lines(lines, W):
        x0, y0, x1, y1 = blk["bbox"]
        info = _ink_info(img, (x0, y0, x1, y1))
        cx = (x0 + x1) / 2
        align = "center" if abs(cx - W / 2) <= 0.02 * W else ("right" if x1 >= 0.92 * W and x0 > W * 0.45 else "left")
        pitches = [blk["lines"][i + 1][1] - blk["lines"][i][1] for i in range(len(blk["lines"]) - 1)]
        blocks.append({
            "ink_bbox": [x0, y0, x1 - x0, y1 - y0], "lines": len(blk["lines"]),
            "line_height_px": round(median([ln[3] - ln[1] for ln in blk["lines"]])),
            "line_pitch_px": round(median(pitches)) if pitches else 0,
            "ink_color": list(info["ink"]), "accent_color": list(info["accent"]) if info["accent"] else None,
            "bg_color": list(info["bg"]), "align": align,
        })

    # ---- papéis sugeridos (palpite) para os blocos do painel ----
    rest = [b for b in blocks if "suggested_role" not in b]
    if rest:
        main = max(rest, key=lambda b: b["line_height_px"] * (b["lines"] + 1))
        after = [b for b in sorted(rest, key=lambda b: b["ink_bbox"][1]) if b["ink_bbox"][1] > main["ink_bbox"][1]]
        for b in rest:
            if b is main:
                b["suggested_role"], b["confidence"] = "título", "média"
            elif b in after and b is after[-1] and len(after) >= 2:
                b["suggested_role"], b["confidence"] = "crédito", "média"
            elif b in after:
                b["suggested_role"], b["confidence"] = "resumo", "média"
            else:
                b["suggested_role"], b["confidence"] = "não classificado", "baixa"
    ordered = sorted(blocks, key=lambda b: (b["ink_bbox"][1], b["ink_bbox"][0]))
    for i, b in enumerate(ordered, start=1):
        b["id"] = i
    fixed = {}
    if header:
        fixed["header"] = header
    if logo:
        fixed["logo"] = [logo[0], logo[1], logo[2] - logo[0], logo[3] - logo[1]]
    if footer:
        fixed["footer"] = footer

    def rect(c):
        return [c[0], c[1], c[2] - c[0], c[3] - c[1]]

    with open(path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    report = {
        "image": {"file": os.path.basename(path), "sha256": sha, "format": src_format, "width": W, "height": H, "aspect": round(W / H, 4)},
        "photo": photo, "panel": panel_info, "fixed_zones": fixed, "text_blocks": ordered,
        "accent_bars": [rect(a) for a in accents],
        "shapes": {k: rect(v) for k, v in shapes.items() if v},
        "notes": notes + [
            "Caixas de tinta, cores e alinhamento são medidos; 'suggested_role' é palpite. Confirmar cada bloco no overlay.png.",
            "A caixa de tinta é o mínimo do texto de exemplo; a capacidade real da zona (linhas máximas, margens) deve ser confirmada.",
            "Tamanho da fonte só fecha com o arquivo da fonte aprovada no repositório.",
        ] + (["Entrada em JPEG: medidas PRELIMINARES; o definitivo deve vir do PNG original."] if src_format == "JPEG" else []),
    }
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        _overlay(img, report).save(os.path.join(out_dir, "overlay.png"))
        with open(os.path.join(out_dir, "layout-spec.proposed.json"), "w", encoding="utf-8") as f:
            json.dump(propose_spec(report), f, ensure_ascii=False, indent=2)
    return report


def _overlay(img, report):
    scale = min(1.0, 1400 / img.width)
    view = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    d = ImageDraw.Draw(view)
    try:
        font = ImageFont.load_default(16)
    except TypeError:
        font = ImageFont.load_default()

    def box(rect, color, label):
        label = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
        x, y, w, h = [v * scale for v in rect]
        d.rectangle((x, y, x + w, y + h), outline=color, width=3)
        d.rectangle((x, y, x + 8 + 9 * len(label), y + 20), fill=color)
        d.text((x + 4, y + 2), label, fill=(0, 0, 0), font=font)

    if report["photo"]:
        box(report["photo"], (255, 200, 0), "FOTO")
    if report.get("panel"):
        box(report["panel"]["rect"], (255, 0, 255), "PAINEL")
    for name, r in report["fixed_zones"].items():
        box(r, (0, 220, 120), name.upper())
    for b in report["text_blocks"]:
        box(b["ink_bbox"], (255, 60, 60), f"{b['id']} {b['suggested_role'].split(' ')[0]}")
    for r in report["accent_bars"]:
        box(r, (255, 140, 0), "barra")
    return view


def propose_spec(report):
    """Rascunho da spec com as caixas medidas. Continua PENDING_REFERENCE: fonte e tamanhos ficam para confirmar."""
    W, H = report["image"]["width"], report["image"]["height"]
    zones = {}
    if report["photo"]:
        zones["photo"] = {"rect": report["photo"], "fit": "cover", "focus_y": 0.32, "radius": 0, "clear": {"mode": "solid", "color": [0, 0, 0]}}
    names = {"título": "title", "resumo": "summary", "crédito": "credit", "categoria (chip)": "category", "data": "date"}
    for b in report["text_blocks"]:
        name = names.get(b["suggested_role"])
        if name and name not in zones:
            zones[name] = {
                "rect": b["ink_bbox"], "measured_from_example_text": True,
                "text": {"font": "bold", "size": 0, "min_size": 0, "color": b["ink_color"], "align": b["align"]},
                "clear": {"mode": "interpolate_rows", "pad": 4},
            }
    return {
        "schema_version": "1.0", "kind": "feed", "status": "PENDING_REFERENCE", "proposal": True,
        "note": "Gerado por scripts/measure_reference.py. Caixas = tinta do texto de exemplo; ampliar até a capacidade real do design antes de aprovar.",
        "reference": {"file": "assets/templates/reference/" + report["image"]["file"], "sha256": report["image"]["sha256"], "width": W, "height": H},
        "zones": zones, "fixed_zones": report["fixed_zones"],
    }
