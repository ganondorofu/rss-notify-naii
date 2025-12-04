#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSS通知システム - WebUI版
複数のRSSフィードを監視し、新着記事をDiscordに通知する
"""

import feedparser
import requests
import json
import os
import re
import threading
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse
from flask import Flask, render_template, request, jsonify, redirect, url_for
from bs4 import BeautifulSoup

# ===== 設定 =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Docker環境ではdataディレクトリを使用
DATA_DIR = os.path.join(BASE_DIR, "data") if os.path.exists(os.path.join(BASE_DIR, "data")) else BASE_DIR
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
SEEN_FILE = os.path.join(DATA_DIR, "seen_guids.json")
CHECK_INTERVAL = 300  # チェック間隔（秒）

app = Flask(__name__)

# グローバル変数
monitor_thread = None
is_running = False

def load_config():
    """設定ファイルを読み込む"""
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "discord_webhook_url": "",
            "check_interval": 300,
            "feeds": []
        }
        save_config(default_config)
        return default_config
    
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    """設定ファイルを保存"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def load_seen_guids():
    """既読のGUIDをファイルから読み込む"""
    if not os.path.exists(SEEN_FILE):
        return {}
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_seen_guids(guids):
    """既読のGUIDをファイルに保存"""
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(guids, f, ensure_ascii=False, indent=2)

def detect_rss_feeds(url):
    """
    URLからRSSフィードを自動検出する
    サイトのURLを渡すとRSSフィードのURLを探して返す
    """
    feeds_found = []
    
    # まずURLがRSSフィードかどうか確認
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # 直接RSSとしてパースしてみる
        feed = feedparser.parse(url)
        if feed.entries and not feed.bozo:
            # 有効なRSSフィード
            title = feed.feed.get('title', urlparse(url).netloc)
            return [{
                'url': url,
                'title': title,
                'type': 'direct'
            }]
        
        # HTMLページからRSSリンクを探す
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # サイトのタイトルを取得
        site_title = soup.find('title')
        site_title = site_title.text.strip() if site_title else urlparse(url).netloc
        
        # link タグからRSS/Atomフィードを探す
        feed_links = soup.find_all('link', type=re.compile(r'application/(rss|atom)\+xml'))
        for link in feed_links:
            href = link.get('href')
            if href:
                feed_url = urljoin(url, href)
                title = link.get('title', site_title)
                feeds_found.append({
                    'url': feed_url,
                    'title': title,
                    'type': 'link_tag'
                })
        
        # よくあるRSSパスを試す
        common_paths = [
            '/feed/', '/feed', '/rss/', '/rss', '/rss.xml', '/feed.xml',
            '/atom.xml', '/index.xml', '/feeds/posts/default',
            '/?feed=rss2', '/?feed=rss', '/?feed=atom',
            '/blog/feed/', '/blog/rss/',
        ]
        
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        
        for path in common_paths:
            test_url = urljoin(base_url, path)
            # 既に見つかったURLは除外
            if any(f['url'] == test_url for f in feeds_found):
                continue
            
            try:
                test_feed = feedparser.parse(test_url)
                if test_feed.entries and not test_feed.bozo:
                    title = test_feed.feed.get('title', site_title)
                    feeds_found.append({
                        'url': test_url,
                        'title': title,
                        'type': 'common_path'
                    })
            except:
                pass
        
        # aタグからRSSリンクを探す
        rss_links = soup.find_all('a', href=re.compile(r'(rss|feed|atom)', re.IGNORECASE))
        for link in rss_links:
            href = link.get('href')
            if href and ('rss' in href.lower() or 'feed' in href.lower() or 'atom' in href.lower()):
                feed_url = urljoin(url, href)
                # 既に見つかったURLは除外
                if any(f['url'] == feed_url for f in feeds_found):
                    continue
                
                # 実際にRSSかどうか確認
                try:
                    test_feed = feedparser.parse(feed_url)
                    if test_feed.entries and not test_feed.bozo:
                        title = test_feed.feed.get('title', link.text.strip() or site_title)
                        feeds_found.append({
                            'url': feed_url,
                            'title': title,
                            'type': 'a_tag'
                        })
                except:
                    pass
        
        # 重複を除去
        seen_urls = set()
        unique_feeds = []
        for feed in feeds_found:
            if feed['url'] not in seen_urls:
                seen_urls.add(feed['url'])
                unique_feeds.append(feed)
        
        return unique_feeds
        
    except Exception as e:
        print(f"RSS検出エラー: {e}")
        return []

