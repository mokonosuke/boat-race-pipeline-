import os
import requests
import pandas as pd
import lightgbm as lgb
from datetime import date
import traceback
import sys

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
    '11': {'water_type': 0.0, 'in_rate': 0.45}, '12': {'water_type': 1.0, 'in_rate': 0.55},
    '13': {'water_type': 1.0, 'in_rate': 0.55}, '14': {'water_type': 1.0, 'in_rate': 0.45},
    '15': {'water_type': 1.0, 'in_rate': 0.50}, '16': {'water_type': 1.0, 'in_rate': 0.45},
    '17': {'water_type': 1.0, 'in_rate': 0.50}, '18': {'water_type': 1.0, 'in_rate': 0.60},
    '19': {'water_type': 1.0, 'in_rate': 0.55}, '20': {'water_type': 1.0, 'in_rate': 0.50},
    '21': {'water_type': 1.0, 'in_rate': 0.60}, '22': {'water_type': 0.5, 'in_rate': 0.45},
    '23': {'water_type': 1.0, 'in_rate': 0.55}, '24': {'water_type': 1.0, 'in_rate': 0.60}
}

# --- 特徴量スコア計算（展示タイムの相対評価対応） ---
def get_factor_score(boat_data, assigned_course, stadium_code, race_avg_exh):
    local_3ren = safe_float(boat_data.get('local_in3rd', 0.0), 0.0)
    ave_st = safe_float(boat_data.get('aveST', 0.20), 0.20)
    course_key = f"course_{assigned_course}_2nd_rate"
    course_record_score = safe_float(boat_data.get(course_key, 30.0), 30.0)
    motor_rate = safe_float(boat_data.get('motor_2nd_rate', 30.0), 30.0)
    boat_rate = safe_float(boat_data.get('boat_2nd_rate', 30.0), 30.0)
    
    national_win = safe_float(boat_data.get('national_win_rate', 5.0), 5.0)
    national_2nd = safe_float(boat_data.get('national_2nd_rate', 30.0), 30.0)
    
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

    raw_exh = safe_float(boat_data.get('exhibition_time', 6.80), 6.80)
    # 展示タイムの相対評価（レース平均との差分：マイナスであるほど速い）
    exh_time = raw_exh - race_avg_exh
    
    turn_time = safe_float(boat_data.get('turn_time', 6.80), 6.80)
    
    s_key = str(stadium_code).zfill(2)
    trait = STADIUM_TRAITS.get(s_key, {'water_type': 0.5, 'in_rate': 0.5})

    return (local_3ren, ave_st, course_record_score, kimarite_score, 
            motor_rate, boat_rate, racer_rank_score, exh_time, turn_time, 
            trait['water_type'], trait['in_rate'], national_win, national_2nd)

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
    'exh_time', 'turn_time', 'water_type', 'in_rate',
    'national_win_rate', 'national_2nd_rate'
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
        exacta_odds_info = boatrace.get_odds_exacta_quinella(d=today, stadium=stadium_code, race=race_no)
        race_info = boatrace.get_race_info(d=today, stadium=stadium_code, race=race_no)
        
        if not odds_info or not race_info:
            return f"⚠️ 会場コード: {target_stadium} / 第{target_race_no}R のデータまたはオッズが取得できませんでした。"
        
        # レース全体の平均展示タイムを算出（相対評価用）
        exh_list = []
        for b_idx in range(1, 7):
            b_data = race_info.get(f"boat{b_idx}", {})
            if isinstance(b_data, dict):
                et = safe_float(b_data.get('exhibition_time', 0.0), 0.0)
                if et > 0:
                    exh_list.append(et)
        race_avg_exh = sum(exh_list) / len(exh_list) if exh_list else 6.80
        
        wind_speed = safe_float(race_info.get('wind_speed', 0.0), 0.0)
        wind_dir = str(race_info.get('wind_direction', ''))

        is_headwind = 1 if ('向' in wind_dir or '向かい風' in wind_dir) else 0
        is_tailwind = 1 if ('追' in wind_dir or '追い風' in wind_dir) else 0

        race_combos = []
        exacta_trifecta_odds = {}

        for combo, odds in odds_info.items():
            if not isinstance(combo, str) or '-' not in combo:
                continue
            odds_val = safe_float(odds, 0.0)
            if odds_val <= 0:
                continue
            
            parts = combo.split('-')
            if len(parts) == 3:
                ex_combo = f"{parts[0]}-{parts[1]}"
                if ex_combo not in exacta_trifecta_odds:
                    exacta_trifecta_odds[ex_combo] = []
                exacta_trifecta_odds[ex_combo].append(odds_val)
            
            min_odds = 3.0 if combo.startswith('1-') else 5.0
            if not (min_odds <= odds_val <= 200.0):
                continue
            
            try:
                boats = [int(b) for b in parts]
            except (ValueError, TypeError):
                continue
            
            t_l3, t_st, t_cr, t_kim, t_mot, t_bot, t_rnk, t_exh, t_turn = 0, 0, 0, 0, 0, 0, 0, 0, 0
            t_nat_win, t_nat_2nd = 0, 0
            water_val, in_rate_val = 0.5, 0.5
            
            for idx, b in enumerate(boats):
                assigned_course = idx + 1
                boat_key = f"boat{b}"
                boat_data = race_info.get(boat_key, {})
                if not isinstance(boat_data, dict):
                    boat_data = {}
                
                l3, st, cr, kim, mot, bot, rnk, exh, turn, water, in_rate, nat_w, nat_2 = get_factor_score(boat_data, assigned_course, stadium_code, race_avg_exh)
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
                'is_tailwind': is_tailwind
            })
            
        if not race_combos:
            return f"⚠️ 会場コード: {target_stadium} / 第{target_race_no}R は有効な買い目条件に合うデータがありません。"
            
        df_test = pd.DataFrame(race_combos)
        X_test = df_test[FEATURES]
        
        preds = model.predict(X_test)
        df_test['pred_prob'] = preds
        df_test['ev'] = df_test['pred_prob'] * df_test['odds']
        
        # --- 各艇の1着予想確率の算出（1着予想軸の強化） ---
        boat_1st_probs = {}
        for b in range(1, 7):
            b_str = str(b)
            p_sum = df_test[df_test['combo'].str.startswith(b_str + '-')]['pred_prob'].sum()
            boat_1st_probs[b] = p_sum

        # --- 3連単の選出 ---
        valid_trifecta = df_test[df_test['ev'] >= 1.0]
        if valid_trifecta.empty:
            valid_trifecta = df_test
        top_picks_df = valid_trifecta.sort_values(by='pred_prob', ascending=False).head(4)

        CONFIDENCE_THRESHOLD = 0.12
        top_prob = top_picks_df.iloc[0]['pred_prob'] if not top_picks_df.empty else 0.0
        is_trifecta_confident = top_prob >= CONFIDENCE_THRESHOLD

        # --- 2連単の選出（2連単重視・軸のステップアップ） ---
        df_test['exacta_combo'] = df_test['combo'].apply(lambda x: '-'.join(x.split('-')[:2]))
        exacta_prob_df = df_test.groupby('exacta_combo')['pred_prob'].sum().reset_index()
        
        exacta_list = []
        for _, row in exacta_prob_df.iterrows():
            ex_combo = row['exacta_combo']
            prob = row['pred_prob']
            
            odds_val = 0.0
            if exacta_odds_info and isinstance(exacta_odds_info, dict):
                for k, v in exacta_odds_info.items():
                    if k.replace('=', '-') == ex_combo or k == ex_combo:
                        odds_val = safe_float(v, 0.0)
                        break
            
            if odds_val <= 0 and ex_combo in exacta_trifecta_odds:
                odds_list = exacta_trifecta_odds[ex_combo]
                if odds_list:
                    inv_sum = sum(1.0 / o for o in odds_list if o > 0)
                    if inv_sum > 0:
                        odds_val = 1.0 / inv_sum
            
            ev = prob * odds_val if odds_val > 0 else 0.0
            exacta_list.append({
                'exacta_combo': ex_combo,
                'odds': odds_val,
                'pred_prob': prob,
                'ev': ev
            })

        df_exacta = pd.DataFrame(exacta_list)
        top_exacta_df = pd.DataFrame()
        if not df_exacta.empty:
            top_exacta_df = df_exacta.sort_values(by='pred_prob', ascending=False).head(2)

        strategy_name = f"17特徴量（展示相対評価・2連単/1着軸強化）"
        
        lines = [f"🎯 **【直前予測・{strategy_name}】 会場コード: {target_stadium} / 第{target_race_no}R**"]
        
        # 1着予想確率の表示
        lines.append("\n**【各艇の1着予想確率】**")
        for b in range(1, 7):
            p = boat_1st_probs.get(b, 0.0)
            lines.append(f"• {b}号艇: {p*100:.1f}%")

        # 2連単を上位に配置（2連単軸のステップアップ）
        if not top_exacta_df.empty:
            lines.append("\n**【2連単 推奨買い目】**")
            for _, row in top_exacta_df.iterrows():
                odds_text = f"{row['odds']:.1f}倍" if row['odds'] > 0 else "算出中"
                lines.append(f"• **{row['exacta_combo']}** (オッズ: {odds_text} / 予測確率: {row['pred_prob']*100:.1f}%)")

        if not is_trifecta_confident:
            lines.append(f"\n🛑 *(※3連単の最高確率が {top_prob*100:.1f}% と低いため、3連単勝負は見送り推奨)*")
            lines.append("**【3連単 参考買い目】**")
        else:
            lines.append("\n**【3連単 推奨買い目】**")

        for _, row in top_picks_df.iterrows():
            lines.append(f"• **{row['combo']}** (オッズ: {row['odds']:.1f}倍 / 予測確率: {row['pred_prob']*100:.1f}%)")
            
        return "\n".join(lines)

    except Exception as e:
        error_msg = traceback.format_exc()
        raise Exception(f"推論処理中にエラーが発生しました: {e}\n{error_msg}")

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
    silent_mode = (os.environ.get('SILENT_MODE', 'false').lower() == 'true')

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
                        if res:
                            if not silent_mode:
                                send_discord_notification(res)
                            total_success += 1
                    else:
                        print("⚠️ モデルファイルが存在しないため、推論をスキップしました。")
            
            if total_success > 0:
                print(f"☀️ 自動予測完了（計 {total_success} レース処理）")
                
        except Exception as e:
            err_msg = f"⚠️ 自動判定処理で致命的なエラーが発生しました: {e}"
            print(err_msg)
            send_discord_notification(err_msg)
            sys.exit(1)
    else:
        target_stadium = parse_stadium(raw_stadium)
        if target_stadium:
            races_to_run = list(range(1, 13)) if str(target_race_no).upper() == 'AUTO' else [int(target_race_no)]
            
            for r_no in races_to_run:
                try:
                    if model is not None:
                        prediction_text = run_inference(model, target_stadium, r_no)
                        send_discord_notification(prediction_text)
                    else:
                        print("⚠️ モデルファイルが存在しないため、推論をスキップしました。")
                except Exception as e:
                    err_msg = f"⚠️ {target_stadium} 第{r_no}レースでエラー: {e}"
                    print(err_msg)
                    send_discord_notification(err_msg)
                    sys.exit(1)

if __name__ == '__main__':
    predict_main()
