#!/usr/bin/env python3
"""Valida uma arte contra a spec (fase 2). Não publica nem altera nada.

Por padrão valida contra a spec V1 (assets/templates/layout-spec.v1.json), aprovada para uso
operacional. Use --spec assets/templates/layout-spec.json para a spec oficial definitiva (ainda
PENDING_REFERENCE, aguardando o PNG original).

Códigos de saída: 0 aprovada | 1 reprovada | 2 spec pendente/inválida ou arquivos ausentes
O relatório JSON tem o mesmo formato de context.validator_report do pedido de revisão.
"""
import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image  # noqa: E402

from news_art import master as M, spec as S, validate as V  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spec", default="assets/templates/layout-spec.v1.json")
    p.add_argument("--root", default=".")
    p.add_argument("--art", required=True)
    p.add_argument("--source-photo")
    p.add_argument("--fit-report", help="JSON com a lista de encaixe (campo 'fit' do resultado do gerador)")
    p.add_argument("--public-url", help="URL pública do arquivo; confere se o sha256 é o do arquivo validado")
    p.add_argument("--output-json")
    a = p.parse_args(argv)

    try:
        spec = S.load_spec(a.spec)
        S.require_approved(spec)
        mode = S.thresholds(spec)["mode"]
        master = reference = None
        if mode == "reference":
            master, info = M.load_master(spec, a.root)
            reference = info["reference"]
        public = None
        if a.public_url:
            with urllib.request.urlopen(a.public_url, timeout=30) as resp:
                public = resp.read()
        fit = None
        if a.fit_report:
            with open(a.fit_report, encoding="utf-8") as f:
                data = json.load(f)
            fit = data.get("fit", data) if isinstance(data, dict) else data
        photo = Image.open(a.source_photo) if a.source_photo else None
        kw = {"public_bytes": public}
        if mode == "reference":
            kw.update(reference=reference, fit_report=fit, source_photo=photo, templates_dir=os.path.join(a.root, "assets", "templates"))
        report = V.validate(a.art, spec, master, **kw)
    except (S.SpecError, OSError) as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 2
    if a.output_json:
        with open(a.output_json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    for c in report["checks"]:
        print(f"[{c['result'].upper():4}] {c['id']}: {c['detail']}")
    print("APROVADA" if report["passed"] else "REPROVADA")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
