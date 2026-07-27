from datetime import date
import os
from pyjpboatrace import PyJPBoatrace
from pyjpboatrace.drivers import create_httpget_driver
import requests

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def send_discord_notification(message):
  if not WEBHOOK_URL:
    return
  # Discordの文字数制限（2000文字）対策に分割または切り詰め
  if len(message) > 1900:
    message = message[:1900] + "\n...(以下略)"
  payload = {"content": message}
  requests.post(WEBHOOK_URL, json=payload)


def main():
  print("--- pyjpboatrace 構造確認開始 ---")

  try:
    driver = create_httpget_driver()
    bot = PyJPBoatrace(driver=driver)

    # botオブジェクトが持つメソッドや属性の一覧を取得
    methods = [m for m in dir(bot) if not m.startswith("_")]
    methods_str = ", ".join(methods)

    msg = f"【pyjpboatrace メソッド一覧】\n{methods_str}"
    print(msg)
    send_discord_notification(msg)

  except Exception as e:
    error_msg = f"【エラー】構造確認失敗: {e}"
    print(error_msg)
    send_discord_notification(error_msg)


if __name__ == "__main__":
  main()
