import sys
import os

# scikit-learnの自動チェック＆インストール
try:
    import sklearn
except ImportError:
    print("📦 scikit-learnをインストールしています...")
    os.system(f"{sys.executable} -m pip install scikit-learn")

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

from datetime import date, timedelta
import re
import pandas as pd
import lightgbm as lgb

try:
    from pyjpboatrace import PyJPBoatrace
except Exception as e:
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

FEATURES = [
    'local_3ren', 'st', 'course', 'kimarite', 
    'motor', 'boat', 'racer_rank', 
    'wind_speed', 'is_headwind', 'is_tailwind',
    'exh_time', 'turn_time', 'water_type', 'in_rate',
    'national_win_rate', 'national_2nd_rate',
    'grade_score', 'is_rough_sign'
]

def safe_float(val, default=0.0):
    if val is None:
        return default
    val_str = str(val).replace('m', '').replace('%', '').strip()
    if val_str in ['', '-', 'ー']:
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

                weather_info = just_before.get('weather_information', {}) if isinstance(just_before, dict) else {}
                wind_speed = safe_float(weather_info.get('wind_speed', race_info.get('wind_speed', 2.0)), 2.0)
                is_rough_sign = 1 if wind_speed >= trait.get('wind_limit_rough', 4.0) else 0

                wind_dir_raw = weather_info.get('wind_direction', weather_info.get('direction', ''))
                wind_dir_str = str(wind_dir_raw)
                
                is_headwind = 1 if ('向' in wind_dir_str or 'head' in wind_dir_str.lower() or wind_dir_raw in [9, 10, 11]) else 0
                is_tailwind = 1 if ('追' in wind_dir_str or 'tail' in wind_dir_str.lower() or wind_dir_raw in [1, 2, 15, 16]) else 0

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
                        boat_data = race_info.get(f"boat{b}", {}) if isinstance(race_info, dict) else {}
                        jb_boat_data = just_before.get(f"boat{b}", {}) if isinstance(just_before, dict) else {}

                        local_3ren = safe_float(boat_data.get('local_in3rd', 35.0), 35.0)
                        ave_st = safe_float(boat_data.get('aveST', 0.18), 0.18)
                        course_rate = safe_float(boat_data.get(f"course_{assigned_course}_2nd_rate", 35.0), 35.0)
                        motor_rate = safe_float(boat_data.get('motor_2nd_rate', 35.0), 35.0)
                        boat_rate = safe_float(boat_data.get('boat_2nd_rate', 35.0), 35.0)
                        national_win = safe_float(boat_data.get('national_win_rate', 5.5), 5.5)
                        national_2nd = safe_float(boat_data.get('national_2nd_rate', 35.0), 35.0)
                        
                        rank_raw = str(boat_data.get('racer_class', 'B1'))
                        rank_match = re.search(r'(A[12]|B[12])', rank_raw.upper())
                        rank_str = rank_match.group(1) if rank_match else 'B1'
                        racer_rank_score = {'A1': 4.0, 'A2': 3.0, 'B1': 2.0, 'B2': 1.0}.get(rank_str, 2.0)
                        
                        kimarite_type = str(boat_data.get('primary_kimarite', 'normal'))
                        if kimarite_type in ['makuri', 'tsuki_makuri'] and assigned_course in [4, 5, 6]:
                            kimarite_score = 45.0
                        elif kimarite_type == 'sashi' and assigned_course in [2, 3]:
                            kimarite_score = 45.0
                        elif kimarite_type == 'nige' and assigned_course == 1:
                            kimarite_score = 50.0
                        else:
                            kimarite_score = 35.0 + (assigned_course * 1.0)

                        exh_time = safe_float(jb_boat_data.get('exhibition_time', 6.75), 6.75)
                        turn_time = safe_float(jb_boat_data.get('turn_time', 6.75), 6.75)
                        
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
                        'date': date_str,
                        'stadium': stadium,
                        'rno': rno,
                        'combo': combo,
                        'local_3ren': t_l3 / 3,
                        'st': t_st / 3,
                        'course': t_cr / 3,
                        'kimarite': t_kim / 3,
                        'motor': t_mot / 3,
                        'boat': t_bot / 3,
                        'racer_rank': t_rnk / 3,
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
                        'is_rough_sign': is_rough_sign,
                        'target': 1 if combo == actual_win else 0
                    })
                
                if race_combos:
                    cache_data.extend(race_combos)
                
        current_date += timedelta(days=1)

    return cache_data

def main():
    print("=== 学習パイプライン開始（データ蓄積 & LambdaRank版） ===")
    
    target_date = date.today() - timedelta(days=1)
    new_records = fetch_recent_races(target_date, target_date)
    new_df = pd.DataFrame(new_records)
    
    csv_path = "dataset.csv"
    
    if os.path.exists(csv_path):
        try:
            existing_df = pd.read_csv(csv_path)
            if len(new_df) > 0:
                df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['date', 'stadium', 'rno', 'combo']).reset_index(drop=True)
            else:
                df = existing_df
        except Exception:
            print("⚠️ 既存CSVの破損を検知したため新規作成します。")
            df = new_df
    else:
        df = new_df
        
    if len(df) == 0:
        print("❌ 学習データが空です。処理を終了します。")
        return

    df.to_csv(csv_path, index=False)
    print(f"💾 累計データセット保存完了: 総行数 {len(df)} 行")

    df = df.sort_values(by=['date', 'stadium', 'rno']).reset_index(drop=True)
    group = df.groupby(['date', 'stadium', 'rno'], sort=False).size().values

    X_train = df[FEATURES]
    y_train = df['target']
    
    model = lgb.LGBMRanker(
        objective="lambdarank",
        metric="ndcg",
        n_estimators=500,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42
    )
    
    model.fit(X_train, y_train, group=group)
    model.booster_.save_model('model.txt')
    
    print("=== 学習パイプライン完了！ model.txt を更新しました ===")

if __name__ == '__main__':
    main()

