import sys
import os
import requests
import pandas as pd
from datetime import datetime

# ログを溜め込まずにリアルタイムで画面に出力させる設定
try:
    sys.stdout.reconfigure(line_buffering=True)
except AttributeError:
    pass

def main():
    print("🚀 ボートレースデータパイプラインを開始します...", flush=True)

    # 1. データの保存先ディレクトリの確認・作成
    os.makedirs("data", exist_ok=True)
    
    # 2. 日付の取得とデータ処理
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"📅 本日の日付: {today_str}", flush=True)

    # データ処理（必要に応じてご自身のスクレイピング処理に書き換えてください）
    df = pd.DataFrame({
        "date": [today_str],
        "status": ["completed"]
    })
    
    file_path = f"data/boat_race_{today_str}.csv"
    df.to_csv(file_path, index=False)
    print(f"💾 データを保存しました: {file_path}", flush=True)

    # 3. Discord通知の送信処理
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    
    if webhook_url:
        print(f"DEBUG: DISCORD_WEBHOOK_URL is set (Length: {len(webhook_url)})", flush=True)
    else:
        print("❌ DEBUG: DISCORD_WEBHOOK_URL is NOT SET", flush=True)

    if webhook_url:
        payload = {
            "content": f"🚤 ボートレースのデータ更新とGitHubへの保存が完了しました！ ({today_str})"
        }
        try:
            response = requests.post(webhook_url, json=payload)
            print(f"DEBUG: Discord API Response Status: {response.status_code}", flush=True)
            print(f"DEBUG: Discord API Response Body: {response.text}", flush=True)
            
            if response.status_code in [200, 204]:
                print("📢 Discord通知を送信しました！", flush=True)
            else:
                print(f"⚠️ Discord通知の送信に失敗しました (ステータス: {response.status_code})", flush=True)
        except Exception as e:
            print(f"❌ Discord通知送信中に例外が発生しました: {e}", flush=True)
    else:
        print("❌ エラー: DISCORD_WEBHOOK_URL 環境変数が設定されていません。", flush=True)

if __name__ == "__main__":
    main()
