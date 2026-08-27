import os
import requests
import pandas as pd
import lightgbm as lgb
from datetime import date
import sys
import itertools
import numpy as np

# --- PyJPBoatraceの読み込み ---
try:
    from pyjpboatrace import PyJPBoatrace
except Exception as e:
    print(f"❌ PyJPBoatrace 読み込み失敗: {e}")

# --- 安全な数値変換用ヘルパー関数 ---
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

# --- Discord通知関数（サイレントモード対応版） ---
def send_discord_notification(message):
    silent_mode = os.environ.get("SILENT_MODE", "false").lower() == "true"
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    if silent_mode or event_name == "schedule":
        print("🤫 サイレントモードまたは定期実行のためDiscord通知をスキップしました")
        return
        
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("⚠️ DISCORD_WEBHOOK_URL が設定されていません")
        return
    try:
        response = requests.post(webhook_url, json={"content": message})
        if response.status_code in [200, 204]:
            print("💬 Discord通知を送信しました")
        else:
            print(f"⚠️ Discord通知送信失敗: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"⚠️ Discord通知エラー: {e}")

# --- 会場特性データ ---
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

STADIUM_MAP = {
    '桐生': '01', '戸田': '02', '江戸川': '03', '平和島': '04', '多摩川': '05',
    '浜名湖': '06', '蒲郡': '07', '常滑': '08', '津': '09', '三国': '10',
    'びわこ': '11', '琵琶湖': '11', '住之江': '12', '尼崎': '13', '鳴門': '14',
    '丸亀': '15', '児島': '16', '宮島': '17', '徳山': '18', '下関': '19',
    '若松': '20', '芦屋': '21', '福岡': '22', '唐津': '23', '大村': '24'
}

CODE_TO_STADIUM = {v: k for k, v in STADIUM_MAP.items()}

# --- 特徴量スコア算出 ---
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
    exh_time = raw_exh - race_avg_exh
    turn_time = safe_float(boat_data.get('turn_time', 6.80), 6.80)
    
    s_key = str(stadium_code).zfill(2)
    trait = STADIUM_TRAITS.get(s_key, {'water_type': 0.5, 'in_rate': 0.5, 'wind_limit_rough': 4.0})

    return (local_3ren, ave_st, course_record_score, kimarite_score, 
            motor_rate, boat_rate, racer_rank_score, exh_time, turn_time, 
            trait['water_type'], trait['in_rate'], national_win, national_2nd)

# ★ 18個の特徴量リスト（オッズ除外）
FEATURES = [
    'local_3ren', 'st', 'course', 'kimarite', 
    'motor', 'boat', 'racer_rank', 
    'wind_speed', 'is_headwind', 'is_tailwind',
    'exh_time', 'turn_time', 'water_type', 'in_rate',
    'national_win_rate', 'national_2nd_rate',
    'grade_score',
    'is_rough_sign'
]

# --- 推論・通知メッセージ作成 ---
def run_inference(model, target_stadium, target_race_no):
    try:
        boatrace = PyJPBoatrace()
        today = date.today()
        stadium_code = int(target_stadium)
        race_no = int(target_race_no)
        s_code_str = str(target_stadium).zfill(2)
        stadium_name = CODE_TO_STADIUM.get(s_code_str, target_stadium)
        
        race_info = boatrace.get_race_info(d=today, stadium=stadium_code, race=race_no)
        if not race_info or not isinstance(race_info, dict):
            return None

        grade_str = str(race_info.get('grade', '一般'))
        grade_map = {'一般': 1, 'G3': 2, 'G2': 3, 'G1': 4, 'SG': 5}
        grade_score = grade_map.get(grade_str, 1)

        wind_speed = safe_float(race_info.get('wind_speed', 0.0), 0.0)
        trait = STADIUM_TRAITS.get(s_code_str, {'wind_limit_rough': 4.0})
        is_rough_sign = 1 if wind_speed >= trait.get('wind_limit_rough', 4.0) else 0

        exh_list = []
        for b_idx in range(1, 7):
            b_data = race_info.get(f"boat{b_idx}", {})
            if isinstance(b_data, dict):
                et = safe_float(b_data.get('exhibition_time', 0.0), 0.0)
                if et > 0:
                    exh_list.append(et)
        race_avg_exh = sum(exh_list) / len(exh_list) if exh_list else 6.80
        
        wind_dir = str(race_info.get('wind_direction', ''))
        is_headwind = 1 if ('向' in wind_dir or '向かい風' in wind_dir) else 0
        is_tailwind = 1 if ('追' in wind_dir or '追い風' in wind_dir) else 0

        race_combos = []
        for p in itertools.permutations(range(1, 7), 3):
            combo = f"{p[0]}-{p[1]}-{p[2]}"
            
            t_l3, t_st, t_cr, t_kim, t_mot, t_bot, t_rnk, t_exh, t_turn = 0, 0, 0, 0, 0, 0, 0, 0, 0
            t_nat_win, t_nat_2nd = 0, 0
            water_val, in_rate_val = 0.5, 0.5
            
            for idx, b in enumerate(p):
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
            
        if not race_combos:
            return None
            
        df_test = pd.DataFrame(race_combos)
        X_test = df_test[FEATURES]
        
        raw_preds = model.predict(X_test)
        
        np.random.seed(42)
        unique_noise = np.linspace(0.99, 1.01, len(raw_preds))
        
        adjusted_preds = raw_preds * unique_noise
        exp_preds = np.exp((adjusted_preds - np.mean(adjusted_preds)) / (np.std(adjusted_preds) + 1e-9) * 3.0)
        probs = exp_preds / np.sum(exp_preds)
        
        df_test['pred_prob'] = probs
        
        boat_1st_probs = {}
        for b in range(1, 7):
            b_str = str(b)
            p_sum = df_test[df_test['combo'].str.startswith(b_str + '-')]['pred_prob'].sum()
            boat_1st_probs[b] = p_sum

        total_1st_prob = sum(boat_1st_probs.values())
        if total_1st_prob > 0:
            for b in boat_1st_probs:
                boat_1st_probs[b] = boat_1st_probs[b] / total_1st_prob

        top_picks_df = df_test.sort_values(by='pred_prob', ascending=False).head(4)

        df_test['exacta_combo'] = df_test['combo'].apply(lambda x: '-'.join(x.split('-')[:2]))
        exacta_prob_df = df_test.groupby('exacta_combo')['pred_prob'].sum().reset_index()
        top_exacta_df = exacta_prob_df.sort_values(by='pred_prob', ascending=False).head(2)

        strategy_name = "直前予測・18特徴量（オッズ除外・展示相対評価統合）"
        
        lines = [f"🎯 **[{strategy_name}]**\n📍 **{stadium_name} / 第{target_race_no}R**"]
        
        if is_rough_sign == 1:
            lines.append("⚠️ **【トリセツ警報：荒れるサイン点灯】** 風速条件クリア！波乱・センター強襲警戒")
        if grade_score >= 4:
            lines.append(f"🏆 **【{grade_str}戦】** トップ機力・調整勝負")

        lines.append("\n**【各艇の1着予想確率】**")
        for b in range(1, 7):
            p = boat_1st_probs.get(b, 0.0)
            lines.append(f"• {b}号艇: {p*100:.1f}%")

        if not top_exacta_df.empty:
            lines.append("\n**【2連単 推奨買い目】**")
            for _, row in top_exacta_df.iterrows():
                p_val = row['pred_prob'] * 100
                lines.append(f"• **{row['exacta_combo']}** (予測確率: {p_val:.1f}%)")

        top_3ren_prop = top_picks_df.iloc[0]['pred_prob'] * 100 if not top_picks_df.empty else 0.0
        
        if top_3ren_prop < 4.0:
            lines.append(f"\n🛑 (※3連単の最高確率が{top_3ren_prop:.1f}%と低いため、３連単勝負は見送り推奨)")

        lines.append("\n**【3連単 参考買い目】**" if top_3ren_prop < 4.0 else "\n**【3連単 推奨買い目】**")
        for _, row in top_picks_df.iterrows():
            p_val = row['pred_prob'] * 100
            lines.append(f"• **{row['combo']}** (予測確率: {p_val:.1f}%)")
            
        reason_lines = []
        if is_rough_sign == 1:
            reason_lines.append("• **荒れサイン点灯**: 風速が会場の限界値を超えており、インの信頼度低下やセンター・アウト勢の台頭を反映。")
        else:
            top_1st_boat = max(boat_1st_probs, key=boat_1st_probs.get) if boat_1st_probs else 1
            top_1st_prob = boat_1st_probs.get(top_1st_boat, 0.0) * 100
            
            if top_1st_boat == 1 and top_1st_prob >= 35.0:
                reason_lines.append("• **イン信頼コンディション**: 1号艇の軸信頼度が高く、イン主体の堅実な展開を予想。")
            elif top_1st_boat in [5, 6]:
                reason_lines.append(f"• **波乱・外枠警戒**: 安定板や水面・機力傾向を反映し、{top_1st_boat}号艇 が頭に浮上する高配当狙いの構成。")
            else:
                reason_lines.append(f"• **混戦コンディション**: 抜けた軸が不在のため、各艇の機力やコース実績に基づく展開を分析。")
            
        if grade_score >= 4:
            reason_lines.append(f"• **{grade_str}戦補正**: トップレーサーの高い調整力と機力差を加味。")
            
        reason_lines.append("• **18特徴量（オッズ除外）**: 当地勝率、モーター2連率、展示タイム（相対評価）、コース別実績を純粋に分析。")
        
        lines.append("\n🤖 **AIの判断理由・根拠**:\n" + "\n".join(reason_lines))
            
        return "\n".join(lines)

    except Exception as e:
        print(f"Error in inference: {e}")
        return None

# --- メイン処理 ---
def predict_main():
    model_path = 'model.txt'
    model = None
    if os.path.exists(model_path):
        model = lgb.Booster(model_file=model_path)
    else:
        print(f"⚠️ 警告: モデルファイル '{model_path}' が見つかりません。")

    boatrace = PyJPBoatrace()
    today = date.today()

    input_stadium = os.environ.get("INPUT_STADIUM", "AUTO").strip()
    input_race_no = os.environ.get("INPUT_RACE_NO", "AUTO").strip()

    try:
        if input_stadium and input_stadium != "AUTO" and input_race_no and input_race_no != "AUTO":
            print(f"🎯 個別予測モード: 会場={input_stadium}, レース={input_race_no}")
            
            stadium_code = STADIUM_MAP.get(input_stadium, str(input_stadium).zfill(2))

            if model is not None and stadium_code in CODE_TO_STADIUM:
                res = run_inference(model, stadium_code, int(input_race_no))
                if res:
                    send_discord_notification(res)
                    print(f"🎯 指定されたレースの予測を通知しました ({CODE_TO_STADIUM[stadium_code]} 第{input_race_no}R)")
                else:
                    print("⚠️ 指定されたレースの予測データが取得できませんでした。")
            else:
                print(f"⚠️ 無効な会場指定です: {input_stadium}")
            return

        stadiums_info = boatrace.get_stadiums(today)
        target_stadiums = []
        for s_name, info in stadiums_info.items():
            if s_name == 'date': continue
            code = STADIUM_MAP.get(s_name)
            if code: target_stadiums.append((code, s_name))
        
        if not target_stadiums:
            print("ℹ️ 本日開催のレース場はありません。")
            return
            
        total_success = 0
        for stadium_code, s_name in target_stadiums:
            for r_no in range(1, 13):
                if model is not None:
                    try:
                        res = run_inference(model, stadium_code, r_no)
                        if res:
                            send_discord_notification(res)
                            total_success += 1
                    except Exception:
                        continue
        print(f"☀️ 全レース一括予測完了（計 {total_success} レース処理）")
            
    except Exception as e:
        err_msg = f"⚠️ 自動判定処理で致命的なエラーが発生しました: {e}"
        print(err_msg)
        send_discord_notification(err_msg)
        sys.exit(1)

if __name__ == '__main__':
    predict_main()
