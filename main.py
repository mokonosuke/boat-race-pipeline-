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
  stadium_id = 4  # 平和島競艇場
  race_no = 1

  print(f"--- データ拡張取得開始: 平和島 第{race_no}R ({today}) ---")

  try:
    driver = create_httpget_driver()
    bot = PyJPBoatrace(driver=driver)

    # 1. レース情報（出走表など）の取得
    race_info = bot.get_race_info(today, stadium_id, race_no)
    
    # 2. 3連単オッズの取得
    trifecta_odds = bot.get_odds_trifecta(today, stadium_id, race_no)

    print(f"レース情報取得成功: {type(race_info)}")
    print(f"3連単オッズ取得成功: {type(trifecta_odds)}")

    # 3. 成功時の通知
    msg = (
        f"【ボートレース拡張テスト成功】\n"
        f"本日 ({today}) 平和島 第{race_no}R のデータを取得しました！\n"
        f"- レース情報: {type(race_info)}\n"
        f"- 3連単オッズ: {type(trifecta_odds)}"
    )
    send_discord_notification(msg)

  except Exception as e:
    error_msg = f"【エラー】データ拡張取得失敗: {e}"
    print(error_msg)
    send_discord_notification(error_msg)


if __name__ == "__main__":
  main()
