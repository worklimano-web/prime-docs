# План 1-го этажа (1ST FLOOR), редакция 2 — эталонный пример метода (см. ../README.md).
# Геометрия снята с изображения, увеличенного в 3 раза: грани стен — по краям линий оригинала,
# координаты в метрах от пересечения осей (левая нижняя колонна = 0,0).
# Масштаб изображения определён по сетке осей 7,40 м. Чертёж чёрно-белый (все слои цвета 7).
# Стены кабинетов 3, 4 и 6 — стеклянные перегородки (решение заказчика).
#
#   python3 plan2_1st_floor.py out.dxf
#   python3 ../tools/render.py out.dxf out.pdf --paper A2P --scale 75
#   python3 ../tools/dxf2dwg.py out.dxf out.dwg
import math
import sys

import ezdxf
from ezdxf import units
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

OUT = sys.argv[1]
S = 75  # 1:75 — мм модели на 1 мм бумаги (лист A2 книжный)
BLACK = 7


def mm(v):
    return round(v * 1000.0, 1)


def P(x, y):
    return (mm(x), mm(y))


doc = ezdxf.new("R2018", setup=True)
doc.units = units.MM
doc.header["$INSUNITS"] = 4
doc.header["$MEASUREMENT"] = 1
doc.header["$LUNITS"] = 2
doc.header["$LTSCALE"] = 1.0
msp = doc.modelspace()

doc.linetypes.add("AXIS", pattern=[1700, 1200, -200, 100, -200], description="Axis __ . __")
doc.styles.add("PLAN", font="arial.ttf")

LAYERS = {
    "A-GRID": (13, "AXIS"), "A-COLS": (35, "Continuous"), "A-WALL-CONC": (35, "Continuous"),
    "A-WALL-PART": (35, "Continuous"), "A-WALL-NEW": (35, "Continuous"), "A-WALL-GLASS": (18, "Continuous"),
    "A-GLAZ": (18, "Continuous"), "A-SLAB": (13, "Continuous"), "A-DOOR": (18, "Continuous"),
    "A-STAIR": (18, "Continuous"), "A-LIFT": (13, "Continuous"), "A-FIXT": (13, "Continuous"),
    "A-DIMS": (13, "Continuous"), "A-ROOM-DIMS": (13, "Continuous"), "A-ROOM-NAME": (18, "Continuous"),
    "A-ANNO": (18, "Continuous"), "A-FRAME": (50, "Continuous"),
}
for name, (lw, lt) in LAYERS.items():
    doc.layers.add(name, color=BLACK, lineweight=lw, linetype=lt)


def dimstyle(name, txt):
    ds = doc.dimstyles.new(name)
    for k, v in dict(dimtxt=txt, dimtxsty="PLAN", dimtsz=1.2 * S, dimasz=1.2 * S, dimexo=1.2 * S, dimexe=1.5 * S,
                     dimgap=0.6 * S, dimtad=1, dimtih=0, dimtoh=0, dimdec=0, dimrnd=10, dimzin=8, dimlunit=2,
                     dimdle=0, dimtofl=1, dimtmove=2, dimclrd=BLACK, dimclre=BLACK, dimclrt=BLACK).items():
        setattr(ds.dxf, k, v)


dimstyle("MM75", 2.2 * S)
dimstyle("ROOM75", 1.8 * S)


def line(p, q, layer, **kw):
    a = {"layer": layer}
    a.update(kw)
    return msp.add_line(P(*p), P(*q), dxfattribs=a)


def pline(pts, layer, close=False, **kw):
    a = {"layer": layer}
    a.update(kw)
    return msp.add_lwpolyline([P(*p) for p in pts], close=close, dxfattribs=a)


def rect(x0, y0, x1, y1, layer, **kw):
    return pline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer, close=True, **kw)


def text(s, x, y, h, layer="A-ANNO", align=TextEntityAlignment.MIDDLE_CENTER, rot=0.0):
    t = msp.add_text(s, height=h, rotation=rot, dxfattribs={"layer": layer, "style": "PLAN"})
    t.set_placement(P(x, y), align=align)
    return t


def hatch(pts_mm, layer, pattern="SOLID", scale=1.0):
    h = msp.add_hatch(color=BLACK, dxfattribs={"layer": layer})
    if pattern != "SOLID":
        h.set_pattern_fill(pattern, scale=scale)
    h.paths.add_polyline_path(pts_mm, is_closed=True)
    return h


