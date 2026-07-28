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

    race_info = bot.get_race_info(today, stadium_id, race_no)
    trifecta_odds = bot.get_odds_trifecta(today, stadium_id, race_no)

    # 1号艇のデータ構造と、代表的な3連単オッズ（例：1-2-3）の値を取得
    boat1_data = race_info.get("boat1", {})
    odds_123 = trifecta_odds.get("1-2-3", "N/A")

    msg = (
        f"【詳細データ・オッズの確認】\n"
        f"🔹 1号艇データのキー:\n{list(boat1_data.keys()) if isinstance(boat1_data, dict) else boat1_data}\n\n"
        f"🔹 1号艇データの中身:\n{boat1_data}\n\n"
        f"🔹 3連単 '1-2-3' のオッズ: {odds_123}"
    )
    print(msg)
    send_discord_notification(msg)

  except Exception as e:
    error_msg = f"【エラー】詳細確認失敗: {e}"
    print(error_msg)
    send_discord_notification(error_msg)


if __name__ == "__main__":
  main()
