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

  print(
      f"--- ボートレース自動アナライズ開始: 平和島 第{race_no}R ({today}) ---"
  )

  try:
    driver = create_httpget_driver()
    bot = PyJPBoatrace(driver=driver)

    # 1. レース情報とオッズの取得
    race_info = bot.get_race_info(today, stadium_id, race_no)
    trifecta_odds = bot.get_odds_trifecta(today, stadium_id, race_no)

    # 2. 全6艇の簡易出走メンバー作成
    boat_summaries = []
    for i in range(1, 7):
      b_data = race_info.get(f"boat{i}", {})
      name = b_data.get("name", "不明")
      cls = b_data.get("class", "--")
      g_win = b_data.get("global_win_pt", 0.0)
      motor = b_data.get("motor", "--")
      m_in2nd = b_data.get("motor_in2nd", 0.0)
      boat_summaries.append(
          f"{i}号艇: {name} ({cls}) | 勝率:{g_win} | モーター:{motor} ({m_in2nd}%)"
      )

    # 3. 「うまみ」判定ロジック（例：15倍〜35倍の中穴・高配当狙い）
    target_odds = []
    if isinstance(trifecta_odds, dict):
      for combo, odds_val in trifecta_odds.items():
        if "-" in combo and isinstance(odds_val, (int, float)):
          if 15.0 <= odds_val <= 35.0:
            target_odds.append(f"{combo}: {odds_val}倍")

    # 4. 通知メッセージの構築
    members_str = "\n".join(boat_summaries)
    target_str = (
        "\n".join(target_odds[:8])
        if target_odds
        else "該当するオッズはありませんでした"
    )

    msg = (
        f"【ボートレース自動分析レポート】\n"
        f"📍 平和島 第{race_no}R ({today})\n\n"
        f"📋 **【出走メンバー概要】**\n"
        f"{members_str}\n\n"
        f"🎯 **【推奨うまみオッズ (15倍〜35倍)】**\n"
        f"{target_str}"
    )

    print(msg)
    send_discord_notification(msg)

  except Exception as e:
    error_msg = f"【エラー】分析処理失敗: {e}"
    print(error_msg)
    send_discord_notification(error_msg)


if __name__ == "__main__":
  main()
