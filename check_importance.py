import lightgbm as lgb
import pandas as pd

# 学習済みモデルの読み込み
model = lgb.Booster(model_file='model.txt')

# 特徴量名と重要度（ゲインベース）を取得
features = model.feature_name()
importance = model.feature_importance(importance_type='gain')

# データフレームにまとめて降順ソート
importance_df = pd.DataFrame({
    'feature': features,
    'importance': importance
}).sort_values(by='importance', ascending=False)

print("📊 【特徴量重要度ランキング】")
print(importance_df.to_string(index=False))
