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

# --- 共通の特徴量リスト（気象データを含む） ---
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

def main():
    print("=== 学習パイプライン開始 ===")
    
    # 1. 過去データの収集・読み込み
    # （※お手元のデータ収集ロジックに合わせ、df に気象データを格納してください）
    # 例:
    # df['air_temp'] = raw_data['air_temperature'].apply(float)
    # df['water_temp'] = raw_data['water_temperature'].apply(float)
    # df['wind_speed'] = raw_data['wind_speed'].apply(float)
    # df['wave_height'] = raw_data['wave_height'].apply(float)
    # df['weather'] = raw_data['weather'].apply(encode_weather)
    # df['wind_direction'] = raw_data['wind_direction'].apply(encode_wind_direction)

    # 2. LightGBM / LambdaRank の学習処理
    # X_train = df[FEATURES]
    # y_train = df['target']
    # group = df['group_id'] # レースごとのグループ
    
    # model = lgb.LGBMRanker(...)
    # model.fit(X_train, y_train, group=group)
    # model.booster_.save_model('model.txt')
    
    print("=== 学習パイプライン終了 ===")

if __name__ == '__main__':
    main()

