from datetime import datetime
import os
from bs4 import BeautifulSoup
import pandas as pd
import requests

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def scrape_shimonoseki_racelist():
  try:
    today_ymd = datetime.now().strftime("%Y%m%d")
    today_str = datetime.now().strftime("%Y-%m-%d")
    jcd = "19"
    url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno=1&jcd={jcd}&hd={today_ymd}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    data_list = []
    racer_rows = soup.select(".table1 tbody tr")

    if racer_rows:
      for row in racer_rows:
        cols = row.find_all("td")
        if len(cols) >= 3:
          try:
            boat_num = cols[0].get_text(strip=True)
            racer_info = cols[2].get_text(strip=True)
            data_list.append({
                "日付": today_str,
                "場": "下関",
                "レース": "第1R",
                "枠番": boat_num,
                "選手": racer_info,
            })
          except Exception:
            continue

    if not data_list:
      data_list.append({
          "日付": today_str,
          "場": "下関",
          "レース": "第1R",
          "枠番": "-",
          "選手": "本日の出走データなし",
      })

    df = pd.DataFrame(data_list)
    return df

  except Exception as e:
    print(f"スクレイピングエラー: {e}")
    return None


def save_data(df):
  os.makedirs("data", exist_ok=True)
  today_str = datetime.now().strftime("%Y%m%d")
  file_path = f"data/shimonoseki_racelist_{today_str}.csv"

  if os.path.exists(file_path):
    df.to_csv(file_path, mode="a", header=False, index=False, encoding="utf-8-sig")
  else:
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
  return file_path


def send_discord_notification(message, df_preview=None):
  """Discordへ通知を送る関数（詳細なエラーログ出力付き）"""
  if not DISCORD_WEBHOOK_URL:
    print("⚠️ 警告: DISCORD_WEBHOOK_URL が空です。")
    return

  embed = {
      "title": "🚤 【下関ボートレース出走表 取得速報】",
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

  try:
    response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    print(f"Discord通知レスポンスコード: {response.status_code}")
    if response.status_code not in [200, 204]:
      print(f"⚠️ Discord通知エラー詳細: {response.text}")
  except Exception as e:
    print(f"⚠️ Discord通知の送信中に例外が発生しました: {e}")


if __name__ == "__main__":
  df = scrape_shimonoseki_racelist()
  if df is not None and not df.empty:
    file_path = save_data(df)
    msg = f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n保存先: `{file_path}`"
    send_discord_notification(msg, df)
    print("処理が正常に完了しました。")
  else:
    print("有効なデータが取得できませんでした。")
