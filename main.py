from datetime import datetime
import os
from bs4 import BeautifulSoup
import pandas as pd
import requests

# Discord Webhook URL (GitHub Secretsから自動取得)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def scrape_boat_race_data():
  """ボートレースのデータを取得する関数

  （現在は安定動作の確認と今後の拡張をしやすくするためのベース構成にしています）
  """
  try:
    # 例として公式トップページや対象レースのURLを指定
    url = "https://www.boatrace.jp/owpc/pc/index.html"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }

    # サイトへのアクセス
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # --- 実際のスクレイピング処理エリア ---
    # ここにBeautifulSoupを使ったタグ解析処理を組み込んでいきます。
    # 例として、取得日時や実際のスクレイピング構築に向けた土台データを生成します。
    today_str = datetime.now().strftime("%Y-%m-%d")

    data = [{
        "日付": today_str,
        "レース": "第1R",
        "場": "福岡",
        "選手": "選手A",
        "オッズ": 2.5,
    }, {
        "日付": today_str,
        "レース": "第1R",
        "場": "福岡",
        "選手": "選手B",
        "オッズ": 4.1,
    }]

    df = pd.DataFrame(data)
    return df

  except Exception as e:
    print(f"スクレイピングエラーが発生しました: {e}")
    return None


def save_data(df):
  """取得したデータをCSVとして保存する関数"""
  os.makedirs("data", exist_ok=True)
  today_str = datetime.now().strftime("%Y%m%d")
  file_path = f"data/boat_race_{today_str}.csv"

  # CSVファイルに保存（既にファイルがある場合は追記）
  if os.path.exists(file_path):
    df.to_csv(file_path, mode="a", header=False, index=False, encoding="utf-8-sig")
  else:
    df.to_csv(file_path, index=False, encoding="utf-8-sig")

  return file_path


def send_discord_notification(message, df_preview=None):
  """Discordへ通知を送る関数"""
  if not DISCORD_WEBHOOK_URL:
    return

  embed = {
      "title": "🚤 【ボートレース自動データ取得速報】",
      "description": message,
      "color": 3447003,
  }

  if df_preview is not None:
    preview_text = "```\n" + df_preview.to_string(index=False) + "\n```"
    embed["fields"] = [{
        "name": "取得データプレビュー:",
        "value": preview_text,
        "inline": False,
    }]

  payload = {"embeds": [embed]}
  requests.post(DISCORD_WEBHOOK_URL, json=payload)


if __name__ == "__main__":
  print("データ取得プロセスを開始します...")
  df = scrape_boat_race_data()

  if df is not None and not df.empty:
    file_path = save_data(df)
    msg = f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n保存先: `{file_path}`"
    send_discord_notification(msg, df)
    print("処理が正常に完了しました。")
  else:
    print("有効なデータが取得できませんでした。")
