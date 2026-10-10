# Проверка готового DWG независимым чтением: LibreDWG (dwg2dxf) и, если собран, libdxfrw (движок LibreCAD).
# Печатает число объектов по типам, предупреждения декодера и рендерит прочитанное в PNG,
# чтобы сравнить глазами с PDF. AutoCAD-а в среде нет — это лучшая доступная проверка.
#
#   python3 check_dwg.py plan.dwg check.png --paper A2P --scale 75
#
#   LIBREDWG_PREFIX  (по умолчанию /opt/libredwg) — нужен bin/dwg2dxf и bin/dwgread
#   LIBDXFRW_DWG2DXF (необязательно) — путь к dwg2dxf из libdxfrw
import argparse
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter

import ezdxf
from ezdxf.addons import Importer

ap = argparse.ArgumentParser()
ap.add_argument("dwg")
ap.add_argument("png")
ap.add_argument("--paper", default="A2L")
ap.add_argument("--scale", default="100")
args = ap.parse_args()

prefix = os.environ.get("LIBREDWG_PREFIX", "/opt/libredwg")
tmp = tempfile.mkdtemp(prefix="chkdwg_")
dxf = os.path.join(tmp, "back.dxf")

r = subprocess.run([os.path.join(prefix, "bin", "dwgread"), "-v2", args.dwg], capture_output=True, text=True)
issues = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l or "Warning" in l]
print(f"LibreDWG dwgread: ошибок/предупреждений {len(issues)}")
for l in issues[:10]:
    print("   ", l)

subprocess.run([os.path.join(prefix, "bin", "dwg2dxf"), "-y", "-o", dxf, args.dwg], capture_output=True)
if not os.path.exists(dxf):
    sys.exit("LibreDWG не смог прочитать DWG")

rw = os.environ.get("LIBDXFRW_DWG2DXF")
if rw and os.path.exists(rw):
    out = os.path.join(tmp, "rw.dxf")
    r = subprocess.run([rw, args.dwg, "-y", "-v2000", out], capture_output=True, text=True)
    print("libdxfrw:", (r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else r.returncode)

src = ezdxf.readfile(dxf)
doc = ezdxf.new("R2018")
imp = Importer(src, doc)
imp.import_modelspace()
imp.import_tables()
imp.finalize()
for e in doc.modelspace().query("TEXT"):  # \U+XXXX -> символы (так R2000 хранит не-ASCII текст)
    e.dxf.text = re.sub(r"\\U\+([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), e.dxf.text)
print("объекты:", dict(sorted(Counter(e.dxftype() for e in doc.modelspace()).items())))
print("слои:", ", ".join(l.dxf.name for l in doc.layers))
fixed = os.path.join(tmp, "back_utf8.dxf")
doc.saveas(fixed)
here = os.path.dirname(os.path.abspath(__file__))
subprocess.run([sys.executable, os.path.join(here, "render.py"), fixed, args.png,
                "--paper", args.paper, "--scale", args.scale], check=True)
