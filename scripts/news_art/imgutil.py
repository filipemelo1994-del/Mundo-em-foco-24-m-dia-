import hashlib

from PIL import Image, ImageChops, ImageStat


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def mean_abs_diff(a, b):
    """Erro médio absoluto por pixel e canal (0-255)."""
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    return sum(ImageStat.Stat(diff).mean) / 3.0


def diff_ratio(a, b, threshold=40):
    """Fração de pixels cuja diferença de luminância passa de `threshold`."""
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB")).convert("L")
    hist = diff.histogram()
    return sum(hist[threshold + 1:]) / float(a.width * a.height)


def gray_std(img):
    return ImageStat.Stat(img.convert("L")).stddev[0]


def mean_color(img):
    return tuple(ImageStat.Stat(img.convert("RGB")).mean)


def _pixels(img):
    # getdata() está obsoleto no Pillow 14; get_flattened_data() é o substituto
    return list(getattr(img, "get_flattened_data", img.getdata)())


def dhash(img, size=8):
    """Hash perceptual de diferença (64 bits para size=8)."""
    g = img.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    px = _pixels(g)
    bits = 0
    for r in range(size):
        for c in range(size):
            bits = (bits << 1) | (1 if px[r * (size + 1) + c] > px[r * (size + 1) + c + 1] else 0)
    return bits


def hamming(a, b):
    return bin(a ^ b).count("1")


def correlation(a, b, size=48):
    """Correlação normalizada (Pearson) entre duas imagens em cinza reduzidas."""
    ga = _pixels(a.convert("L").resize((size, size), Image.Resampling.BILINEAR))
    gb = _pixels(b.convert("L").resize((size, size), Image.Resampling.BILINEAR))
    n = len(ga)
    ma, mb = sum(ga) / n, sum(gb) / n
    va = sum((x - ma) ** 2 for x in ga)
    vb = sum((x - mb) ** 2 for x in gb)
    if va == 0 or vb == 0:
        return 0.0
    cov = sum((x - ma) * (y - mb) for x, y in zip(ga, gb))
    return cov / (va ** 0.5 * vb ** 0.5)
