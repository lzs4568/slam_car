#!/bin/bash
# ============================================
# ELF2 语音桥接 启动脚本
# 自动绕过 conda 环境干扰，使用系统 Python
# 用法:
#   ./launch.sh
#   ./launch.sh --port /dev/ttyACM0
# ============================================

set -e

# ---- 解除 conda 干扰 ----
# conda 会修改 site-packages 搜索路径，导致系统包 (apt install 的) 找不到
# 直接删掉 conda 注入的环境变量，用纯净的系统 Python
unset PYTHONHOME PYTHONPATH
unset CONDA_PREFIX CONDA_DEFAULT_ENV CONDA_EXE CONDA_PYTHON_EXE
unset CONDA_SHLVL CONDA_PROMPT_MODIFIER
export PATH=$(echo "$PATH" | tr ':' '\n' | grep -v conda | tr '\n' ':')

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ---- 显式指定系统 Python + site-packages ----
export PYTHONIOENCODING=utf-8
export PYTHONPATH="/home/elf/.local/lib/python3.10/site-packages:/usr/lib/python3/dist-packages:/usr/lib/python3.10/dist-packages"

# ---- API Key ----
if [ -z "$DASHSCOPE_API_KEY" ]; then
    export DASHSCOPE_API_KEY="sk-ws-H.RXEEMRY.cv7r.MEUCIQDEs_PBUeJQUDjqU94v5brBHQM66EJebkiWaTeYT5BlSgIgQ5Ll2l4hzOIHBwhEFurnK5KK6a0NNbFlpwHgopLh2ls"
fi

echo "✅ 纯净 Python 环境就绪"
echo "   python3: $(/usr/bin/python3 --version 2>&1)"
echo "   serial:  $(/usr/bin/python3 -c 'import serial; print(serial.__version__)' 2>&1)"
echo ""

exec /usr/bin/python3 main.py "$@"
