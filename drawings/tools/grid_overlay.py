# Вырезает фрагмент изображения по окну в единицах чертежа и накладывает координатную сетку
# с подписями. По таким фрагментам (их смотрит модель с «зрением» или человек) снимаются
# координаты стен, дверей, лестниц: «стена идёт по x = 7,03…7,20 от y = 5,45 до 15,78».
#
#   python3 grid_overlay.py src.png crop.png X0 Y0 X1 Y1 --origin PX PY --ppu K [--zoom 2] [--step 0.1]
#
#   X0 Y0 X1 Y1  окно в единицах чертежа (метры или футы)
#   --zoom       увеличение фрагмента (nearest при zoom >= 2, чтобы не размывать)
#   --step       шаг мелкой сетки; целые единицы — красным, половины — синим
import argparse
import math

from PIL import Image, ImageDraw

from calib import Calib, add_args

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("window", nargs=4, type=float)
add_args(ap)
ap.add_argument("--zoom", type=float, default=2)
ap.add_argument("--step", type=float, default=0.1)
args = ap.parse_args()
C = Calib(args)
x0, y0, x1, y1 = args.window
Z, step = args.zoom, args.step

im = Image.open(args.src).convert("RGB")
box = (int(C.px(x0)), int(C.py(y1)), int(C.px(x1)), int(C.py(y0)))
c = im.crop(box)
c = c.resize((int(c.width * Z), int(c.height * Z)), Image.NEAREST if Z >= 2 else Image.LANCZOS)
d = ImageDraw.Draw(c, "RGBA")


def X(x):
    return (C.px(x) - box[0]) * Z


def Y(y):
    return (C.py(y) - box[1]) * Z


def lines(a, b, horiz):
    v = math.ceil(a / step) * step
    while v <= b + 1e-9:
        r = round(v, 3)
        whole = abs(r - round(r)) < 1e-6
        half = abs(r * 2 - round(r * 2)) < 1e-6
        col = (255, 0, 0, 170) if whole else ((0, 110, 255, 110) if half else (0, 170, 0, 55))
        lab = (255, 0, 0, 255) if whole else (0, 90, 220, 255)
        if horiz:
            d.line([(0, Y(r)), (c.size[0], Y(r))], fill=col, width=1)
            if whole or half:
                d.text((2, Y(r) + 1), f"{r:g}", fill=lab)
        else:
            d.line([(X(r), 0), (X(r), c.size[1])], fill=col, width=1)
            if whole or half:
                d.text((X(r) + 2, 2), f"{r:g}", fill=lab)
        v += step


lines(x0, x1, False)
lines(y0, y1, True)
c.save(args.dst)
print("saved", args.dst, c.size)
