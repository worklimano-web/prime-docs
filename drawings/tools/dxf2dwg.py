# DXF -> DWG (AutoCAD 2000, AC1015) через C API LibreDWG (dwg_add_*).
# Встроенный импорт DXF в LibreDWG (dxf2dwg) на наших файлах падает, поэтому DWG собирается
# заново из примитивов: размеры, штриховки и штриховые типы линий раскладываются на
# LINE / LWPOLYLINE / SOLID / TEXT, чтобы файл одинаково отображался в любом CAD.
# Имена слоёв и стилей транслитерируются в ASCII. Текст хранится в кодовой странице ANSI_1251
# (как в русских DWG из AutoCAD): кириллица — 1 байт на букву, символы вне 1251 (², ×, греческие) —
# как \U+XXXX. Первая версия писала весь не-ASCII текст через \U+XXXX; длинные русские строки
# выходили за 255 байт, и LibreDWG при обратном чтении в DXF их обрезал.
#
#   python3 dxf2dwg.py in.dxf out.dwg
#
# Нужна собранная LibreDWG 0.14 (см. ../install_system.sh); путь — переменная LIBREDWG_PREFIX
# (по умолчанию /opt/libredwg: include/dwg.h, include/dwg_api.h, lib/libredwg.a) и gcc.
import math
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

import ezdxf
from ezdxf.math import Vec2, Vec3
from ezdxf.math.triangulation import mapbox_earcut_2d
from ezdxf.render import hatching

SRC, DST = sys.argv[1], sys.argv[2]
LDWG = os.environ.get("LIBREDWG_PREFIX", "/opt/libredwg")

doc = ezdxf.readfile(SRC)
msp = doc.modelspace()

prims = []  # (kind, layer, color, data)

TR = dict(zip("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
              ["A", "B", "V", "G", "D", "E", "E", "ZH", "Z", "I", "Y", "K", "L", "M", "N", "O", "P", "R", "S", "T",
               "U", "F", "KH", "TS", "CH", "SH", "SHCH", "", "Y", "", "E", "YU", "YA"]))


def asc(name):
    out = []
    for c in name:
        u = c.upper()
        if ord(c) < 128:
            out.append(c)
        elif u in TR:
            t = TR[u]
            out.append(t if c == u else t.lower())
        else:
            out.append("_")
    return "".join(out)


def lt_pattern(e):
    name = e.dxf.get("linetype", "BYLAYER")
    if name.upper() == "BYLAYER":
        lay = doc.layers.get(e.dxf.layer) if doc.layers.has_entry(e.dxf.layer) else None
        name = lay.dxf.linetype if lay else "Continuous"
    if name.upper() in ("CONTINUOUS", "BYBLOCK"):
        return None
    if not doc.linetypes.has_entry(name):
        return None
    lt = doc.linetypes.get(name)
    simple = lt.simplified_line_pattern()
    pat = [abs(v) if i % 2 == 0 else -abs(v) for i, v in enumerate(simple)]
    return pat if sum(abs(v) for v in pat) > 0 else None


def dash_segments(a, b, pat):
    """разложить отрезок a-b по шаблону [dash, -gap, dot(0), -gap ...]"""
    a, b = Vec2(a), Vec2(b)
    L = (b - a).magnitude
    if L < 1e-6:
        return []
    u = (b - a).normalize()
    out, t, i = [], 0.0, 0
    while t < L:
        v = pat[i % len(pat)]
        if v >= 0:
            seg = max(v, 0.0)
            t1 = min(t + seg, L)
            if seg == 0:  # точка — короткий штрих
                t1 = min(t + 20, L)
            out.append((a + u * t, a + u * t1))
            t = t1
        else:
            t += -v
        i += 1
    return out


def add_line(layer, color, a, b, pat):
    if pat:
        for p, q in dash_segments(a, b, pat):
            prims.append(("line", layer, color, [p.x, p.y, q.x, q.y]))
    else:
        prims.append(("line", layer, color, [a[0], a[1], b[0], b[1]]))


def add_solid_polys(layer, color, paths):
    """paths: список контуров (первый внешний, остальные отверстия) — триангуляция в SOLID"""
    ext = [Vec2(p) for p in paths[0]]
    holes = [[Vec2(p) for p in h] for h in paths[1:]]
    for tri in mapbox_earcut_2d(ext, holes):
        p = [(v.x, v.y) for v in tri]
        prims.append(("solid", layer, color, [p[0][0], p[0][1], p[1][0], p[1][1], p[2][0], p[2][1], p[2][0], p[2][1]]))


