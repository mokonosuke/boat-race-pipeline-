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
