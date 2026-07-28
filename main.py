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

  print(f"--- 予測・うまみ判定テスト開始: 平和島 第{race_no}R ({today}) ---")

  try:
    driver = create_httpget_driver()
    bot = PyJPBoatrace(driver=driver)

    # 1. レース情報とオッズの取得
    race_info = bot.get_race_info(today, stadium_id, race_no)
    trifecta_odds = bot.get_odds_trifecta(today, stadium_id, race_no)

    # 1号艇の情報を取得
    boat1 = race_info.get("boat1", {})
    p_name = boat1.get("name", "不明")
    p_global_win = boat1.get("global_win_pt", 0.0)

    # 2. 「うまみ」判定ロジックの例
    # 例: 3連単オッズが 10.0倍 以上 20.0倍未満 のものを「中穴・うまみ枠」として抽出
    target_odds = []
    if isinstance(trifecta_odds, dict):
      for combo, odds_val in trifecta_odds.items():
        # キーがレース情報等ではなく「1-2-3」のような組み合わせ形式のときのみ処理
        if "-" in combo and isinstance(odds_val, (int, float)):
          if 10.0 <= odds_val < 20.0:
            target_odds.append(f"{combo}: {odds_val}倍")

    # 3. 通知メッセージの作成
    target_str = (
        "\n".join(target_odds[:10])
        if target_odds
        else "条件に合うオッズはありませんでした"
    )

    msg = (
        f"【ボートレースうまみ判定テスト】\n"
        f"📍 平和島 第{race_no}R ({today})\n"
        f"🔹 1号艇: {p_name} (全国勝率: {p_global_win})\n\n"
        f"🎯 【10倍〜20倍の狙い目オッズ一覧】\n"
        f"{target_str}"
    )

    print(msg)
    send_discord_notification(msg)

  except Exception as e:
    error_msg = f"【エラー】判定処理失敗: {e}"
    print(error_msg)
    send_discord_notification(error_msg)


if __name__ == "__main__":
  main()
