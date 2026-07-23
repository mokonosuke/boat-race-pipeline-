from datetime import datetime
import os
from bs4 import BeautifulSoup
import pandas as pd
import requests

# GitHub SecretsからDiscordのWebhook URLを取得します
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def scrape_boat_race():
  print("ボートレースデータの取得処理を開始します...")

  # --- ここに実際のスクレイピング処理を記述します ---
  # 現在はそのまま動くサンプルデータ（表形式）を設定しています
  data = [
      {"レース": "第1R", "場": "平和島", "選手": "選手A", "オッズ": 2.5},
      {"レース": "第1R", "場": "平和島", "選手": "選手B", "オッズ": 4.1},
      {"レース": "第2R", "場": "多摩川", "選手": "選手C", "オッズ": 1.8},
  ]

  df = pd.DataFrame(data)
  return df


def save_data(df):
  # dataフォルダがない場合は自動で作成します
  os.makedirs("data", exist_ok=True)
  today = datetime.now().strftime("%Y%m%d")
  file_path = f"data/boat_race_{today}.csv"

  # CSVファイルとして保存（文字化け防止のutf-8-sig）
  df.to_csv(file_path, index=False, encoding="utf-8-sig")
  print(f"データを保存しました: {file_path}")
  return file_path


def send_discord_notification(df):
  if not DISCORD_WEBHOOK_URL:
    print("エラー: Discord Webhook URLが設定されていません。")
    return

  # Discordに送るメッセージの作成
  content = "🚤 **【ボートレース自動データ取得速報】**\n"
  content += f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
  content += "取得データプレビュー:\n```text\n"
  content += df.to_string(index=False)
  content += "\n```"

  payload = {"content": content}

  response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
  if response.status_code == 204:
    print("Discordへの通知に成功しました！")
  else:
    print(f"Discord通知に失敗しました（ステータスコード: {response.status_code}）")


if __name__ == "__main__":
  df = scrape_boat_race()
  save_data(df)
  send_discord_notification(df)
