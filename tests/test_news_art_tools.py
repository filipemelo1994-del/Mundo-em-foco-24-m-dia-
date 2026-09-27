"""Medição automática, mestre com janela transparente e CLIs do gerador v2 (referência SINTÉTICA)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import test_news_art as T  # noqa: E402
from news_art import master as M, measure, render as R, spec as S, validate as V  # noqa: E402


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def banded_reference():
    """Referência sintética com bordas retas de largura total (como a arte real), para a medição automática."""
    ref = T.make_reference(1)
    d = ImageDraw.Draw(ref)
    d.rectangle((0, 168, 1080, 171), fill=(38, 181, 241))
    d.rectangle((0, 1240, 1080, 1243), fill=(38, 181, 241))
    return ref


@unittest.skipIf(T.FONT is None, "sem fonte TrueType no sistema")
class MeasureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "ref.png")
        banded_reference().save(self.path)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def near(self, a, b, tol=8):
        self.assertTrue(all(abs(x - y) <= tol for x, y in zip(a, b)), f"{a} != {b} (±{tol})")

    def test_bands_photo_panel_and_text_blocks(self):
        rep = measure.measure_reference(self.path, os.path.join(self.tmp, "out"))
        self.assertEqual((rep["image"]["width"], rep["image"]["height"], rep["image"]["aspect"]), (1080, 1350, 0.8))
        self.near(rep["fixed_zones"]["header"], [0, 0, 1080, 172], 4)
        self.near(rep["fixed_zones"]["footer"], [0, 1240, 1080, 110], 4)
        self.near(rep["photo"], [0, 172, 1080, 698], 24)
        roles = {b["suggested_role"]: b for b in rep["text_blocks"]}
        self.near(roles["título"]["ink_bbox"][:2], [50, 908], 10)
        self.near(roles["resumo"]["ink_bbox"][:2], [52, 1145], 10)
        for name in ("report.json", "overlay.png", "layout-spec.proposed.json"):
            self.assertTrue(os.path.isfile(os.path.join(self.tmp, "out", name)))

    def test_proposal_is_never_approved_and_carries_the_reference_hash(self):
        rep = measure.measure_reference(self.path)
        proposal = measure.propose_spec(rep)
        self.assertEqual((proposal["status"], proposal["proposal"]), ("PENDING_REFERENCE", True))
        self.assertEqual(proposal["reference"]["sha256"], rep["image"]["sha256"])
        with self.assertRaises(S.SpecError):
            S.require_approved(proposal)

    def test_cli_info_and_auto(self):
        out = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "measure_reference.py"), "auto", self.path, "--out-dir", os.path.join(self.tmp, "o")],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("Painel de texto", out.stdout)
        info = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "measure_reference.py"), "info", self.path], capture_output=True, text=True)
        self.assertEqual(json.loads(info.stdout)["width"], 1080)


@unittest.skipIf(T.FONT is None, "sem fonte TrueType no sistema")
class LinePositionTests(unittest.TestCase):
    def test_accented_capitals_are_pushed_down_instead_of_hitting_the_line_above(self):
        from PIL import ImageFont
        big = ImageFont.truetype(T.FONT, 120)
        plain, _ = R.line_positions(big, ["TESTE DE LAYOUT", "CASA MESA"], 2, 100, 30)      # passo curto de propósito
        accent, _ = R.line_positions(big, ["TESTE DE LAYOUT", "TRÊS LINHAS"], 2, 100, 30)
        self.assertGreater(accent[1], accent[0] + 30)                                        # empurrada pelo circunflexo
        self.assertGreaterEqual(plain[1], plain[0] + 30)
        roomy, _ = R.line_positions(big, ["TESTE", "TRÊS"], 2, 100, 400)                      # com folga, mantém o passo nominal
        self.assertEqual(roomy, [100, 500])


@unittest.skipIf(T.FONT is None, "sem fonte TrueType no sistema")
class OverlayMasterTests(unittest.TestCase):
    """Mestre RGBA: janela da foto transparente; chip e bordas suaves ficam POR CIMA da foto."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        ref = T.make_reference(1)
        ref.save(os.path.join(self.tmp, "reference.png"))
        spec = T.make_spec(1)
        clean, _ = M.load_master(spec, self.tmp)
        rgba = clean.convert("RGBA")
        x0, y0, x1, y1 = S.to_box(spec["zones"]["photo"]["rect"])
        ImageDraw.Draw(rgba).rectangle((x0, y0, x1 - 1, y1 - 1), fill=(0, 0, 0, 0))            # janela transparente
        ImageDraw.Draw(rgba).polygon([(40, 780), (330, 780), (300, 869), (40, 869)], fill=(0, 100, 220, 255))  # chip sobre a foto
        rgba.save(os.path.join(self.tmp, "master.png"))
        spec["master"] = {"source": "file", "file": "master.png"}
        self.spec = spec

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_photo_goes_under_the_master_and_the_chip_stays_on_top(self):
        master, info = M.load_master(self.spec, self.tmp)
        self.assertEqual(master.mode, "RGBA")
        img, fit = R.render_feed(self.spec, master, T.photo_image(), T.FIELDS, self.tmp)
        self.assertEqual(img.getpixel((100, 820)), (0, 100, 220))      # chip por cima da foto
        self.assertNotEqual(img.getpixel((600, 400)), (0, 0, 0))       # foto visível na janela
        path = os.path.join(self.tmp, "art.jpg")
        R.save_jpeg(img, path, self.spec)
        rep = V.validate_feed(path, self.spec, master, reference=info["reference"], fit_report=fit, source_photo=T.photo_image())
        self.assertTrue(rep["passed"], rep["checks"])

    def test_flattened_master_with_content_in_the_photo_window_is_rejected(self):
        opaque = Image.open(os.path.join(self.tmp, "master.png")).convert("RGB")     # sem alpha: o chip vira "conteúdo de exemplo"
        opaque.save(os.path.join(self.tmp, "master_opaque.png"))
        spec = json.loads(json.dumps(self.spec))
        spec["master"]["file"] = "master_opaque.png"
        with self.assertRaises(S.SpecError) as ctx:
            M.load_master(spec, self.tmp)
        self.assertIn("photo", str(ctx.exception))


