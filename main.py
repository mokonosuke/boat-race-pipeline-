from datetime import datetime
import os
import re
import time
from bs4 import BeautifulSoup
import pandas as pd
import requests

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def scrape_shimonoseki_racelist():
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

  response = None
  for attempt in range(3):
    try:
      print(f"URLにアクセス中 (試行 {attempt + 1}/3): {url}")
      response = requests.get(url, headers=headers, timeout=20)
      response.raise_for_status()
      break
    except requests.exceptions.RequestException as e:
      print(f"⚠️ 接続エラー (試行 {attempt + 1}/3): {e}")
      if attempt < 2:
        time.sleep(5)
      else:
        print("❌ すべてのリトライが失敗しました。")
        return None

  try:
    soup = BeautifulSoup(response.text, "html.parser")
    data_list = []
    racer_rows = soup.select(".table1 tbody tr")

    current_boat_num = "-"
    if racer_rows:
      for row in racer_rows:
        cols = row.find_all("td")
        row_text = row.get_text(separator=" ", strip=True)

        # 1列目に枠番（1〜6）がある場合は現在の艇番を更新する（セル結合対策）
        if len(cols) > 0:
          first_col_text = cols[0].get_text(strip=True)
          if first_col_text in ["1", "2", "3", "4", "5", "6"]:
            current_boat_num = first_col_text

        # 4桁の登録番号と「/」が含まれている行を正確な選手データとして抽出する
        if re.search(r"\d{4}", row_text) and "/" in row_text:
          racer_info = re.sub(r"\s+", " ", row_text)

          if current_boat_num in ["1", "2", "3", "4", "5", "6"]:
            # 同じ枠番が重複して追加されないようにチェック
            if not any(
                d["枠番"] == f"{current_boat_num}号艇" for d in data_list
            ):
              data_list.append({
                  "日付": today_str,
                  "場": "下関",
                  "レース": "第1R",
                  "枠番": f"{current_boat_num}号艇",
                  "選手情報": racer_info,
              })

    if not data_list:
      data_list.append({
          "日付": today_str,
          "場": "下関",
          "レース": "第1R",
          "枠番": "-",
          "選手情報": "本日の出走データなし",
      })

    df = pd.DataFrame(data_list)
    return df

  except Exception as e:
    print(f"スクレイピング解析エラー: {e}")
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
  if not DISCORD_WEBHOOK_URL:
    print("⚠️ 警告: DISCORD_WEBHOOK_URL が空です。")
    return

  text = f"🚤 **【下関ボートレース出走表 取得速報】**\n{message}"

  if df_preview is not None:
    preview_text = "```\n" + df_preview.to_string(index=False) + "\n```"
    if len(preview_text) > 1900:
      preview_text = preview_text[:1900] + "\n...(以下省略)...\n```"
    text += f"\n{preview_text}"

  payload = {"content": text}

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
