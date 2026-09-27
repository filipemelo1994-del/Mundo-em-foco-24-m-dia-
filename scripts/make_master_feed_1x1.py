#!/usr/bin/env python3
"""Gera o master RGBA do feed 1:1 e a spec de teste a partir da referência preliminar (1536x1536).

Específico da arte aprovada em 26/09/2026. Coordenadas = medição automática validada
(scripts/measure_reference.py) aprovada como base de trabalho. Faz, nesta ordem:
  1. remove data, categoria (cabeçalho) e texto do chip por interpolação das margens;
  2. reconstrói o painel escuro (sem foto, sem título/resumo/crédito) a partir da cor por linha;
  3. abre a janela transparente da foto (linhas 250-835) com rampa suave até o painel opaco (835-885);
  4. mantém por CIMA da foto o chip da categoria (com o texto removido);
  5. preserva globo, barra de destaque, cabeçalho, logo e rodapé como pixels originais;
  6. calcula tamanho e linha de base da fonte pela largura da tinta dos textos de exemplo.
Saídas: assets/templates/master-feed-v1.png e assets/templates/layout-spec.v1.json (spec V1
aprovada para uso operacional; refinamentos de posição e a fonte definitiva ficam para V1.1).
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageChops, ImageDraw, ImageFont  # noqa: E402

from news_art import imgutil, master as M  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = "assets/templates/reference/referencia-preliminar-1536.jpg"
MASTER_OUT = "assets/templates/master-feed-v1.png"
SPEC_OUT = "assets/templates/layout-spec.v1.json"
BOLD = "assets/fonts/WorkSans_800ExtraBold.ttf"
REGULAR = "assets/fonts/WorkSans_500Medium.ttf"

W = H = 1536
HEADER_LINE_END = 250          # até aqui o cabeçalho (e o brilho da borda) fica opaco
RAMP_TOP, RAMP_BOTTOM = 835, 885
PANEL_END = 1332               # abaixo disso: brilho da borda do rodapé, preservado
CLEAN_RECTS = {                # [x, y, largura, altura] com folga sobre a tinta medida
    "date": (1196, 58, 255, 46),
    "category": (1155, 145, 305, 50),
    "chip_text": (104, 835, 233, 42),
}
KEEP_GLOBE = (1235, 1110, 1536, PANEL_END)     # x0, y0, x1, y1 (bordas esquerda e superior com transição de 44 px)
KEEP_FEATHER = 44
KEEP_BAR = (86, 1156, 108, 1278)
CHIP_BOX = (45, 811, 399, 901)

# medidas de tinta dos textos de exemplo (medição automática aprovada): texto -> [x0, y0, x1, y1]
MEASURED = {
    "title": [("ALIBABA APRESENTA NOVO", (85, 917, 1288, 979)), ("CHIP DE IA E PREPARA", (88, 996, 1047, 1056)), ("MODELOS QWEN MAIORES", (90, 1073, 1221, 1144))],
    "summary": [("Empresa chinesa apresentou o Zhenwu V900 e informou que", (130, 1164, 1080, 1187)),
                ("trabalha em modelos de inteligência artificial com escala de", (128, 1202, 1021, 1225)),
                ("5 trilhões de parâmetros, ampliando sua competitividade no setor.", (129, 1241, 1117, 1268))],
    "credit": [("Foto: REUTERS/Dado Ruvic | Ilustração de arquivc", (91, 1310, 634, 1329))],
    "date": [("27 SET 2026", (1206, 68, 1441, 94))],
    "category": [("TECNOLOGIA", (1165, 155, 1450, 185))],
    "category_chip": [("TECNOLOGIA", (114, 845, 327, 867))],
}


def flat(im):
    return list(getattr(im, "get_flattened_data", im.getdata)())


def row_median(img, y, x0, x1):
    px = flat(img.crop((x0, y, x1, y + 1)))
    return tuple(sorted(p[c] for p in px)[len(px) // 2] for c in range(3))


def smooth(values, window=11):
    half = window // 2
    out = []
    for i in range(len(values)):
        seg = values[max(0, i - half): i + half + 1]
        out.append(tuple(sorted(s[c] for s in seg)[len(seg) // 2] for c in range(3)))
    return out


def panel_colors(img):
    ys = list(range(RAMP_BOTTOM, PANEL_END))
    mid = {y: row_median(img, y, 420, 1090) for y in range(RAMP_BOTTOM, 916)}
    left = {y: row_median(img, y, 8, 60) for y in range(905, PANEL_END)}
    off = [sum(mid[y][c] - left[y][c] for y in range(905, 916)) / 11 for c in range(3)]
    raw = [mid[y] if y <= 915 else tuple(round(left[y][c] + off[c]) for c in range(3)) for y in ys]
    return dict(zip(ys, smooth(raw)))


def build_master(img):
    clean = img.copy()
    for rect in CLEAN_RECTS.values():
        M.clear_zone(clean, list(rect), {"mode": "interpolate_rows", "pad": 6})
    colors = panel_colors(img)
    base = Image.new("RGB", (W, H), (0, 0, 0))
    base.paste(clean.crop((0, 0, W, HEADER_LINE_END)), (0, 0))                       # cabeçalho, logo, brilho da borda
    d = ImageDraw.Draw(base)
    for y in range(RAMP_TOP, RAMP_BOTTOM):
        d.line((0, y, W, y), fill=colors[RAMP_BOTTOM])
    for y in range(RAMP_BOTTOM, PANEL_END):
        d.line((0, y, W, y), fill=colors[y])
    base.paste(clean.crop((0, PANEL_END, W, H)), (0, PANEL_END))                     # brilho da borda + rodapé
    gx0, gy0, gx1, gy1 = KEEP_GLOBE
    gmask = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(gmask)
    for i in range(KEEP_FEATHER):                       # transição suave: o fundo original do globo é um pouco mais claro que o painel
        v = round(255 * (i + 1) / KEEP_FEATHER)
        gd.rectangle((gx0 + i, gy0 + i, gx1, gy1), fill=v)
    base.paste(clean, (0, 0), gmask)
    base.paste(clean.crop(KEEP_BAR), KEEP_BAR[:2])
    # alfa: cabeçalho opaco, janela transparente, rampa suave, painel opaco
    alpha = Image.new("L", (W, H), 255)
    ad = ImageDraw.Draw(alpha)
    ad.rectangle((0, HEADER_LINE_END, W, RAMP_TOP - 1), fill=0)
    for y in range(RAMP_TOP, RAMP_BOTTOM):
        t = (y - RAMP_TOP) / (RAMP_BOTTOM - RAMP_TOP)
        ad.line((0, y, W, y), fill=round(255 * t * t * (3 - 2 * t)))
    # chip da categoria por cima da foto (texto já removido), com borda suave
    x0, y0, x1, y1 = CHIP_BOX
    r, _, b = clean.crop(CHIP_BOX).split()
    chip_a = ImageChops.subtract(b, r).point(lambda v: max(0, min(255, round((v - 70) * 255 / 60))))
    chip_full = Image.new("L", (W, H), 0)
    chip_full.paste(chip_a, (x0, y0))
    rgb = Image.composite(clean, base, chip_full)
    alpha = ImageChops.lighter(alpha, chip_full)
    rgba = rgb.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba


def size_for_width(path, text, target):
    lo, hi = 6.0, 400.0
    for _ in range(28):
        mid = (lo + hi) / 2
        b = ImageFont.truetype(path, mid).getbbox(text, anchor="ls")
        lo, hi = (mid, hi) if (b[2] - b[0]) < target else (lo, mid)
    return (lo + hi) / 2


def calibrate(group, font_path):
    sizes = [size_for_width(os.path.join(ROOT, font_path), t, bb[2] - bb[0]) for t, bb in MEASURED[group]]
    return sum(sizes) / len(sizes)


def top_offset(font_path, size, text):
    return -ImageFont.truetype(os.path.join(ROOT, font_path), size).getbbox(text, anchor="ls")[1]


def build_spec(master_sha):
    with open(os.path.join(ROOT, REF), "rb") as f:
        ref_sha = hashlib.sha256(f.read()).hexdigest()
    s_title, s_date, s_cat, s_chip = (calibrate(g, BOLD) for g in ("title", "date", "category", "category_chip"))
    s_sum, s_cred = calibrate("summary", REGULAR), calibrate("credit", REGULAR)
    sum_tops = [bb[1] for _, bb in MEASURED["summary"]]
    cred_text, cred_bb = MEASURED["credit"][0]

    def text(font, size, color, **kw):
        return {"font": font, "size": round(size), "min_size": round(size * 0.82), "color": color, **kw}

    clear = {"mode": "none"}
    return {
        "schema_version": "1.0", "kind": "feed", "status": "APPROVED",
        "approval": {
            "scope": "V1 operacional do feed (1080x1080)",
            "state": "aprovada por Filipe em 2026-09-27 para uso operacional; revisão do ChatGPT pendente antes do merge em main",
            "v1_1_pending": [
                "título: ajuste fino de quebra de linha e posição",
                "transição foto→painel (borda suave entre a foto e o painel de texto)",
                "forma/posição do chip de categoria sobre a foto",
                "posicionamento geral fino (globe, barra de destaque)",
                "fonte definitiva da arte aprovada (hoje: Work Sans, provisória — ver assets/fonts/README.md)",
                "PNG original íntegro no lugar da referência JPEG preliminar (assets/templates/reference/referencia-preliminar-1536.jpg)",
            ],
        },
        "note": "V1 do feed 1:1 (saída 1080x1080). Master RGBA gerado por scripts/make_master_feed_1x1.py a partir da referência preliminar JPEG 1536x1536. Zonas e separação template/conteúdo variável não devem mudar em V1.1; V1.1 ajusta apenas posição/medidas dentro dessa mesma arquitetura e, quando chegar, o PNG original.",
        "reference": {"file": REF, "sha256": ref_sha, "width": W, "height": H},
        "master": {"source": "file", "file": MASTER_OUT, "sha256": master_sha},
        "output": {"width": 1080, "height": 1080, "jpeg_quality": 95, "max_bytes": 8388608, "text_supersample": 2},
        "fonts": {"bold": [BOLD], "regular": [REGULAR],
                  "credits": "Work Sans (Wei Huang), SIL OFL 1.1, via npm @expo-google-fonts/work-sans 0.4.2; escolhida por sobreposição de tinta com a referência"},
        "zones": {
            "photo": {"rect": [0, 245, 1536, 640], "window": [0, 255, 1536, 570], "fit": "cover", "focus_y": 0.4, "radius": 0, "clear": clear},
            "date": {"rect": [1174, 56, 300, 52], "clear": clear,
                     "text": text("bold", s_date, [8, 22, 53], align="center", case="upper", max_lines=1, baseline_first=94)},
            "category": {"rect": [1137, 143, 341, 56], "clear": clear,
                         "text": text("bold", s_cat, [243, 248, 251], align="center", case="upper", max_lines=1, baseline_first=185)},
            "category_chip": {"rect": [80, 834, 281, 44], "clear": clear,
                              "text": text("bold", s_chip, [240, 250, 254], align="center", case="upper", max_lines=1, baseline_first=867)},
            "title": {"rect": [85, 905, 1216, 250], "clear": clear,
                      "text": text("bold", s_title, [249, 250, 251], case="upper", max_lines=3, baseline_first=979, line_pitch=77,
                                   accent_color=[5, 233, 250], accent_last_words=2)},
            "summary": {"rect": [128, 1160, 1000, 120], "clear": clear, "required": False,
                        "text": text("regular", s_sum, [234, 241, 251], max_lines=3, ellipsis=True, line_pitch=38.5,
                                     baseline_first=round(sum_tops[0] + top_offset(REGULAR, s_sum, MEASURED["summary"][0][0]), 1))},
            "credit": {"rect": [89, 1302, 610, 30], "clear": clear, "required": False,
                       "text": text("regular", s_cred, [173, 182, 203], max_lines=1, prefix="Foto: ",
                                    baseline_first=round(cred_bb[1] + top_offset(REGULAR, s_cred, cred_text), 1))},
        },
        "fixed_zones": {
            "header_left": [0, 0, 880, 245], "logo": [74, 21, 694, 214], "footer": [0, 1353, 1536, 183],
            "globe": [1235, 1146, 301, 207], "bar": [91, 1160, 11, 113],
        },
        "master_clean_regions": [[0, 896, 80, 436], [112, 896, 1123, 436]],
        "validation": {"mode": "reference"},
    }


def main():
    img = Image.open(os.path.join(ROOT, REF)).convert("RGB")
    assert img.size == (W, H), img.size
    rgba = build_master(img)
    master_path = os.path.join(ROOT, MASTER_OUT)
    rgba.save(master_path, optimize=True)
    spec = build_spec(imgutil.sha256_file(master_path))
    spec_path = os.path.join(ROOT, SPEC_OUT)
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({"master": MASTER_OUT, "spec": SPEC_OUT,
                      "sizes": {k: v["text"]["size"] for k, v in spec["zones"].items() if "text" in v}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
