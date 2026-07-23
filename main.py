from datetime import datetime
import os
import re
import time
from bs4 import BeautifulSoup
import pandas as pd
import requests

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

VENUE_DICT = {
    "01": "桐生",
    "02": "戸田",
    "03": "江戸川",
    "04": "平和島",
    "05": "多摩川",
    "06": "浜名湖",
    "07": "蒲郡",
    "08": "常滑",
    "09": "津",
    "10": "三国",
    "11": "琵琶湖",
    "12": "住之江",
    "13": "尼崎",
    "14": "鳴門",
    "15": "丸亀",
    "16": "児島",
    "17": "宮島",
    "18": "徳山",
    "19": "下関",
    "20": "若松",
    "21": "芦屋",
    "22": "福岡",
    "23": "唐津",
    "24": "大村",
}


def scrape_race_data_with_results():
  today_ymd = datetime.now().strftime("%Y%m%d")
  today_str = datetime.now().strftime("%Y-%m-%d")
  data_list = []

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  active_venues_count = 0

  for jcd, venue_name in VENUE_DICT.items():
    # 開催チェック (第1Rの出走表が存在するか)
    url_r1 = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno=1&jcd={jcd}&hd={today_ymd}"
    try:
      res_r1 = requests.get(url_r1, headers=headers, timeout=10)
      if res_r1.status_code != 200:
        continue
      soup_r1 = BeautifulSoup(res_r1.text, "html.parser")
      if not soup_r1.select(".table1 tbody tr"):
        continue
    except Exception:
      continue

    active_venues_count += 1
    print(f"📍 開催検知・データ取得中: {venue_name}")

    # 第1R〜第12Rまでループ
    for rno in range(1, 13):
      # 1. 出走表（特徴量）の取得
      url_list = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={rno}&jcd={jcd}&hd={today_ymd}"
      # 2. レース結果（正解ラベル）の取得URL
      url_res = f"https://www.boatrace.jp/owpc/pc/race/result?rno={rno}&jcd={jcd}&hd={today_ymd}"

      # 出走表の取得
      resp_list = None
      for _ in range(3):
        try:
          resp_list = requests.get(url_list, headers=headers, timeout=15)
          resp_list.raise_for_status()
          break
        except:
          time.sleep(1)

      if resp_list is None:
        continue

      # 結果ページの取得（レースが終了していれば結果が取れる）
      rank_dict = {}  # 艇番ごとの着順を格納 (例: {"1": "1", "3": "2", ...})
      try:
        resp_res = requests.get(url_res, headers=headers, timeout=15)
        if resp_res.status_code == 200:
          soup_res = BeautifulSoup(resp_res.text, "html.parser")
          # 結果ページの着順テーブルを解析
          result_rows = soup_res.select(
              ".table1.is-paddingsetting-none tbody tr, .table1 tbody tr"
          )
          for row in result_rows:
            row_text = row.get_text(separator=" ", strip=True)
            # 結果テーブルから着順と艇番のパターンを抽出する簡易処理
            cols = row.find_all("td")
            if len(cols) >= 2:
              rank_candidate = cols[0].get_text(strip=True)
              # 着順が数字（1〜6）の場合
              if rank_candidate in ["1", "2", "3", "4", "5", "6"]:
                # 艇番を探す（通常、着順行の中に2文字程度の数字や艇番が含まれる）
                boat_match = re.search(r"\b([1-6])\b", cols[1].get_text())
                if boat_match:
                  boat_num = boat_match.group(1)
                  rank_dict[boat_num] = rank_candidate
      except Exception:
        pass  -  # 結果がまだ出ていないレースの場合はスルー

      # 出走表の解析と結果の紐付け
      try:
        soup = BeautifulSoup(resp_list.text, "html.parser")
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

              # この艇の着順（未確定の場合は "-"）
              finish_order = rank_dict.get(current_boat_num, "-")

              # 重複防止しつつ追加
              if not any(
                  d["場"] == venue_name
                  and d["レース"] == f"第{rno}R"
                  and d["枠番"] == f"{current_boat_num}号艇"
                  for d in data_list
              ):
                data_list.append({
                    "日付": today_str,
                    "場": venue_name,
                    "レース": f"第{rno}R",
                    "枠番": f"{current_boat_num}号艇",
                    "選手情報": racer_info,
                    "当地勝率": local_win_rate,
                    "当地2連対率": local_2rate,
                    "モーター2連対率": motor_2rate,
                    "着順": finish_order,  # ★ここに正解ラベルが格納されます！
                })
      except Exception as e:
        print(f"{venue_name} 第{rno}Rの解析エラー: {e}")

      time.sleep(0.3)

  if not data_list:
    data_list.append({
        "日付": today_str,
        "場": "-",
        "レース": "-",
        "枠番": "-",
        "選手情報": "データなし",
        "当地勝率": "-",
        "当地2連対率": "-",
        "モーター2連対率": "-",
        "着順": "-",
    })

  print(f"本日開催の全会場数: {active_venues_count}場")
  return pd.DataFrame(data_list)


def save_data(df):
  os.makedirs("data", exist_ok=True)
  today_str = datetime.now().strftime("%Y%m%d")
  file_path = f"data/all_racedata_with_result_{today_str}.csv"

  if os.path.exists(file_path):
    df.to_csv(file_path, mode="a", header=False, index=False, encoding="utf-8-sig")
  else:
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
  return file_path


def send_discord_notification(message, total_rows=0):
  if not DISCORD_WEBHOOK_URL:
    return
  text = (
      f"🚤 **【ボートレース 学習用データ（結果付き）取得速報】**\n{message}\n"
      f"• 総レコード数: **{total_rows}件**"
  )
  try:
    requests.post(DISCORD_WEBHOOK_URL, json={"content": text}, timeout=10)
  except Exception:
    pass


if __name__ == "__main__":
  df = scrape_race_data_with_results()
  if df is not None and not df.empty:
    file_path = save_data(df)
    msg = f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n保存先: `{file_path}`"
    send_discord_notification(msg, len(df))
    print("すべての処理が正常に完了しました。")

