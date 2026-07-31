import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

print("🚀 [1/4] リアルタイム予想パイプライン開始")

import os
from datetime import date, timedelta
import re
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
import requests

print("🚀 [2/4] モジュールインポート完了")
try:
    from pyjpboatrace import PyJPBoatrace
    print("✅ PyJPBoatrace 読み込み成功")
except Exception as e:
    print(f"❌ 読み込み失敗: {e}")
    sys.exit(1)

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
TARGET_JCD = 11  # びわこ競走場（ゆくゆくは全会場ループに拡張可能）

def get_factor_score(boat_data, assigned_course):
    local_3ren = float(boat_data.get('local_in3rd', 0.0))
    ave_st = float(boat_data.get('aveST', 0.20))
    course_key = f"course_{assigned_course}_2nd_rate"
    course_record_score = float(boat_data.get(course_key, 30.0))
    motor_rate = float(boat_data.get('motor_2nd_rate', 30.0))
    boat_rate = float(boat_data.get('boat_2nd_rate', 30.0))
    
    rank_str = str(boat_data.get('racer_class', boat_data.get('rank', 'B1'))).upper()
    rank_map = {'A1': 4.0, 'A2': 3.0, 'B1': 2.0, 'B2': 1.0}
    racer_rank_score = rank_map.get(rank_str, 2.0)
    
    kimarite_type = boat_data.get('primary_kimarite', 'normal')
    if kimarite_type in ['makuri', 'tsuki_makuri'] and assigned_course in [4, 5, 6]:
        kimarite_score = 45.0
    elif kimarite_type == 'sashi' and assigned_course in [2, 3]:
        kimarite_score = 45.0
    elif kimarite_type == 'nige' and assigned_course == 1:
        kimarite_score = 50.0
    else:
        kimarite_score = 35.0

    return local_3ren, ave_st, course_record_score, kimarite_score, motor_rate, boat_rate, racer_rank_score

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

def fetch_training_data(start_date, end_date):
    print("📚 過去データからAIモデルを訓練するためのデータを収集中...")
    boatrace = PyJPBoatrace()
    cache_data = []
    current_date = start_date
    
    while current_date <= end_date:
        date_str = str(current_date)
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
                
                total_l3, total_st, total_cr, total_kim, total_motor, total_boat, total_rank = 0, 0, 0, 0, 0, 0, 0
                for idx, b in enumerate(boats):
                    assigned_course = idx + 1
                    boat_key = f"boat{b}"
                    boat_data = race_info.get(boat_key, {})
                    l3, st, cr, kim, mot, bot, rnk = get_factor_score(boat_data, assigned_course)
                    total_l3 += l3
                    total_st += st
                    total_cr += cr
                    total_kim += kim
                    total_motor += mot
                    total_boat += bot
                    total_rank += rnk
                
                race_combos.append({
                    'combo': combo,
                    'odds': odds_val,
                    'avg_l3': total_l3 / 3,
                    'avg_st': total_st / 3,
                    'avg_cr': total_cr / 3,
                    'avg_kim': total_kim / 3,
                    'avg_motor': total_motor / 3,
                    'avg_boat': total_boat / 3,
                    'avg_rank': total_rank / 3
                })
            
            if race_combos:
                cache_data.append({
                    'actual_win': actual_win,
                    'combos': race_combos
                })
        current_date += timedelta(days=1)
    return cache_data

