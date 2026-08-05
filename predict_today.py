import os
import pandas as pd
import lightgbm as lgb

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

def predict_main():
    # GitHub Actions の環境変数から手動入力値を取得
    target_stadium = os.environ.get('INPUT_STADIUM', '').strip()
    target_race_no = os.environ.get('INPUT_RACE_NO', '').strip()

    # 学習済みモデルの読み込み
    # model = lgb.Booster(model_file='model.txt')

    if target_stadium and target_race_no:
        print(f"=== 【手動トリガー】 {target_stadium}場 第{target_race_no}レースの直前予測を開始 ===")
        # TODO: 特定レースの直前情報（展示タイム等）を含むデータ取得・予測ロジックをここに記述
        
    else:
        print("=== 【定期実行】 全場の通常予測を開始 ===")
        # TODO: 通常の全レース予測ロジックをここに記述

    print("=== 予測・通知パイプライン終了 ===")

if __name__ == '__main__':
    predict_main()
