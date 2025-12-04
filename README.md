# RSS通知システム - WebUI版

複数のRSSフィードを監視し、新着記事をDiscordに通知するシステムです。

## 機能

- 🌐 WebUIで簡単に管理
- 🔍 URLからRSSを自動検出
- ➕ 複数サイトのRSSフィード監視
- 📤 Discord Webhookで通知
- ⏱️ カスタム可能なチェック間隔
- 🔄 フィードごとの有効/無効切り替え
- 🐳 Docker対応

## セットアップ

### 方法1: Docker Compose（推奨）

```bash
# 起動
docker-compose up -d

# ログ確認
docker-compose logs -f

# 停止
docker-compose down
```

ブラウザで `http://localhost:5000` にアクセスしてください。

### 方法2: 直接実行

```bash
pip install -r requirements.txt
python app.py
```

### 方法3: Windows

`start.bat` をダブルクリック

### 方法4: Linux

```bash
chmod +x start.sh
./start.sh
```

## Linuxサーバーでの運用

### systemdでのサービス化

1. サービスファイルを編集
```bash
# rss-notify.service を編集してパスとユーザー名を変更
nano rss-notify.service
```

2. サービスファイルをコピー
```bash
sudo cp rss-notify.service /etc/systemd/system/
```

3. サービスを有効化・起動
```bash
sudo systemctl daemon-reload
sudo systemctl enable rss-notify
sudo systemctl start rss-notify
```

4. ステータス確認
```bash
sudo systemctl status rss-notify
```

## 使い方

1. **Discord Webhook URL設定**: Discord設定セクションでWebhook URLを入力して保存
2. **サイト追加**: サイトのURLを入力して「フィードを探す」をクリック
3. **監視開始**: 「監視開始」ボタンをクリック

## ファイル構成

```
rss-notify-naii/
├── app.py              # メインアプリケーション
├── templates/
│   └── index.html      # WebUI
├── data/               # データ保存ディレクトリ（Docker用）
│   ├── config.json     # 設定ファイル（自動生成）
│   └── seen_guids.json # 既読記事（自動生成）
├── requirements.txt    # 依存パッケージ
├── Dockerfile          # Docker設定
├── docker-compose.yml  # Docker Compose設定
├── start.bat          # Windows起動スクリプト
├── start.sh           # Linux起動スクリプト
└── rss-notify.service # systemdサービスファイル
```

## 設定ファイル (config.json)

```json
{
  "discord_webhook_url": "https://discord.com/api/webhooks/...",
  "check_interval": 300,
  "feeds": [
    {
      "id": "1234567890",
      "name": "サイト名",
      "url": "https://example.com/feed/",
      "enabled": true
    }
  ]
}
```