@unittest.skipIf(T.FONT is None, "sem fonte TrueType no sistema")
class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        T.make_reference(1).save(os.path.join(self.tmp, "reference.png"))
        self.spec_path = os.path.join(self.tmp, "spec.json")
        with open(self.spec_path, "w", encoding="utf-8") as f:
            json.dump(T.make_spec(1), f)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, script, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", script), *args], capture_output=True, text=True)

    def test_pending_spec_refuses_both_clis(self):
        pending = os.path.join(ROOT, "assets", "templates", "layout-spec.json")
        r = self.run_cli("build_news_art_v2.py", "--spec", pending, "--sample", os.path.join(self.tmp, "x.jpg"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("PENDING_REFERENCE", r.stderr)
        r = self.run_cli("validate_news_art.py", "--spec", pending, "--art", os.path.join(self.tmp, "x.jpg"))
        self.assertEqual(r.returncode, 2)

    def test_emit_master_sample_request_and_validate(self):
        out = os.path.join(self.tmp, "master")
        r = self.run_cli("build_news_art_v2.py", "--spec", self.spec_path, "--root", self.tmp, "--emit-master", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        meta = load(os.path.join(out, "master-feed.meta.json"))
        self.assertEqual(len(meta["sha256_png"]), 64)
        sample = os.path.join(self.tmp, "amostra.jpg")
        r = self.run_cli("build_news_art_v2.py", "--spec", self.spec_path, "--root", self.tmp, "--sample", sample)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        photo = os.path.join(self.tmp, "foto.png")
        T.photo_image().save(photo)
        req = os.path.join(self.tmp, "req.json")
        with open(req, "w", encoding="utf-8") as f:
            json.dump({"id": "noticia-teste-26-09-2026", **T.FIELDS}, f)
        res = os.path.join(self.tmp, "res.json")
        r = self.run_cli("build_news_art_v2.py", "--spec", self.spec_path, "--root", self.tmp, "--request-json", req, "--photo-file", photo,
                         "--out-dir", os.path.join(self.tmp, "saida"), "--output-json", res)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        result = load(res)
        self.assertEqual((result["status"], result["validation"]["passed"]), ("ok", True))
        art = result["path"]
        r = self.run_cli("validate_news_art.py", "--spec", self.spec_path, "--root", self.tmp, "--art", art, "--source-photo", photo, "--fit-report", res)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("APROVADA", r.stdout)

    def test_template_copy_is_rejected_by_validator_cli(self):
        out = os.path.join(self.tmp, "m")
        self.run_cli("build_news_art_v2.py", "--spec", self.spec_path, "--root", self.tmp, "--emit-master", out)
        bad = os.path.join(self.tmp, "publicar.jpg")
        Image.open(os.path.join(out, "master-feed.png")).convert("RGB").resize((1080, 1350)).save(bad, "JPEG", quality=93)
        r = self.run_cli("validate_news_art.py", "--spec", self.spec_path, "--root", self.tmp, "--art", bad)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("REPROVADA", r.stdout)
        self.assertIn("not_equal_to_master", r.stdout)


if __name__ == "__main__":
    unittest.main()
