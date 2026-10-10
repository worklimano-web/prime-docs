#!/usr/bin/env bash
# Установка системных зависимостей для drawings/ (Ubuntu 24.04 / Debian 12).
# Запуск: sudo bash install_system.sh        (LibreDWG ставится в /opt/libredwg)
# Ключей и паролей не требует; сеть нужна для apt, pip и git clone с GitHub.
set -euo pipefail

PREFIX="${LIBREDWG_PREFIX:-/opt/libredwg}"
SRC="${SRC_DIR:-/opt/src}"

# 1. Системные пакеты
#    сборка LibreDWG: build-essential autoconf automake libtool pkg-config texinfo git
#    poppler-utils: pdfimages / pdftoppm — вынуть растр из PDF-скана и сделать превью
#    fonts-dejavu-core: шрифт с кириллицей и греческим для рендера PDF (вместо arial.ttf)
#    cmake: только для необязательной libdxfrw (второй, независимый читатель DWG)
apt-get update
apt-get install -y build-essential autoconf automake libtool pkg-config texinfo git \
    poppler-utils fonts-dejavu-core cmake python3 python3-pip python3-venv

# 2. LibreDWG 0.14 (тег 0.14, коммит d9468ae9) — запись DWG через C API.
#    Скачать архив релиза с github.com/…/releases из нашей облачной среды не дало (403),
#    поэтому git clone; у ftp.gnu.org тоже не было доступа.
mkdir -p "$SRC"
if [ ! -d "$SRC/libredwg" ]; then
    git clone --depth 1 --branch 0.14 --recurse-submodules --shallow-submodules \
        https://github.com/LibreDWG/libredwg.git "$SRC/libredwg"
fi
cd "$SRC/libredwg"
sh autogen.sh
./configure --disable-bindings --disable-docs --prefix="$PREFIX"
make -j"$(nproc)"
make install
echo "LibreDWG: $PREFIX/bin/dwgread $($PREFIX/bin/dwgread --version 2>&1 | head -1)"

# 3. (необязательно) libdxfrw — движок чтения DWG из LibreCAD, для перекрёстной проверки DWG.
#    Проверялось на коммите 25a2f8d. Утилита: $SRC/libdxfrw/build/dwg2dxf/dwg2dxf
if [ "${WITH_LIBDXFRW:-1}" = "1" ]; then
    if [ ! -d "$SRC/libdxfrw" ]; then
        git clone --depth 1 https://github.com/LibreCAD/libdxfrw.git "$SRC/libdxfrw"
    fi
    mkdir -p "$SRC/libdxfrw/build"
    cd "$SRC/libdxfrw/build"
    cmake .. -DCMAKE_BUILD_TYPE=Release
    make -j"$(nproc)"
    echo "libdxfrw: export LIBDXFRW_DWG2DXF=$SRC/libdxfrw/build/dwg2dxf/dwg2dxf"
fi

echo "Готово. Python-зависимости: pip install -r requirements.txt"
