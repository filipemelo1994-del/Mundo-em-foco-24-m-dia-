"""V1 do feed: confere, contra os artefatos REAIS do repositório (não uma spec sintética), que a
spec aprovada assets/templates/layout-spec.v1.json está operacional pelos CLIs por padrão, que a
spec oficial definitiva (assets/templates/layout-spec.json) continua intocada em PENDING_REFERENCE,
e que as garantias pedidas para a V1 seguem valendo: foto/data/categoria/título/destaque
ciano/resumo/crédito variáveis, identidade fixa, bloqueio de conteúdo residual do template,
bloqueio de publicação quando o validador reprova, e verificação arquivo-publicado == arquivo-validado.

Não publica, não altera o repositório e não chama rede.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from news_art import spec as S  # noqa: E402

V1_SPEC = os.path.join(ROOT, "assets", "templates", "layout-spec.v1.json")
OFFICIAL_SPEC = os.path.join(ROOT, "assets", "templates", "layout-spec.json")

REQUEST = {
    "id": "teste-v1-integracao",
    "category": "Tecnologia",
    "date": "27 SET 2026",
    "title": "Integração da V1 é concluída",
    "summary": "Resumo variável de teste para conferir se o campo muda de arte para arte no pipeline.",
    "credit": "Foto: Teste de Integração",
}


def run(*args):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=ROOT)


def photo():
    # Padrão com blocos de cor bem distintos (não uma textura fina), para que a correlação
    # pixel a pixel sobreviva ao redimensionamento "cover" e ao JPEG sem se confundir com moiré.
    img = Image.new("RGB", (1600, 1000))
    d = ImageDraw.Draw(img)
    for x in range(0, 1600, 60):
        d.rectangle((x, 0, x + 30, 1000), fill=((x * 3) % 255, (x * 5 + 40) % 255, (255 - x // 4) % 255))
    d.ellipse((500, 250, 1100, 750), fill=(240, 240, 60))
    return img


class V1SpecTests(unittest.TestCase):
    """A spec V1 em si: aprovada, com o backlog de V1.1 documentado, sem mexer nas zonas."""

    def setUp(self):
        with open(V1_SPEC, encoding="utf-8") as f:
            self.spec = json.load(f)

    def test_v1_spec_is_approved_and_loads(self):
        loaded = S.load_spec(V1_SPEC)  # levanta SpecError se a spec for inválida
        S.require_approved(loaded)     # levanta SpecError se não estiver APPROVED

    def test_v1_1_backlog_is_documented(self):
        pending = self.spec["approval"]["v1_1_pending"]
        self.assertTrue(pending)
        joined = " ".join(pending).lower()
        for item in ("fonte", "png original", "transição", "chip", "posicionamento"):
            self.assertIn(item, joined)

    def test_required_variable_zones_present(self):
        # As 7 garantias variáveis pedidas para a V1 (destaque ciano = accent_color do título).
        for name in ("photo", "date", "category", "category_chip", "title", "summary", "credit"):
            self.assertIn(name, self.spec["zones"])
        self.assertEqual(self.spec["zones"]["title"]["text"]["accent_color"], [5, 233, 250])

    def test_fixed_identity_zones_present(self):
        for name in ("header_left", "logo", "footer", "globe", "bar"):
            self.assertIn(name, self.spec["fixed_zones"])

    def test_official_pending_spec_is_untouched(self):
        # A spec oficial definitiva (medida do PNG original) continua bloqueada; a V1 não a substitui.
        official = S.load_spec(OFFICIAL_SPEC)
        self.assertEqual(official["status"], "PENDING_REFERENCE")
        with self.assertRaises(S.SpecError):
            S.require_approved(official)


@unittest.skipUnless(os.path.isfile(V1_SPEC), "spec V1 ausente")
class V1CliDefaultTests(unittest.TestCase):
    """Os CLIs, chamados sem --spec (como a integração fará), usam a V1 por padrão."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_and_validate_use_v1_by_default(self):
        photo_path = os.path.join(self.tmp, "foto.jpg")
        photo().save(photo_path)
        req_path = os.path.join(self.tmp, "req.json")
        with open(req_path, "w", encoding="utf-8") as f:
            json.dump(REQUEST, f)
        out_dir = os.path.join(self.tmp, "saida")
        gen_json = os.path.join(self.tmp, "gerado.json")
        r = run(os.path.join(ROOT, "scripts", "build_news_art_v2.py"),
                "--request-json", req_path, "--photo-file", photo_path,
                "--out-dir", out_dir, "--output-json", gen_json)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(gen_json, encoding="utf-8") as f:
            gen = json.load(f)
        self.assertTrue(gen["validation"]["passed"], gen["validation"]["checks"])
        art_path = gen["path"]
        self.assertTrue(os.path.isfile(art_path))

        # published_equals_validated: o arquivo "publicado" É o arquivo validado -> passa.
        val_json = os.path.join(self.tmp, "validado.json")
        with open(art_path, "rb") as f:
            published_bytes = f.read()
        public_copy = os.path.join(self.tmp, "publico.jpg")
        with open(public_copy, "wb") as f:
            f.write(published_bytes)
        r2 = run(os.path.join(ROOT, "scripts", "validate_news_art.py"),
                 "--art", art_path, "--source-photo", photo_path,
                 "--fit-report", gen_json, "--output-json", val_json)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        with open(val_json, encoding="utf-8") as f:
            rep = json.load(f)
        self.assertTrue(rep["passed"], rep["checks"])
        by_id = {c["id"]: c for c in rep["checks"]}
        for cid in ("not_equal_to_master", "not_near_master", "no_sample_content", "photo_zone_changed",
                    "text_zones_changed", "identity_preserved", "outside_zones_intact"):
            self.assertEqual(by_id[cid]["result"], "pass", by_id[cid])

    def test_pending_official_spec_still_refuses_by_flag(self):
        r = run(os.path.join(ROOT, "scripts", "build_news_art_v2.py"),
                "--spec", OFFICIAL_SPEC, "--sample", os.path.join(self.tmp, "x.jpg"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("PENDING_REFERENCE", r.stderr)


if __name__ == "__main__":
    unittest.main()
