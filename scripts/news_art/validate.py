"""Validador determinístico de arte (feed por referência; story estrutural).

Sai com passed=False se qualquer check falhar. Não decide publicar; só bloqueia arte ruim.
"""
import os

from PIL import Image, ImageChops, ImageDraw, ImageStat

from . import imgutil
from .master import flatten
from .render import source_photo_tile
from .spec import SpecError, TEXT_ZONES, thresholds, to_box

MIN_BYTES = 20_000


def _check(checks, cid, ok, detail="", skip=False):
    checks.append({"id": cid, "result": "skip" if skip else ("pass" if ok else "fail"), "detail": detail})


def _finish(checks, art_path, img, data_len):
    return {
        "passed": all(c["result"] != "fail" for c in checks),
        "sha256": imgutil.sha256_file(art_path),
        "width": img.width if img else None,
        "height": img.height if img else None,
        "bytes": data_len,
        "checks": checks,
    }


def _template_hashes(templates_dir):
    hashes = {}
    if templates_dir and os.path.isdir(templates_dir):
        for name in sorted(os.listdir(templates_dir)):
            full = os.path.join(templates_dir, name)
            if os.path.isfile(full):
                hashes[imgutil.sha256_file(full)] = name
    return hashes


def _open(art_path, checks, spec):
    out = spec["output"]
    size = os.path.getsize(art_path)
    try:
        img = Image.open(art_path)
        img.load()
        img = img.convert("RGB")
    except Exception as e:  # arquivo quebrado
        _check(checks, "dimensions", False, f"não abre como imagem: {e}")
        return None, size
    ok = img.size == (out["width"], out["height"])
    _check(checks, "dimensions", ok, f"{img.width}x{img.height}, esperado {out['width']}x{out['height']}")
    max_bytes = out.get("max_bytes", 8 * 1024 * 1024)
    _check(checks, "size_limits", MIN_BYTES <= size <= max_bytes, f"{size} bytes (limites {MIN_BYTES}..{max_bytes})")
    return img, size