ATTACH = {1: (0, 3), 2: (1, 3), 3: (2, 3), 4: (0, 2), 5: (1, 2), 6: (2, 2), 7: (0, 1), 8: (1, 1), 9: (2, 1)}


def handle(e, depth=0):
    t = e.dxftype()
    layer = asc(e.dxf.layer)
    color = e.dxf.get("color", 256)
    if layer.lower() == "defpoints" or t == "POINT":
        return
    if t == "LINE":
        add_line(layer, color, e.dxf.start, e.dxf.end, lt_pattern(e))
    elif t == "LWPOLYLINE":
        pts = [Vec2(p[0], p[1]) for p in e.get_points("xy")]
        closed = e.closed
        pat = lt_pattern(e)
        if pat:
            seq = pts + ([pts[0]] if closed else [])
            for a, b in zip(seq, seq[1:]):
                add_line(layer, color, a, b, pat)
        else:
            prims.append(("pline", layer, color, {"closed": closed, "pts": [[p.x, p.y] for p in pts]}))
    elif t == "ARC":
        prims.append(("arc", layer, color, [e.dxf.center.x, e.dxf.center.y, e.dxf.radius,
                                            math.radians(e.dxf.start_angle), math.radians(e.dxf.end_angle)]))
    elif t == "CIRCLE":
        prims.append(("circle", layer, color, [e.dxf.center.x, e.dxf.center.y, e.dxf.radius]))
    elif t == "ELLIPSE":
        pts = [Vec2(v) for v in e.flattening(5)]
        prims.append(("pline", layer, color, {"closed": False, "pts": [[p.x, p.y] for p in pts]}))
    elif t == "SOLID" or t == "TRACE":
        v = [e.dxf.vtx0, e.dxf.vtx1, e.dxf.vtx2, e.dxf.get("vtx3", e.dxf.vtx2)]
        prims.append(("solid", layer, color, [v[0].x, v[0].y, v[1].x, v[1].y, v[2].x, v[2].y, v[3].x, v[3].y]))
    elif t == "HATCH":
        if e.dxf.solid_fill:
            paths = []
            for path in e.paths.rendering_paths(e.dxf.hatch_style):
                pts = [(v[0], v[1]) for v in path.vertices]
                paths.append(pts)
            if paths:
                add_solid_polys(layer, color, paths)
        else:
            for ln in hatching.hatch_entity(e):
                a, b = (ln.start, ln.end) if hasattr(ln, "start") else (ln[0], ln[1])
                prims.append(("line", layer, color, [a.x, a.y, b.x, b.y]))
            # контур штриховки не рисуем — он уже есть отдельной полилинией
    elif t == "TEXT":
        h, v = e.dxf.get("halign", 0), e.dxf.get("valign", 0)
        ins = e.dxf.insert
        al = e.dxf.get("align_point", ins)
        prims.append(("text", layer, color, {"s": e.dxf.text, "x": ins.x, "y": ins.y, "ax": al.x, "ay": al.y,
                                             "h": e.dxf.height, "rot": math.radians(e.dxf.get("rotation", 0)),
                                             "ha": h, "va": v, "style": asc(e.dxf.get("style", "Standard"))}))
    elif t == "MTEXT":
        txt = e.plain_text(split=True)
        ha, va = ATTACH.get(e.dxf.get("attachment_point", 1), (0, 3))
        h = e.dxf.char_height
        if e.dxf.hasattr("text_direction"):
            d = Vec3(e.dxf.text_direction)
            rot = math.atan2(d.y, d.x)
        else:
            rot = math.radians(e.dxf.get("rotation", 0))
        ins = Vec2(e.dxf.insert)
        n = len(txt)
        step = h * 1.667
        ux, uy = math.cos(rot), math.sin(rot)
        nx, ny = -uy, ux  # «вверх» относительно текста
        # смещение первой строки относительно точки вставки
        if va == 3:
            first = -h / 2
        elif va == 2:
            first = (n - 1) * step / 2
        else:
            first = (n - 1) * step + h / 2
        for i, line in enumerate(txt):
            off = first - i * step
            px, py = ins.x + nx * off, ins.y + ny * off
            prims.append(("text", layer, color, {"s": line, "x": px, "y": py, "ax": px, "ay": py, "h": h, "rot": rot,
                                                 "ha": ha, "va": 2, "style": asc(e.dxf.get("style", "Standard"))}))
    elif t in ("DIMENSION", "INSERT"):
        for sub in e.virtual_entities():
            if sub.dxf.layer == "0":
                sub.dxf.layer = e.dxf.layer
            if sub.dxf.get("color", 256) == 0:  # BYBLOCK
                sub.dxf.color = color
            handle(sub, depth + 1)
    else:
        print("skip", t, file=sys.stderr)


