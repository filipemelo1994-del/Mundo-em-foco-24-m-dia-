#!/usr/bin/env python3
"""Gerador v2 do feed (fase 2). NÃO é chamado pelos workflows atuais.

Identidade = pixels da referência aprovada; variáveis = foto, categoria, data, título, resumo e
crédito. Por padrão usa a spec V1 (assets/templates/layout-spec.v1.json), aprovada para uso
operacional a partir da referência JPEG preliminar; refinamentos de posição, fonte definitiva e o
PNG original entram como V1.1 sem mudar essa arquitetura de zonas. A spec oficial definitiva
(assets/templates/layout-spec.json, medida a partir do PNG original íntegro) continua
PENDING_REFERENCE e pode ser usada com --spec; enquanto estiver PENDING_REFERENCE o gerador recusa
rodar com ela.

  --emit-master DIR        grava o template mestre (referência sem a matéria de exemplo) e seus hashes
  --sample ARQUIVO.jpg     arte de teste com foto placeholder, para comparação visual
  --request-json R.json    gera a arte de uma pauta (id, title, summary, category, date, credit, imageCandidates)

Códigos de saída: 0 ok e validada | 2 spec pendente/inválida | 3 erro de renderização ou mídia |
                  4 arte gerada, mas REPROVADA pelo validador (não publicar)
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from news_art import imgutil, master as M, render as R, spec as S, validate as V  # noqa: E402

SAMPLE_FIELDS = {
    "category": "Tecnologia", "date": "26 SET 2026",
    "title": "Teste de layout: título em três linhas com destaque em ciano no final",
    "summary": "Resumo sintético de teste com até três linhas para verificar quebra, espaçamento e alinhamento do texto dentro da zona reservada ao resumo.",
    "credit": "Crédito de teste",
}


def placeholder_photo(w=1600, h=1000):
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        d.line((0, y, w, y), fill=(40 + y * 90 // h, 90 + y * 60 // h, 140 + y * 80 // h))
    for x in range(-h, w, 120):
        d.line((x, h, x + h, 0), fill=(255, 255, 255), width=3)
    d.rectangle((w // 2 - 330, h // 2 - 80, w // 2 + 330, h // 2 + 80), fill=(0, 0, 0))
    try:
        f = ImageFont.load_default(72)
    except TypeError:
        f = ImageFont.load_default()
    d.text((w // 2, h // 2), "FOTO DE TESTE", font=f, fill=(255, 255, 255), anchor="mm")
    return img


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spec", default="assets/templates/layout-spec.v1.json",
                    help="padrão: spec V1 aprovada (assets/templates/layout-spec.v1.json). Use "
                         "assets/templates/layout-spec.json para a spec oficial definitiva "
                         "(ainda PENDING_REFERENCE, aguardando o PNG original).")
    p.add_argument("--root", default=".")
    p.add_argument("--emit-master")
    p.add_argument("--sample")
    p.add_argument("--request-json")
    p.add_argument("--photo-file")
    p.add_argument("--image", action="append", default=[], help="URL(s) da foto (usa o download do gerador atual)")
    p.add_argument("--out-dir", default="public/news-art")
    p.add_argument("--output-json")
    p.add_argument("--no-validate", action="store_true")
    a = p.parse_args(argv)

    try:
        spec = S.load_spec(os.path.join(a.root, a.spec) if not os.path.isabs(a.spec) and not os.path.exists(a.spec) else a.spec)
        S.require_approved(spec)
        master, info = M.load_master(spec, a.root)
    except (S.SpecError, OSError) as e:
        print(f"ERRO de spec/mestre: {e}", file=sys.stderr)
        return 2

    out = spec["output"]
    if a.emit_master:
        os.makedirs(a.emit_master, exist_ok=True)
        master.save(os.path.join(a.emit_master, "master-feed.png"))
        master.resize((out["width"], out["height"]), Image.Resampling.LANCZOS).convert("RGB").save(os.path.join(a.emit_master, "master-feed-preview.jpg"), "JPEG", quality=92)
        meta = M.master_meta(master, (out["width"], out["height"]))
        with open(os.path.join(a.emit_master, "master-feed.meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(json.dumps(meta, ensure_ascii=False))
        return 0

    request = {}
    if a.sample:
        fields, photo, nid = SAMPLE_FIELDS, placeholder_photo(), "amostra"
        dest = a.sample
        source_used = "placeholder"
    else:
        if not a.request_json:
            print("ERRO: informe --emit-master, --sample ou --request-json", file=sys.stderr)
            return 2
        with open(a.request_json, encoding="utf-8") as f:
            request = json.load(f)
        fields = {k: request.get(k, "") for k in ("category", "date", "title", "summary", "credit")}
        nid = request.get("id")
        if a.photo_file:
            photo, source_used = Image.open(a.photo_file), a.photo_file
        else:
            import build_news_art as v1
            urls = a.image or request.get("imageCandidates") or [request.get("sourceImage") or request.get("image")]
            try:
                photo, source_used = v1.download([u for u in urls if u])
            except RuntimeError as e:
                result = {"id": nid, "status": "media_error", "error": str(e)}
                print("RESULT_JSON: " + json.dumps(result, ensure_ascii=False))
                return 3
        import re
        dest = os.path.join(a.out_dir, re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9_-]", "-", str(nid))).strip("-") + ".jpg")

    try:
        img, fit = R.render_feed(spec, master, photo, fields, a.root)
    except R.RenderError as e:
        print(f"ERRO de renderização: {e}", file=sys.stderr)
        return 3
    quality = R.save_jpeg(img, dest, spec)
    result = {"id": nid, "status": "ok", "path": dest, "sourceImage": source_used, "width": out["width"], "height": out["height"],
              "bytes": os.path.getsize(dest), "jpegQuality": quality, "sha256": imgutil.sha256_file(dest), "fit": fit}
    code = 0
    if not a.no_validate:
        photo_src = photo if not a.sample else None
        report = V.validate_feed(dest, spec, master, reference=info["reference"], fit_report=fit, source_photo=photo_src,
                                 templates_dir=os.path.join(a.root, "assets", "templates"))
        result["validation"] = report
        if not report["passed"]:
            result["status"] = "validation_failed"
            code = 4
    if a.output_json:
        with open(a.output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    print("RESULT_JSON: " + json.dumps({k: v for k, v in result.items() if k not in ("fit", "validation")}, ensure_ascii=False))
    if code:
        failed = [c["id"] for c in result["validation"]["checks"] if c["result"] == "fail"]
        print("REPROVADA pelo validador: " + ", ".join(failed), file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