def get_site_info(url):
    """サイトの情報（タイトル、ファビコン等）を取得"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # タイトル取得
        title = soup.find('title')
        title = title.text.strip() if title else urlparse(url).netloc
        
        # ファビコン取得
        favicon = None
        icon_link = soup.find('link', rel=re.compile(r'icon', re.IGNORECASE))
        if icon_link and icon_link.get('href'):
            favicon = urljoin(url, icon_link.get('href'))
        
        return {
            'title': title,
            'favicon': favicon,
            'domain': urlparse(url).netloc
        }
    except:
        return {
            'title': urlparse(url).netloc,
            'favicon': None,
            'domain': urlparse(url).netloc
        }

def send_discord_message(webhook_url, title, url, site_name=None):
    """
    DiscordのWebhookにシンプルなメッセージを送信
    """
    if not webhook_url:
        print("Webhook URLが設定されていません")
        return False
    
    # シンプルなメッセージ形式
    if site_name:
        content = f"📰 **{site_name}** に新着記事！\n**{title}**\n{url}"
    else:
        content = f"📰 新着記事！\n**{title}**\n{url}"
    
    data = {"content": content}
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(webhook_url, json=data, headers=headers, timeout=10)
        if 200 <= response.status_code < 300:
            print(f"Discord送信成功: {title}")
            return True
        else:
            print(f"Discord送信失敗: {response.status_code}, {response.text}")
            return False
    except Exception as e:
        print(f"Discord送信エラー: {e}")
        return False

def extract_image_from_content(entry):
    """RSSエントリーから画像URLを抽出する"""
    # media_thumbnail から取得
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url')
    
    # media_content から取得
    if hasattr(entry, 'media_content') and entry.media_content:
        for media in entry.media_content:
            if media.get('medium') == 'image' or media.get('type', '').startswith('image/'):
                return media.get('url')
        if entry.media_content[0].get('url'):
            return entry.media_content[0].get('url')
    
    # content から img タグを抽出
    content = ''
    if hasattr(entry, 'content') and entry.content:
        content = entry.content[0].get('value', '')
    elif hasattr(entry, 'summary'):
        content = entry.summary
    
    if content:
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE)
        if img_match:
            return img_match.group(1)
    
    return None

def check_single_feed(feed_config, webhook_url, seen_guids):
    """単一のRSSフィードをチェック"""
    feed_url = feed_config.get("url", "")
    feed_name = feed_config.get("name", "不明なサイト")
    feed_id = feed_config.get("id", feed_url)
    
    if not feed_url:
        return 0
    
    try:
        feed = feedparser.parse(feed_url)
        
        if feed.bozo:
            print(f"RSSパースエラー ({feed_name}): {feed.bozo_exception}")
            return 0
        
        # このフィードの既読GUIDを取得
        feed_seen = set(seen_guids.get(feed_id, []))
        new_count = 0
        new_entries = []
        
        for entry in feed.entries:
            guid = entry.get("id", entry.get("link", ""))
            if guid and guid not in feed_seen:
                new_entries.append({
                    "title": entry.get("title", "タイトルなし"),
                    "link": entry.get("link", ""),
                    "guid": guid
                })
                feed_seen.add(guid)
        
        # 新着記事を古い順に通知
        new_entries.reverse()
        
        for entry in new_entries:
            if send_discord_message(webhook_url, entry['title'], entry['link'], feed_name):
                new_count += 1
                time.sleep(1)  # レート制限対策
        
        # 既読リストを更新
        seen_guids[feed_id] = list(feed_seen)
        
        return new_count
        
    except Exception as e:
        print(f"フィードチェックエラー ({feed_name}): {e}")
        return 0

def check_all_feeds():
    """全てのRSSフィードをチェック"""
    config = load_config()
    webhook_url = config.get("discord_webhook_url", "")
    feeds = config.get("feeds", [])
    
    if not feeds:
        print("監視するフィードがありません")
        return
    
    seen_guids = load_seen_guids()
    total_new = 0
    
    for feed_config in feeds:
        if feed_config.get("enabled", True):
            new_count = check_single_feed(feed_config, webhook_url, seen_guids)
            total_new += new_count
    
    save_seen_guids(seen_guids)
    
    if total_new > 0:
        print(f"合計 {total_new} 件の新着記事を通知しました")
    else:
        print("新着記事はありません")

def monitor_loop():
    """監視ループ"""
    global is_running
    while is_running:
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] フィードをチェック中...")
            check_all_feeds()
        except Exception as e:
            print(f"監視エラー: {e}")
        
        config = load_config()
        interval = config.get("check_interval", CHECK_INTERVAL)
        
        # 待機（1秒ごとにis_runningをチェック）
        for _ in range(interval):
            if not is_running:
                break
            time.sleep(1)

# ===== Webルート =====

@app.route("/")
def index():
    """メインページ"""
    config = load_config()
    return render_template("index.html", config=config, is_running=is_running)

@app.route("/api/config", methods=["GET"])
def get_config():
    """設定を取得（Webhook URLはマスク）"""
    config = load_config()
    # Webhook URLは設定済みかどうかだけ返す
    webhook_url = config.get("discord_webhook_url", "")
    config_response = {
        "check_interval": config.get("check_interval", 300),
        "webhook_configured": bool(webhook_url and len(webhook_url) > 10)
    }
    return jsonify(config_response)

@app.route("/api/config", methods=["POST"])
def update_config():
    """設定を更新"""
    data = request.json
    config = load_config()
    
    if "discord_webhook_url" in data:
        config["discord_webhook_url"] = data["discord_webhook_url"]
    if "check_interval" in data:
        config["check_interval"] = int(data["check_interval"])
    
    save_config(config)
    return jsonify({"status": "success"})

@app.route("/api/feeds", methods=["GET"])
def get_feeds():
    """フィード一覧を取得"""
    config = load_config()
    return jsonify(config.get("feeds", []))

@app.route("/api/feeds", methods=["POST"])
def add_feed():
    """フィードを追加"""
    data = request.json
    config = load_config()
    
    feed_url = data.get("url", "")
    feed_name = data.get("name", "")
    
    new_feed = {
        "id": str(int(time.time() * 1000)),
        "name": feed_name,
        "url": feed_url,
        "enabled": True
    }
    
    if "feeds" not in config:
        config["feeds"] = []
    
    config["feeds"].append(new_feed)
    save_config(config)
    
    # 新規追加時：最新記事1件だけ通知し、残りは既読にする
    try:
        feed = feedparser.parse(feed_url)
        if feed.entries and not feed.bozo:
            seen_guids = load_seen_guids()
            all_guids = [entry.get("id", entry.get("link", "")) for entry in feed.entries]
            
            # 最新記事（最初の1件）以外を既読にする
            seen_guids[new_feed["id"]] = all_guids[1:] if len(all_guids) > 1 else []
            save_seen_guids(seen_guids)
            
            # 最新記事を通知
            webhook_url = config.get("discord_webhook_url", "")
            if webhook_url and all_guids:
                latest = feed.entries[0]
                send_discord_message(
                    webhook_url,
                    latest.get("title", "タイトルなし"),
                    latest.get("link", ""),
                    feed_name
                )
                # 通知した記事も既読に追加
                seen_guids[new_feed["id"]].append(all_guids[0])
                save_seen_guids(seen_guids)
    except Exception as e:
        print(f"初期通知エラー: {e}")
    
    return jsonify({"status": "success", "feed": new_feed})

@app.route("/api/feeds/<feed_id>", methods=["DELETE"])
def delete_feed(feed_id):
    """フィードを削除"""
    config = load_config()
    config["feeds"] = [f for f in config.get("feeds", []) if f.get("id") != feed_id]
    save_config(config)
    return jsonify({"status": "success"})

@app.route("/api/feeds/<feed_id>", methods=["PUT"])
def update_feed(feed_id):
    """フィードを更新（名前変更など）"""
    data = request.json
    config = load_config()
    
    for feed in config.get("feeds", []):
        if feed.get("id") == feed_id:
            if "name" in data:
                feed["name"] = data["name"]
            break
    
    save_config(config)
    return jsonify({"status": "success"})

@app.route("/api/feeds/<feed_id>/toggle", methods=["POST"])
def toggle_feed(feed_id):
    """フィードの有効/無効を切り替え"""
    config = load_config()
    for feed in config.get("feeds", []):
        if feed.get("id") == feed_id:
            feed["enabled"] = not feed.get("enabled", True)
            break
    save_config(config)
    return jsonify({"status": "success"})

@app.route("/api/check", methods=["POST"])
def manual_check():
    """手動でフィードをチェック"""
    try:
        check_all_feeds()
        return jsonify({"status": "success", "message": "チェック完了"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/detect-feed", methods=["POST"])
def detect_feed():
    """URLからRSSフィードを自動検出"""
    data = request.json
    url = data.get("url", "").strip()
    
    if not url:
        return jsonify({"status": "error", "message": "URLを入力してください"}), 400
    
    # http/https がなければ追加
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    try:
        feeds = detect_rss_feeds(url)
        site_info = get_site_info(url)
        
        if not feeds:
            return jsonify({
                "status": "not_found",
                "message": "RSSフィードが見つかりませんでした",
                "site_info": site_info
            })
        
        return jsonify({
            "status": "success",
            "feeds": feeds,
            "site_info": site_info
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/monitor/start", methods=["POST"])
def start_monitor():
    """監視を開始"""
    global monitor_thread, is_running
    
    if is_running:
        return jsonify({"status": "already_running"})
    
    is_running = True
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    
    return jsonify({"status": "started"})

@app.route("/api/monitor/stop", methods=["POST"])
def stop_monitor():
    """監視を停止"""
    global is_running
    is_running = False
    return jsonify({"status": "stopped"})

@app.route("/api/monitor/status", methods=["GET"])
def monitor_status():
    """監視状態を取得"""
    return jsonify({"is_running": is_running})

@app.route("/api/test-webhook", methods=["POST"])
def test_webhook():
    """Webhookをテスト"""
    config = load_config()
    webhook_url = config.get("discord_webhook_url", "")
    
    if not webhook_url:
        return jsonify({"status": "error", "message": "Webhook URLが設定されていません"}), 400
    
    success = send_discord_message(
        webhook_url,
        "テスト通知",
        "https://example.com",
        "RSS監視システム"
    )
    
    if success:
        return jsonify({"status": "success", "message": "テスト通知を送信しました"})
    else:
        return jsonify({"status": "error", "message": "通知の送信に失敗しました"}), 500

if __name__ == "__main__":
    # テンプレートフォルダがなければ作成
    templates_dir = os.path.join(BASE_DIR, "templates")
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
    
    print("RSS通知システム起動中...")
    print("http://0.0.0.0:5000 でアクセスしてください")
    app.run(host="0.0.0.0", port=5000, debug=False)
