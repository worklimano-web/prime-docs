# Печать DXF в PDF / PNG / SVG на лист заданного формата в заданном масштабе.
# Рамка листа должна быть нарисована в самом DXF (её строят скрипты plans/*.py):
# чертёж центрируется по габариту, поэтому рамка совпадает с краем листа.
#
#   python3 render.py plan.dxf out.pdf [out.png out@300.png out.svg] --paper A2L --scale 100
#
#   --paper  A0..A4 + L (альбомный) / P (книжный), по умолчанию A2L
#   --scale  знаменатель масштаба: 100 -> 1:100, 75 -> 1:75
#   --color  сохранить цвета DXF (по умолчанию всё печатается чёрным по белому)
#   PNG: «имя@300.png» — 300 dpi (по умолчанию 150)
import argparse

import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext, layout, pymupdf, svg
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration, LineweightPolicy

SIZES = {"A0": (1189, 841), "A1": (841, 594), "A2": (594, 420), "A3": (420, 297), "A4": (297, 210)}

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("outs", nargs="+")
ap.add_argument("--paper", default="A2L")
ap.add_argument("--scale", type=float, default=100)
ap.add_argument("--color", action="store_true")
args = ap.parse_args()

w, h = SIZES[args.paper[:2].upper()]
if args.paper[2:].upper() == "P":
    w, h = h, w

doc = ezdxf.readfile(args.src)
msp = doc.modelspace()
cfg = Configuration(
    background_policy=BackgroundPolicy.WHITE,
    color_policy=ColorPolicy.COLOR if args.color else ColorPolicy.BLACK,
    lineweight_policy=LineweightPolicy.ABSOLUTE,
    min_lineweight=0.1,
)
page = layout.Page(w, h, layout.Units.mm, margins=layout.Margins.all(0))
settings = layout.Settings(fit_page=False, scale=1.0 / args.scale)

for o in args.outs:
    if o.endswith(".svg"):
        be = svg.SVGBackend()
        Frontend(RenderContext(doc), be, config=cfg).draw_layout(msp)
        open(o, "w", encoding="utf-8").write(be.get_string(page, settings=settings))
    else:
        be = pymupdf.PyMuPdfBackend()
        Frontend(RenderContext(doc), be, config=cfg).draw_layout(msp)
        if o.endswith(".pdf"):
            open(o, "wb").write(be.get_pdf_bytes(page, settings=settings))
        else:
            dpi = int(o.rsplit("@", 1)[1].split(".")[0]) if "@" in o else 150
            open(o, "wb").write(be.get_pixmap_bytes(page, fmt="png", settings=settings, dpi=dpi))
    print("saved", o)
