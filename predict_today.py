import os
import re
import requests
import pandas as pd
import lightgbm as lgb
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

# --- 3連単の結果文字列を抽出する関数 ---
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

# --- 特徴量スコア計算 ---
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

# --- 会場名からコードへの変換マップ ---
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
        from datetime import date
        today = date.today()
        
        stadium_code = int(target_stadium)
        race_no = int(target_race_no)
        
        odds_info = boatrace.get_odds_trifecta(d=today, stadium=stadium_code, race=race_no)
        race_info = boatrace.get_race_info(d=today, stadium=stadium_code, race=race_no)
        result_info = boatrace.get_race_result(d=today, stadium=stadium_code, race=race_no)
        
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
            
            try:
                boats = [int(b) for b in combo.split('-')]
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
                'racer_rank': total_rank / 3,
                'wind_speed': wind_speed,
                'is_headwind': is_headwind,
                'is_tailwind': is_tailwind
            })
            
        if not race_combos:
            return f"⚠️ 有効な買い目データを作成できませんでした。"
            
        df_test = pd.DataFrame(race_combos)
        X_test = df_test[FEATURES]
        
        preds = model.predict(X_test)
        df_test['pred_prob'] = preds
        
        filtered = df_test[(df_test['odds'] >= 5.0) & (df_test['odds'] <= 60.0)]
        if len(filtered) == 0:
            filtered = df_test
            
        # --- パターンB：AIの予測スコア基準による動的点数変更ロジック ---
        sorted_filtered = filtered.sort_values('pred_prob', ascending=False).reset_index(drop=True)
        
        if len(sorted_filtered) >= 2:
            top_score = sorted_filtered.loc[0, 'pred_prob']
            second_score = sorted_filtered.loc[1, 'pred_prob']
            score_diff = top_score - second_score
            
            if top_score > 0.12 or score_diff > 0.03:
                n_picks = 3
                strategy_name = "3点絞り（本命・堅調）"
            else:
                n_picks = 4
                strategy_name = "4点網羅（混戦・警戒）"
        else:
            n_picks = min(3, len(sorted_filtered))
            strategy_name = f"{n_picks}点"

        top_n = sorted_filtered.head(n_picks)
        
        lines = [f"🎯 **【直前予測・{strategy_name}】 会場コード: {target_stadium} / 第{target_race_no}R**"]
        for _, row in top_n.iterrows():
            lines.append(f"• 推奨買い目: **{row['combo']}** (オッズ: {row['odds']:.1f}倍 / スコア: {row['pred_prob']:.4f})")
            
        # --- 自動結果検証機能（なぜ外れたかの蓄積） ---
        actual_win = extract_trifecta_result(result_info)
        if actual_win:
            # 全体の予測結果の中から実際の勝者を探す（フィルタ前の全組み合わせから順位を特定）
            all_sorted = df_test.sort_values('pred_prob', ascending=False).reset_index(drop=True)
            matched_row = all_sorted[all_sorted['combo'] == actual_win]
            
            if not matched_row.empty:
                rank_idx = matched_row.index[0] + 1
                actual_score = matched_row.iloc[0]['pred_prob']
                actual_odds = matched_row.iloc[0]['odds']
                
                # 推奨買い目（top_n）に含まれていたか判定
                recommended_combos = top_n['combo'].values
                if actual_win in recommended_combos:
                    result_msg = f"✅ **【結果速報】的中！** 正解: **{actual_win}** (オッズ: {actual_odds:.1f}倍) [AI評価: {rank_idx}位 / スコア: {actual_score:.4f}]"
                else:
                    result_msg = f"❌ **【結果速報】不的中** 正解: **{actual_win}** (オッズ: {actual_odds:.1f}倍) → **[AIの内部評価: {rank_idx}位 / スコア: {actual_score:.4f}]**"
            else:
                result_msg = f"❌ **【結果速報】不的中** 正解: **{actual_win}** (AIの候補外またはオッズ対象外)"
            
            lines.append(result_msg)

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
    from datetime import date
    today = date.today()

    if raw_stadium.upper() == 'AUTO' or not raw_stadium:
        try:
            stadiums_info = boatrace.get_stadiums(today)
            target_stadiums = []
            
            women_keywords = ['女子', 'レディース', 'ヴィーナス', 'オールレディース', 'クイーンズクライマックス', '男女w']
            
            for s_name, info in stadiums_info.items():
                if s_name == 'date':
                    continue
                grade_list = [g.lower() for g in info.get('grade', [])]
                title = info.get('title', '')
                
                is_major = any(g in ['sg', 'g1', 'pg1'] for g in grade_list)
                is_women = any(kw in title for kw in women_keywords)
                
                if is_major or is_women:
                    code = STADIUM_MAP.get(s_name)
                    if code:
                        target_stadiums.append((code, s_name, title))
            
            if not target_stadiums:
                print("ℹ️ 本日開催のSG・G1・女子戦はありません。")
                return
                
            for stadium_code, s_name, title in target_stadiums:
                print(f"🔍 対象レース発見: {s_name} ({title})")
                races_to_run = list(range(1, 13)) if str(target_race_no).upper() == 'AUTO' else [int(target_race_no)]
                
                for r_no in races_to_run:
                    if model is not None:
                        prediction_text = run_inference(model, stadium_code, r_no)
                        notification = f"📌 **【対象レース】 {s_name} ({title})**\n{prediction_text}"
                        send_discord_notification(notification)
                    else:
                        send_discord_notification("⚠️ モデルファイルが存在しないため、推論をスキップしました。")
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