def validate_feed(art_path, spec, master, *, reference=None, source_photo=None, fit_report=None, templates_dir=None, public_bytes=None):
    th = thresholds(spec)
    checks = []
    master = flatten(master)
    img, size = _open(art_path, checks, spec)
    known = _template_hashes(templates_dir)
    if img is None or img.size != (spec["output"]["width"], spec["output"]["height"]):
        # mesmo com tamanho errado, uma cópia exata de arquivo de template precisa ser acusada
        art_sha = imgutil.sha256_file(art_path)
        if art_sha in known:
            _check(checks, "not_equal_to_master", False, f"sha igual a {known[art_sha]}")
        return _finish(checks, art_path, img, size)

    ref_w, ref_h = spec["reference"]["width"], spec["reference"]["height"]
    sx, sy = img.width / ref_w, img.height / ref_h
    master_out = master.resize(img.size, Image.Resampling.LANCZOS)

    # 1) igual ao template mestre (arquivo idêntico, cópia recodificada ou quase igual)
    art_sha = imgutil.sha256_file(art_path)
    mae_full = imgutil.mean_abs_diff(img, master_out)
    same_file = art_sha in known
    _check(checks, "not_equal_to_master", not same_file and mae_full >= th["master_mae_min"],
           f"sha igual a {known[art_sha]}" if same_file else f"diferença média para o mestre {mae_full:.2f} (mínimo {th['master_mae_min']})")
    dist = imgutil.hamming(imgutil.dhash(img), imgutil.dhash(master_out))
    _check(checks, "not_near_master", dist >= th["dhash_min_distance"], f"distância dhash {dist} (mínimo {th['dhash_min_distance']})")

    # 1b) sobra da matéria de exemplo da referência (o caso "Alibaba dentro de outra notícia")
    if reference is None:
        _check(checks, "no_sample_content", True, "referência não informada", skip=True)
    else:
        ref_out = reference.resize(img.size, Image.Resampling.LANCZOS)
        ref_dist = imgutil.hamming(imgutil.dhash(img), imgutil.dhash(ref_out))
        ref_mae = imgutil.mean_abs_diff(img, ref_out)
        left = []
        if ref_mae < th["master_mae_min"] or ref_dist < th["dhash_min_distance"]:
            left.append("arte inteira igual à referência")
        for name, cfg in spec["zones"].items():
            # categoria e data podem coincidir legitimamente com as do exemplo; foto, título, resumo e crédito não
            if name not in ("photo", "title", "summary", "credit"):
                continue
            zb = to_box(cfg["rect"], sx, sy)
            a, r = img.crop(zb), ref_out.crop(zb)
            if name == "photo":
                if imgutil.mean_abs_diff(a, r) < th["photo_mae_min"]:
                    left.append("foto")
            elif imgutil.diff_ratio(a, r) < th["text_diff_ratio_min"]:
                left.append(name)
        _check(checks, "no_sample_content", not left, "conteúdo da referência ainda presente em: " + ", ".join(left) if left else "nenhuma zona repete a matéria de exemplo")

    # 2) foto trocada e não achatada
    photo_cfg = spec["zones"]["photo"]
    photo_box = to_box(photo_cfg["rect"], sx, sy)
    art_photo = img.crop(photo_box)
    win_box = to_box(photo_cfg.get("window") or photo_cfg["rect"], sx, sy)   # janela transparente do mestre, quando houver
    art_win, master_win = img.crop(win_box), master_out.crop(win_box)
    photo_mae = imgutil.mean_abs_diff(art_win, master_win)
    photo_std = imgutil.gray_std(art_win)
    _check(checks, "photo_zone_changed", photo_mae >= th["photo_mae_min"] and photo_std >= th["photo_std_min"],
           f"diferença {photo_mae:.1f} (mín {th['photo_mae_min']}), variação {photo_std:.1f} (mín {th['photo_std_min']})")

    # 3) campos de texto obrigatórios realmente escritos
    weak = []
    for name in TEXT_ZONES:
        zone = spec["zones"].get(name)
        if not zone or not zone.get("required", name in ("category", "category_chip", "date", "title")):
            continue
        box = to_box(zone["rect"], sx, sy)
        ratio = imgutil.diff_ratio(img.crop(box), master_out.crop(box))
        if ratio < th["text_diff_ratio_min"]:
            weak.append(f"{name} ({ratio:.4f})")
    _check(checks, "text_zones_changed", not weak, "sem texto visível em: " + ", ".join(weak) if weak else "todas as zonas obrigatórias têm texto")

    # 4) identidade preservada: zonas fixas e todo o complemento das zonas variáveis
    bad_fixed = []
    for name, rect in (spec.get("fixed_zones") or {}).items():
        box = to_box(rect, sx, sy)
        mae = imgutil.mean_abs_diff(img.crop(box), master_out.crop(box))
        if mae > th["identity_mae_max"]:
            bad_fixed.append(f"{name} ({mae:.1f})")
    _check(checks, "identity_preserved", not bad_fixed,
           "zonas fixas alteradas: " + ", ".join(bad_fixed) if bad_fixed else f"zonas fixas dentro de {th['identity_mae_max']}")
    diff = ImageChops.difference(img, master_out)
    draw = ImageDraw.Draw(diff)
    var_area = 0
    for cfg in spec["zones"].values():
        b = to_box(cfg["rect"], sx, sy)
        draw.rectangle((b[0], b[1], b[2] - 1, b[3] - 1), fill=(0, 0, 0))
        var_area += (b[2] - b[0]) * (b[3] - b[1])
    total = img.width * img.height
    outside = sum(ImageStat.Stat(diff).mean) / 3.0 * total / max(1, total - var_area)
    _check(checks, "outside_zones_intact", outside <= th["complement_mae_max"],
           f"diferença fora das zonas variáveis {outside:.2f} (máx {th['complement_mae_max']}); acusa texto vazando ou elementos sobrepostos")

    # 5) encaixe de texto (relatório do renderizador)
    if fit_report is None:
        _check(checks, "text_fit", True, "sem relatório de encaixe; outside_zones_intact cobre texto fora das zonas", skip=True)
    else:
        bad = [r["zone"] for r in fit_report if r.get("overflow") or (r.get("truncated") and not r.get("allow_ellipsis"))]
        _check(checks, "text_fit", not bad, "texto cortado ou fora da zona: " + ", ".join(bad) if bad else "todos os textos couberam")

    # 6) a foto usada é a da pauta
    if source_photo is None:
        _check(checks, "photo_matches_source", True, "foto de origem não informada", skip=True)
    else:
        tile = source_photo_tile(spec, source_photo).resize(art_photo.size, Image.Resampling.LANCZOS)
        corr = imgutil.correlation(art_photo, tile)
        _check(checks, "photo_matches_source", corr >= th["photo_match_min"], f"correlação {corr:.2f} (mín {th['photo_match_min']})")

    # 7) arquivo público == arquivo validado
    if public_bytes is None:
        _check(checks, "published_equals_validated", True, "arquivo público ainda não conferido", skip=True)
    else:
        same = imgutil.sha256_bytes(public_bytes) == art_sha
        _check(checks, "published_equals_validated", same, "sha256 do arquivo público " + ("confere" if same else "DIFERE do validado"))
    return _finish(checks, art_path, img, size)


