# Калибровка «пиксели изображения <-> единицы чертежа» и общие аргументы командной строки.
#
# Калибровка задаётся тремя числами:
#   --origin PX PY   пиксель, где лежит начало координат чертежа (обычно пересечение двух осей)
#   --ppu K          пикселей на единицу (на метр или на фут); можно задать отдельно --ppu-y
# Ось Y чертежа направлена вверх, ось Y изображения — вниз.
#
# Как получить: найти на изображении две оси (или две колонны) с известным расстоянием между ними
# (подписанный размер), измерить расстояние в пикселях (см. measure_walls.py) и поделить.
#   План 1 (скан 150 dpi, футы):      --origin 1065 1785 --ppu 18.92 --ppu-y 18.68
#   План 2 (скриншот, метры):         --origin 345 995  --ppu 40.02
#   План 2, увеличенный в 3 раза:     --origin 1036 2986 --ppu 120.06


def add_args(ap):
    ap.add_argument("--origin", nargs=2, type=float, required=True, metavar=("PX", "PY"))
    ap.add_argument("--ppu", type=float, required=True, help="пикселей на единицу чертежа по X")
    ap.add_argument("--ppu-y", type=float, default=None, help="пикселей на единицу по Y (если отличается)")


class Calib:
    def __init__(self, args):
        self.ox, self.oy = args.origin
        self.kx = args.ppu
        self.ky = args.ppu_y or args.ppu

    def px(self, x):
        return self.ox + self.kx * x

    def py(self, y):
        return self.oy - self.ky * y

    def ux(self, px):
        return (px - self.ox) / self.kx

    def uy(self, py):
        return (self.oy - py) / self.ky
