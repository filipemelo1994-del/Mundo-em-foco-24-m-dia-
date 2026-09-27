#!/usr/bin/env python3
"""Mede o PNG de referência aprovado (não desenha nada).

  measure_reference.py info   REF.png
  measure_reference.py auto   REF.png --out-dir DIR     # report.json, overlay.png, layout-spec.proposed.json
  measure_reference.py crop   REF.png --rect x,y,w,h --out recorte.png
  measure_reference.py sample REF.png --at x,y [--radius 3]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageStat  # noqa: E402

from news_art import measure  # noqa: E402


def ints(text):
    return [int(v) for v in text.split(",")]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("info", "auto", "crop", "sample"):
        s = sub.add_parser(name)
        s.add_argument("ref")
        if name == "auto":
            s.add_argument("--out-dir", required=True)
        if name == "crop":
            s.add_argument("--rect", required=True)
            s.add_argument("--out", required=True)
        if name == "sample":
            s.add_argument("--at", required=True)
            s.add_argument("--radius", type=int, default=3)
    a = p.parse_args(argv)

    if a.cmd == "info":
        im = Image.open(a.ref)
        print(json.dumps({"width": im.width, "height": im.height, "mode": im.mode, "format": im.format, "aspect": round(im.width / im.height, 4)}, ensure_ascii=False))
        return 0
    if a.cmd == "crop":
        x, y, w, h = ints(a.rect)
        Image.open(a.ref).crop((x, y, x + w, y + h)).save(a.out)
        print(a.out)
        return 0
    if a.cmd == "sample":
        x, y = ints(a.at)
        r = a.radius
        im = Image.open(a.ref).convert("RGB")
        print(json.dumps({"at": [x, y], "mean_rgb": [round(v) for v in ImageStat.Stat(im.crop((x - r, y - r, x + r + 1, y + r + 1))).mean]}))
        return 0

    rep = measure.measure_reference(a.ref, a.out_dir)
    print(f"Imagem: {rep['image']['width']}x{rep['image']['height']} (proporção {rep['image']['aspect']})")
    print(f"Foto: {rep['photo']}")
    if rep.get("panel"):
        print(f"Painel de texto: {rep['panel']['rect']} cor {rep['panel']['color']}")
    for name, rect in rep["fixed_zones"].items():
        print(f"Fixa {name}: {rect}")
    for b in rep["text_blocks"]:
        acc = f", destaque {b['accent_color']}" if b.get("accent_color") else ""
        print(f"Bloco {b['id']} [{b['suggested_role']}, confiança {b['confidence']}]: tinta {b['ink_bbox']}, {b['lines']} linha(s), altura {b['line_height_px']}px, passo {b['line_pitch_px']}px, alinhamento {b['align']}, cor {b['ink_color']}{acc} sobre {b['bg_color']}")
    for r in rep.get("accent_bars", []):
        print(f"Barra de destaque: {r}")
    for k, r in rep.get("shapes", {}).items():
        print(f"Forma {k}: {r}")
    for n in rep["notes"]:
        print("Nota:", n)
    print(f"Arquivos em {a.out_dir}: report.json, overlay.png, layout-spec.proposed.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
