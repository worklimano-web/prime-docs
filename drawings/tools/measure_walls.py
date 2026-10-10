# Точное снятие положения стен с (увеличенного) изображения: поперечные профили по строке или столбцу.
# Для каждой линии профиля печатаются отрезки: D — тёмная линия (контур), g — заливка «охра»
# (перегородки в цветном исходнике), R — красная заливка (новые стены), C — серая заливка (бетон,
# показывается только полосой от 6 px, чтобы не ловить серые края сглаживания).
# Грань стены = край тёмного отрезка D, толщина = расстояние между двумя гранями.
#
#   python3 measure_walls.py src_x3.png --origin PX PY --ppu K  row 15.2 6.6 9.9   col 7.6 5.0 16.2 ...
#
#   row Y A B   — горизонтальный профиль на высоте Y от x=A до x=B
#   col X A B   — вертикальный профиль на абсциссе X от y=A до y=B
#   --dark N    — порог «тёмного» (0..255, по умолчанию 110; 170 — чтобы ловить и тонкие серые линии)
import argparse

import numpy as np
from PIL import Image

from calib import Calib, add_args

ap = argparse.ArgumentParser()
ap.add_argument("src")
add_args(ap)
ap.add_argument("--dark", type=int, default=110)
ap.add_argument("probes", nargs="+")
args = ap.parse_args()
C = Calib(args)

a = np.array(Image.open(args.src).convert("RGB")).astype(int)
R, G, B = a[..., 0], a[..., 1], a[..., 2]
gray = (R + G + B) / 3
MASKS = {
    "D": gray < args.dark,
    "g": (R > 150) & (G > 110) & (B < 170) & (R - B > 45) & (G - B > 20) & (R - G < 70),
    "R": (R > 150) & (G < 110) & (B < 110) & (R - G > 80),
    "C": (abs(R - G) < 16) & (abs(G - B) < 16) & (R > 60) & (R < 175),
}


def runs(v):
    idx = np.nonzero(v)[0]
    if len(idx) == 0:
        return []
    out = [[idx[0], idx[0]]]
    for i in idx[1:]:
        if i - out[-1][1] <= 1:
            out[-1][1] = i
        else:
            out.append([i, i])
    return out


def profile(kind, at, a0, a1):
    found = []
    if kind == "row":
        r = int(round(C.py(at)))
        c0, c1 = int(C.px(a0)), int(C.px(a1))
        for lab, m in MASKS.items():
            v = m[r - 1:r + 2, c0:c1].any(0)
            found += [(C.ux(c0 + s), C.ux(c0 + e + 1), lab) for s, e in runs(v) if lab != "C" or e - s >= 5]
    else:
        c = int(round(C.px(at)))
        r0, r1 = max(0, int(C.py(a1))), min(a.shape[0], int(C.py(a0)))
        for lab, m in MASKS.items():
            v = m[r0:r1, c - 1:c + 2].any(1)
            found += [(C.uy(r0 + e + 1), C.uy(r0 + s), lab) for s, e in runs(v) if lab != "C" or e - s >= 5]
    found.sort()
    print(f"{kind} {at:g}: " + " ".join(f"{lab}[{s:.2f}..{e:.2f}]" for s, e, lab in found))


p = args.probes
if len(p) % 4:
    ap.error("пробы задаются четвёрками: row|col ПОЛОЖЕНИЕ ОТ ДО")
for i in range(0, len(p), 4):
    profile(p[i], float(p[i + 1]), float(p[i + 2]), float(p[i + 3]))
