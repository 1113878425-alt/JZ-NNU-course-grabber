#!/usr/bin/env bash
# ============================================================
#  JZ-NNU-course-grabber 一键启动脚本（macOS / Linux）
#  功能：自动检测 Python3 -> 创建/复用虚拟环境 -> 安装依赖 -> 启动
#  用法：chmod +x run.sh && ./run.sh
# ============================================================
set -e
cd "$(dirname "$0")"

echo
echo "============================================================"
echo "  JZ-NNU-course-grabber 选课抢课脚本"
echo "============================================================"
echo

# ---------- 1. 查找可用的 Python3 ----------
PY=""
for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then
        if "$cand" -c 'import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)' 2>/dev/null; then
            PY="$cand"
            break
        fi
    fi
done

if [ -z "$PY" ]; then
    echo "[错误] 未检测到 Python 3.8 或更高版本。"
    echo
    echo "  macOS : brew install python3"
    echo "  Ubuntu: sudo apt install python3 python3-venv python3-pip"
    echo
    echo "或者使用 uv（自动管理 Python，无需手动安装）："
    echo "    pip install uv && uv run main.py"
    echo
    exit 1
fi
echo "[1/3] 已检测到 $("$PY" --version 2>&1)"

# ---------- 2. 创建/复用虚拟环境 ----------
VENV_DIR=".venv"
if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "[2/3] 首次运行，正在创建虚拟环境 .venv ..."
    "$PY" -m venv "$VENV_DIR"
else
    echo "[2/3] 复用已有虚拟环境 .venv"
fi
VENV_PY="$VENV_DIR/bin/python"

# ---------- 3. 安装依赖（国内镜像源，已装则跳过）----------
if "$VENV_PY" -c "import requests" >/dev/null 2>&1; then
    echo "[3/3] 依赖已就绪"
else
    echo "[3/3] 正在安装依赖（使用清华镜像源，请稍候）..."
    MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
    if ! "$VENV_PY" -m pip install -r requirements.txt -i "$MIRROR"; then
        echo "[警告] 镜像源安装失败，尝试官方源..."
        "$VENV_PY" -m pip install -r requirements.txt
    fi
fi

# ---------- 4. 启动 ----------
echo
echo "-------- 启动主程序 --------"
echo
"$VENV_PY" main.py
