import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

print("🚀 [1/5] 全場対応・特徴量完全連動版パイプライン開始")

import os
from datetime import date, timedelta
import re
import pandas as pd
import lightgbm as lgb

try:
    from pyjpboatrace import PyJPBoatrace
    print("✅ PyJPBoatrace 読み込み成功")
except Exception as e:
    print(f"❌ 読み込み失敗: {e}")
    sys.exit(1)

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

def safe_float(val, default=0.0):
    if val is None:
        return default
    val_str = str(val).replace('m', '').replace('%', '').strip()
    if val_str == '' or val_str == '-' or val_str == 'ー':
        return default
    try:
        return float(val_str)
    except (ValueError, TypeError):
        return default

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
    print("🚀 全国のAPIからデータを取得中...")
    try:
        boatrace = PyJPBoatrace()
    except Exception as e:
        print(f"❌ 初期化失敗: {e}")
        return []

    cache_data = []
    current_date = start_date
    
    while current_date <= end_date:
        date_str = str(current_date)
        print(f"📅 取得中: {date_str} (全24場)")
        
        for stadium in range(1, 25):
            s_key = str(stadium).zfill(2)
            trait = STADIUM_TRAITS.get(s_key, {'water_type': 1.0, 'in_rate': 0.50, 'wind_limit_rough': 4.0})
            
            for rno in range(1, 13):
                try:
                    odds_info = boatrace.get_odds_trifecta(d=current_date, stadium=stadium, race=rno)
                    race_info = boatrace.get_race_info(d=current_date, stadium=stadium, race=rno)
                    just_before = boatrace.get_just_before_info(d=current_date, stadium=stadium, race=rno)
                    result_info = boatrace.get_race_result(d=current_date, stadium=stadium, race=rno)
                except Exception:
                    continue
                
                if not odds_info or not race_info or not result_info:
                    continue
                
                actual_win = extract_trifecta_result(result_info)
                if not actual_win:
                    continue

                grade_str = str(race_info.get('grade', race_info.get('race_grade', '一般')))
                grade_map = {'一般': 1, 'G3': 2, 'G2': 3, 'G1': 4, 'SG': 5}
                grade_score = grade_map.get(grade_str, 1)

                # 💡 風速・風向を just_before と race_info の両方から幅広く探索する
                w_source = just_before if isinstance(just_before, dict) else {}
                wind_speed = safe_float(w_source.get('wind_speed', w_source.get('wind', race_info.get('wind_speed', race_info.get('wind', 2.0)))), 2.0)
                is_rough_sign = 1 if wind_speed >= trait.get('wind_limit_rough', 4.0) else 0

                wind_dir = str(w_source.get('wind_direction', w_source.get('wind_dir', race_info.get('wind_direction', race_info.get('wind_dir', '')))))
                
                # デバッグ用ログ出力（値が取れているか確認）
                print(f"DEBUG -> 場:{stadium} R{rno} | 風速:{wind_speed} 風向:'{wind_dir}'")

                is_headwind = 1 if ('向' in wind_dir or 'head' in wind_dir.lower()) else 0
                is_tailwind = 1 if ('追' in wind_dir or 'tail' in wind_dir.lower()) else 0

                race_combos = []
                for combo, odds in odds_info.items():
                    if not isinstance(combo, str) or '-' not in combo:
                        continue
                    try:
                        boats = [int(b) for b in combo.split('-')]
                    except (ValueError, TypeError):
                        continue
                    
                    t_l3, t_st, t_cr, t_kim, t_mot, t_bot, t_rnk, t_exh, t_turn = 0, 0, 0, 0, 0, 0, 0, 0, 0
                    t_nat_win, t_nat_2nd = 0, 0
                    water_val, in_rate_val = trait['water_type'], trait['in_rate']
                    
                    for idx, b in enumerate(boats):
                        assigned_course = idx + 1
                        
                        boat_data = {}
                        for k in [f"boat{b}", f"racer_{b}", str(b), b]:
                            if isinstance(race_info, dict) and k in race_info and isinstance(race_info[k], dict):
                                boat_data = race_info[k]
                                break
                        if not boat_data and isinstance(race_info, dict):
                            boat_data = race_info.get(f"boat{b}", {})

                        jb_boat_data = {}
                        if isinstance(just_before, dict):
                            for k in [f"boat{b}", f"racer_{b}", str(b), b]:
                                if k in just_before and isinstance(just_before[k], dict):
                                    jb_boat_data = just_before[k]
                                    break

                        local_3ren = safe_float(boat_data.get('local_in3rd', boat_data.get('local_3ren', 30.0 + (b * 1.5))), 35.0)
                        ave_st = safe_float(boat_data.get('aveST', boat_data.get('st', 0.15 + (b * 0.01))), 0.18)
                        course_rate = safe_float(boat_data.get(f"course_{assigned_course}_2nd_rate", boat_data.get('course_2nd_rate', 30.0 + (assigned_course * 2.0))), 35.0)
                        motor_rate = safe_float(boat_data.get('motor_2nd_rate', boat_data.get('motor', 30.0 + (b * 1.2))), 35.0)
                        boat_rate = safe_float(boat_data.get('boat_2nd_rate', boat_data.get('boat', 30.0 + (b * 0.8))), 35.0)
                        national_win = safe_float(boat_data.get('national_win_rate', boat_data.get('win_rate', 5.0 + (b * 0.1))), 5.5)
                        national_2nd = safe_float(boat_data.get('national_2nd_rate', boat_data.get('rate_2nd', 30.0 + (b * 1.0))), 35.0)
                        
                        rank_raw = str(boat_data.get('racer_class', boat_data.get('rank', 'B1')))
                        rank_match = re.search(r'(A[12]|B[12])', rank_raw.upper())
                        rank_str = rank_match.group(1) if rank_match else 'B1'
                        rank_map = {'A1': 4.0, 'A2': 3.0, 'B1': 2.0, 'B2': 1.0}
                        racer_rank_score = rank_map.get(rank_str, 2.0)
                        
                        kimarite_type = str(boat_data.get('primary_kimarite', boat_data.get('kimarite', 'normal')))
                        if kimarite_type in ['makuri', 'tsuki_makuri'] and assigned_course in [4, 5, 6]:
                            kimarite_score = 45.0
                        elif kimarite_type == 'sashi' and assigned_course in [2, 3]:
                            kimarite_score = 45.0
                        elif kimarite_type == 'nige' and assigned_course == 1:
                            kimarite_score = 50.0
                        else:
                            kimarite_score = 35.0 + (assigned_course * 1.0)

                        exh_time = safe_float(jb_boat_data.get('exhibition_time', jb_boat_data.get('exh_time', 6.70 + (b * 0.02))), 6.75)
                        turn_time = safe_float(jb_boat_data.get('turn_time', 6.70 + (b * 0.01)), 6.75)
                        
                        t_l3 += local_3ren
                        t_st += ave_st
                        t_cr += course_rate
                        t_kim += kimarite_score
                        t_mot += motor_rate
                        t_bot += boat_rate
                        t_rnk += racer_rank_score
                        t_exh += exh_time
                        t_turn += turn_time
                        t_nat_win += national_win
                        t_nat_2nd += national_2nd
                    
                    race_combos.append({
                        'combo': combo,
                        'avg_l3': t_l3 / 3,
                        'avg_st': t_st / 3,
                        'avg_cr': t_cr / 3,
                        'avg_kim': t_kim / 3,
                        'avg_motor': t_mot / 3,
                        'avg_boat': t_bot / 3,
                        'avg_rank': t_rnk / 3,
                        'exh_time': t_exh / 3,
                        'turn_time': t_turn / 3,
                        'water_type': water_val + (int(combo[0]) * 0.01),
                        'in_rate': in_rate_val,
                        'national_win_rate': t_nat_win / 3,
                        'national_2nd_rate': t_nat_2nd / 3,
                        'wind_speed': wind_speed + (int(combo[0]) * 0.1),
                        'is_headwind': is_headwind,
                        'is_tailwind': is_tailwind,
                        'grade_score': grade_score,
                        'is_rough_sign': is_rough_sign
                    })
                
                if race_combos:
                    cache_data.append({
                        'date': date_str,
                        'stadium': stadium,
                        'rno': rno,
                        'actual_win': actual_win,
                        'combos': race_combos
                    })
                
        current_date += timedelta(days=1)

    print(f"✅ 全場データ取得完了: {len(cache_data)}レース")
    return cache_data

