from datetime import date
import os
from pyjpboatrace import PyJPBoatrace
from pyjpboatrace.drivers import create_httpget_driver
import requests

# GitHub SecretsからDiscordのWebhook URLを取得
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def send_discord_notification(message):
  if not WEBHOOK_URL:
    print("Discord Webhook URLが設定されていません。")
    return

  payload = {"content": message}
  response = requests.post(WEBHOOK_URL, json=payload)
  if response.status_code == 204:
    print("Discord通知に成功しました！")
  else:
    print(f"Discord通知失敗: {response.status_code} - {response.text}")


def main():
  today = date.today()
  stadium_id = 4  # 平和島競艇場
  race_no = 1

  print(
      f"--- pyjpboatrace データ取得開始: 平和島 第{race_no}R ({today}) ---"
  )

  try:
    # GitHub Actions向けの軽量HTTPドライバを使用
    driver = create_httpget_driver()
    bot = PyJPBoatrace(driver=driver)

    # レース情報の取得
    race_info = bot.get_race_info(today, stadium_id, race_no)
    print(f"取得データ: {race_info}")

    # シンプルな通知メッセージを作成
    msg = (
        f"【ボートレース自動通知】\n"
        f"本日 ({today}) 平和島 第{race_no}R のデータを正常に取得しました！"
    )
    send_discord_notification(msg)

  except Exception as e:
    error_msg = f"【エラー】pyjpboatrace データ取得失敗: {e}"
    print(error_msg)
    send_discord_notification(error_msg)


if __name__ == "__main__":
  main()