for e in msp:
    handle(e)

layers = []
for lay in doc.layers:
    lw = lay.dxf.get("lineweight", -3)
    layers.append({"name": asc(lay.dxf.name), "color": abs(lay.dxf.color), "lw": lw})
used_styles = {d["style"] for k, _, _, d in prims if k == "text"}
styles = [{"name": asc(s.dxf.name), "font": s.dxf.get("font", "arial.ttf")} for s in doc.styles
          if asc(s.dxf.name) in used_styles]

xs = [p for k, _, _, d in prims if k == "line" for p in (d[0], d[2])]
ys = [p for k, _, _, d in prims if k == "line" for p in (d[1], d[3])]
data = {"layers": layers, "styles": styles, "prims": prims,
        "ext": [min(xs), min(ys), max(xs), max(ys)]}

# ---------------------------------------------------------------------------
# C-программа: читает текстовый файл с примитивами и создаёт DWG через dwg_add_*
# ---------------------------------------------------------------------------
C_SRC = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <dwg.h>
#include <dwg_api.h>

EXPORT BITCODE_BSd dxf_revcvt_lweight (const int lw);

static char *read_all(const char *fn, long *n) {
  FILE *f = fopen(fn, "rb"); if (!f) return NULL;
  fseek(f, 0, SEEK_END); *n = ftell(f); fseek(f, 0, SEEK_SET);
  char *b = malloc(*n + 1); fread(b, 1, *n, f); b[*n] = 0; fclose(f); return b;
}

static void set_common(Dwg_Data *dwg, void *ent, const char *layer, int color) {
  Dwg_Object_Entity *c = ((Dwg_Entity_LINE *)ent)->parent;
  BITCODE_H h = dwg_find_tablehandle (dwg, layer, "LAYER");
  if (h) dwg_dynapi_common_set_value (ent, "layer", &h, 0);
  c->color.index = (BITCODE_BSd)color;
}