def polys(g):
    return [p for p in (g.geoms if hasattr(g, "geoms") else [g]) if p.area > 100]


def outline(poly, layer):
    ext = [(round(x, 1), round(y, 1)) for x, y in poly.exterior.coords][:-1]
    msp.add_lwpolyline(ext, close=True, dxfattribs={"layer": layer})
    for ring in poly.interiors:
        msp.add_lwpolyline([(round(x, 1), round(y, 1)) for x, y in ring.coords][:-1], close=True,
                           dxfattribs={"layer": layer})
    return ext


def draw_geom(g, layer, pattern=None, scale=1.0):
    for poly in polys(g):
        ext = outline(poly, layer)
        if pattern:
            h = msp.add_hatch(color=BLACK, dxfattribs={"layer": layer})
            if pattern != "SOLID":
                h.set_pattern_fill(pattern, scale=scale)
            h.paths.add_polyline_path(ext, is_closed=True, flags=1)
            for ring in poly.interiors:
                h.paths.add_polyline_path([(round(x, 1), round(y, 1)) for x, y in ring.coords][:-1],
                                          is_closed=True, flags=0)


def B(x0, y0, x1, y1):
    return box(mm(x0), mm(y0), mm(x1), mm(y1))


def arrowhead(tip, frm, layer, size=0.35):
    dx, dy = tip[0] - frm[0], tip[1] - frm[1]
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    bx, by = tip[0] - ux * size, tip[1] - uy * size
    w = size * 0.3
    hatch([P(*tip), P(bx - uy * w, by + ux * w), P(bx + uy * w, by - ux * w)], layer)


# =============================================================================
# ОСИ: по вертикали 7400 (по оригиналу), по горизонтали 7300 + 7400 (по колоннам)
# =============================================================================
GX = [0.0, 7.30, 14.70]
GY = [0.0, 7.40, 14.80, 22.20]
for x in GX:
    line((x, -3.0), (x, 25.6), "A-GRID")
for y in GY:
    line((-2.4, y), (18.2, y), "A-GRID")

# =============================================================================
# КРАЙ ПЛИТЫ ТЕРРАСЫ (наружный контур и парапет)
# =============================================================================
# наружная кромка террасы (от угла витража вокруг здания до противоположного угла)
TERR = [(-0.80, -0.41), (-0.80, -2.50), (17.30, -2.50), (17.30, 7.50), (15.40, 7.50), (15.40, 14.63),
        (17.30, 14.63), (17.30, 24.47), (-1.55, 24.47), (-1.55, 14.72), (-0.47, 14.72)]
pline(TERR, "A-SLAB")
par = LineString([P(*p) for p in TERR]).offset_curve(130, join_style=2)  # парапет, внутрь террасы
msp.add_lwpolyline([(round(x, 1), round(y, 1)) for x, y in par.coords], dxfattribs={"layer": "A-SLAB"})
for x0, y0, x1, y1 in [(0.15, 24.20, 5.85, 24.31), (10.55, 24.20, 12.35, 24.31), (0.50, -2.41, 4.20, -2.30),
                       (12.90, -2.41, 16.00, -2.30), (17.04, 18.05, 17.15, 21.10), (17.04, 0.90, 17.15, 6.60)]:
    rect(x0, y0, x1, y1, "A-SLAB")
    hatch([P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)], "A-SLAB", "ANSI31", 8)

# =============================================================================
# ВИТРАЖ (НАВЕСНОЙ ФАСАД): полосы (наружная..внутренняя грань) и импосты
# =============================================================================
GLAZ = [
    (-0.47, 22.41, 15.18, 22.60),   # север
    (-0.47, 15.70, -0.27, 22.60),   # запад, верхняя часть
    (-0.31, 6.14, -0.22, 15.70),   # запад, у ядра
    (-0.80, -0.41, -0.60, 5.93),    # запад, нижняя часть
    (-0.80, -0.41, 16.25, -0.20),   # юг
    (16.05, -0.41, 16.25, 7.47),    # восток, нижняя часть
    (15.80, 7.27, 16.25, 7.47),     # уступ
    (15.01, 7.48, 15.30, 14.94),    # восток, середина
    (14.99, 16.05, 15.18, 22.60),   # восток, верхняя часть (выше двери)
    (14.99, 15.18, 15.18, 15.33),
]
glaz = unary_union([B(*g) for g in GLAZ])
for poly in polys(glaz):
    outline(poly, "A-GLAZ")


