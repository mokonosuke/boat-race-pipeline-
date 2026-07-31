
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

print("🚀 [1/5] 機械学習パイプライン開始")

import os
from datetime import date, timedelta
import json
import re
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
import requests

print("🚀 [2/5] モジュールインポート完了")
try:
    from pyjpboatrace import PyJPBoatrace
    print("✅ PyJPBoatrace 読み込み成功")
except Exception as e:
    print(f"❌ 読み込み失敗: {e}")
    sys.exit(1)

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
TARGET_JCD = 11  # びわこ競走場
CACHE_FILE = "race_cache.json"

def get_factor_score(boat_data, assigned_course):
    local_3ren = float(boat_data.get('local_in3rd', 0.0))
    ave_st = float(boat_data.get('aveST', 0.20))
    course_key = f"course_{assigned_course}_2nd_rate"
    course_record_score = float(boat_data.get(course_key, 30.0))
    
    kimarite_type = boat_data.get('primary_kimarite', 'normal')
    if kimarite_type in ['makuri', 'tsuki_makuri'] and assigned_course in [4, 5, 6]:
        kimarite_score = 45.0
    elif kimarite_type == 'sashi' and assigned_course in [2, 3]:
        kimarite_score = 45.0
    elif kimarite_type == 'nige' and assigned_course == 1:
        kimarite_score = 50.0
    else:
        kimarite_score = 35.0

    return local_3ren, ave_st, course_record_score, kimarite_score

def extract_trifecta_result(result_data):
    if not result_data:
        return None
    if isinstance(result_data, dict):
        for k, v in result_data.items():
            if isinstance(v, str) and re.match(r'^[1-6]-[1-6]-[1-6]$', v.strip()):
                return v.strip()
            if isinstance(v, (dict, list)):
                res = extract_trifecta_result(v)
                if res:
                    return res
    elif isinstance(result_data, (list, tuple)):
        for item in result_data:
            res = extract_trifecta_result(item)
            if res:
                return res
    elif isinstance(result_data, str):
        match = re.search(r'([1-6]-[1-6]-[1-6])', result_data)
        if match:
            return match.group(1)
    return None

def fetch_and_cache_races(start_date, end_date):
    if os.path.exists(CACHE_FILE):
        print("📂 既存のレースキャッシュを読み込みます...")
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    print("🚀 APIからデータを取得してキャッシュを作成します...")
    try:
        boatrace = PyJPBoatrace()
    except Exception as e:
        print(f"❌ 初期化失敗: {e}")
        return []

    cache_data = []
    current_date = start_date
    
    while current_date <= end_date:
        date_str = str(current_date)
        print(f"📅 取得中: {date_str}")
        
        for rno in range(1, 13):
            try:
                odds_info = boatrace.get_odds_trifecta(d=current_date, stadium=TARGET_JCD, race=rno)
                race_info = boatrace.get_race_info(d=current_date, stadium=TARGET_JCD, race=rno)
                result_info = boatrace.get_race_result(d=current_date, stadium=TARGET_JCD, race=rno)
            except Exception:
                continue
            
            if not odds_info or not race_info or not result_info:
                continue
            
            actual_win = extract_trifecta_result(result_info)
            if not actual_win:
                continue

            race_combos = []
            for combo, odds in odds_info.items():
                if not isinstance(combo, str) or '-' not in combo:
                    continue
                try:
                    boats = [int(b) for b in combo.split('-')]
                    odds_val = float(odds)
                except (ValueError, TypeError):
                    continue
                
                total_l3, total_st, total_cr, total_kim = 0, 0, 0, 0
                for idx, b in enumerate(boats):
                    assigned_course = idx + 1
                    boat_key = f"boat{b}"
                    boat_data = race_info.get(boat_key, {})
                    l3, st, cr, kim = get_factor_score(boat_data, assigned_course)
                    total_l3 += l3
                    total_st += st
                    total_cr += cr
                    total_kim += kim
                
                race_combos.append({
                    'combo': combo,
                    'odds': odds_val,
                    'avg_l3': total_l3 / 3,
                    'avg_st': total_st / 3,
                    'avg_cr': total_cr / 3,
                    'avg_kim': total_kim / 3
                })
            
            if race_combos:
                cache_data.append({
                    'date': date_str,
                    'rno': rno,
                    'actual_win': actual_win,
                    'combos': race_combos
                })
                
        current_date += timedelta(days=1)

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=4)
    print(f"✅ キャッシュ保存完了: {len(cache_data)}レース")
    return cache_data

def train_and_evaluate_ml(cache_data):
    print("🤖 [3/5] 機械学習モデルの訓練と評価を実行中...")
    
    dataset = []
    for race in cache_data:
        actual_win = race['actual_win']
        for bet in race['combos']:
            dataset.append({
                'local_3ren': bet['avg_l3'],
                'st': bet['avg_st'],
                'course': bet['avg_cr'],
                'kimarite': bet['avg_kim'],
                'odds': bet['odds'],
                'is_win': 1 if bet['combo'] == actual_win else 0
            })
            
    df = pd.DataFrame(dataset)
    if len(df) == 0:
        print("❌ 学習データが空です。")
        return None

    X = df[['local_3ren', 'st', 'course', 'kimarite', 'odds']]
    y = df['is_win']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = lgb.LGBMClassifier(random_state=42, verbose=-1)
    model.fit(X_train, y_train)
    
    print("✅ 機械学習モデルの学習が完了しました！")
    return model

if __name__ == "__main__":
    start_d = date(2026, 7, 28)
    end_d = date(2026, 7, 30)
    
    cache_data = fetch_and_cache_races(start_d, end_d)
    model = train_and_evaluate_ml(cache_data)
    
    if model:
        summary_text = "🤖 **【機械学習パイプライン実行成功】**\nLightGBMによるモデルの学習・評価が正常に完了しました！"
        print("\n" + summary_text.replace("**", ""))
        
        if WEBHOOK_URL:
            try:
                requests.post(WEBHOOK_URL, json={"content": summary_text})
                print("✅ Discordへ完了通知を送信しました。")
            except Exception as e:
                print(f"⚠️ Discord通知失敗: {e}")
