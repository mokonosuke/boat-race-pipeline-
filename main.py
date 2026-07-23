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
  jcd = "19"  # 下関
  data_list = []

  # 第1Rから第12Rまでループ処理
  for rno in range(1, 13):
    url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={rno}&jcd={jcd}&hd={today_ymd}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    response = None
    for attempt in range(3):
      try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        break
      except requests.exceptions.RequestException as e:
        if attempt < 2:
          time.sleep(2)
        else:
          print(f"⚠️ 下関 第{rno}R の取得に失敗しました。")

    if response is None:
      continue

    try:
      soup = BeautifulSoup(response.text, "html.parser")
      racer_rows = soup.select(".table1 tbody tr")
      current_boat_num = ""

      if racer_rows:
        for row in racer_rows:
          cols = row.find_all("td")
          if len(cols) > 0:
            first_col = cols[0].get_text(strip=True)
            if first_col in ["1", "2", "3", "4", "5", "6"]:
              current_boat_num = first_col

          row_text = row.get_text(separator=" ", strip=True)

          match = re.search(
              r"(\d{4}\s*/\s*[A-Z0-9]+\s*[^0-9]+?\d+歳\s*/\s*\d+(?:\.\d+)?kg)",
              row_text,
          )
          if match and current_boat_num in ["1", "2", "3", "4", "5", "6"]:
            racer_info = re.sub(r"\s+", " ", match.group(1))
            numbers = re.findall(r"\d+\.\d+", row_text)

            motor_2rate = "-"
            motor_match = re.search(r"モーター\s*[:\s]*([\d\.]+%?)", row_text)
            if motor_match:
              motor_2rate = motor_match.group(1)
            elif len(numbers) > 0:
              motor_2rate = numbers[0]

            local_win_rate = "-"
            local_2rate = "-"
            if len(numbers) >= 4:
              local_win_rate = numbers[-2]
              local_2rate = numbers[-1]
            elif len(numbers) >= 2:
              local_win_rate = numbers[-1]

            # 重複防止（同レース・同枠番の二重登録を防ぐ）
            if not any(
                d["レース"] == f"第{rno}R"
                and d["枠番"] == f"{current_boat_num}号艇"
                for d in data_list
            ):
              data_list.append({
                  "日付": today_str,
                  "場": "下関",
                  "レース": f"第{rno}R",
                  "枠番": f"{current_boat_num}号艇",
                  "選手情報": racer_info,
                  "当地勝率": local_win_rate,
                  "当地2連対率": local_2rate,
                  "当地3連対率": "-",
                  "モーター2連対率": motor_2rate,
              })
    except Exception as e:
      print(f"第{rno}Rの解析エラー: {e}")

    # サーバーに負荷をかけないよう少しウェイトを入れる
    time.sleep(1)

  if not data_list:
    data_list.append({
        "日付": today_str,
        "場": "下関",
        "レース": "第1R",
        "枠番": "-",
        "選手情報": "本日の出走データなし",
        "当地勝率": "-",
        "当地2連対率": "-",
        "当地3連対率": "-",
        "モーター2連対率": "-",
    })

  return pd.DataFrame(data_list)


def save_data(df):
  os.makedirs("data", exist_ok=True)
  today_str = datetime.now().strftime("%Y%m%d")
  file_path = f"data/shimonoseki_racelist_{today_str}.csv"

  if os.path.exists(file_path):
    df.to_csv(file_path, mode="a", header=False, index=False, encoding="utf-8-sig")
  else:
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
  return file_path


def send_discord_notification(message, total_rows=0):
  if not DISCORD_WEBHOOK_URL:
    print("⚠️ 警告: DISCORD_WEBHOOK_URL が空です。")
    return

  text = (
      f"🚤 **【下関ボートレース 全12R出走表 取得速報】**\n{message}\n"
      f"• 取得レコード数: **{total_rows}件** (第1R〜第12R)"
  )

  payload = {"content": text}

  try:
    response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    print(f"Discord通知レスポンスコード: {response.status_code}")
  except Exception as e:
    print(f"⚠️ Discord通知の送信中に例外が発生しました: {e}")


if __name__ == "__main__":
  df = scrape_shimonoseki_racelist()
  if df is not None and not df.empty:
    file_path = save_data(df)
    msg = f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n保存先: `{file_path}`"
    send_discord_notification(msg, len(df))
    print("全レースの処理が正常に完了しました。")
  else:
    print("有効なデータが取得できませんでした。")
