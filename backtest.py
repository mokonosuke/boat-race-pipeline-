import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

print("🚀 [1/5] 拡張機械学習パイプライン開始（18特徴量・オッズ除外＆バックテスト版）")

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

# --- 会場特性データ（荒れる風速限界値を追加） ---
STADIUM_TRAITS = {
    '01': {'water_type': 0.0, 'in_rate': 0.50, 'wind_limit_rough': 4.0}, 
    '02': {'water_type': 0.0, 'in_rate': 0.40, 'wind_limit_rough': 3.5},
    '03': {'water_type': 0.5, 'in_rate': 0.40, 'wind_limit_rough': 3.0}, 
    '04': {'water_type': 0.5, 'in_rate': 0.45, 'wind_limit_rough': 4.0},
    '05': {'water_type': 0.0, 'in_rate': 0.50, 'wind_limit_rough': 4.5}, 
    '06': {'water_type': 1.0, 'in_rate': 0.50, 'wind_limit_rough': 4.0},
    '07': {'water_type': 1.0, 'in_rate': 0.55, 'wind_limit_rough': 4.0}, 
    '08': {'water_type': 1.0, 'in_rate': 0.55, 'wind_limit_rough': 4.0},
    '09': {'water_type': 1.0, 'in_rate': 0.50, 'wind_limit_rough': 4.0}, 
    '10': {'water_type': 0.0, 'in_rate': 0.45, 'wind_limit_rough': 3.5},
    '11': {'water_type': 0.0, 'in_rate': 0.45, 'wind_limit_rough': 3.5}, 
    '12': {'water_type': 1.0, 'in_rate': 0.55, 'wind_limit_rough': 4.5},
    '13': {'water_type': 1.0, 'in_rate': 0.55, 'wind_limit_rough': 4.0}, 
    '14': {'water_type': 1.0, 'in_rate': 0.45, 'wind_limit_rough': 4.0},
    '15': {'water_type': 1.0, 'in_rate': 0.50, 'wind_limit_rough': 4.0}, 
    '16': {'water_type': 1.0, 'in_rate': 0.45, 'wind_limit_rough': 4.0},
    '17': {'water_type': 1.0, 'in_rate': 0.50, 'wind_limit_rough': 4.0}, 
    '18': {'water_type': 1.0, 'in_rate': 0.60, 'wind_limit_rough': 4.5},
    '19': {'water_type': 1.0, 'in_rate': 0.55, 'wind_limit_rough': 4.0}, 
    '20': {'water_type': 1.0, 'in_rate': 0.50, 'wind_limit_rough': 4.0},
    '21': {'water_type': 1.0, 'in_rate': 0.60, 'wind_limit_rough': 4.5}, 
    '22': {'water_type': 0.5, 'in_rate': 0.45, 'wind_limit_rough': 3.5},
    '23': {'water_type': 1.0, 'in_rate': 0.55, 'wind_limit_rough': 4.0}, 
    '24': {'water_type': 1.0, 'in_rate': 0.60, 'wind_limit_rough': 5.0}
}

def get_factor_score(boat_data, assigned_course, stadium_code):
    local_3ren = float(boat_data.get('local_in3rd', 0.0) or 0.0)
    ave_st = float(boat_data.get('aveST', 0.20) or 0.20)
    course_key = f"course_{assigned_course}_2nd_rate"
    course_record_score = float(boat_data.get(course_key, 30.0) or 30.0)
    motor_rate = float(boat_data.get('motor_2nd_rate', 30.0) or 30.0)
    boat_rate = float(boat_data.get('boat_2nd_rate', 30.0) or 30.0)
    national_win = float(boat_data.get('national_win_rate', 5.0) or 5.0)
    national_2nd = float(boat_data.get('national_2nd_rate', 30.0) or 30.0)
    
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

    exh_time = float(boat_data.get('exhibition_time', 6.80) or 6.80)
    turn_time = float(boat_data.get('turn_time', 6.80) or 6.80)
    
    s_key = str(stadium_code).zfill(2)
    trait = STADIUM_TRAITS.get(s_key, {'water_type': 0.5, 'in_rate': 0.5, 'wind_limit_rough': 4.0})

    return (local_3ren, ave_st, course_record_score, kimarite_score, 
            motor_rate, boat_rate, racer_rank_score, exh_time, turn_time, 
            trait['water_type'], trait['in_rate'], national_win, national_2nd)

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

