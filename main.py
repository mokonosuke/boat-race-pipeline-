from datetime import date
import os
from pyjpboatrace import PyJPBoatrace
from pyjpboatrace.drivers import create_httpget_driver
import requests

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def send_discord_notification(message):
  if not WEBHOOK_URL:
    return
  payload = {"content": message}
  requests.post(WEBHOOK_URL, json=payload)


def main():
  today = date.today()
  stadium_id = 4  # 平和島競艇場
  race_no = 1

  print(
      f"--- データ拡張取得開始: 平和島 第{race_no}R ({today}) ---"
  )

  try:
    driver = create_httpget_driver()
    bot = PyJPBoatrace(driver=driver)

    # 1. 出走表（プログラム）情報の取得
    # ※pyjpboatraceの仕様に合わせてメソッドを調整します
    program = bot.get_program(today, stadium_id, race_no)
    
    # 2. オッズ情報の取得
    odds = bot.get_odds(today, stadium_id, race_no, n3t=True) # 3連単オッズなど

    print(f"出走表データ取得成功: {type(program)}")
    print(f"オッズデータ取得成功: {type(odds)}")

    # 3. 現段階での確認用通知メッセージ
    msg = (
        f"【ボートレース拡張テスト】\n"
        f"本日 ({today}) 平和島 第{race_no}R の出走表・オッズの取得に成功しました！\n"
        f"ここから独自の予測ロジックや「うまみ」判定を組み込んでいきます。"
    )
    send_discord_notification(msg)

  except Exception as e:
    error_msg = f"【エラー】データ拡張取得失敗: {e}"
    print(error_msg)
    send_discord_notification(error_msg)


if __name__ == "__main__":
  main()
