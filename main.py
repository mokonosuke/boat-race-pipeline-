from datetime import date
import os
from pyjpboatrace import PyJPBoatrace
from pyjpboatrace.drivers import create_httpget_driver
import requests

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def send_discord_notification(message):
  if not WEBHOOK_URL:
    return
  if len(message) > 1900:
    message = message[:1900] + "\n...(以下略)"
  payload = {"content": message}
  requests.post(WEBHOOK_URL, json=payload)


def main():
  today = date.today()
  stadium_id = 11  # びわこ競艇場 (SG開催地)

  print(f"--- びわこSG 全レース自動アナライズ開始 ({today}) ---")

  try:
    driver = create_httpget_driver()
    bot = PyJPBoatrace(driver=driver)

    report_lines = [f"🏆 **【びわこSG 全レースうまみ分析】** ({today})\n"]

    # 1Rから12Rまでを自動巡回
    for race_no in range(1, 13):
      try:
        trifecta_odds = bot.get_odds_trifecta(today, stadium_id, race_no)

        # 15倍〜35倍の中穴・うまみオッズを抽出
        target_odds = []
        if isinstance(trifecta_odds, dict):
          for combo, odds_val in trifecta_odds.items():
            if "-" in combo and isinstance(odds_val, (int, float)):
              if 15.0 <= odds_val <= 35.0:
                target_odds.append(f"{combo}({odds_val}倍)")

        # 上位3件ほどを抽出して一行にまとめる
        odds_summary = ", ".join(target_odds[:3]) if target_odds else "該当オッズなし"
        report_lines.append(f"・第{race_no}R: {odds_summary}")

      except Exception:
        report_lines.append(f"・第{race_no}R: データ取得前 (または非開催)")

    # 全レースの結果をまとめて送信
    full_message = "\n".join(report_lines)
    print(full_message)
    send_discord_notification(full_message)

  except Exception as e:
    error_msg = f"【エラー】びわこ全体分析失敗: {e}"
    print(error_msg)
    send_discord_notification(error_msg)


if __name__ == "__main__":
  main()
# 例：各艇の当地3連対率をチェックしてフィルタリング・スコアリングに活用するロジック

def evaluate_with_local_rate(race_info, trifecta_odds_list):
  # 例として、各艇の当地3連対率を保持する辞書（実際のプログラムデータから取得）
  # boat_local_3ren = {1: 45.2, 2: 32.1, 3: 50.4, 4: 28.0, 5: 35.5, 6: 20.0}

  recommended_bets = []

  for bet in trifecta_odds_list:
    combination = bet['combination']  # 例: '1-2-3'
    odds = bet['odds']

    # 1. オッズのうまみ判定（15.0〜35.0倍）
    if not (15.0 <= odds <= 35.0):
      continue

    # 2. 買い目を構成する艇番を分解（例: '1-2-3' -> 1, 2, 3）
    boat_nums = [int(x) for x in combination.split('-')]

    # 3. 当地3連対率に基づく条件判定
    # 例：買い目に含まれる選手の「当地3連対率の平均」が一定以上、
    # または「軸となる選手（1着 or 2着）の当地3連対率が40%以上」などの条件を設定
    
    # 簡易的な例として、絡む選手全員の当地3連対率の平均を計算
    avg_local_3ren = sum(boat_local_3ren[b] for b in boat_nums) / 3

    # 例：平均当地3連対率が 38.0% 以上のレース・買い目のみ採用する
    if avg_local_3ren >= 38.0:
      recommended_bets.append({
          'combination': combination,
          'odds': odds,
          'avg_local_3ren': avg_local_3ren
      })

  return recommended_bets
