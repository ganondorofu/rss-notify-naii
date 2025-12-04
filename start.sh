#!/bin/bash
# RSS通知システム起動スクリプト

cd "$(dirname "$0")"

# 仮想環境がなければ作成
if [ ! -d "venv" ]; then
    echo "仮想環境を作成中..."
    python3 -m venv venv
fi

# 仮想環境を有効化
source venv/bin/activate

# 依存パッケージをインストール
echo "依存パッケージを確認中..."
pip install -q -r requirements.txt

# アプリケーションを起動
echo "RSS通知システムを起動中..."
echo "ブラウザで http://localhost:5000 にアクセスしてください"
python app.py