def mullions(x0, y0, x1, y1, step=0.95):
    horiz = (x1 - x0) > (y1 - y0)
    L = (x1 - x0) if horiz else (y1 - y0)
    n = max(1, round(L / step))
    for i in range(n + 1):
        t = i * L / n
        if horiz:
            c = x0 + t
            pts = [P(c - 0.04, y0), P(c + 0.04, y0), P(c + 0.04, y1), P(c - 0.04, y1)]
        else:
            c = y0 + t
            pts = [P(x0, c - 0.04), P(x1, c - 0.04), P(x1, c + 0.04), P(x0, c + 0.04)]
        hatch(pts, "A-GLAZ")


mullions(-0.47, 22.41, 15.18, 22.60)
mullions(-0.47, 15.93, -0.27, 22.60)
mullions(14.99, 16.05, 15.18, 22.60)
mullions(15.01, 7.48, 15.30, 14.94)
mullions(16.05, -0.41, 16.25, 7.47)
mullions(-0.80, -0.41, 16.25, -0.20)
mullions(-0.80, -0.41, -0.60, 5.93)

# =============================================================================
# КОЛОННЫ 350 x 400
# =============================================================================
COLS = [(x, y) for x in GX for y in (0.0, 22.20)] + [(14.70, 14.80), (14.70, 7.40)]
cols = unary_union([B(x - 0.175, y - 0.20, x + 0.175, y + 0.20) for x, y in COLS])

# =============================================================================
# СТЕНЫ (грани — по осям линий оригинала)
# =============================================================================
CONC = [(-0.22, 13.49, 5.04, 13.70), (2.80, 9.70, 3.00, 13.49), (2.55, 7.50, 2.75, 9.92),
        (2.55, 9.70, 5.04, 9.92), (4.80, 12.20, 5.04, 13.49), (4.78, 10.74, 5.04, 11.12),
        (2.55, 7.50, 5.04, 7.70)]
PART = [
    (-0.47, 15.70, 9.56, 15.93),                                   # северная стена ядра
    (0.07, 6.14, 0.15, 15.70),                                    # западная стена ядра
    (2.47, 13.70, 2.66, 15.70),                                    # серверная, восточная
    (2.97, 13.70, 3.02, 14.15), (2.97, 15.42, 3.02, 15.70),        # шахта стояков, откосы
    (-0.80, 5.93, 4.82, 6.14), (4.82, 5.33, 5.04, 6.14), (5.04, 5.33, 5.43, 5.54),  # южная стена ядра
    (7.01, 5.33, 7.23, 15.93), (9.37, 5.33, 9.56, 15.93), (6.85, 5.33, 9.56, 5.54),   # блок санузлов
    (7.23, 13.46, 9.37, 13.56), (8.20, 12.13, 9.37, 12.23), (7.01, 10.81, 9.37, 10.91),
    (8.20, 9.48, 9.37, 9.58), (7.23, 8.05, 9.37, 8.26),
    (0.15, 7.51, 1.66, 7.73),                                     # зона МГН
    (4.98, 6.14, 5.04, 6.42), (4.98, 7.38, 5.04, 7.50),           # откосы двери холла
    (3.00, 10.56, 4.80, 10.68),                                    # перегородка в шахте лифта
    (14.47, 14.94, 15.27, 15.18), (14.52, 7.25, 15.80, 7.48),      # торцы витража справа
]
NEW = [(7.12, 15.93, 7.22, 22.0), (5.07, 17.39, 7.22, 17.49), (5.04, 17.49, 5.14, 17.87),
       (7.61, 3.09, 7.71, 5.33)]
GLASS = [(3.02, -0.20, 3.12, 5.93), (-0.60, 3.19, 3.02, 3.29),           # кабинеты 3, 4
         (7.61, -0.20, 7.71, 3.09), (7.71, 2.99, 13.32, 3.09), (13.22, -0.20, 13.32, 2.99)]  # кабинет 6
