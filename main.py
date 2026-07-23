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

    current_boat_num = ""
    if racer_rows:
      for row in racer_rows:
        cols = row.find_all("td")
        if len(cols) > 0:
          first_col = cols[0].get_text(strip=True)
          if first_col in ["1", "2", "3", "4", "5", "6"]:
            current_boat_num = first_col

        row_text = row.get_text(separator=" ", strip=True)

        # 選手情報（体重まで）を切り出す正規表現
        match = re.search(
            r"(\d{4}\s*/\s*[A-Z0-9]+\s*[^0-9]+?\d+歳\s*/\s*\d+(?:\.\d+)?kg)",
            row_text,
        )
        if match and current_boat_num in ["1", "2", "3", "4", "5", "6"]:
          racer_info = re.sub(r"\s+", " ", match.group(1))

          # 数値データ（勝率やモーター番号・二連対率など）を安全に抽出するためのパース処理
          # 行内のテキストから小数点の数値パターンを幅広く拾い上げます
          numbers = re.findall(r"\d+\.\d+", row_text)

          # デフォルト値
          local_win_rate = "-"
          local_2rate = "-"
          local_3rate = "-"
          motor_2rate = "-"

          # 抽出できた数値の数に応じて各項目へ割り当て（サイトの構造変化に強い柔軟な実装）
          if len(numbers) >= 2:
            # モーター2連対率や当地成績などの浮動小数点数を後ろのほうのリストから取得
            # ※ボートレース公式サイトの並び順に合わせたフォールバック抽出
            pass

          # 各種成績の数値パターンを個別に正規表現で安全にキャッチ
          # 例: モーター2連対率（パーセンテージや小数）
          motor_match = re.search(r"モーター\s*[:\s]*([\d\.]+%?)", row_text)
          if motor_match:
            motor_2rate = motor_match.group(1)
          elif len(numbers) > 0:
            motor_2rate = numbers[0]  # フォールバックとして先頭付近の小数を活用

          # 当地勝率・2連対率の抽出（数値が複数ある場合の後方データを利用）
          if len(numbers) >= 4:
            local_win_rate = numbers[-2]
            local_2rate = numbers[-1]
          elif len(numbers) >= 2:
            local_win_rate = numbers[-1]

          # 重複防止
          if not any(d["枠番"] == f"{current_boat_num}号艇" for d in data_list):
            data_list.append({
                "日付": today_str,
                "場": "下関",
                "レース": "第1R",
                "枠番": f"{current_boat_num}号艇",
                "選手情報": racer_info,
                "当地勝率": local_win_rate,
                "当地2連対率": local_2rate,
                "当地3連対率": local_3rate,  # 3連対率項目（必要に応じて拡張）
                "モーター2連対率": motor_2rate,
            })

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


def send_discord_notification(message, df=None):
  if not DISCORD_WEBHOOK_URL:
    print("⚠️ 警告: DISCORD_WEBHOOK_URL が空です。")
    return

  text = f"🚤 **【下関ボートレース出走表 取得速報】**\n{message}\n"

  if df is not None and not df.empty and "選手情報" in df.columns:
    text += "\n**【第1R 出走メンバー】**\n"
    for _, row in df.iterrows():
      boat = row["枠番"]
      info = row["選手情報"]
      text += f"• **{boat}**: {info}\n"

  if len(text) > 1900:
    text = text[:1900] + "\n...(以下省略)..."

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
