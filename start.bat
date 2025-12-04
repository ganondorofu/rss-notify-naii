@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   RSS通知システム - 起動スクリプト
echo ========================================
echo.

REM 仮想環境がなければ作成
if not exist "venv" (
    echo 仮想環境を作成中...
    python -m venv venv
)

REM 仮想環境を有効化
call venv\Scripts\activate.bat

REM 依存パッケージをインストール
echo 依存パッケージを確認中...
pip install -q -r requirements.txt

echo.
echo ----------------------------------------
echo RSS通知システムを起動中...
echo ブラウザで http://localhost:5000 にアクセスしてください
echo 終了するには Ctrl+C を押してください
echo ----------------------------------------
echo.

python app.py

pause
