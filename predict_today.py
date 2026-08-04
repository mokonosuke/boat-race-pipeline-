import pandas as pd
import lightgbm as lgb

# --- 天気・風向の数値化関数（main.pyと完全に同一にする） ---
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

# --- 共通の特徴量リスト（main.pyと完全に同一にする） ---
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

def predict_main():
    print("=== 本日の予測・通知パイプライン開始 ===")
    
    # 1. 学習済みモデルの読み込み
    # model = lgb.Booster(model_file='model.txt')
    
    # 2. 本日の出走表および気象データの取得・構築
    # df_today に各特徴量を格納（気象データも必ず含める）
    # df_today['air_temp'] = ...
    # df_today['weather'] = encode_weather(...)
    # ...
    
    # 3. 特徴量を揃えて予測を実行
    # X_today = df_today[FEATURES]
    # preds = model.predict(X_today)
    
    # 4. Discordへの通知処理
    # ...
    
    print("=== 本日の予測・通知パイプライン終了 ===")

if __name__ == '__main__':
    predict_main()
