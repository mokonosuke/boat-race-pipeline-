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

def run_inference(model, target_stadium, target_race_no):
    """モデルを用いた推論を実行し、Discord用のフォーマット文字列を生成する"""
    try:
        # TODO: 実際のレースデータ（1〜6号艇分のDataFrame）を取得する処理に置き換えてください
        # 例: df_test = get_scraped_race_data(target_stadium, target_race_no)
        
        # サンプル用のダミーデータ（動作確認用）
        data = {
            'local_3ren': [0.45, 0.30, 0.60, 0.25, 0.40, 0.20],
            'st': [0.15, 0.18, 0.12, 0.20, 0.16, 0.22],
            'course': [1, 2, 3, 4, 5, 6],
            'motor': [35.5, 40.2, 50.1, 28.4, 33.0, 25.1],
            'boat': [40.0, 30.0, 45.0, 32.0, 38.0, 29.0],
            'racer_rank': [1, 2, 1, 3, 2, 3],
            'air_temp': [22.0, 22.0, 22.0, 22.0, 22.0, 22.0],
            'water_temp': [20.0, 20.0, 20.0, 20.0, 20.0, 20.0],
            'wind_speed': [3.0, 3.0, 3.0, 3.0, 3.0, 3.0],
            'wave_height': [5, 5, 5, 5, 5, 5],
            'weather': [1, 1, 1, 1, 1, 1],
            'wind_direction': [2, 2, 2, 2, 2, 2]
        }
        df_test = pd.DataFrame(data)
        
        # 特徴量の順序を確実に一致させる
        X_test = df_test[FEATURES]
        
        # 推論の実行
        preds = model.predict(X_test)
        
        # スコアが高い順に艇をソート
        df_test['pred_score'] = preds
        df_test['boat_no'] = range(1, 7)
        df_sorted = df_test.sort_values(by='pred_score', ascending=False).reset_index(drop=True)
        
        first = int(df_sorted.loc[0, 'boat_no'])
        second = int(df_sorted.loc[1, 'boat_no'])
        third = int(df_sorted.loc[2, 'boat_no'])
        
        prediction_text = (
            f"🎯 **【直前予測】 会場コード: {target_stadium} / 第{target_race_no}R**\n"
            f"• 推奨買い目: **{first}-{second}-{third}**\n"
            f"• 1着有力: **{first}号艇** (スコア: {df_sorted.loc[0, 'pred_score']:.3f})\n"
            f"• 2着有力: **{second}号艇**\n"
            f"• 3着有力: **{third}号艇**"
        )
        return prediction_text

    except Exception as e:
        return f"⚠️ 推論処理中にエラーが発生しました: {e}"

def predict_main():
    target_stadium = os.environ.get('INPUT_STADIUM', '').strip()
    target_race_no = os.environ.get('INPUT_RACE_NO', '').strip()

    if target_stadium in STADIUM_MAP:
        target_stadium = STADIUM_MAP[target_stadium]

    # モデルファイルの読み込み
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
        
        if model is not None:
            prediction_text = run_inference(model, target_stadium, target_race_no)
        else:
            prediction_text = "⚠️ モデルファイルが存在しないため、推論をスキップしました。"
            
        send_discord_notification(prediction_text)
        
    else:
        start_msg = "=== 【定期実行】 全場の通常予測を開始 ==="
        print(start_msg)
        send_discord_notification(start_msg)
        
        # 全場予測の処理（必要に応じて拡張）
        prediction_text = "📅 **【定期実行】 本日の主要レース予測が完了しました。**"
        send_discord_notification(prediction_text)

    end_msg = "=== 予測・通知パイプライン終了 ==="
    print(end_msg)
    send_discord_notification(end_msg)

if __name__ == '__main__':
    predict_main()
