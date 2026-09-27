"""Template mestre: a arte aprovada SEM a matéria de exemplo.

O mestre é derivado do PNG de referência: as zonas variáveis (foto, categoria, data, título,
resumo, crédito) são limpas e todo o resto continua sendo os pixels originais. A matéria da
referência (por exemplo Alibaba) não pode sobrar no mestre; `residual_report` acusa se sobrou.
Se preferirem entregar um mestre já limpo, use master.source = "file" na spec.
"""
import os

from PIL import Image, ImageDraw

from . import imgutil
from .spec import SpecError, thresholds, to_box


def clear_zone(img, rect, cfg):
    mode = (cfg or {}).get("mode", "none")
    if mode == "none":
        return
    x0, y0, x1, y1 = to_box(rect)
    w, h = x1 - x0, y1 - y0
    W, H = img.size
    if mode == "solid":
        ImageDraw.Draw(img).rectangle((x0, y0, x1 - 1, y1 - 1), fill=tuple(cfg["color"]))
    elif mode == "interpolate_rows":
        # cada linha vira a interpolação linear entre a cor à esquerda e à direita da zona
        pad = int(cfg.get("pad", 4))
        left = img.crop((max(0, x0 - pad), y0, x0, y1)).resize((1, h), Image.Resampling.BOX)
        right = img.crop((x1, y0, min(W, x1 + pad), y1)).resize((1, h), Image.Resampling.BOX)
        pair = Image.new("RGB", (2, h))
        pair.paste(left, (0, 0))
        pair.paste(right, (1, 0))
        img.paste(pair.resize((w, h), Image.Resampling.BILINEAR), (x0, y0))
    elif mode == "interpolate_cols":
        pad = int(cfg.get("pad", 4))
        top = img.crop((x0, max(0, y0 - pad), x1, y0)).resize((w, 1), Image.Resampling.BOX)
        bottom = img.crop((x0, y1, x1, min(H, y1 + pad))).resize((w, 1), Image.Resampling.BOX)
        pair = Image.new("RGB", (w, 2))
        pair.paste(top, (0, 0))
        pair.paste(bottom, (0, 1))
        img.paste(pair.resize((w, h), Image.Resampling.BILINEAR), (x0, y0))
    else:
        raise SpecError(f"clear.mode desconhecido: {mode}")


def build_master(reference, spec):
    master = reference.convert("RGB").copy()
    for name, cfg in spec["zones"].items():
        clear_zone(master, cfg["rect"], cfg.get("clear"))
    return master


def flatten(master, gray=128):
    """Mestre RGBA (janela da foto transparente) achatado sobre cinza neutro, para comparações."""
    if master.mode != "RGBA":
        return master.convert("RGB")
    base = Image.new("RGBA", master.size, (gray, gray, gray, 255))
    return Image.alpha_composite(base, master).convert("RGB")


def residual_report(master, spec, std_max):
    """Zonas variáveis do mestre que ainda têm detalhe (sobra de texto ou foto de exemplo)."""
    has_alpha = master.mode == "RGBA"
    master = flatten(master)
    bad = []
    for name, cfg in spec["zones"].items():
        if name == "photo" and has_alpha:   # janela transparente: o que há por baixo é a foto, não conteúdo de exemplo
            continue
        crop = master.crop(to_box(cfg["rect"]))
        std = imgutil.gray_std(crop)
        if std > std_max:
            bad.append({"zone": name, "std": round(std, 2)})
    clean_max = thresholds(spec)["master_clean_std_max"]
    for i, rect in enumerate(spec.get("master_clean_regions") or []):
        std = imgutil.gray_std(master.crop(to_box(rect)))
        if std > clean_max:
            bad.append({"zone": f"master_clean_regions[{i}]", "std": round(std, 2)})
    return bad


def load_master(spec, root="."):
    """Devolve (mestre RGB no tamanho da referência, info). Falha se o mestre ainda tiver a matéria de exemplo."""
    ref_cfg = spec["reference"]
    master_cfg = spec.get("master") or {"source": "generate"}
    reference = None
    ref_path = os.path.join(root, ref_cfg["file"])
    if os.path.isfile(ref_path):
        reference = Image.open(ref_path)
        reference.load()
        reference = reference.convert("RGB")
    if master_cfg.get("source") == "file":
        path = os.path.join(root, master_cfg["file"])
        raw = Image.open(path)
        raw.load()
        # com transparência: a foto entra POR BAIXO do mestre (chip, painel e bordas suaves ficam por cima)
        master = raw.convert("RGBA") if raw.mode in ("RGBA", "LA") or "transparency" in raw.info else raw.convert("RGB")
        source = master_cfg["file"]
    else:
        if reference is None:
            raise SpecError(f"PNG de referência não encontrado: {ref_cfg['file']}")
        expected = ref_cfg.get("sha256")
        if expected and imgutil.sha256_file(ref_path) != expected:
            raise SpecError("sha256 do PNG de referência não confere com a spec")
        if reference.size != (ref_cfg["width"], ref_cfg["height"]):
            raise SpecError(f"PNG de referência tem {reference.size}, a spec diz {ref_cfg['width']}x{ref_cfg['height']}")
        master = build_master(reference, spec)
        source = "generated:" + ref_cfg["file"]
    if master.size != (ref_cfg["width"], ref_cfg["height"]):
        raise SpecError(f"mestre tem {master.size}, esperado {ref_cfg['width']}x{ref_cfg['height']}")
    residual = residual_report(master, spec, thresholds(spec)["master_residual_std_max"])
    if residual:
        raise SpecError(
            "o mestre ainda tem conteúdo da matéria de exemplo nas zonas: "
            + ", ".join(f"{r['zone']} (desvio {r['std']})" for r in residual)
            + ". Ajuste o rect/clear dessas zonas na spec ou forneça um mestre limpo (master.source=file)."
        )
    return master, {"source": source, "reference": reference}


def master_meta(master, out_size):
    """Metadados para conferência: hash exato do PNG do mestre e hash perceptual no tamanho de saída."""
    import io
    buf = io.BytesIO()
    master.save(buf, "PNG")
    resized = flatten(master).resize(out_size, Image.Resampling.LANCZOS)
    return {
        "sha256_png": imgutil.sha256_bytes(buf.getvalue()),
        "dhash": f"{imgutil.dhash(resized):016x}",
        "reference_size": list(master.size),
        "output_size": list(out_size),
    }
