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

  try:
    driver = create_httpget_driver()
    bot = PyJPBoatrace(driver=driver)

    # データの取得
    race_info = bot.get_race_info(today, stadium_id, race_no)
    trifecta_odds = bot.get_odds_trifecta(today, stadium_id, race_no)

    # 辞書のキー（項目名）を取り出す
    race_keys = (
        list(race_info.keys()) if isinstance(race_info, dict) else "Not dict"
    )
    odds_keys = (
        list(trifecta_odds.keys())
        if isinstance(trifecta_odds, dict)
        else "Not dict"
    )

    msg = (
        f"【データ構造（キー）の確認】\n"
        f"🔹 race_info のキー:\n{race_keys}\n\n"
        f"🔹 trifecta_odds のキー:\n{odds_keys}"
    )
    print(msg)
    send_discord_notification(msg)

  except Exception as e:
    error_msg = f"【エラー】データ構造確認失敗: {e}"
    print(error_msg)
    send_discord_notification(error_msg)


if __name__ == "__main__":
  main()
