"""Composição do feed: mestre (identidade fixa) + foto + textos nas zonas da spec."""
import os

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .spec import SpecError, TEXT_ZONES, REQUIRED_TEXT_ZONES, to_box


class RenderError(Exception):
    pass


class FontBook:
    def __init__(self, spec, root="."):
        self.spec = spec
        self.root = root
        self._cache = {}

    def load(self, name, size):
        key = (name, size)
        if key in self._cache:
            return self._cache[key]
        candidates = (self.spec.get("fonts") or {}).get(name) or []
        for path in candidates:
            full = path if os.path.isabs(path) else os.path.join(self.root, path)
            if os.path.isfile(full):
                self._cache[key] = ImageFont.truetype(full, size)
                return self._cache[key]
        if (self.spec.get("fonts") or {}).get("allow_fallback"):
            self._cache[key] = ImageFont.load_default(size)
            return self._cache[key]
        raise RenderError(f"fonte '{name}' não encontrada; procurei: {candidates}. A fonte da arte aprovada precisa estar no repositório.")


def wrap(measure, text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        test = (cur + " " + word).strip()
        if measure.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def layout_text(text, cfg, w, h, loader):
    """Encaixa o texto na zona: reduz a fonte até `min_size`; se ainda não couber, corta e sinaliza."""
    size = cfg["size"]
    min_size = cfg.get("min_size", size)
    max_lines = cfg.get("max_lines", 1)
    spacing = (cfg["line_pitch"] / cfg["size"]) if "line_pitch" in cfg else cfg.get("line_spacing", 1.15)
    ellipsis_ok = cfg.get("ellipsis", False)
    measure = ImageDraw.Draw(Image.new("L", (1, 1)))
    while True:
        font = loader(size)
        lines = wrap(measure, text, font, w)
        fits = (
            len(lines) <= max_lines
            and len(lines) * size * spacing <= h + 0.5
            and all(measure.textlength(line, font=font) <= w for line in lines)
        )
        if fits or size <= min_size:
            break
        size -= 1
    truncated = ellipsized = overflow = False
    if not fits:
        truncated = True
        lines = lines[:max_lines]
        if ellipsis_ok and lines:
            last = lines[-1].split()
            while last and measure.textlength(" ".join(last) + "…", font=font) > w:
                last.pop()
            lines[-1] = (" ".join(last).rstrip(",.;:") + "…") if last else "…"
            ellipsized = True
        elif any(measure.textlength(line, font=font) > w for line in lines):
            overflow = True
        if len(lines) * size * spacing > h + 0.5:
            overflow = True
        if not ellipsis_ok:
            overflow = True
    return font, size, lines, {"font_size": size, "lines": len(lines), "truncated": truncated, "ellipsized": ellipsized, "overflow": overflow}


def _place_photo(work, photo, zone):
    x0, y0, x1, y1 = to_box(zone["rect"])
    w, h = x1 - x0, y1 - y0
    src = ImageOps.exif_transpose(photo).convert("RGB")
    if zone.get("fit", "cover") == "contain":
        fitted = ImageOps.contain(src, (w, h), Image.Resampling.LANCZOS)
        tile = Image.new("RGB", (w, h), tuple(zone.get("letterbox", [0, 0, 0])))
        tile.paste(fitted, ((w - fitted.width) // 2, (h - fitted.height) // 2))
    else:
        tile = ImageOps.fit(src, (w, h), Image.Resampling.LANCZOS, centering=(0.5, zone.get("focus_y", 0.5)))
    radius = int(zone.get("radius", 0))
    if radius > 0:
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
        work.paste(tile, (x0, y0), mask)
    else:
        work.paste(tile, (x0, y0))
    return tile


def _line_words(line, first_index, total, cfg):
    words = line.split(" ")
    accent_n = int(cfg.get("accent_last_words", 0))
    out = []
    for k, w in enumerate(words):
        idx = first_index + k
        color = tuple(cfg["accent_color"]) if accent_n and idx >= total - accent_n and cfg.get("accent_color") else tuple(cfg["color"])
        out.append((w, color))
    return out


def line_positions(big, lines, ss, baseline_first, pitch, gap=6):
    """Linhas de base (px do espaço de referência). Mantém o passo nominal, mas empurra a linha para baixo
    quando acentos de maiúsculas (Ê, Í, Ã) bateriam nas letras da linha anterior. Devolve (ys, fundo_da_última)."""
    ys, prev_bottom = [], None
    for i, line in enumerate(lines):
        _, top, _, bottom = big.getbbox(line, anchor="ls")
        top, bottom = top / ss, bottom / ss
        y = baseline_first + i * pitch
        if prev_bottom is not None:
            y = max(y, prev_bottom + gap - top)
        ys.append(y)
        prev_bottom = y + bottom
    return ys, prev_bottom


def render_feed(spec, master, photo, fields, root="."):
    """Devolve (imagem RGB no tamanho de saída, relatório de encaixe por zona).

    Mestre RGBA: a foto entra por baixo e o mestre por cima. O texto é desenhado em uma camada com
    supersampling (`output.text_supersample`, padrão 2) e reduzido com LANCZOS antes de compor.
    """
    for name in REQUIRED_TEXT_ZONES:
        if not str(fields.get(name) or "").strip():
            raise RenderError(f"campo obrigatório vazio: {name}")
    if photo is None:
        raise RenderError("foto ausente")
    if master.mode == "RGBA":
        canvas = Image.new("RGB", master.size, (0, 0, 0))
        _place_photo(canvas, photo, spec["zones"]["photo"])
        work = Image.alpha_composite(canvas.convert("RGBA"), master).convert("RGB")
    else:
        work = master.convert("RGB").copy()
        _place_photo(work, photo, spec["zones"]["photo"])
    W, H = work.size
    out = spec["output"]
    ss = int(out.get("text_supersample", 2))
    layer = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    fonts = FontBook(spec, root)
    report = []
    for name in TEXT_ZONES:
        zone = spec["zones"].get(name)
        text = str(fields.get(name) or (fields.get("category") if name == "category_chip" else "") or "").strip()
        if not zone or not text:
            continue
        cfg = zone["text"]
        if cfg.get("prefix") and not text.lower().startswith(cfg["prefix"].lower()):
            text = cfg["prefix"] + text
        if cfg.get("case") == "upper":
            text = text.upper()
        x0, y0, x1, y1 = to_box(zone["rect"])
        w, h = x1 - x0, y1 - y0
        font, size, lines, info = layout_text(text, cfg, w, h, lambda s, n=cfg["font"]: fonts.load(n, s))
        big = fonts.load(cfg["font"], size * ss)
        ratio = size / cfg["size"]
        pitch = (cfg["line_pitch"] * ratio) if "line_pitch" in cfg else size * cfg.get("line_spacing", 1.15)
        total_words = sum(len(l.split(" ")) for l in lines)
        done = 0
        ys = None
        if "baseline_first" in cfg:
            ys, last_bottom = line_positions(big, lines, ss, cfg["baseline_first"], pitch)
            if last_bottom > y1 + 2:            # com o empurrão dos acentos a última linha passou da zona
                info = dict(info, overflow=True)
        for i, line in enumerate(lines):
            lw = big.getlength(line) / ss
            align = cfg.get("align", "left")
            x = x0 + ((w - lw) / 2 if align == "center" else (w - lw) if align == "right" else 0)
            if ys is not None:
                y, anchor = ys[i], "ls"
            else:
                total = pitch * len(lines)
                y, anchor = y0 + ((h - total) / 2 if cfg.get("valign", "top") == "middle" else 0) + i * pitch, "la"
            cursor = x * ss
            space = big.getlength(" ")
            for word, color in _line_words(line, done, total_words, cfg):
                draw.text((cursor, y * ss), word, font=big, fill=color + (255,), anchor=anchor)
                cursor += big.getlength(word) + space
            done += len(line.split(" "))
        report.append({"zone": name, "allow_ellipsis": bool(cfg.get("ellipsis")), **info})
    layer = layer.resize((W, H), Image.Resampling.LANCZOS)
    work = Image.alpha_composite(work.convert("RGBA"), layer).convert("RGB")
    final = work if work.size == (out["width"], out["height"]) else work.resize((out["width"], out["height"]), Image.Resampling.LANCZOS)
    return final, report


def save_jpeg(img, path, spec):
    out = spec["output"]
    quality = int(out.get("jpeg_quality", 95))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    while True:
        img.save(path, "JPEG", quality=quality, optimize=True, progressive=True, subsampling=0)
        if os.path.getsize(path) <= out.get("max_bytes", 8 * 1024 * 1024) or quality <= 65:
            return quality
        quality -= 4


def source_photo_tile(spec, photo):
    """A foto como o renderizador a coloca (para conferir depois se a foto certa foi usada)."""
    tmp = Image.new("RGB", tuple(spec["reference"][k] for k in ("width", "height")))
    return _place_photo(tmp, photo, spec["zones"]["photo"])