OPEN = [
    (0.34, 15.65, 1.83, 15.98), (5.17, 15.65, 6.86, 15.98),        # двери в северной стене ядра
    (6.95, 13.63, 7.30, 14.57), (6.95, 10.93, 7.30, 11.89), (6.95, 9.81, 7.30, 10.79),  # санузлы
    (9.30, 6.00, 9.62, 7.55),
    (7.05, 16.48, 7.30, 17.40),                                    # новая перегородка — дверь
    (2.95, 2.48, 3.20, 3.19), (2.95, 3.29, 3.20, 3.98),            # кабинеты 3, 4
    (7.55, 3.68, 7.80, 4.66), (7.71, 2.95, 8.41, 3.12),            # холл -> офис, кабинет 6
]
op = unary_union([B(*o) for o in OPEN])
conc = unary_union([B(*w) for w in CONC])
part = unary_union([B(*w) for w in PART]).difference(op).difference(conc).difference(cols)
new = unary_union([B(*w) for w in NEW]).difference(op).difference(cols)
glass = unary_union([B(*w) for w in GLASS]).difference(op).difference(cols)
draw_geom(conc, "A-WALL-CONC", "ANSI31", 22)
draw_geom(part, "A-WALL-PART")
draw_geom(new, "A-WALL-NEW", "SOLID")
draw_geom(glass, "A-WALL-GLASS")
# стекло: осевая линия в каждом участке стеклянной перегородки
for g in GLASS:
    horiz = (g[2] - g[0]) > (g[3] - g[1])
    for poly in polys(B(*g).difference(op).difference(cols)):
        x0, y0, x1, y1 = poly.bounds
        if horiz:
            msp.add_line((x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2), dxfattribs={"layer": "A-WALL-GLASS"})
        else:
            msp.add_line(((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1), dxfattribs={"layer": "A-WALL-GLASS"})
draw_geom(cols, "A-COLS", "SOLID")

# =============================================================================
# ДВЕРИ (полотно открыто на 90°, дуга 90°)
# =============================================================================
DIRS = {"+x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "-y": (0, -1)}


def door(hinge, closed, width, swing):
    cx, cy = DIRS[closed]
    sx, sy = DIRS[swing]
    hx, hy = hinge
    line(hinge, (hx + width * sx, hy + width * sy), "A-DOOR")
    a_c = math.degrees(math.atan2(cy, cx))
    a_o = math.degrees(math.atan2(sy, sx))
    start, end = (a_c, a_o) if (a_o - a_c) % 360 == 90 else (a_o, a_c)
    msp.add_arc(P(hx, hy), mm(width), start, end, dxfattribs={"layer": "A-DOOR"})


for d in [
    ((0.34, 15.70), "+x", 0.745, "-y"), ((1.83, 15.70), "-x", 0.745, "-y"),   # серверная WD-02
    ((3.00, 15.42), "-y", 0.635, "+x"), ((3.00, 14.15), "+y", 0.635, "+x"),   # шахта стояков
    ((5.17, 15.70), "+x", 0.845, "-y"), ((6.86, 15.70), "-x", 0.845, "-y"),   # холл, север
    ((5.43, 5.43), "+x", 0.71, "+y"), ((6.85, 5.43), "-x", 0.71, "+y"),       # холл, юг
    ((5.00, 6.55), "+y", 0.93, "-x"),                                         # нижний холл
    ((2.55, 7.73), "-x", 0.89, "+y"),                                        # лестница
    ((7.01, 13.63), "+y", 0.94, "-x"),                                        # пом. 13
    ((7.23, 10.93), "+y", 0.96, "+x"), ((7.23, 10.79), "-y", 0.98, "+x"),     # санузлы
    ((9.37, 7.55), "-y", 0.775, "-x"), ((9.37, 6.00), "+y", 0.775, "-x"),     # пом. 16
    ((14.99, 15.33), "+y", 0.72, "-x"),                                       # выход на террасу
    ((7.12, 17.40), "-y", 0.92, "-x"),
    ((3.02, 3.29), "+y", 0.69, "-x"), ((3.02, 3.19), "-y", 0.71, "-x"),     # кабинеты 3, 4
    ((7.71, 4.66), "-y", 0.98, "+x"),
    ((7.71, 2.99), "+x", 0.70, "-y"),                                        # кабинет 6
    ((7.90, -0.20), "+x", 0.70, "+y"),                                        # кабинет 6 -> терраса
]:
    door(*d)
# двери лифтов
line((4.92, 11.12), (4.92, 12.20), "A-DOOR")
line((4.80, 7.70), (4.80, 8.30), "A-LIFT")
line((4.80, 9.20), (4.80, 9.70), "A-LIFT")
line((4.92, 8.30), (4.92, 9.20), "A-DOOR")
line((4.80, 9.92), (4.80, 10.74), "A-LIFT")
line((3.07, 6.14), (3.07, 7.50), "A-WALL-PART")  # лёгкая перегородка (тонкая линия в оригинале)

# =============================================================================
# ЛИФТЫ, ЛЕСТНИЦА
# =============================================================================
for x0, y0, x1, y1 in [(3.00, 10.68, 4.80, 13.49), (2.75, 7.70, 4.78, 9.70)]:
    line((x0, y0), (x1, y1), "A-LIFT")
    line((x0, y1), (x1, y0), "A-LIFT")

rect(1.37, 10.30, 1.57, 12.45, "A-STAIR")
line((1.34, 8.92), (1.34, 12.45), "A-STAIR")
line((1.60, 10.30), (1.60, 12.19), "A-STAIR")
line((0.15, 8.92), (1.34, 8.92), "A-STAIR")
for k in range(13):
    y = 9.02 + k * 0.27
    line((0.15, y), (1.34, y), "A-STAIR")
for k in range(8):
    y = 10.30 + k * 0.27
    line((1.60, y), (2.80, y), "A-STAIR")
pline([(0.72, 9.25), (0.72, 12.80), (2.20, 12.80), (2.20, 10.60)], "A-STAIR")
arrowhead((2.20, 10.35), (2.20, 10.60), "A-STAIR")
msp.add_circle(P(0.72, 9.25), 60, dxfattribs={"layer": "A-STAIR"})

# зона безопасности МГН (штриховка)
rect(0.15, 6.14, 1.25, 7.51, "A-FIXT")
hatch([P(0.15, 6.14), P(1.25, 6.14), P(1.25, 7.51), P(0.15, 7.51)], "A-FIXT", "ANSI31", 20)

# =============================================================================
# САНТЕХНИКА (условно)
# =============================================================================
line((7.87, 13.56), (7.87, 15.70), "A-FIXT")
rect(7.23, 14.60, 7.48, 15.02, "A-FIXT")
line((8.67, 10.91), (8.67, 13.46), "A-FIXT")
line((8.67, 8.26), (8.67, 10.81), "A-FIXT")
line((8.27, 5.54), (8.27, 8.05), "A-FIXT")


def wc(cy, x_wall):
    rect(x_wall - 0.22, cy - 0.22, x_wall, cy + 0.22, "A-FIXT")
    msp.add_ellipse(P(x_wall - 0.48, cy), major_axis=(mm(0.27), 0), ratio=0.68, dxfattribs={"layer": "A-FIXT"})


for cy in (12.84, 11.52, 10.19, 8.87):
    wc(cy, 9.37)
rect(7.55, 7.55, 8.22, 7.98, "A-FIXT")
rect(7.62, 7.62, 8.15, 7.91, "A-FIXT")

# =============================================================================
# ПОМЕЩЕНИЯ: имена, площади, внутренние размеры
# =============================================================================
OPEN_SPACE = [(7.22, 22.41), (14.99, 22.41), (14.99, 15.18), (14.47, 15.18), (14.47, 14.94), (15.01, 14.94),
              (15.01, 7.48), (14.52, 7.48), (14.52, 7.25), (16.05, 7.25), (16.05, -0.20), (13.32, -0.20),
              (13.32, 3.09), (7.71, 3.09), (7.71, 5.33), (9.56, 5.33), (9.56, 15.93), (7.22, 15.93)]
ROOMS = [
    # (№, имя, полигон, подпись (x, y[, поворот]), [размеры: (p1, p2, вертикальный[, база вынесенной линии])])
    (1, "Офис", [(-0.27, 15.93), (7.12, 15.93), (7.12, 22.41), (-0.27, 22.41)], (2.6, 19.2),
     [((-0.27, 21.7), (7.12, 21.7), False), ((0.65, 15.93), (0.65, 22.41), True)]),
    (2, "Офис (open space)", OPEN_SPACE, (11.3, 18.9),
     [((7.22, 21.7), (14.99, 21.7), False), ((8.10, 15.93), (8.10, 22.41), True),
      ((9.56, 11.0), (15.01, 11.0), False), ((14.20, -0.20), (14.20, 22.41), True),
      ((7.71, 4.30), (16.05, 4.30), False), ((15.60, -0.20), (15.60, 7.25), True),
      ((13.32, 1.40), (16.05, 1.40), False), ((10.30, 3.09), (10.30, 5.33), True)]),
    (3, "Кабинет", [(-0.60, 3.29), (3.02, 3.29), (3.02, 5.93), (-0.60, 5.93)], (1.25, 4.45),
     [((-0.60, 5.25), (3.02, 5.25), False), ((0.25, 3.29), (0.25, 5.93), True)]),
    (4, "Кабинет", [(-0.60, -0.20), (3.02, -0.20), (3.02, 3.19), (-0.60, 3.19)], (1.25, 1.55),
     [((-0.60, 0.45), (3.02, 0.45), False), ((0.25, -0.20), (0.25, 3.19), True)]),
    (5, "Холл", [(3.12, -0.20), (7.61, -0.20), (7.61, 5.33), (4.82, 5.33), (4.82, 5.93), (3.12, 5.93)],
     (5.6, 2.7), [((3.12, 0.45), (7.61, 0.45), False), ((4.00, -0.20), (4.00, 5.93), True)]),
    (6, "Кабинет", [(7.71, -0.20), (13.22, -0.20), (13.22, 2.99), (7.71, 2.99)], (10.6, 1.5),
     [((7.71, 0.40), (13.22, 0.40), False), ((12.50, -0.20), (12.50, 2.99), True)]),
    (7, "Серверная", [(0.15, 13.70), (2.47, 13.70), (2.47, 15.70), (0.15, 15.70)], (1.40, 14.85),
     [((0.15, 14.05), (2.47, 14.05), False), ((0.45, 13.70), (0.45, 15.70), True)]),
    (8, "Лестница", [(0.15, 7.73), (2.55, 7.73), (2.55, 9.92), (2.80, 9.92), (2.80, 13.49), (0.15, 13.49)],
     (1.45, 8.35), [((0.15, 13.10), (2.80, 13.10), False), ((0.45, 7.73), (0.45, 13.49), True)]),
    (9, "Лифт", [(3.00, 10.68), (4.80, 10.68), (4.80, 13.49), (3.00, 13.49)], (3.90, 12.55),
     [((3.00, 11.20), (4.80, 11.20), False), ((3.35, 10.68), (3.35, 13.49), True)]),
    (10, "Лифт", [(2.75, 7.70), (4.78, 7.70), (4.78, 9.70), (2.75, 9.70)], (3.80, 9.15),
     [((2.75, 8.10), (4.78, 8.10), False), ((3.10, 7.70), (3.10, 9.70), True)]),
    (11, "Лифтовой холл", [(5.04, 5.54), (7.01, 5.54), (7.01, 15.70), (3.00, 15.70), (3.00, 13.70), (5.04, 13.70)],
     (5.95, 11.6, 90), [((5.04, 8.30), (7.01, 8.30), False), ((6.65, 5.54), (6.65, 15.70), True),
                        ((3.00, 15.20), (7.01, 15.20), False), ((4.40, 13.70), (4.40, 15.70), True)]),
    (12, "Холл", [(0.15, 6.14), (5.00, 6.14), (5.00, 7.50), (0.15, 7.50)], (2.05, 6.85),
     [((0.15, 7.22), (5.00, 7.22), False), ((4.55, 6.14), (4.55, 7.50), True)]),
    (13, "Помещение", [(7.23, 13.56), (9.37, 13.56), (9.37, 15.70), (7.23, 15.70)], (8.55, 14.55),
     [((7.23, 15.35), (9.37, 15.35), False), ((9.56, 13.56), (9.56, 15.70), True, 10.15)]),
    (14, "Санузел", [(7.23, 10.91), (9.37, 10.91), (9.37, 13.46), (7.23, 13.46)], (7.95, 12.35),
     [((7.23, 13.10), (9.37, 13.10), False), ((9.56, 10.91), (9.56, 13.46), True, 10.15)]),
    (15, "Санузел", [(7.23, 8.26), (9.37, 8.26), (9.37, 10.81), (7.23, 10.81)], (7.95, 9.75),
     [((7.23, 8.60), (9.37, 8.60), False), ((9.56, 8.26), (9.56, 10.81), True, 10.15)]),
    (16, "Помещение", [(7.23, 5.54), (9.37, 5.54), (9.37, 8.05), (7.23, 8.05)], (8.30, 6.75),
     [((7.23, 5.90), (9.37, 5.90), False), ((9.56, 5.54), (9.56, 8.05), True, 10.15)]),
]


def area(poly):
    return Polygon(poly).area


for no, name, poly, lab, dims in ROOMS:
    for dd in dims:
        p1, p2, vertical = dd[:3]
        ext = len(dd) > 3
        base = (dd[3], p1[1]) if (ext and vertical) else ((p1[0], dd[3]) if ext else p1)
        ov = {} if ext else {"dimse1": 1, "dimse2": 1}
        d = msp.add_linear_dim(base=P(*base), p1=P(*p1), p2=P(*p2), angle=90 if vertical else 0,
                               dimstyle="ROOM75", override=ov, dxfattribs={"layer": "A-ROOM-DIMS"})
        d.render()
    a = area(poly)
    small = a < 6
    lx, ly = lab[0], lab[1]
    rot = lab[2] if len(lab) > 2 else 0
    off = 0.13 if small else 0.2
    dx, dy = (-off, 0) if rot else (0, off)
    text(f"{no}. {name}", lx + dx, ly + dy, (1.8 if small else 2.5) * S, "A-ROOM-NAME", rot=rot)
    text(f"{a:.2f} м²".replace(".", ","), lx - dx, ly - dy, (1.6 if small else 2.1) * S, "A-ROOM-NAME", rot=rot)

text("WD-02 · FR60 · 1500×2100", 1.05, 16.35, 1.5 * S)

# =============================================================================
# ОБЩИЕ РАЗМЕРЫ (мм)
# =============================================================================


def dim(p1, p2, base, vertical, style="MM75", layer="A-DIMS"):
    if vertical:
        d = msp.add_linear_dim(base=P(base, p1[1]), p1=P(*p1), p2=P(*p2), angle=90, dimstyle=style,
                               dxfattribs={"layer": layer})
    else:
        d = msp.add_linear_dim(base=P(p1[0], base), p1=P(*p1), p2=P(*p2), angle=0, dimstyle=style,
                               dxfattribs={"layer": layer})
    d.render()


for a, b in zip(GY, GY[1:]):
    dim((-2.4, a), (-2.4, b), -2.9, True)
dim((-2.9, GY[0]), (-2.9, GY[-1]), -3.9, True)
for a, b in zip(GX, GX[1:]):
    dim((a, -3.0), (b, -3.0), -3.3, False)
dim((-0.80, -0.41), (16.25, -0.41), -4.3, False)
dim((-0.47, 22.60), (15.18, 22.60), 25.4, False)
dim((17.30, -0.41), (17.30, 22.60), 18.6, True)

# =============================================================================
# РАМКА A2 книжная (420 x 594), 1:75, ЭКСПЛИКАЦИЯ, ШТАМП
# =============================================================================
FX0, FY0 = -4400 - 60 * S, 25800 - 581 * S
FW, FH = 420 * S, 594 * S


def PX(v):
    return FX0 + v * S


def PY(v):
    return FY0 + v * S


msp.add_lwpolyline([(FX0, FY0), (FX0 + FW, FY0), (FX0 + FW, FY0 + FH), (FX0, FY0 + FH)], close=True,
                   dxfattribs={"layer": "A-FRAME", "lineweight": 13})
msp.add_lwpolyline([(PX(20), PY(5)), (PX(415), PY(5)), (PX(415), PY(589)), (PX(20), PY(589))], close=True,
                   dxfattribs={"layer": "A-FRAME", "lineweight": 70})


def tb(s_, x, y, h=2.5, attach=4, layer="A-ANNO"):
    t = msp.add_mtext(s_, dxfattribs={"layer": layer, "style": "PLAN", "char_height": h * S,
                                      "attachment_point": attach})
    t.set_location((x, y))


def fl(x0, y0, x1, y1, lw=13):
    msp.add_line((x0, y0), (x1, y1), dxfattribs={"layer": "A-FRAME", "lineweight": lw})


TX0, TY0, TX1, TY1 = PX(230), PY(5), PX(415), PY(60)
msp.add_lwpolyline([(TX0, TY0), (TX1, TY0), (TX1, TY1), (TX0, TY1)], close=True,
                   dxfattribs={"layer": "A-FRAME", "lineweight": 50})
for k in range(1, 5):
    fl(TX0, TY0 + k * 11 * S, TX1, TY0 + k * 11 * S, 18)
fl(TX0 + 40 * S, TY0, TX0 + 40 * S, TY1 - 11 * S, 18)
tb("План 1-го этажа (1ST FLOOR) — размеры помещений", TX0 + 3 * S, TY1 - 5.5 * S, 3.3)
for i, (k, v) in enumerate([
    ("Источник", "изображение плана, перечерчено (ред. 2)"),
    ("Масштаб", "1:75 (лист A2); размеры в мм, площади в м²"),
    ("Размеры", "по масштабу; шаг осей 7400 мм — по оригиналу"),
    ("Точность", "±30 мм (разбор при увеличении ×3)"),
]):
    yy = TY1 - 16.5 * S - i * 11 * S
    tb(k, TX0 + 3 * S, yy, 2.4)
    tb(v, TX0 + 43 * S, yy, 2.3)

LX, LY = PX(22), PY(163)
tb("Экспликация помещений", LX, LY, 3.5, attach=7)
CWID = [0, 12, 62, 140, 185]
rows = [("№", "Наименование", "Размеры в свету, мм", "Площадь, м²")]
total = 0.0
for no, name, poly, _, dims in ROOMS:
    a = area(poly)
    total += a
    p1, p2 = dims[0][:2]
    q1, q2 = dims[1][:2]
    w = int(abs(p2[0] - p1[0]) * 100 + 0.5 + 1e-6) * 10
    h = int(abs(q2[1] - q1[1]) * 100 + 0.5 + 1e-6) * 10
    if no == 2:
        size = "сложной формы — см. план"
    else:
        size = f"{w} × {h}" if len(poly) == 4 else f"{w} × {h} (сложной формы)"
    rows.append((str(no), name, size, f"{a:.2f}".replace(".", ",")))
rows.append(("", "Итого", "", f"{total:.2f}".replace(".", ",")))
RH = 6.5 * S
ty = LY - 7 * S
for r, row in enumerate(rows):
    y_top = ty - r * RH
    fl(LX, y_top, LX + CWID[-1] * S, y_top, 13 if r else 35)
    for c, cell in enumerate(row):
        tb(cell, LX + CWID[c] * S + 1.5 * S, y_top - RH / 2, 2.3 if r else 2.4)
y_bot = ty - len(rows) * RH
fl(LX, y_bot, LX + CWID[-1] * S, y_bot, 35)
for c in CWID:
    fl(LX + c * S, ty, LX + c * S, y_bot, 13)

RX, RY = PX(230), PY(163)
tb("Условные обозначения", RX, RY, 3.3, attach=7)
SAMPLES = [("A-WALL-CONC", "ANSI31", "железобетонные стены"), ("A-WALL-PART", None, "перегородки существующие"),
           ("A-WALL-NEW", "SOLID", "перегородки новые"), ("A-WALL-GLASS", "GLASS", "перегородки стеклянные"),
           ("A-COLS", "SOLID", "колонны 350×400")]
for i, (lay, pat, s_) in enumerate(SAMPLES):
    yy = RY - 10 * S - i * 6 * S
    th = 0.6 if lay == "A-WALL-GLASS" else 1.3
    pts = [(RX, yy - th * S), (RX + 15 * S, yy - th * S), (RX + 15 * S, yy + th * S), (RX, yy + th * S)]
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": lay})
    if pat == "GLASS":
        msp.add_line((RX, yy), (RX + 15 * S, yy), dxfattribs={"layer": lay})
    elif pat:
        h = msp.add_hatch(color=BLACK, dxfattribs={"layer": lay})
        if pat != "SOLID":
            h.set_pattern_fill(pat, scale=22)
        h.paths.add_polyline_path(pts, is_closed=True)
    tb(s_, RX + 19 * S, yy, 2.3)
yy = RY - 10 * S - len(SAMPLES) * 6 * S
msp.add_line((RX, yy), (RX + 15 * S, yy), dxfattribs={"layer": "A-GLAZ"})
tb("витраж (навесной фасад)", RX + 19 * S, yy, 2.3)
yy -= 6 * S
msp.add_line((RX, yy), (RX + 15 * S, yy), dxfattribs={"layer": "A-GRID"})
tb("оси", RX + 19 * S, yy, 2.3)
yy -= 9 * S
for i, s_ in enumerate([
    "Примечания",
    "1. Размеры помещений — в свету, между гранями стен и витража.",
    "2. Шаг осей по вертикали 7400 мм — по оригиналу; шаг по горизонтали",
    "    (7300, 7400) и все размеры помещений определены по масштабу.",
    "3. Стены кабинетов 3, 4 и 6 — стеклянные перегородки.",
    "4. Маркеры разрезов/фасадов и марки дверей/окон не перенесены;",
    "    сантехника и лестница показаны упрощённо.",
]):
    tb(s_, RX, yy - i * 4.6 * S, 2.8 if i == 0 else 2.2, attach=7)

doc.set_modelspace_vport(height=FH * 1.05, center=(FX0 + FW / 2, FY0 + FH / 2))
doc.saveas(OUT)
print("saved", OUT, "rooms total area", round(total, 2))
