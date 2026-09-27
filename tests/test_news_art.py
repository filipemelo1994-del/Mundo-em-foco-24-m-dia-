"""Testes do gerador v2 e do validador, com uma referência SINTÉTICA (não é a arte oficial)."""
import copy
import os
import shutil
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from news_art import imgutil, master as M, render as R, spec as S, validate as V  # noqa: E402

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
FONT = next((p for p in FONT_CANDIDATES if os.path.isfile(p)), None)


def gradient_bg(w, h):
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line((0, y, w, y), fill=(int(5 + 5 * t), int(31 + 40 * t), int(63 + 77 * t)))
    return img


def make_reference(scale=1):
    """1080x1350 sintético: cabeçalho com 'logo', foto de exemplo, textos de exemplo e rodapé."""
    W, H = 1080, 1350
    ref = gradient_bg(W, H)
    d = ImageDraw.Draw(ref)
    d.rectangle((0, 0, W, 169), fill=(4, 31, 66))                       # cabeçalho
    d.ellipse((40, 20, 140, 120), fill=(255, 255, 255))                 # "logo"
    d.rectangle((150, 40, 600, 100), fill=(38, 181, 241))               # "nome" fixo
    d.rectangle((0, 1240, W, H), fill=(3, 43, 91))                      # rodapé fixo
    d.rectangle((0, 170, W, 869), fill=(120, 110, 90))                  # foto de exemplo (a matéria "Alibaba")
    for i in range(0, 1080, 40):
        d.rectangle((i, 170, i + 20, 869), fill=(200 - i // 8, 90 + i // 12, 40 + i // 10))
    f_big, f_small = ImageFont.truetype(FONT, 44), ImageFont.truetype(FONT, 28)
    d.text((50, 900), "ALIBABA LANCA NOVO CHIP DE IA", font=f_big, fill=(255, 255, 255))
    d.text((50, 1140), "Resumo da materia de exemplo que nao pode ficar.", font=f_small, fill=(225, 237, 249))
    d.text((50, 1215), "Foto: Exemplo", font=f_small, fill=(220, 230, 240))
    d.text((770, 100), "TECNOLOGIA", font=f_small, fill=(255, 255, 255))
    d.text((770, 40), "17 SET 2026", font=f_small, fill=(255, 255, 255))
    if scale != 1:
        ref = ref.resize((W * scale, H * scale), Image.Resampling.LANCZOS)
    return ref


def make_spec(scale=1, ref_file="reference.png"):
    def r(x, y, w, h):
        return [x * scale, y * scale, w * scale, h * scale]

    def text(size, min_size, color, **kw):
        return {"font": "bold", "size": size * scale, "min_size": min_size * scale, "color": color, **kw}

    interp = {"mode": "interpolate_rows", "pad": 4}
    return {
        "schema_version": "1.0", "kind": "feed", "status": "APPROVED",
        "reference": {"file": ref_file, "sha256": "", "width": 1080 * scale, "height": 1350 * scale},
        "master": {"source": "generate"},
        "output": {"width": 1080, "height": 1350, "jpeg_quality": 93, "max_bytes": 8 * 1024 * 1024},
        "fonts": {"bold": [FONT]},
        "zones": {
            "photo": {"rect": r(0, 170, 1080, 700), "fit": "cover", "focus_y": 0.3, "clear": {"mode": "solid", "color": [20, 20, 20]}},
            "category": {"rect": r(760, 90, 300, 50), "text": text(28, 18, [255, 255, 255], align="center", valign="middle", case="upper", max_lines=1), "clear": interp},
            "date": {"rect": r(760, 30, 300, 50), "text": text(26, 16, [255, 255, 255], align="right", valign="middle", case="upper", max_lines=1), "clear": interp},
            "title": {"rect": r(50, 890, 980, 240), "text": text(60, 34, [255, 255, 255], case="upper", max_lines=3, line_spacing=1.1), "clear": interp},
            "summary": {"rect": r(50, 1135, 980, 70), "required": False, "text": text(28, 20, [225, 237, 249], max_lines=2, ellipsis=True, line_spacing=1.2), "clear": interp},
            "credit": {"rect": r(50, 1210, 980, 28), "required": False, "text": text(22, 16, [220, 230, 240], max_lines=1, prefix="Foto: "), "clear": interp},
        },
        "fixed_zones": {"header": r(0, 0, 750, 170), "logo": r(30, 10, 130, 130), "footer": r(0, 1240, 1080, 110)},
        "validation": {"mode": "reference"},
    }


def photo_image(seed=0):
    img = Image.new("RGB", (900, 600))
    d = ImageDraw.Draw(img)
    for x in range(0, 900, 30):
        d.rectangle((x, 0, x + 15, 600), fill=((x * 3 + seed * 70) % 255, (x * 5 + 40) % 255, (255 - x // 4 + seed * 30) % 255))
    d.ellipse((300 + seed * 40, 150, 600 + seed * 40, 450), fill=(240, 240, 60))
    return img


FIELDS = {"category": "Tecnologia", "date": "26 set 2026", "title": "Novo chip de IA muda o mercado de servidores",
          "summary": "Empresa apresenta processador voltado a modelos de linguagem.", "credit": "Divulgação"}


@unittest.skipIf(FONT is None, "sem fonte TrueType no sistema")
class FeedTests(unittest.TestCase):
    scale = 1

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ref = make_reference(self.scale)
        self.ref.save(os.path.join(self.tmp, "reference.png"))
        self.spec = make_spec(self.scale)
        self.master, info = M.load_master(self.spec, self.tmp)
        self.reference = info["reference"]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def art(self, name="art.jpg", fields=None, photo=None):
        img, report = R.render_feed(self.spec, self.master, photo or photo_image(), fields or FIELDS, self.tmp)
        path = os.path.join(self.tmp, name)
        R.save_jpeg(img, path, self.spec)
        return path, report

    def checks(self, report):
        return {c["id"]: c["result"] for c in report["checks"]}

    # ---- mestre ----
    def test_master_has_no_sample_content_and_keeps_identity(self):
        for name, cfg in self.spec["zones"].items():
            crop = self.master.crop(S.to_box(cfg["rect"]))
            self.assertLess(imgutil.gray_std(crop), 3.0, f"sobrou conteúdo em {name}")
        for name, rect in self.spec["fixed_zones"].items():
            box = S.to_box(rect)
            self.assertLess(imgutil.mean_abs_diff(self.master.crop(box), self.ref.crop(box)), 0.01, f"zona fixa {name} mudou")

    def test_master_with_leftover_sample_text_is_rejected(self):
        bad = copy.deepcopy(self.spec)
        bad["zones"]["title"]["rect"][2] = 500 * self.scale   # zona estreita demais: o "ALIBABA..." invade a faixa usada na interpolação
        with self.assertRaises(S.SpecError) as ctx:
            M.load_master(bad, self.tmp)
        self.assertIn("title", str(ctx.exception))

    def test_reference_sha_mismatch_is_rejected(self):
        bad = copy.deepcopy(self.spec)
        bad["reference"]["sha256"] = "0" * 64
        with self.assertRaises(S.SpecError):
            M.load_master(bad, self.tmp)

    def test_pending_spec_refuses(self):
        pending = S.load_spec(os.path.join(ROOT, "assets", "templates", "layout-spec.json"))
        with self.assertRaises(S.SpecError):
            S.require_approved(pending)

    def test_aspect_mismatch_is_reported(self):
        bad = copy.deepcopy(self.spec)
        bad["output"] = {"width": 1080, "height": 1080}
        with self.assertRaises(S.SpecError) as ctx:
            S.validate_spec(bad)
        self.assertIn("proporção", str(ctx.exception))

    # ---- arte correta ----
    def test_valid_art_passes_every_check(self):
        path, fit = self.art()
        with open(path, "rb") as f:
            published = f.read()
        rep = V.validate_feed(path, self.spec, self.master, reference=self.reference, fit_report=fit, source_photo=photo_image(),
                              public_bytes=published)
        self.assertTrue(rep["passed"], rep["checks"])
        self.assertEqual((rep["width"], rep["height"]), (1080, 1350))
        self.assertEqual(self.checks(rep)["photo_matches_source"], "pass")

    def test_long_summary_is_ellipsized_and_allowed_but_long_title_is_not(self):
        long_summary = dict(FIELDS, summary="palavra " * 80)
        path, fit = self.art("s.jpg", long_summary)
        summary = next(r for r in fit if r["zone"] == "summary")
        self.assertTrue(summary["ellipsized"])
        self.assertTrue(V.validate_feed(path, self.spec, self.master, fit_report=fit)["passed"])
        long_title = dict(FIELDS, title="manchete gigantesca " * 30)
        path, fit = self.art("t.jpg", long_title)
        rep = V.validate_feed(path, self.spec, self.master, fit_report=fit)
        self.assertEqual(self.checks(rep)["text_fit"], "fail")
        self.assertFalse(rep["passed"])

    def test_required_fields_and_photo_are_mandatory(self):
        for missing in ("title", "category", "date"):
            with self.assertRaises(R.RenderError):
                R.render_feed(self.spec, self.master, photo_image(), dict(FIELDS, **{missing: " "}), self.tmp)
        with self.assertRaises(R.RenderError):
            R.render_feed(self.spec, self.master, None, FIELDS, self.tmp)

    def test_credit_gets_prefix_once(self):
        _, fit = self.art()
        self.assertEqual(next(r for r in fit if r["zone"] == "credit")["lines"], 1)
        img, _ = R.render_feed(self.spec, self.master, photo_image(), dict(FIELDS, credit="Foto: Já tem prefixo"), self.tmp)
        self.assertEqual(img.size, (1080, 1350))

    # ---- bloqueios ----
    def test_master_published_as_is_is_blocked(self):
        path = os.path.join(self.tmp, "master.jpg")
        self.master.resize((1080, 1350), Image.Resampling.LANCZOS).save(path, "JPEG", quality=93)
        rep = V.validate_feed(path, self.spec, self.master)
        c = self.checks(rep)
        self.assertFalse(rep["passed"])
        self.assertEqual((c["not_equal_to_master"], c["not_near_master"], c["photo_zone_changed"]), ("fail", "fail", "fail"))

    def test_byte_identical_copy_of_a_template_file_is_blocked(self):
        templates = os.path.join(self.tmp, "templates")
        os.makedirs(templates)
        self.master.save(os.path.join(templates, "master.png"))
        shutil.copy(os.path.join(templates, "master.png"), os.path.join(self.tmp, "publicar.png"))
        rep = V.validate_feed(os.path.join(self.tmp, "publicar.png"), self.spec, self.master, templates_dir=templates)
        bad = next(c for c in rep["checks"] if c["id"] == "not_equal_to_master")
        self.assertEqual(bad["result"], "fail")
        self.assertIn("master.png", bad["detail"])

    def test_the_original_reference_with_sample_story_is_blocked(self):
        path = os.path.join(self.tmp, "ref.jpg")
        self.ref.resize((1080, 1350), Image.Resampling.LANCZOS).save(path, "JPEG", quality=93)
        rep = V.validate_feed(path, self.spec, self.master, reference=self.reference)
        self.assertFalse(rep["passed"])  # a matéria de exemplo não pode ser publicada como se fosse a notícia
        self.assertEqual(self.checks(rep)["no_sample_content"], "fail")

    def test_sample_title_left_over_in_a_new_art_is_blocked(self):
        path, fit = self.art()
        img = Image.open(path).convert("RGB")
        box = S.to_box(self.spec["zones"]["title"]["rect"], 1080 / self.spec["reference"]["width"], 1350 / self.spec["reference"]["height"])
        ref_out = self.reference.resize((1080, 1350), Image.Resampling.LANCZOS)
        img.paste(ref_out.crop(box), box[:2])      # o título "ALIBABA..." voltou
        img.save(path, "JPEG", quality=95)
        rep = V.validate_feed(path, self.spec, self.master, reference=self.reference, fit_report=fit)
        c = self.checks(rep)
        self.assertEqual(c["no_sample_content"], "fail")
        self.assertIn("title", next(x for x in rep["checks"] if x["id"] == "no_sample_content")["detail"])

    def test_flat_photo_is_blocked(self):
        path, fit = self.art("flat.jpg", photo=Image.new("RGB", (800, 600), (128, 128, 128)))
        rep = V.validate_feed(path, self.spec, self.master, fit_report=fit)
        self.assertEqual(self.checks(rep)["photo_zone_changed"], "fail")

    def test_deformed_logo_is_blocked(self):
        path, fit = self.art()
        img = Image.open(path).convert("RGB")
        ImageDraw.Draw(img).rectangle((30, 10, 160, 140), fill=(200, 0, 0))   # retângulo sobre o logo
        img.save(path, "JPEG", quality=95)
        rep = V.validate_feed(path, self.spec, self.master, fit_report=fit)
        self.assertEqual(self.checks(rep)["identity_preserved"], "fail")

    def test_text_spilling_outside_its_zone_is_blocked(self):
        path, fit = self.art()
        img = Image.open(path).convert("RGB")
        ImageDraw.Draw(img).text((40, 1290), "TEXTO VAZANDO PARA O RODAPE " * 3, font=ImageFont.truetype(FONT, 40), fill=(255, 255, 255))
        img.save(path, "JPEG", quality=95)
        rep = V.validate_feed(path, self.spec, self.master, fit_report=fit)
        c = self.checks(rep)
        self.assertEqual(c["identity_preserved"], "fail")
        self.assertEqual(c["outside_zones_intact"], "fail")

    def test_missing_title_pixels_is_blocked(self):
        path, fit = self.art()
        img = Image.open(path).convert("RGB")
        box = S.to_box(self.spec["zones"]["title"]["rect"], 1080 / self.spec["reference"]["width"], 1350 / self.spec["reference"]["height"])
        mres = self.master.resize((1080, 1350), Image.Resampling.LANCZOS)
        img.paste(mres.crop(box), box[:2])
        img.save(path, "JPEG", quality=95)
        rep = V.validate_feed(path, self.spec, self.master, fit_report=fit)
        self.assertEqual(self.checks(rep)["text_zones_changed"], "fail")

    def test_wrong_dimensions_are_blocked(self):
        path, _ = self.art()
        Image.open(path).resize((1000, 1250)).save(path, "JPEG", quality=93)
        rep = V.validate_feed(path, self.spec, self.master)
        self.assertEqual(self.checks(rep)["dimensions"], "fail")
        self.assertFalse(rep["passed"])

    def test_wrong_source_photo_is_blocked(self):
        path, fit = self.art(photo=photo_image(0))
        rep = V.validate_feed(path, self.spec, self.master, fit_report=fit, source_photo=photo_image(2))
        self.assertEqual(self.checks(rep)["photo_matches_source"], "fail")

    def test_public_file_must_match_validated_file(self):
        path, fit = self.art()
        rep = V.validate_feed(path, self.spec, self.master, fit_report=fit, public_bytes=b"outro arquivo")
        self.assertEqual(self.checks(rep)["published_equals_validated"], "fail")

    def test_not_an_image_is_reported_not_crashed(self):
        path = os.path.join(self.tmp, "quebrado.jpg")
        with open(path, "wb") as f:
            f.write(b"nao sou imagem" * 3000)
        rep = V.validate_feed(path, self.spec, self.master)
        self.assertFalse(rep["passed"])
        self.assertEqual(self.checks(rep)["dimensions"], "fail")


@unittest.skipIf(FONT is None, "sem fonte TrueType no sistema")
class FeedAtDoubleResolutionTests(FeedTests):
    """Referência 2160x2700 e saída 1080x1350: tudo deve continuar valendo."""
    scale = 2


class UtilTests(unittest.TestCase):
    def test_dhash_hamming_and_correlation(self):
        a, b = photo_image(0), photo_image(3)
        self.assertEqual(imgutil.hamming(imgutil.dhash(a), imgutil.dhash(a)), 0)
        self.assertGreater(imgutil.hamming(imgutil.dhash(a), imgutil.dhash(b)), 0)
        self.assertAlmostEqual(imgutil.correlation(a, a), 1.0, places=3)
        self.assertEqual(imgutil.correlation(Image.new("RGB", (10, 10), (5, 5, 5)), a), 0.0)


@unittest.skipIf(FONT is None, "sem fonte TrueType no sistema")
class StoryTests(unittest.TestCase):
    def setUp(self):
        import build_news_art as v1
        self.v1 = v1
        self.spec = S.load_spec(os.path.join(ROOT, "assets", "templates", "layout-spec-story.json"))
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def story(self, photo):
        img = self.v1.render_story(photo, "Novo chip de IA muda o mercado de servidores", "Tecnologia", "26 SET 2026", "Divulgação",
                                   "Empresa apresenta processador voltado a modelos de linguagem.")
        path = os.path.join(self.tmp, "story.jpg")
        img.save(path, "JPEG", quality=93)
        return path

    def test_real_story_render_passes(self):
        rep = V.validate(self.story(photo_image()), self.spec)
        self.assertTrue(rep["passed"], rep["checks"])
        self.assertEqual((rep["width"], rep["height"]), (1080, 1920))

    def test_flat_photo_and_wrong_size_are_blocked(self):
        rep = V.validate(self.story(Image.new("RGB", (900, 600), (100, 100, 100))), self.spec)
        self.assertEqual({c["id"]: c["result"] for c in rep["checks"]}["photo_zone_changed"], "fail")
        path = self.story(photo_image())
        Image.open(path).resize((1080, 1350)).save(path, "JPEG", quality=93)
        self.assertFalse(V.validate(path, self.spec)["passed"])


if __name__ == "__main__":
    unittest.main()
