"""Leitura e validação da especificação de layout (assets/templates/layout-spec*.json).

Coordenadas das zonas ficam no espaço de pixels do PNG de referência ([x, y, largura, altura]).
Uma spec com status PENDING_REFERENCE recusa gerar/validar arte: o gerador falha fechado
enquanto as medidas não forem extraídas do PNG aprovado.
"""
import json

TEXT_ZONES = ("category", "category_chip", "date", "title", "summary", "credit")
REQUIRED_TEXT_ZONES = ("category", "date", "title")

DEFAULT_VALIDATION = {
    "mode": "reference",
    "master_mae_min": 3.0,       # arte inteira x mestre: abaixo disso é "igual ao template"
    "dhash_min_distance": 10,    # de 64 bits
    "photo_mae_min": 8.0,
    "photo_std_min": 6.0,
    "photo_match_min": 0.85,
    "text_diff_ratio_min": 0.003,
    "identity_mae_max": 4.0,     # zonas fixas x mestre (tolera ruído de JPEG)
    "complement_mae_max": 4.0,   # tudo fora das zonas variáveis x mestre
    "master_residual_std_max": 3.0,
    "master_clean_std_max": 4.0,  # regiões que o mestre precisa ter limpas (spec.master_clean_regions)
}


class SpecError(Exception):
    pass


def load_spec(path):
    with open(path, encoding="utf-8") as f:
        spec = json.load(f)
    validate_spec(spec)
    return spec


def _rect_ok(rect, bounds=None):
    if not (isinstance(rect, (list, tuple)) and len(rect) == 4 and all(isinstance(v, int) for v in rect)):
        return False
    x, y, w, h = rect
    if x < 0 or y < 0 or w <= 0 or h <= 0:
        return False
    if bounds and (x + w > bounds[0] or y + h > bounds[1]):
        return False
    return True


def validate_spec(spec):
    errs = []
    if spec.get("schema_version") != "1.0":
        errs.append("schema_version deve ser 1.0")
    if spec.get("kind") not in ("feed", "story"):
        errs.append("kind deve ser feed ou story")
    if spec.get("status") not in ("APPROVED", "PENDING_REFERENCE"):
        errs.append("status deve ser APPROVED ou PENDING_REFERENCE")
    out = spec.get("output") or {}
    if not all(isinstance(out.get(k), int) and out[k] > 0 for k in ("width", "height")):
        errs.append("output.width e output.height são obrigatórios")
    if errs or spec.get("status") == "PENDING_REFERENCE":
        if errs:
            raise SpecError("; ".join(errs))
        return
    mode = (spec.get("validation") or {}).get("mode", "reference")
    zones = spec.get("zones") or {}
    if mode == "reference":
        ref = spec.get("reference") or {}
        if not all(isinstance(ref.get(k), int) and ref[k] > 0 for k in ("width", "height")) or not ref.get("file"):
            errs.append("reference.file, reference.width e reference.height são obrigatórios")
        else:
            bounds = (ref["width"], ref["height"])
            ratio_ref = ref["width"] / ref["height"]
            ratio_out = out["width"] / out["height"]
            if abs(ratio_ref - ratio_out) / ratio_out > 0.005:
                errs.append(
                    f"proporção da referência ({ref['width']}x{ref['height']}) difere da saída ({out['width']}x{out['height']}); "
                    "ajuste output para a mesma proporção da arte aprovada"
                )
            if "photo" not in zones:
                errs.append("zona photo é obrigatória")
            for name in REQUIRED_TEXT_ZONES:
                if name not in zones:
                    errs.append(f"zona {name} é obrigatória")
            for name, cfg in zones.items():
                if not _rect_ok(cfg.get("rect"), bounds):
                    errs.append(f"zona {name}: rect inválido ou fora da referência")
                if name in TEXT_ZONES:
                    text = cfg.get("text") or {}
                    if not (text.get("font") and isinstance(text.get("size"), int) and text.get("color")):
                        errs.append(f"zona {name}: text.font, text.size e text.color são obrigatórios")
            for name, rect in (spec.get("fixed_zones") or {}).items():
                if not _rect_ok(rect, bounds):
                    errs.append(f"fixed_zones.{name}: rect inválido ou fora da referência")
            if not spec.get("fonts"):
                errs.append("fonts é obrigatório")
    else:
        for name, cfg in zones.items():
            if not _rect_ok(cfg.get("rect"), (out["width"], out["height"])):
                errs.append(f"zona {name}: rect inválido ou fora da arte")
    if errs:
        raise SpecError("; ".join(errs))


def require_approved(spec):
    if spec.get("status") != "APPROVED":
        raise SpecError(
            "layout-spec pendente (status=PENDING_REFERENCE): falta o PNG de referência e a medição das zonas. "
            "O gerador não roda enquanto a spec não for aprovada."
        )


def thresholds(spec):
    merged = dict(DEFAULT_VALIDATION)
    merged.update(spec.get("validation") or {})
    return merged


def to_box(rect, sx=1.0, sy=1.0):
    """[x, y, w, h] -> (x0, y0, x1, y1) escalado e arredondado."""
    x, y, w, h = rect
    return (round(x * sx), round(y * sy), round((x + w) * sx), round((y + h) * sy))
