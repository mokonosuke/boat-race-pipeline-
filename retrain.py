import os
import pandas as pd
import lightgbm as lgb

FEATURES = [
    'local_3ren', 'st', 'course', 'kimarite', 
    'motor', 'boat', 'racer_rank', 'odds',
    'wind_speed', 'is_headwind', 'is_tailwind',
    'exh_time', 'turn_time', 'water_type', 'in_rate',
    'national_win_rate', 'national_2nd_rate'
]

def retrain_model():
    log_file = 'history_data.csv'
    if not os.path.exists(log_file):
        print("⚠️ 学習データ（history_data.csv）がまだありません。")
        return

    print("📊 蓄積された履歴データからモデルを再学習します...")
    df = pd.read_csv(log_file)
    
    if len(df) < 100:
        print(f"⚠️ データ数がまだ少なすぎます（現在 {len(df)}件）。もう少しデータを溜めてから再学習します。")
        return

    X = df[FEATURES]
    y = df['target'] # 的中(1)か外れ(0)か

    # LightGBMのデータセット作成
    train_data = lgb.Dataset(X, label=y)

    params = {
        'objective': 'binary',
        'metric': 'auc',
        'boosting_type': 'gbdt',
        'learning_rate': 0.05,
        'num_leaves': 31,
        'seed': 42,
        'verbose': -1
    }

    # モデルの再学習
    model = lgb.train(params, train_data, num_boost_round=100)
    
    # 新しいモデルを保存
    model.save_model('model.txt')
    print("🎯 モデルの再学習が完了し、model.txtを更新しました！")

if __name__ == '__main__':
    retrain_model()

