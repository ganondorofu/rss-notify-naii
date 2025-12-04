FROM python:3.11-slim

WORKDIR /app

# 依存パッケージをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションをコピー
COPY app.py .
COPY templates/ templates/

# データ保存用ディレクトリ
RUN mkdir -p /app/data

# ポート公開
EXPOSE 5000

# 環境変数  
ENV PYTHONUNBUFFERED=1

# 起動コマンド
CMD ["python", "app.py"]