def fetch_today_races(target_date):
    print(f"🎯 本日({target_date})のレース・オッズ情報を取得中...")
    boatrace = PyJPBoatrace()
    today_data = []
    
    for rno in range(1, 13):
        try:
            odds_info = boatrace.get_odds_trifecta(d=target_date, stadium=TARGET_JCD, race=rno)
            race_info = boatrace.get_race_info(d=target_date, stadium=TARGET_JCD, race=rno)
        except Exception:
            continue
        
        if not odds_info or not race_info:
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
            
            total_l3, total_st, total_cr, total_kim, total_motor, total_boat, total_rank = 0, 0, 0, 0, 0, 0, 0
            for idx, b in enumerate(boats):
                assigned_course = idx + 1
                boat_key = f"boat{b}"
                boat_data = race_info.get(boat_key, {})
                l3, st, cr, kim, mot, bot, rnk = get_factor_score(boat_data, assigned_course)
                total_l3 += l3
                total_st += st
                total_cr += cr
                total_kim += kim
                total_motor += mot
                total_boat += bot
                total_rank += rnk
            
            race_combos.append({
                'combo': combo,
                'odds': odds_val,
                'local_3ren': total_l3 / 3,
                'st': total_st / 3,
                'course': total_cr / 3,
                'kimarite': total_kim / 3,
                'motor': total_motor / 3,
                'boat': total_boat / 3,
                'racer_rank': total_rank / 3
            })
        
        if race_combos:
            today_data.append({
                'rno': rno,
                'combos': race_combos
            })
    return today_data

def train_model(cache_data):
    print("🤖 AIモデルを訓練中...")
    dataset = []
    for race_idx, race in enumerate(cache_data):
        actual_win = race['actual_win']
        for bet in race['combos']:
            dataset.append({
                'local_3ren': bet['avg_l3'],
                'st': bet['avg_st'],
                'course': bet['avg_cr'],
                'kimarite': bet['avg_kim'],
                'motor': bet['avg_motor'],
                'boat': bet['avg_boat'],
                'racer_rank': bet['avg_rank'],
                'odds': bet['odds'],
                'is_win': 1 if bet['combo'] == actual_win else 0
            })
            
    df = pd.DataFrame(dataset)
    features = ['local_3ren', 'st', 'course', 'kimarite', 'motor', 'boat', 'racer_rank', 'odds']
    X = df[features]
    y = df['is_win']
    
    model = lgb.LGBMClassifier(
        n_estimators=120,
        max_depth=4,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbose=-1
    )
    model.fit(X, y)
    return model, features

if __name__ == "__main__":
    today = date.today()
    train_end = today - timedelta(days=1)
    train_start = train_end - timedelta(days=14)
    
    # 1. 過去データで訓練
    training_data = fetch_training_data(train_start, train_end)
    model, features = train_model(training_data)
    
    # 2. 今日のレースを予測
    today_races = fetch_today_races(today)
    
    predictions = []
    for race in today_races:
        rno = race['rno']
        df_race = pd.DataFrame(race['combos'])
        if len(df_race) == 0:
            continue
            
        X_pred = df_race[features]
        df_race['pred_prob'] = model.predict_proba(X_pred)[:, 1]
        
        # オッズフィルタリング適用 (5倍〜60倍)
        filtered = df_race[(df_race['odds'] >= 5.0) & (df_race['odds'] <= 60.0)]
        if len(filtered) == 0:
            continue
            
        best_bet = filtered.loc[filtered['pred_prob'].idxmax()]
        predictions.append({
            'rno': rno,
            'combo': best_bet['combo'],
            'odds': best_bet['odds'],
            'prob': best_bet['pred_prob'] * 100
        })
    
    # 3. Discord通知メッセージの作成
    if predictions:
        pred_lines = [f"・第{p['rno']}R: **{p['combo']}** (オッズ: {p['odds']}倍 / 期待度: {p['prob']:.1f}%)" for p in predictions]
        summary_text = (
            f"🎯 **【本日のAI買い目配信】** ({today})\n" +
            "\n".join(pred_lines)
        )
    else:
        summary_text = f"🎯 **【本日のAI買い目配信】** ({today})\n本日は条件に一致する推奨レースはありませんでした。"
        
    print("\n" + summary_text.replace("**", ""))
    
    if WEBHOOK_URL:
        try:
            requests.post(WEBHOOK_URL, json={"content": summary_text})
            print("✅ Discordへ本日の予想を送信しました。")
        except Exception as e:
            print(f"⚠️ Discord通知失敗: {e}")

