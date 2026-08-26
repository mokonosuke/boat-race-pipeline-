import pandas as pd
import lightgbm as lgb

# --- 更新後の特徴量リスト（18個・オッズ除外版） ---
FEATURES = [
    'local_3ren', 'st', 'course', 'kimarite', 
    'motor', 'boat', 'racer_rank', 
    'wind_speed', 'is_headwind', 'is_tailwind',
    'exh_time', 'turn_time', 'water_type', 'in_rate',
    'national_win_rate', 'national_2nd_rate',
    'grade_score', 'is_rough_sign'
]

def main():
    print("=== 学習パイプライン開始（18特徴量・オッズ除外版） ===")
    
    # ここにデータ読み込み処理が必要です
    # 例: df = pd.read_csv('your_data.csv')
    
    # --- データ加工例 ---
    # 新しい特徴量を df に格納する処理（お手元のデータ構造に合わせて調整してください）
    # df['local_3ren'] = ...
    # df['st'] = ...
    # ...（全18項目を df に追加）...
    
    # ※特に重要：
    # 'national_win_rate', 'national_2nd_rate', 'grade_score', 'is_rough_sign' などの
    # 新しい項目が df に正しく入っていることを確認してください。

    # --- 学習処理 ---
    X_train = df[FEATURES]
    y_train = df['target']
    group = df['group_id'] # レースごとのグループ
    
    # モデルの構築（LambdaRank等の設定）
    model = lgb.LGBMRanker(
        objective="lambdarank",
        metric="ndcg",
        n_estimators=1000,
        learning_rate=0.05
    )
    
    model.fit(X_train, y_train, group=group)
    model.booster_.save_model('model.txt')
    
    print("=== 学習パイプライン完了！ model.txt を作成しました ===")

if __name__ == '__main__':
    main()