def validate_structural(art_path, spec, *, public_bytes=None):
    """Story: sem referência por pixels; confere dimensões, foto, texto presente e assinatura de cor."""
    th = thresholds(spec)
    checks = []
    img, size = _open(art_path, checks, spec)
    if img is None or img.size != (spec["output"]["width"], spec["output"]["height"]):
        return _finish(checks, art_path, img, size)
    zones = spec["zones"]
    if "photo" in zones:
        box = to_box(zones["photo"]["rect"])
        inner = zones["photo"].get("inner")
        if inner:  # foto "contain" tem faixas nas bordas: olhar só o miolo, onde a foto sempre está
            w, h = box[2] - box[0], box[3] - box[1]
            dx, dy = int(w * (1 - inner) / 2), int(h * (1 - inner) / 2)
            box = (box[0] + dx, box[1] + dy, box[2] - dx, box[3] - dy)
        std = imgutil.gray_std(img.crop(box))
        _check(checks, "photo_zone_changed", std >= th["photo_std_min"], f"variação da foto {std:.1f} (mín {th['photo_std_min']})")
    empty = []
    for name in TEXT_ZONES:
        if name in zones:
            std = imgutil.gray_std(img.crop(to_box(zones[name]["rect"])))
            if std < zones[name].get("min_std", 3.0):
                empty.append(f"{name} ({std:.1f})")
    _check(checks, "text_zones_changed", not empty, "sem texto visível em: " + ", ".join(empty) if empty else "texto presente")
    off = []
    for sig in spec.get("signature_zones", []):
        mean = imgutil.mean_color(img.crop(to_box(sig["rect"])))
        if max(abs(a - b) for a, b in zip(mean, sig["color"])) > sig.get("tol", 20):
            off.append(f"{sig['name']} {tuple(round(v) for v in mean)}")
    _check(checks, "identity_preserved", not off, "cor fora da identidade em: " + ", ".join(off) if off else "cores fixas conferem")
    if public_bytes is None:
        _check(checks, "published_equals_validated", True, "arquivo público ainda não conferido", skip=True)
    else:
        same = imgutil.sha256_bytes(public_bytes) == imgutil.sha256_file(art_path)
        _check(checks, "published_equals_validated", same, "sha256 do arquivo público " + ("confere" if same else "DIFERE do validado"))
    return _finish(checks, art_path, img, size)


def validate(art_path, spec, master=None, **kw):
    mode = thresholds(spec)["mode"]
    if mode == "structural":
        return validate_structural(art_path, spec, public_bytes=kw.get("public_bytes"))
    if master is None:
        raise SpecError("validação por referência precisa do mestre")
    return validate_feed(art_path, spec, master, **kw)