def fetch_recent_races(start_date, end_date):
    print("🚀 APIから最新データ（展示・風速・グレード等）を取得します...")
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

            # --- グレードと荒れフラグの算出 ---
            grade_str = str(race_info.get('grade', '一般'))
            grade_map = {'一般': 1, 'G3': 2, 'G2': 3, 'G1': 4, 'SG': 5}
            grade_score = grade_map.get(grade_str, 1)

            wind_speed = 0.0
            wind_dir = ""
            try:
                raw_wind_speed = race_info.get('wind_speed', 0.0)
                if raw_wind_speed is not None:
                    wind_str = str(raw_wind_speed).replace('m', '').strip()
                    if wind_str and wind_str != '-':
                        wind_speed = float(wind_str)
            except Exception:
                wind_speed = 0.0

            try:
                wind_dir = str(race_info.get('wind_direction', ''))
            except Exception:
                wind_dir = ""

            s_key = str(TARGET_JCD).zfill(2)
            trait = STADIUM_TRAITS.get(s_key, {'wind_limit_rough': 4.0})
            is_rough_sign = 1 if wind_speed >= trait.get('wind_limit_rough', 4.0) else 0

            is_headwind = 1 if ('向' in wind_dir or '向かい風' in wind_dir) else 0
            is_tailwind = 1 if ('追' in wind_dir or '追い風' in wind_dir) else 0

            race_combos = []
            for combo, odds in odds_info.items():
                if not isinstance(combo, str) or '-' not in combo:
                    continue
                try:
                    boats = [int(b) for b in combo.split('-')]
                    odds_val = float(odds)
                except (ValueError, TypeError):
                    continue
                
                t_l3, t_st, t_cr, t_kim, t_mot, t_bot, t_rnk, t_exh, t_turn = 0, 0, 0, 0, 0, 0, 0, 0, 0
                t_nat_win, t_nat_2nd = 0, 0
                water_val, in_rate_val = 0.5, 0.5
                
                for idx, b in enumerate(boats):
                    assigned_course = idx + 1
                    boat_key = f"boat{b}"
                    boat_data = race_info.get(boat_key, {})
                    l3, st, cr, kim, mot, bot, rnk, exh, turn, water, in_rate, nat_w, nat_2 = get_factor_score(boat_data, assigned_course, TARGET_JCD)
                    t_l3 += l3
                    t_st += st
                    t_cr += cr
                    t_kim += kim
                    t_mot += mot
                    t_bot += bot
                    t_rnk += rnk
                    t_exh += exh
                    t_turn += turn
                    t_nat_win += nat_w
                    t_nat_2nd += nat_2
                    water_val = water
                    in_rate_val = in_rate
                
                race_combos.append({
                    'combo': combo,
                    'odds': odds_val,
                    'local_3ren': t_l3 / 3,
                    'st': t_st / 3,
                    'course': t_cr / 3,
                    'kimarite': t_kim / 3,
                    'motor': t_mot / 3,
                    'boat': t_bot / 3,
                    'racer_rank': t_rnk / 3,
                    'exh_time': t_exh / 3,
                    'turn_time': t_turn / 3,
                    'water_type': water_val,
                    'in_rate': in_rate_val,
                    'national_win_rate': t_nat_win / 3,
                    'national_2nd_rate': t_nat_2nd / 3,
                    'wind_speed': wind_speed,
                    'is_headwind': is_headwind,
                    'is_tailwind': is_tailwind,
                    'grade_score': grade_score,
                    'is_rough_sign': is_rough_sign
                })
            
            if race_combos:
                cache_data.append({
                    'date': date_str,
                    'rno': rno,
                    'actual_win': actual_win,
                    'combos': race_combos
                })
                
        current_date += timedelta(days=1)

    print(f"✅ データ取得完了: {len(cache_data)}レース")
    return cache_data

