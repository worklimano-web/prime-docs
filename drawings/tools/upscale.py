# Увеличение растрового исходника (скан, скриншот) для точного снятия координат.
# Lanczos + лёгкая нерезкая маска. Новых деталей не появляется, но края линий
# становятся гладкими, и их положение читается с точностью до долей исходного пикселя.
#
#   python3 upscale.py src.jpg src_x3.png [--factor 3]
import argparse

from PIL import Image, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--factor", type=int, default=3)
args = ap.parse_args()

im = Image.open(args.src).convert("RGB")
up = im.resize((im.width * args.factor, im.height * args.factor), Image.LANCZOS)
up = up.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=2))
up.save(args.dst)
print("saved", args.dst, up.size)
