# Контроль перерисовки: линии готового DXF (красным, двери — синим) поверх осветлённого исходника.
# Если красная линия идёт точно по грани стены оригинала — геометрия снята верно;
# сдвиг видно сразу. Делать после каждой правки координат, по зонам (ядро, низ, верх, фасады).
#
#   python3 overlay_check.py plan.dxf src_x3.png overlay.png --origin PX PY --ppu K [--units 1000]
#                            [--crop X0 Y0 X1 Y1 crop.png ...]
#
#   --units  мм модели на единицу калибровки (1000 — калибровка в метрах, 304.8 — в футах)
#   --layers какие слои рисовать (по умолчанию стены, колонны, витраж, двери, лестницы, лифты)
#   --crop   дополнительно сохранить фрагменты (окно в единицах калибровки + имя файла)
import argparse
import math

import ezdxf
from PIL import Image, ImageDraw

from calib import Calib, add_args

ap = argparse.ArgumentParser()
ap.add_argument("dxf")
ap.add_argument("src")
ap.add_argument("dst")
add_args(ap)
ap.add_argument("--units", type=float, default=1000.0)
ap.add_argument("--layers", default="A-COLS,A-WALL-CONC,A-WALL-PART,A-WALL-NEW,A-WALL-GLASS,A-GLAZ,A-DOOR,A-STAIR,A-LIFT")
ap.add_argument("--crop", nargs=5, action="append", default=[], metavar=("X0", "Y0", "X1", "Y1", "FILE"))
args = ap.parse_args()
C = Calib(args)
U = args.units
LAY = set(args.layers.split(","))

im = Image.open(args.src).convert("L").point(lambda v: 255 - (255 - v) * 0.5).convert("RGB")
d = ImageDraw.Draw(im)


def T(x, y):
    return (C.px(x / U), C.py(y / U))


for e in ezdxf.readfile(args.dxf).modelspace():
    if e.dxf.layer not in LAY:
        continue
    t = e.dxftype()
    col = (0, 120, 255) if e.dxf.layer == "A-DOOR" else (255, 0, 0)
    if t == "LWPOLYLINE":
        pts = [T(x, y) for x, y in e.get_points("xy")]
        if e.closed:
            pts.append(pts[0])
        d.line(pts, fill=col, width=1)
    elif t == "LINE":
        d.line([T(e.dxf.start.x, e.dxf.start.y), T(e.dxf.end.x, e.dxf.end.y)], fill=col, width=1)
    elif t == "ARC":
        c, r = e.dxf.center, e.dxf.radius
        a0, a1 = e.dxf.start_angle, e.dxf.end_angle
        if a1 < a0:
            a1 += 360
        steps = [a0 + (a1 - a0) * i / 30 for i in range(31)]
        d.line([T(c.x + r * math.cos(math.radians(a)), c.y + r * math.sin(math.radians(a))) for a in steps],
               fill=col, width=1)
im.save(args.dst)
print("saved", args.dst)
for x0, y0, x1, y1, name in args.crop:
    x0, y0, x1, y1 = map(float, (x0, y0, x1, y1))
    im.crop((int(C.px(x0)), int(C.py(y1)), int(C.px(x1)), int(C.py(y0)))).save(name)
    print("saved", name)
