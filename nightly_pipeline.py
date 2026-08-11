import os
import re
import requests
import pandas as pd
import lightgbm as lgb
from datetime import date, timedelta

try:
    from pyjpboatrace import PyJPBoatrace
except Exception as e:
    print(f"❌ PyJPBoatrace 読み込み失敗: {e}")

# --- ヘルパー関数 ---
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
            print(f"⚠️ Discord通知失敗: {response.text}")
    except Exception as e:
        print(f"⚠️ Discord通知エラー: {e}")

def get_factor_score(boat_data, assigned_course):
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

    return local_3ren, ave_st, course_record_score, kimarite_score, motor_rate, boat_rate, racer_rank_score

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
    'wind_speed', 'is_headwind', 'is_tailwind'
]

def nightly_summary_main():
    boatrace = PyJPBoatrace()
    today = date.today()
    model_path = 'model.txt'
    
    if not os.path.exists(model_path):
        send_discord_notification("⚠️ 夜間まとめ: モデルファイルが見つかりません。")
        return

    model = lgb.Booster(model_file=model_path)
    
    try:
        stadiums_info = boatrace.get_stadiums(today)
    except Exception as e:
        print(f"会場情報取得エラー: {e}")
        return

    target_stadiums = []
    # フィルターを外して本日の全開催場を対象にする
    for s_name, info in stadiums_info.items():
        if s_name == 'date':
            continue
        code = STADIUM_MAP.get(s_name)
        if code:
            title = info.get('title', '')
            target_stadiums.append((code, s_name, title))

    total_races = 0
    hit_count = 0
    max_odds_hit = 0.0
    miss_ranks = []

    print("📊 本日のレース結果集計を開始します...")

    for stadium_code, s_name, title in target_stadiums:
        s_code_int = int(stadium_code)
        for r_no in range(1, 13):
            try:
                odds_info = boatrace.get_odds_trifecta(d=today, stadium=s_code_int, race=r_no)
                race_info = boatrace.get_race_info(d=today, stadium=s_code_int, race=r_no)
                result_info = boatrace.get_race_result(d=today, stadium=s_code_int, race=r_no)
                
                if not odds_info or not race_info or not result_info:
                    continue
                
                actual_win = extract_trifecta_result(result_info)
                if not actual_win:
                    continue
                
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
                    try:
                        boats = [int(b) for b in combo.split('-')]
                    except:
                        continue
                    
                    t_l3, t_st, t_cr, t_kim, t_mot, t_bot, t_rnk = 0, 0, 0, 0, 0, 0, 0
                    for idx, b in enumerate(boats):
                        c_no = idx + 1
                        b_data = race_info.get(f"boat{b}", {})
                        l3, st, cr, kim, mot, bot, rnk = get_factor_score(b_data, c_no)
                        t_l3 += l3; t_st += st; t_cr += cr; t_kim += kim; t_mot += mot; t_bot += bot; t_rnk += rnk
                    
                    race_combos.append({
                        'combo': combo, 'odds': odds_val,
                        'local_3ren': t_l3/3, 'st': t_st/3, 'course': t_cr/3,
                        'kimarite': t_kim/3, 'motor': t_mot/3, 'boat': t_bot/3,
                        'racer_rank': t_rnk/3, 'wind_speed': wind_speed,
                        'is_headwind': is_headwind, 'is_tailwind': is_tailwind
                    })
                
                if not race_combos:
                    continue
                
                df_test = pd.DataFrame(race_combos)
                df_test['pred_prob'] = model.predict(df_test[FEATURES])
                
                filtered_base = df_test[(df_test['odds'] >= 5.0) & (df_test['odds'] <= 200.0)]
                if len(filtered_base) == 0:
                    filtered_base = df_test
                sorted_base = filtered_base.sort_values('pred_prob', ascending=False).reset_index(drop=True)
                
                if len(sorted_base) >= 2:
                    if sorted_base.loc[0, 'pred_prob'] > 0.12 or (sorted_base.loc[0, 'pred_prob'] - sorted_base.loc[1, 'pred_prob']) > 0.03:
                        sub_f = sorted_base[sorted_base['odds'] <= 50.0]
                        n_picks = 3 if len(sub_f) >= 3 else len(sorted_base)
                    else:
                        n_picks = 4
                else:
                    n_picks = min(3, len(sorted_base))
                
                top_picks = sorted_base.head(n_picks)['combo'].values
                
                total_races += 1
                all_sorted = df_test.sort_values('pred_prob', ascending=False).reset_index(drop=True)
                matched = all_sorted[all_sorted['combo'] == actual_win]
                
                if not matched.empty:
                    r_idx = matched.index[0] + 1
                    if actual_win in top_picks:
                        hit_count += 1
                        win_odds = matched.iloc[0]['odds']
                        if win_odds > max_odds_hit:
                            max_odds_hit = win_odds
                    else:
                        miss_ranks.append(r_idx)
            except Exception as e:
                continue

    accuracy = (hit_count / total_races * 100) if total_races > 0 else 0.0
    avg_miss_rank = (sum(miss_ranks) / len(miss_ranks)) if miss_ranks else 0.0
    
    summary_msg = (
        f"📊 **【本日のAI予測・結果まとめ】**\n"
        f"• 対象レース数: {total_races}R\n"
        f"• 的中数: {hit_count}R (的中率: {accuracy:.1f}%)\n"
        f"• 最高的中配当: {max_odds_hit:.1f}倍\n"
        f"• 外れレース時の正解の平均AI評価順位: 約 {avg_miss_rank:.1f}位\n"
        f"  *(※惜しい順位にいたかどうかの指標です)*"
    )
    send_discord_notification(summary_msg)

if __name__ == '__main__':
    nightly_summary_main()

