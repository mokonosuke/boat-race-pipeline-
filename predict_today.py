import os
import re
import requests
import pandas as pd
import lightgbm as lgb
from datetime import date

try:
    from pyjpboatrace import PyJPBoatrace
except Exception as e:
    print(f"❌ PyJPBoatrace 読み込み失敗: {e}")

# --- 安全な数値変換用ヘルパー関数 ---
def safe_float(val, default=0.0):
    if val is None:
        return default
    val_str = str(val).replace('m', '').replace('%', '').strip()
    if val_str == '' or val_str == '-':
        return default
    try:
        return float(val_str)
    except (ValueError, TypeError):
        return default

# --- Discord通知関数 ---
def send_discord_notification(message):
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("⚠️ DISCORD_WEBHOOK_URL が設定されていません")
        return
    
    payload = {"content": message}
    try:
        response = requests.post(webhook_url, json=payload)
        if response.status_code in [200, 204]:
            print("💬 Discord通知を送信しました")
        else:
            print(f"⚠️ Discord通知の送信に失敗しました: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"⚠️ Discord通知でエラーが発生しました: {e}")

# --- 会場特性データ ---
STADIUM_TRAITS = {
    '01': {'water_type': 0.0, 'in_rate': 0.50}, '02': {'water_type': 0.0, 'in_rate': 0.40},
    '03': {'water_type': 0.5, 'in_rate': 0.40}, '04': {'water_type': 0.5, 'in_rate': 0.45},
    '05': {'water_type': 0.0, 'in_rate': 0.50}, '06': {'water_type': 1.0, 'in_rate': 0.50},
    '07': {'water_type': 1.0, 'in_rate': 0.55}, '08': {'water_type': 1.0, 'in_rate': 0.55},
    '09': {'water_type': 1.0, 'in_rate': 0.50}, '10': {'water_type': 0.0, 'in_rate': 0.45},
    '11': {'water_type': 0.0, 'in_rate': 0.45}, '12': {'water_type': 0.0, 'in_rate': 0.55},
    '13': {'water_type': 0.0, 'in_rate': 0.55}, '14': {'water_type': 1.0, 'in_rate': 0.45},
    '15': {'water_type': 1.0, 'in_rate': 0.50}, '16': {'water_type': 1.0, 'in_rate': 0.45},
    '17': {'water_type': 1.0, 'in_rate': 0.50}, '18': {'water_type': 1.0, 'in_rate': 0.60},
    '19': {'water_type': 1.0, 'in_rate': 0.55}, '20': {'water_type': 1.0, 'in_rate': 0.50},
    '21': {'water_type': 1.0, 'in_rate': 0.60}, '22': {'water_type': 0.5, 'in_rate': 0.45},
    '23': {'water_type': 1.0, 'in_rate': 0.55}, '24': {'water_type': 1.0, 'in_rate': 0.60}
}

# --- 特徴量スコア計算 ---
def get_factor_score(boat_data, assigned_course, stadium_code):
    local_3ren = safe_float(boat_data.get('local_in3rd', 0.0), 0.0)
    ave_st = safe_float(boat_data.get('aveST', 0.20), 0.20)
    course_key = f"course_{assigned_course}_2nd_rate"
    course_record_score = safe_float(boat_data.get(course_key, 30.0), 30.0)
    motor_rate = safe_float(boat_data.get('motor_2nd_rate', 30.0), 30.0)
    boat_rate = safe_float(boat_data.get('boat_2nd_rate', 30.0), 30.0)
    
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

    exh_time = safe_float(boat_data.get('exhibition_time', 6.80), 6.80)
    turn_time = safe_float(boat_data.get('turn_time', 6.80), 6.80)
    
    s_key = str(stadium_code).zfill(2)
    trait = STADIUM_TRAITS.get(s_key, {'water_type': 0.5, 'in_rate': 0.5})

    return local_3ren, ave_st, course_record_score, kimarite_score, motor_rate, boat_rate, racer_rank_score, exh_time, turn_time, trait['water_type'], trait['in_rate']

STADIUM_MAP = {
    '桐生': '01', '戸田': '02', '江戸川': '03', '平和島': '04', '多摩川': '05',
    '浜名湖': '06', '蒲郡': '07', '常滑': '08', '津': '09', '三国': '10',
    'びわこ': '11', '琵琶湖': '11', '住之江': '12', '尼崎': '13', '鳴門': '14',
    '丸亀': '15', '児島': '16', '宮島': '17', '徳山': '18', '下関': '19',
    '若松': '20', '芦屋': '21', '福岡': '22', '唐津': '23', '大村': '24'
}

FEATURES = [
    'local_3ren', 'st', 'course', 'kimarite', 
    'motor', 'boat', 'racer_rank', 'odds',
    'wind_speed', 'is_headwind', 'is_tailwind',
    'exh_time', 'turn_time', 'water_type', 'in_rate'
]

def parse_stadium(stadium_input):
    stadium_input = str(stadium_input).strip()
    if stadium_input.isdigit():
        return stadium_input.zfill(2)
    if stadium_input in STADIUM_MAP:
        return STADIUM_MAP[stadium_input]
    for name, code in STADIUM_MAP.items():
        if name in stadium_input:
            return code
    return '11'

def run_inference(model, target_stadium, target_race_no):
    try:
        boatrace = PyJPBoatrace()
        today = date.today()
        
        stadium_code = int(target_stadium)
        race_no = int(target_race_no)
        
        odds_info = boatrace.get_odds_trifecta(d=today, stadium=stadium_code, race=race_no)
        race_info = boatrace.get_race_info(d=today, stadium=stadium_code, race=race_no)
        
        if not odds_info or not race_info:
            return f"⚠️ 会場コード: {target_stadium} / 第{target_race_no}R のデータまたはオッズが取得できませんでした。"
        
        wind_speed = safe_float(race_info.get('wind_speed', 0.0), 0.0)
        wind_dir = str(race_info.get('wind_direction', ''))

        is_headwind = 1 if ('向' in wind_dir or '向かい風' in wind_dir) else 0
        is_tailwind = 1 if ('追' in wind_dir or '追い風' in wind_dir) else 0

        race_combos = []
        for combo, odds in odds_info.items():
            if not isinstance(combo, str) or '-' not in combo:
                continue
            odds_val = safe_float(odds, 0.0)
            if odds_val <= 0:
                continue
            
            min_odds = 3.0 if combo.startswith('1-') else 5.0
            if not (min_odds <= odds_val <= 200.0):
                continue
            
            try:
                boats = [int(b) for b in combo.split('-')]
            except (ValueError, TypeError):
                continue
            
            t_l3, t_st, t_cr, t_kim, t_mot, t_bot, t_rnk, t_exh, t_turn = 0, 0, 0, 0, 0, 0, 0, 0, 0
            water_val, in_rate_val = 0.5, 0.5
            
            for idx, b in enumerate(boats):
                assigned_course = idx + 1
                boat_key = f"boat{b}"
                boat_data = race_info.get(boat_key, {})
                l3, st, cr, kim, mot, bot, rnk, exh, turn, water, in_rate = get_factor_score(boat_data, assigned_course, stadium_code)
                t_l3 += l3
                t_st += st
                t_cr += cr
                t_kim += kim
                t_mot += mot
                t_bot += bot
                t_rnk += rnk
                t_exh += exh
                t_turn += turn
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
                'wind_speed': wind_speed,
                'is_headwind': is_headwind,
                'is_tailwind': is_tailwind
            })
            
        if not race_combos:
            return f"⚠️ 会場コード: {target_stadium} / 第{target_race_no}R は有効な買い目条件に合うデータがありません。"
            
        df_test = pd.DataFrame(race_combos)
        X_test = df_test[FEATURES]
        
        preds = model.predict(X_test)
        df_test['pred_prob'] = preds
        
        df_test['ev'] = df_test['pred_prob'] * df_test['odds']
        sorted_df = df_test.sort_values('ev', ascending=False).reset_index(drop=True)
        
        if sorted_df.empty:
            return f"⚠️ 会場コード: {target_stadium} / 第{target_race_no}R は有効な予測データがありません。"
        
        # 期待値 1.0 以上 ＆ 予測確率 1%以上 の条件を満たし、かつ最大8点までに制限
        top_picks_df = sorted_df[(sorted_df['ev'] >= 1.0) & (sorted_df['pred_prob'] >= 0.01)].head(8)
        if top_picks_df.empty:
            top_picks_df = sorted_df.head(2)

        strategy_name = f"15特徴量・期待値ベース（確率1%以上・最大8点・{len(top_picks_df)}点選出）"
        
        lines = [f"🎯 **【直前予測・{strategy_name}】 会場コード: {target_stadium} / 第{target_race_no}R**"]
        for _, row in top_picks_df.iterrows():
            lines.append(f"• 推奨買い目: **{row['combo']}** (オッズ: {row['odds']:.1f}倍 / 期待値: {row['ev']:.2f})")
            
        return "\n".join(lines)

    except Exception as e:
        return f"⚠️ 推論処理中にエラーが発生しました: {e}"

