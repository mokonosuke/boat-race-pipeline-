import os
import pandas as pd
import lightgbm as lgb

# --- 各場のトリセツ（荒れる風速の限界値）の定義 ---
STADIUM_TRAITS = {
    '01': {'wind_limit_rough': 4.0}, '02': {'wind_limit_rough': 3.5},
    '03': {'wind_limit_rough': 3.0}, '04': {'wind_limit_rough': 4.0},
    '05': {'wind_limit_rough': 4.5}, '06': {'wind_limit_rough': 4.0},
    '07': {'wind_limit_rough': 4.0}, '08': {'wind_limit_rough': 4.0},
    '09': {'wind_limit_rough': 4.0}, '10': {'wind_limit_rough': 3.5},
    '11': {'wind_limit_rough': 3.5}, '12': {'wind_limit_rough': 4.5},
    '13': {'wind_limit_rough': 4.0}, '14': {'wind_limit_rough': 4.0},
    '15': {'wind_limit_rough': 4.0}, '16': {'wind_limit_rough': 4.0},
    '17': {'wind_limit_rough': 4.0}, '18': {'wind_limit_rough': 4.5},
    '19': {'wind_limit_rough': 4.0}, '20': {'wind_limit_rough': 4.0},
    '21': {'wind_limit_rough': 4.5}, '22': {'wind_limit_rough': 3.5},
    '23': {'wind_limit_rough': 4.0}, '24': {'wind_limit_rough': 5.0}
}

# --- オッズを除外した18個の特徴量リスト ---
FEATURES = [
    'local_3ren', 'st', 'course', 'kimarite', 
    'motor', 'boat', 'racer_rank', 
    'wind_speed', 'is_headwind', 'is_tailwind',
    'exh_time', 'turn_time', 'water_type', 'in_rate',
    'national_win_rate', 'national_2nd_rate',
    'grade_score',    # レースグレード（一般〜SG）
    'is_rough_sign'   # トリセツの荒れるサイン点灯フラグ
]

def retrain_model():
    log_file = 'history_data.csv'
    if not os.path.exists(log_file):
        print("⚠️ 学習データ（history_data.csv）がまだありません。")
        return

    print("📊 蓄積された履歴データからモデルを再学習します（18特徴量・オッズ除外版）...")
    df = pd.read_csv(log_file)
    
    # --- 新しい特徴量の自動生成・補完処理 ---
    if 'grade_score' not in df.columns:
        grade_map = {'一般': 1, 'G3': 2, 'G2': 3, 'G1': 4, 'SG': 5}
        if 'grade' in df.columns:
            df['grade_score'] = df['grade'].map(grade_map).fillna(1)
        else:
            df['grade_score'] = 1  # カラムがない場合のデフォルト

    if 'is_rough_sign' not in df.columns:
        if 'stadium_id' in df.columns and 'wind_speed' in df.columns:
            def calc_rough_sign(row):
                s_id = str(row['stadium_id']).zfill(2)
                limit = STADIUM_TRAITS.get(s_id, {'wind_limit_rough': 4.0})['wind_limit_rough']
                return 1 if float(row['wind_speed']) >= limit else 0
            df['is_rough_sign'] = df.apply(calc_rough_sign, axis=1)
        else:
            df['is_rough_sign'] = 0  # カラムがない場合のデフォルト

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
    print("🎯 モデルの再学習が完了し、18特徴量（オッズ除外）の新しいmodel.txtを更新しました！")

    # ==========================================
    # 📊 ステップ2：特徴量重要度（Feature Importance）の表示
    # ==========================================
    print("\n📊 【18特徴量 重要度ランキング（Gainベース）】")
    features = model.feature_name()
    importance = model.feature_importance(importance_type='gain')
    importance_df = pd.DataFrame({
        'feature': features,
        'importance': importance
    }).sort_values(by='importance', ascending=False)
    print(importance_df.to_string(index=False))
    print("--------------------------------------------------\n")

if __name__ == '__main__':
    retrain_model()