/* формат входа (построчно):
   L name color lw          — слой
   S name font              — стиль
   line layer color x1 y1 x2 y2
   pline layer color closed n x y x y ...
   arc layer color cx cy r a0 a1
   circle layer color cx cy r
   solid layer color x1 y1 x2 y2 x3 y3 x4 y4
   text layer color style h rot ha va x y ax ay <TAB>string
   E xmin ymin xmax ymax
*/
int main(int argc, char **argv) {
  long n; char *buf = read_all(argv[1], &n);
  if (!buf) { fprintf(stderr, "no input\n"); return 1; }
  Dwg_Data *dwg = dwg_new_Document (R_2000, 0, 0);
  dwg->header.codepage = 29; /* CP_ANSI_1251: LibreDWG перекодирует UTF-8 строки в 1251 при записи */
  Dwg_Object *mspace = dwg_model_space_object (dwg);
  Dwg_Object_BLOCK_HEADER *hdr = mspace->tio.object->tio.BLOCK_HEADER;
  dwg->header_vars.INSUNITS = 4;
  dwg->header_vars.MEASUREMENT = 1;
  dwg->header_vars.LUNITS = 2;
  dwg->header_vars.LUPREC = 0;
  dwg->header_vars.LTSCALE = 1.0;
  dwg->header_vars.LWDISPLAY = 1;
  char *save = NULL;
  for (char *ln = strtok_r(buf, "\n", &save); ln; ln = strtok_r(NULL, "\n", &save)) {
    char kind[16], layer[128];
    int color;
    if (ln[0] == 'L' && ln[1] == ' ') {
      char name[128]; int col, lw;
      sscanf(ln + 2, "%127s %d %d", name, &col, &lw);
      Dwg_Object_LAYER *lay = NULL;
      if (strcmp(name, "0") == 0) continue;
      lay = dwg_add_LAYER (dwg, name);
      if (lay) {
        lay->color.index = col;
        lay->plotflag = 1;
        if (lw >= 0) lay->linewt = dxf_revcvt_lweight (lw);
        lay->flag0 = 16 + ((lay->linewt & 0x1F) << 5);
      }
      continue;
    }
    if (ln[0] == 'S' && ln[1] == ' ') {
      char name[128], font[128];
      sscanf(ln + 2, "%127s %127s", name, font);
      if (strcmp(name, "Standard") == 0 || strcmp(name, "STANDARD") == 0) continue;
      Dwg_Object_STYLE *st = dwg_add_STYLE (dwg, name);
      if (st) st->font_file = dwg_add_u8_input (dwg, font);
      continue;
    }
    if (ln[0] == 'E' && ln[1] == ' ') {
      double a, b, c, d; sscanf(ln + 2, "%lf %lf %lf %lf", &a, &b, &c, &d);
      dwg->header_vars.EXTMIN.x = a; dwg->header_vars.EXTMIN.y = b;
      dwg->header_vars.EXTMAX.x = c; dwg->header_vars.EXTMAX.y = d;
      continue;
    }
    int off = 0;
    if (sscanf(ln, "%15s %127s %d %n", kind, layer, &color, &off) < 3) continue;
    char *p = ln + off;
    if (!strcmp(kind, "line")) {
      dwg_point_3d a = {0}, b = {0};
      sscanf(p, "%lf %lf %lf %lf", &a.x, &a.y, &b.x, &b.y);
      Dwg_Entity_LINE *e = dwg_add_LINE (hdr, &a, &b);
      if (e) set_common(dwg, e, layer, color);
    } else if (!strcmp(kind, "pline")) {
      int closed, np, k = 0; sscanf(p, "%d %d %n", &closed, &np, &k); p += k;
      dwg_point_2d *pts = calloc(np, sizeof(dwg_point_2d));
      for (int i = 0; i < np; i++) { sscanf(p, "%lf %lf %n", &pts[i].x, &pts[i].y, &k); p += k; }
      Dwg_Entity_LWPOLYLINE *e = dwg_add_LWPOLYLINE (hdr, np, pts);
      if (e) { if (closed) e->flag |= 512; set_common(dwg, e, layer, color); }
      free(pts);
    } else if (!strcmp(kind, "arc")) {
      dwg_point_3d c = {0}; double r, a0, a1;
      sscanf(p, "%lf %lf %lf %lf %lf", &c.x, &c.y, &r, &a0, &a1);
      Dwg_Entity_ARC *e = dwg_add_ARC (hdr, &c, r, a0, a1);
      if (e) set_common(dwg, e, layer, color);
    } else if (!strcmp(kind, "circle")) {
      dwg_point_3d c = {0}; double r;
      sscanf(p, "%lf %lf %lf", &c.x, &c.y, &r);
      Dwg_Entity_CIRCLE *e = dwg_add_CIRCLE (hdr, &c, r);
      if (e) set_common(dwg, e, layer, color);
    } else if (!strcmp(kind, "solid")) {
      dwg_point_3d p1 = {0}; dwg_point_2d p2, p3, p4;
      sscanf(p, "%lf %lf %lf %lf %lf %lf %lf %lf", &p1.x, &p1.y, &p2.x, &p2.y, &p3.x, &p3.y, &p4.x, &p4.y);
      Dwg_Entity_SOLID *e = dwg_add_SOLID (hdr, &p1, &p2, &p3, &p4);
      if (e) set_common(dwg, e, layer, color);
    } else if (!strcmp(kind, "text")) {
      char style[128]; double h, rot, x, y, ax, ay; int ha, va;
      sscanf(p, "%127s %lf %lf %d %d %lf %lf %lf %lf", style, &h, &rot, &ha, &va, &x, &y, &ax, &ay);
      char *s = strchr(p, '\t'); if (!s) continue; s++;
      dwg_point_3d ins = {x, y, 0};
      Dwg_Entity_TEXT *e = dwg_add_TEXT (hdr, s, &ins, h);
      if (!e) continue;
      e->rotation = rot;
      e->horiz_alignment = ha;
      e->vert_alignment = va;
      e->width_factor = 1.0;
      e->oblique_angle = 0.0;
      e->elevation = 0.0;
      e->generation = 0;
      e->alignment_pt.x = ax; e->alignment_pt.y = ay;
      /* dataflags: установленный бит = поле отсутствует (значение по умолчанию) */
      {
        unsigned df = 0x01 | 0x04 | 0x10 | 0x20;
        if (rot == 0.0) df |= 0x08;
        if (!ha) df |= 0x40;
        if (!va) df |= 0x80;
        if (!(ha || va)) df |= 0x02;
        e->dataflags = df;
      }
      BITCODE_H sh = dwg_find_tablehandle (dwg, style, "STYLE");
      if (sh) e->style = sh;
      set_common(dwg, e, layer, color);
    }
  }
  int err = dwg_write_file (argv[2], dwg);
  printf("write status %d\n", err);
  return err >= DWG_ERR_CRITICAL;
}
'''

work = tempfile.mkdtemp(prefix="d2d_")
inp = os.path.join(work, "prims.txt")
with open(inp, "w", encoding="utf-8") as f:
    for L in layers:
        f.write(f"L {L['name']} {L['color']} {L['lw']}\n")
    for s in styles:
        f.write(f"S {s['name']} {s['font']}\n")
    for k, layer, color, d in prims:
        if k in ("line", "arc", "circle", "solid"):
            f.write(f"{k} {layer} {color} " + " ".join(f"{v:.3f}" if isinstance(v, float) else str(v) for v in d) + "\n")
        elif k == "pline":
            f.write(f"pline {layer} {color} {1 if d['closed'] else 0} {len(d['pts'])} "
                    + " ".join(f"{x:.3f} {y:.3f}" for x, y in d["pts"]) + "\n")
        elif k == "text":
            if d["ha"] or d["va"]:
                # точка вставки (10) должна отличаться от точки выравнивания (11), иначе в DWG
                # точка выравнивания не записывается; AutoCAD всё равно пересчитает 10 по 11
                w = 0.6 * d["h"] * max(1, len(d["s"]))
                fh = {0: 0.0, 1: 0.5, 2: 1.0, 4: 0.5}.get(d["ha"], 0.0)
                fv = {0: 0.0, 1: 0.0, 2: 0.5, 3: 1.0}.get(d["va"], 0.0)
                ux, uy = math.cos(d["rot"]), math.sin(d["rot"])
                d["x"] = d["ax"] - ux * w * fh + uy * d["h"] * fv
                d["y"] = d["ay"] - uy * w * fh - ux * d["h"] * fv
            s = d["s"].replace("\t", " ").replace("\n", " ")
            # LibreDWG сама перекодирует UTF-8 в cp1251 при записи; символы вне 1251 — заранее в \U+XXXX
            s = "".join(c if c.encode("cp1251", "ignore") else "\\U+%04X" % ord(c) for c in s)
            f.write(f"text {layer} {color} {d['style']} {d['h']:.3f} {d['rot']:.6f} {d['ha']} {d['va']} "
                    f"{d['x']:.3f} {d['y']:.3f} {d['ax']:.3f} {d['ay']:.3f}\t{s}\n")
    e = data["ext"]
    f.write(f"E {e[0]:.1f} {e[1]:.1f} {e[2]:.1f} {e[3]:.1f}\n")

csrc = os.path.join(work, "mk.c")
exe = os.path.join(work, "mk")
open(csrc, "w").write(C_SRC)
inc = os.path.join(LDWG, "include")
lib = os.path.join(LDWG, "lib", "libredwg.a")
if not os.path.exists(lib):
    sys.exit(f"нет {lib}: соберите LibreDWG (install_system.sh) или задайте LIBREDWG_PREFIX")
subprocess.run(["gcc", "-O1", "-w", "-o", exe, csrc, f"-I{inc}", lib, "-lm"], check=True)
if os.path.exists(DST):
    os.remove(DST)
r = subprocess.run([exe, inp, DST], capture_output=True, text=True, errors="replace")
shutil.rmtree(work, ignore_errors=True)
print(r.stdout.strip(), r.stderr.strip()[-500:])
print("primitives:", dict(Counter(k for k, *_ in prims)))
if r.returncode != 0 or not os.path.exists(DST):
    sys.exit("DWG не записан")
