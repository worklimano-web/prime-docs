#!/usr/bin/env bash
# Сквозной прогон метода на примере (план 1-го этажа): все шаги по порядку.
# Результаты — в drawings/out/ (папка не коммитится).
#   bash run_example.sh
# Нужны: pip install -r requirements.txt, LibreDWG в $LIBREDWG_PREFIX (по умолчанию /opt/libredwg).
set -euo pipefail
cd "$(dirname "$0")"
OUT=out
mkdir -p "$OUT/crops"
SRC=examples/input/plan2_1st_floor_source.jpg

# Калибровка исходника 1280×1101: начало координат (пересечение осей у левой нижней колонны) —
# пиксель (345, 995), 40,02 px на метр (шаг осей 7,40 м = 296 px). После увеличения ×3:
CAL3="--origin 1036 2986 --ppu 120.06"

echo "== 1. Увеличение исходника ×3"
python3 tools/upscale.py "$SRC" "$OUT/src_x3.png" --factor 3

echo "== 2. Фрагменты с координатной сеткой (их читает модель/человек)"
python3 tools/grid_overlay.py "$OUT/src_x3.png" "$OUT/crops/stair_core.png" -0.6 6.0 3.4 16.3 $CAL3 --zoom 1.5
python3 tools/grid_overlay.py "$OUT/src_x3.png" "$OUT/crops/wc_block.png" 6.0 10.6 10.0 16.2 $CAL3 --zoom 1.6

echo "== 3. Профили поперёк стен: точные грани"
python3 tools/measure_walls.py "$OUT/src_x3.png" $CAL3 \
    row 12.8 6.6 9.9 \
    col 8.4 5.0 16.2

echo "== 4. Перерисовка: DXF в мм (координаты стен — в plans/plan2_1st_floor.py)"
python3 plans/plan2_1st_floor.py "$OUT/plan2_1st_floor_mm.dxf"

echo "== 5. Контроль: чертёж поверх исходника"
python3 tools/overlay_check.py "$OUT/plan2_1st_floor_mm.dxf" "$OUT/src_x3.png" "$OUT/overlay.png" $CAL3 \
    --crop -0.8 5.0 10.0 16.4 "$OUT/crops/overlay_core.png"

echo "== 6. PDF (A2 книжный, 1:75, чёрно-белый) и PNG-превью"
python3 tools/render.py "$OUT/plan2_1st_floor_mm.dxf" "$OUT/plan2_1st_floor_mm.pdf" "$OUT/plan2_1st_floor_mm.png" \
    --paper A2P --scale 75

echo "== 7. DWG (AutoCAD 2000)"
python3 tools/dxf2dwg.py "$OUT/plan2_1st_floor_mm.dxf" "$OUT/plan2_1st_floor_mm.dwg"

echo "== 8. Проверка DWG независимым чтением"
python3 tools/check_dwg.py "$OUT/plan2_1st_floor_mm.dwg" "$OUT/dwg_check.png" --paper A2P --scale 75

echo "Готово: $OUT/plan2_1st_floor_mm.pdf, $OUT/plan2_1st_floor_mm.dwg"
