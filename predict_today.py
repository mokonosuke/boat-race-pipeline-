import os
import requests
import pandas as pd
import lightgbm as lgb

# --- Discord通知関数 ---
def send_discord_notification(message):
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("⚠️ DISCORD_WEBHOOK_URL が設定されていません")
        return
    
    payload = {"content": message}
    try:
        response = requests.post(webhook_url, json=payload)
        if response.status_code in [200, 204]:
            print("💬 Discord通知を送信しました")
        else:
            print(f"⚠️ Discord通知の送信に失敗しました: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"⚠️ Discord通知でエラーが発生しました: {e}")

# --- 天気・風向の数値化関数 ---
def encode_weather(weather_str):
    weather_map = {'晴': 1, '曇': 2, '雨': 3, '雪': 4}
    return weather_map.get(str(weather_str).strip(), 0)

def encode_wind_direction(wind_str):
    direction_map = {
        '北': 1, '北北東': 2, '北東': 3, '東北東': 4,
        '東': 5, '東南東': 6, '南東': 7, '南南東': 8,
        '南': 9, '南南西': 10, '南西': 11, '西南西': 12,
        '西': 13, '西北西': 14, '北西': 15, '北北西': 16
    }
    return direction_map.get(str(wind_str).strip(), 0)

# --- 共通の特徴量リスト ---
FEATURES = [
    'local_3ren',
    'st',
    'course',
    'motor',
    'boat',
    'racer_rank',
    'air_temp',
    'water_temp',
    'wind_speed',
    'wave_height',
    'weather',
    'wind_direction',
]

# --- 会場名からコードへの変換マップ ---
STADIUM_MAP = {
    '桐生': '01', '戸田': '02', '江戸川': '03', '平和島': '04', '多摩川': '05',
    '浜名湖': '06', '蒲郡': '07', '常滑': '08', '津': '09', '三国': '10',
    'びわこ': '11', '琵琶湖': '11', '住之江': '12', '尼崎': '13', '鳴門': '14',
    '丸亀': '15', '児島': '16', '宮島': '17', '徳山': '18', '下関': '19',
    '若松': '20', '芦屋': '21', '福岡': '22', '唐津': '23', '大村': '24'
}

def predict_main():
    # GitHub Actions の環境変数から手動入力値を取得
    target_stadium = os.environ.get('INPUT_STADIUM', '').strip()
    target_race_no = os.environ.get('INPUT_RACE_NO', '').strip()

    # 会場名が入力された場合にコードへ変換（直接コードが入力された場合もそのまま対応）
    if target_stadium in STADIUM_MAP:
        target_stadium = STADIUM_MAP[target_stadium]

    # 学習済みモデルの読み込み（ファイルが存在する場合のみ）
    model_path = 'model.txt'
    model = None
    if os.path.exists(model_path):
        model = lgb.Booster(model_file=model_path)
    else:
        print(f"⚠️ 警告: モデルファイル '{model_path}' が見つかりません。")

    if target_stadium and target_race_no:
        start_msg = f"=== 【手動トリガー】 会場コード:{target_stadium} 第{target_race_no}レースの直前予測を開始 ==="
        print(start_msg)
        send_discord_notification(start_msg)
        
        # --- ここに実際の推論処理を記述 ---
        if model is not None:
            # TODO: 該当レースの直前データを取得して DataFrame(X_test) を作成する処理
            # 例: X_test = get_race_data(target_stadium, target_race_no)[FEATURES]
            # preds = model.predict(X_test)
            pass
        
        # 予測結果のサンプル作成（実際の予測値に置き換えてください）
        prediction_text = (
            f"🎯 **【直前予測】 会場コード: {target_stadium} / 第{target_race_no}R**\n"
            f"• 本命: **1-3-5** (推論スコア上位)\n"
            f"• 対抗: **1-4-3**\n"
            f"• 連複: **1-3** 系注目"
        )
        send_discord_notification(prediction_text)
        
    else:
        start_msg = "=== 【定期実行】 全場の通常予測を開始 ==="
        print(start_msg)
        send_discord_notification(start_msg)
        
        # --- 全場予測の処理 ---
        if model is not None:
            # TODO: 全場のデータ取得・推論処理
            pass

        prediction_text = "📅 **【定期実行】 本日の主要レース予測が完了しました。**"
        send_discord_notification(prediction_text)

    end_msg = "=== 予測・通知パイプライン終了 ==="
    print(end_msg)
    send_discord_notification(end_msg)

if __name__ == '__main__':
    predict_main()