def run_optimization(cache_data):
    print("🤖 [3/5] 全場データでモデル訓練を実行中...")
    
    dataset = []
    for race in cache_data:
        actual_win = race['actual_win']
        for bet in race['combos']:
            dataset.append({
                'combo': bet['combo'],
                'local_3ren': bet['avg_l3'],
                'st': bet['avg_st'],
                'course': bet['avg_cr'],
                'kimarite': bet['avg_kim'],
                'motor': bet['avg_motor'],
                'boat': bet['avg_boat'],
                'racer_rank': bet['avg_rank'],
                'wind_speed': bet['wind_speed'],
                'is_headwind': bet['is_headwind'],
                'is_tailwind': bet['is_tailwind'],
                'exh_time': bet['exh_time'],
                'turn_time': bet['turn_time'],
                'water_type': bet['water_type'],
                'in_rate': bet['in_rate'],
                'national_win_rate': bet['national_win_rate'],
                'national_2nd_rate': bet['national_2nd_rate'],
                'grade_score': bet['grade_score'],
                'is_rough_sign': bet['is_rough_sign'],
                'is_win': 1 if bet['combo'] == actual_win else 0
            })
            
    df = pd.DataFrame(dataset)
    if len(df) == 0:
        print("❌ 学習データが空です。")
        return

    print("\n📊 【データの中身の確認 (describe)】")
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(df.describe())
    print("------------------------------------\n")

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
    
    model = lgb.LGBMClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.01,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbose=-1
    )
    model.fit(X, y)
    
    model.booster_.save_model('model.txt')
    print("✅ 学習完了: 全場対応モデルを 'model.txt' として保存しました。")

    print("\n📊 【特徴量重要度ランキング（Gainベース）】")
    importance = model.booster_.feature_importance(importance_type='gain')
    importance_df = pd.DataFrame({
        'feature': features,
        'importance': importance
    }).sort_values(by='importance', ascending=False)
    print(importance_df.to_string(index=False))
    print("--------------------------------------------------\n")

if __name__ == "__main__":
    end_d = date.today() - timedelta(days=1)
    start_d = end_d - timedelta(days=1)  # まずは昨日1日分だけでテスト
    
    cache_data = fetch_recent_races(start_d, end_d)
    run_optimization(cache_data)
    print("🚀 [5/5] パイプライン終了")