def predict_main():
    raw_stadium = os.environ.get('INPUT_STADIUM', 'AUTO').strip()
    target_race_no = os.environ.get('INPUT_RACE_NO', 'AUTO').strip()

    model_path = 'model.txt'
    model = None
    if os.path.exists(model_path):
        model = lgb.Booster(model_file=model_path)
    else:
        print(f"⚠️ 警告: モデルファイル '{model_path}' が見つかりません。")

    boatrace = PyJPBoatrace()
    today = date.today()

    is_auto = (raw_stadium.upper() == 'AUTO' or not raw_stadium) and (str(target_race_no).upper() == 'AUTO' or not target_race_no)

    if is_auto:
        try:
            stadiums_info = boatrace.get_stadiums(today)
            target_stadiums = []
            
            for s_name, info in stadiums_info.items():
                if s_name == 'date':
                    continue
                code = STADIUM_MAP.get(s_name)
                if code:
                    target_stadiums.append((code, s_name))
            
            if not target_stadiums:
                print("ℹ️ 本日開催のレース場はありません。")
                return
                
            total_success = 0
            for stadium_code, s_name in target_stadiums:
                print(f"🔍 処理中: {s_name}")
                
                for r_no in range(1, 13):
                    if model is not None:
                        res = run_inference(model, stadium_code, r_no)
                        if res and not res.startswith("⚠️"):
                            total_success += 1
                    else:
                        print("⚠️ モデルファイルが存在しないため、推論をスキップしました。")
            
            if total_success > 0:
                send_discord_notification(f"☀️ **【自動予測完了】** 本日の全会場・全レースのAI予測データ（15特徴量対応）の作成が完了しました！（計 {total_success} レース処理）")
                
        except Exception as e:
            send_discord_notification(f"⚠️ 自動判定処理でエラーが発生しました: {e}")
    else:
        target_stadium = parse_stadium(raw_stadium)
        if target_stadium:
            races_to_run = list(range(1, 13)) if str(target_race_no).upper() == 'AUTO' else [int(target_race_no)]
            
            for r_no in races_to_run:
                start_msg = f"=== 【予測開始】 会場コード:{target_stadium} 第{r_no}レース ==="
                print(start_msg)
                
                if model is not None:
                    prediction_text = run_inference(model, target_stadium, r_no)
                else:
                    prediction_text = "⚠️ モデルファイルが存在しないため、推論をスキップしました。"
                    
                send_discord_notification(prediction_text)

if __name__ == '__main__':
    predict_main()
