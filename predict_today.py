import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

import os
from datetime import date, timedelta
import re
import pandas as pd
import lightgbm as lgb
import requests

from pyjpboatrace import PyJPBoatrace

# 24場の会場名から整数JCDへのマッピング辞書
NAME_TO_JCD = {
    "桐生": 1, "戸田": 2, "江戸川": 3, "平和島": 4, "多摩川": 5,
    "浜名湖": 6, "蒲郡": 7, "常滑": 8, "津": 9, "三国": 10,
    "びわこ": 11, "住之江": 12, "尼崎": 13, "鳴門": 14, "丸亀": 15,
    "児島": 16, "宮島": 17, "徳山": 18, "下関": 19, "若松": 20,
    "芦屋": 21, "福岡": 22, "唐津": 23, "大村": 24
}

# JCDから会場名への逆引き辞書を作成
JCD_TO_NAME = {v: k for k, v in NAME_TO_JCD.items()}

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# 狙いたいレースのキーワード（タイトルやグレードに含まれる判定用）
TARGET_KEYWORDS = ["SG", "G1", "ヴィーナス", "レディース", "プレミアムGI", "オールレディース"]

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
    print("📚 モデル訓練用の過去データを収集中...")
    boatrace = PyJPBoatrace()
    cache_data = []
    current_date = start_date
    
    for jcd in [11]: 
        while current_date <= end_date:
            for rno in range(1, 13):
                try:
                    odds_info = boatrace.get_odds_trifecta(d=current_date, stadium=jcd, race=rno)
                    race_info = boatrace.get_race_info(d=current_date, stadium=jcd, race=rno)
                    result_info = boatrace.get_race_result(d=current_date, stadium=jcd, race=rno)
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
                    
                    t_l3, t_st, t_cr, t_kim, t_mot, t_bot, t_rnk = 0, 0, 0, 0, 0, 0, 0
                    for idx, b in enumerate(boats):
                        l3, st, cr, kim, mot, bot, rnk = get_factor_score(race_info.get(f"boat{b}", {}), idx + 1)
                        t_l3 += l3; t_st += st; t_cr += cr; t_kim += kim; t_mot += mot; t_bot += bot; t_rnk += rnk
                    
                    race_combos.append({
                        'combo': combo, 'odds': odds_val,
                        'avg_l3': t_l3/3, 'avg_st': t_st/3, 'avg_cr': t_cr/3,
                        'avg_kim': t_kim/3, 'avg_motor': t_mot/3, 'avg_boat': t_bot/3, 'avg_rank': t_rnk/3
                    })
                if race_combos:
                    cache_data.append({'actual_win': actual_win, 'combos': race_combos})
            current_date += timedelta(days=1)
    return cache_data

def train_model(cache_data):
    print("🤖 AIモデルを訓練中...")
    dataset = []
    for race in cache_data:
        for bet in race['combos']:
            dataset.append({
                'local_3ren': bet['avg_l3'], 'st': bet['avg_st'], 'course': bet['avg_cr'],
                'kimarite': bet['avg_kim'], 'motor': bet['avg_motor'], 'boat': bet['avg_boat'],
                'racer_rank': bet['avg_rank'], 'odds': bet['odds'],
                'is_win': 1 if bet['combo'] == race['actual_win'] else 0
            })
    df = pd.DataFrame(dataset)
    features = ['local_3ren', 'st', 'course', 'kimarite', 'motor', 'boat', 'racer_rank', 'odds']
    model = lgb.LGBMClassifier(n_estimators=120, max_depth=4, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, random_state=42, verbose=-1)
    model.fit(df[features], df['is_win'])
    return model, features

def get_today_target_races(target_date):
    print(f"🎯 本日({target_date})の開催スケジュールから、対象グレードを探索中...")
    boatrace = PyJPBoatrace()
    target_races = []
    
    try:
        stadiums_info = boatrace.get_stadiums(target_date)
    except Exception as e:
        print(f"⚠️ 開催会場一覧の取得に失敗しました: {e}")
        return []
    
    for stadium_name, info in stadiums_info.items():
        if stadium_name == 'date' or not isinstance(info, dict):
            continue
            
        jcd = NAME_TO_JCD.get(stadium_name)
        if not jcd:
            continue
            
        title = str(info.get('title', ''))
        grades = [str(g).lower() for g in info.get('grade', [])]
        
        combined_text = f"{stadium_name} {title} {' '.join(grades)}"
        is_matched = any(kw.lower() in combined_text.lower() for kw in TARGET_KEYWORDS) or any(g in ['sg', 'g1', 'pg1'] for g in grades)
        
        if not is_matched:
            continue
            
        print(f"✨ 対象会場を発見: {stadium_name} (JCD: {jcd}) - タイトル: {title}")
        
        for rno in range(1, 13):
            try:
                odds_info = boatrace.get_odds_trifecta(d=target_date, stadium=jcd, race=rno)
                race_info = boatrace.get_race_info(d=target_date, stadium=jcd, race=rno)
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
                
                t_l3, t_st, t_cr, t_kim, t_mot, t_bot, t_rnk = 0, 0, 0, 0, 0, 0, 0
                for idx, b in enumerate(boats):
                    l3, st, cr, kim, mot, bot, rnk = get_factor_score(race_info.get(f"boat{b}", {}), idx + 1)
                    t_l3 += l3; t_st += st; t_cr += cr; t_kim += kim; t_mot += mot; t_bot += bot; t_rnk += rnk
                
                race_combos.append({
                    'combo': combo, 'odds': odds_val,
                    'local_3ren': t_l3/3, 'st': t_st/3, 'course': t_cr/3,
                    'kimarite': t_kim/3, 'motor': t_mot/3, 'boat': t_bot/3, 'racer_rank': t_rnk/3
                })
            if race_combos:
                target_races.append({'stadium': jcd, 'rno': rno, 'combos': race_combos})
                
    return target_races

if __name__ == "__main__":
    today = date.today()
    
    training_data = fetch_training_data(today - timedelta(days=15), today - timedelta(days=1))
    model, features = train_model(training_data)
    
    today_races = get_today_target_races(today)
    
    predictions = []
    for race in today_races:
        df_race = pd.DataFrame(race['combos'])
        if len(df_race) == 0: continue
        
        df_race['pred_prob'] = model.predict_proba(df_race[features])[:, 1]
        
        filtered = df_race[(df_race['odds'] >= 5.0) & (df_race['odds'] <= 60.0)]
        if len(filtered) == 0: continue
        
        best = filtered.loc[filtered['pred_prob'].idxmax()]
        predictions.append({
            'stadium': race['stadium'],
            'rno': race['rno'],
            'combo': best['combo'],
            'odds': best['odds'],
            'prob': best['pred_prob'] * 100
        })
    
    if predictions:
        lines = []
        for p in predictions:
            stadium_name = JCD_TO_NAME.get(p['stadium'], f"会場:{p['stadium']}")
            lines.append(f"・{stadium_name} 第{p['rno']}R: **{p['combo']}** (オッズ: {p['odds']}倍 / 期待度: {p['prob']:.1f}%)")
        msg = f"🎯 **【本日のSG/G1/女子戦 AI買い目配信】** ({today})\n" + "\n".join(lines)
    else:
        msg = f"🎯 **【本日のAI買い目配信】** ({today})\n本日は条件に一致する推奨レースはありませんでした（またはオッズ未確定）。"
        
    print(msg)
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg})