def run_backtest_ml(cache_data):
    print("🤖 [3/5] 18特徴量モデル（オッズ除外）の訓練とバックテストを実行中...")
    
    dataset = []
    for race_idx, race in enumerate(cache_data):
        actual_win = race['actual_win']
        for bet in race['combos']:
            dataset.append({
                'date': race['date'],
                'rno': race['rno'],
                'race_id': race_idx,
                'combo': bet['combo'],
                'odds': bet['odds'],  # バックテストの回収率計算・フィルタリング用に保持
                'local_3ren': bet['local_3ren'],
                'st': bet['st'],
                'course': bet['course'],
                'kimarite': bet['kimarite'],
                'motor': bet['motor'],
                'boat': bet['boat'],
                'racer_rank': bet['racer_rank'],
                'exh_time': bet['exh_time'],
                'turn_time': bet['turn_time'],
                'water_type': bet['water_type'],
                'in_rate': bet['in_rate'],
                'national_win_rate': bet['national_win_rate'],
                'national_2nd_rate': bet['national_2nd_rate'],
                'wind_speed': bet['wind_speed'],
                'is_headwind': bet['is_headwind'],
                'is_tailwind': bet['is_tailwind'],
                'grade_score': bet['grade_score'],
                'is_rough_sign': bet['is_rough_sign'],
                'is_win': 1 if bet['combo'] == actual_win else 0,
                'actual_win': actual_win
            })
            
    df = pd.DataFrame(dataset)
    if len(df) == 0:
        print("❌ 学習データが空です。")
        return None

    # 18特徴量（featuresから 'odds' を除外）
    features = [
        'local_3ren', 'st', 'course', 'kimarite', 
        'motor', 'boat', 'racer_rank', 
        'wind_speed', 'is_headwind', 'is_tailwind',
        'exh_time', 'turn_time', 'water_type', 'in_rate',
        'national_win_rate', 'national_2nd_rate',
        'grade_score', 'is_rough_sign'
    ]
    X = df[features]
    y = df['is_win']
    
    X_train, X_test, y_train, y_test, df_train, df_test = train_test_split(
        X, y, df, test_size=0.2, random_state=42
    )
    
    model = lgb.LGBMClassifier(
        n_estimators=120,
        max_depth=4,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbose=-1
    )
    model.fit(X_train, y_train)
    
    model.booster_.save_model('model.txt')
    print("✅ 学習済みモデルを 'model.txt' として保存しました。")
    
    df_test = df_test.copy()
    df_test['pred_prob'] = model.predict_proba(X_test)[:, 1]
    
    total_races = 0
    hit_count = 0
    total_investment = 0
    total_payout = 0
    
    grouped = df_test.groupby(['date', 'rno'])
    for _, group in grouped:
        filtered_group = group[(group['odds'] >= 3.0) & (group['odds'] <= 200.0)]
        
        if len(filtered_group) == 0:
            continue
            
        total_races += 1
        total_investment += 100
        
        best_bet = filtered_group.loc[filtered_group['pred_prob'].idxmax()]
        
        if best_bet['combo'] == best_bet['actual_win']:
            hit_count += 1
            payout = 100 * best_bet['odds']
            total_payout += payout

    roi = (total_payout / total_investment * 100) if total_investment > 0 else 0
    
    results = {
        "total_races": total_races,
        "hit_count": hit_count,
        "hit_rate": (hit_count / total_races * 100) if total_races > 0 else 0,
        "total_investment": total_investment,
        "total_payout": int(total_payout),
        "roi": round(roi, 2)
    }
    
    print(f"✅ バックテスト完了: 回収率 {results['roi']}%")
    return results

if __name__ == "__main__":
    end_d = date.today() - timedelta(days=1)
    start_d = end_d - timedelta(days=14)
    
    cache_data = fetch_recent_races(start_d, end_d)
    results = run_backtest_ml(cache_data)
    
    if results:
        summary_text = (
            f"🎯 **【18特徴量（オッズ除外版）・バックテスト結果】**\n"
            f"・検証対象期間: {start_d} 〜 {end_d}\n"
            f"・有効投票レース数: {results['total_races']}件\n"
            f"・回収率: **{results['roi']}%**\n"
            f"・的中数 / 的中率: {results['hit_count']}件 ({results['hit_rate']:.2f}%)\n"
            f"・総投資 / 払戻: {results['total_investment']}円 → {results['total_payout']}円"
        )
        print("\n" + summary_text.replace("**", ""))
        
        if WEBHOOK_URL:
            try:
                requests.post(WEBHOOK_URL, json={"content": summary_text})
                print("✅ Discordへ結果を送信しました。")
            except Exception as e:
                print(f"⚠️ Discord通知失敗: {e}")
