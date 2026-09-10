@echo off
REM ============================================================
REM  JZ-NNU-course-grabber 一键启动脚本（Windows）
REM  功能：自动检测 Python -> 创建/复用虚拟环境 -> 安装依赖 -> 启动
REM  用法：直接双击本文件，或在命令行执行 run.bat
REM ============================================================
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo   JZ-NNU-course-grabber 选课抢课脚本
echo ============================================================
echo.

REM ---------- 1. 查找可用的 Python ----------
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (
    where py >nul 2>nul && set "PY=py"
)
if not defined PY (
    echo [错误] 未检测到 Python。
    echo.
    echo 请先安装 Python 3.8 或更高版本： https://www.python.org/downloads/
    echo 安装时请务必勾选 "Add Python to PATH"。
    echo.
    echo 或者使用 uv（自动管理 Python，无需手动安装）：
    echo     pip install uv ^&^& uv run main.py
    echo.
    pause
    exit /b 1
)

REM 校验 Python 版本（需 3.8+）
%PY% -c "import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)" 2>nul
if errorlevel 1 (
    echo [错误] Python 版本过低，需要 3.8 或更高版本。
    %PY% --version
    pause
    exit /b 1
)
echo [1/3] 已检测到 Python：
%PY% --version

REM ---------- 2. 创建/复用虚拟环境 ----------
set "VENV_DIR=.venv"
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [2/3] 首次运行，正在创建虚拟环境 .venv ...
    %PY% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [错误] 虚拟环境创建失败。
        pause
        exit /b 1
    )
) else (
    echo [2/3] 复用已有虚拟环境 .venv
)
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

REM ---------- 3. 安装依赖（国内镜像源，已装则跳过）----------
"%VENV_PY%" -c "import requests" >nul 2>nul
if errorlevel 1 (
    echo [3/3] 正在安装依赖（使用清华镜像源，请稍候）...
    "%VENV_PY%" -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>nul
    "%VENV_PY%" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [警告] 镜像源安装失败，尝试官方源...
        "%VENV_PY%" -m pip install -r requirements.txt
        if errorlevel 1 (
            echo [错误] 依赖安装失败，请检查网络后重试。
            pause
            exit /b 1
        )
    )
) else (
    echo [3/3] 依赖已就绪
)

REM ---------- 4. 启动 ----------
echo.
echo -------- 启动主程序 --------
echo.
"%VENV_PY%" main.py

echo.
echo 程序已退出。
pause
