import os
import requests
import pandas as pd
from datetime import datetime

def main():
    print("🚀 ボートレースデータパイプラインを開始します...")

    # 1. データの保存先ディレクトリの確認・作成
    os.makedirs("data", exist_ok=True)
    
    # 2. 日付の取得とデータ処理
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"📅 本日の日付: {today_str}")

    # ここにご自身のスクレイピング処理を記述できます
    df = pd.DataFrame({
        "date": [today_str],
        "status": ["completed"]
    })
    
    file_path = f"data/boat_race_{today_str}.csv"
    df.to_csv(file_path, index=False)
    print(f"💾 データを保存しました: {file_path}")

    # 3. Discord通知の送信処理（デバッグログ付き）
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    
    # ログにURLがセットされているか（文字数）を出力（セキュリティのため中身は隠します）
    if webhook_url:
        print(f"DEBUG: DISCORD_WEBHOOK_URL is set (Length: {len(webhook_url)})")
    else:
        print("❌ DEBUG: DISCORD_WEBHOOK_URL is NOT SET")

    if webhook_url:
        payload = {
            "content": f"🚤 ボートレースのデータ更新とGitHubへの保存が完了しました！ ({today_str})"
        }
        try:
            response = requests.post(webhook_url, json=payload)
            print(f"DEBUG: Discord API Response Status: {response.status_code}")
            print(f"DEBUG: Discord API Response Body: {response.text}")
            
            if response.status_code in [200, 204]:
                print("📢 Discord通知を送信しました！")
            else:
                print(f"⚠️ Discord通知の送信に失敗しました (ステータス: {response.status_code})")
        except Exception as e:
            print(f"❌ Discord通知送信中に例外が発生しました: {e}")
    else:
        print("❌ エラー: DISCORD_WEBHOOK_URL 環境変数が設定されていません。")

if __name__ == "__main__":
    main()
