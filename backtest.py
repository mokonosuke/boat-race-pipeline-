import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

print("🚀 [1/5] スクリプト開始")

import os
from datetime import date, timedelta
import json
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
HISTORY_FILE = "race_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

def get_factor_score(boat_data, assigned_course):
    local_3ren = float(boat_data.get('local_in3rd', 0.0))
    ave_st = float(boat_data.get('aveST', 0.20))
    course_key = f"course_{assigned_course}_2nd_rate"
    course_record_score = float(boat_data.get(course_key, 30.0))
    
    kimarite_type = boat_data.get('primary_kimarite', 'normal')
    if kimarite_type in ['makuri', 'tsuki_makuri'] and assigned_course in [4, 5, 6]:
        kimarite_score = 45.0
    elif kimarite_type == 'sashi' and assigned_course in [2, 3]:
        kimarite_score = 45.0
    elif kimarite_type == 'nige' and assigned_course == 1:
        kimarite_score = 50.0
    else:
        kimarite_score = 35.0

    return local_3ren, ave_st, course_record_score, kimarite_score

def calculate_score(odds_val, avg_local_3ren, avg_st, avg_course, avg_kimarite, weights):
    score = avg_local_3ren * weights['local_3ren']
    score += (0.18 - avg_st) * weights['st']
    score += avg_course * weights['course']
    score += avg_kimarite * weights['kimarite']
    score += odds_val * weights['odds']
    return score

def run_backtest_for_period(start_date, end_date, weights):
    print("🚀 [3/5] PyJPBoatrace 初期化中...")
    try:
        boatrace = PyJPBoatrace()
        print("✅ 初期化成功")
    except Exception as e:
        print(f"❌ 初期化失敗: {e}")
        return

    current_date = start_date
    
    while current_date <= end_date:
        print(f"\n📅 対象日: {current_date}")
        
        for rno in range(1, 13):
            print(f"▶ 第{rno}R 取得試行...")
            try:
                odds_info = boatrace.get_odds_trifecta(d=current_date, stadium=TARGET_JCD, race=rno)
                race_info = boatrace.get_race_info(d=current_date, stadium=TARGET_JCD, race=rno)
                result_info = boatrace.get_race_result(d=current_date, stadium=TARGET_JCD, race=rno)
                print(f"  成功: 第{rno}R")
            except Exception as e:
                print(f"  ⚠️ スキップ: {e}")
                continue
            
            if not odds_info or not race_info:
                print(f"  ℹ️ データなし")
                continue
            
            scored_bets = []
            for combo, odds in odds_info.items():
                # メタデータキー（stadium等）が混ざっている場合はスキップ
                if not isinstance(combo, str) or '-' not in combo:
                    continue
                try:
                    boats = [int(b) for b in combo.split('-')]
                    odds_val = float(odds)
                except (ValueError, TypeError):
                    continue
                
                total_l3, total_st, total_cr, total_kim = 0, 0, 0, 0
                
                for idx, b in enumerate(boats):
                    assigned_course = idx + 1
                    boat_key = f"boat{b}"
                    boat_data = race_info.get(boat_key, {})
                    l3, st, cr, kim = get_factor_score(boat_data, assigned_course)
                    total_l3 += l3
                    total_st += st
                    total_cr += cr
                    total_kim += kim
                
                avg_l3 = total_l3 / 3
                avg_st = total_st / 3
                avg_cr = total_cr / 3
                avg_kim = total_kim / 3
                
                score = calculate_score(odds_val, avg_l3, avg_st, avg_cr, avg_kim, weights)
                scored_bets.append({'combo': combo, 'odds': odds_val, 'score': score})
            
            if not scored_bets:
                continue
            
            scored_bets.sort(key=lambda x: x['score'], reverse=True)
            top_bet = scored_bets[0]
            
            status = "pending"
            if result_info and "trifecta" in result_info:
                actual_win = result_info["trifecta"]
                if actual_win == top_bet['combo']:
                    status = "win"
                    print(f"    🎉 的中: {top_bet['combo']}")
                else:
                    status = "lose"
                    print(f"    ❌ 不的中: 予想={top_bet['combo']}, 結果={actual_win}")
            else:
                print(f"    ⏳ 未確定: {top_bet['combo']}")
            
            history = load_history()
            existing = next((h for h in history if h["date"] == str(current_date) and h["stadium"] == TARGET_JCD and h["rno"] == rno), None)
            if existing:
                existing["combo"] = top_bet['combo']
                existing["odds"] = top_bet['odds']
                existing["score"] = top_bet['score']
                existing["status"] = status
            else:
                history.append({
                    "date": str(current_date),
                    "stadium": TARGET_JCD,
                    "rno": rno,
                    "combo": top_bet['combo'],
                    "odds": top_bet['odds'],
                    "score": top_bet['score'],
                    "status": status
                })
            save_history(history)
            
        current_date += timedelta(days=1)

if __name__ == "__main__":
    print("🚀 [4/5] メイン処理開始")
    default_weights = {
        'local_3ren': 0.7,
        'st': 180,
        'course': 0.3,
        'kimarite': 0.2,
        'odds': 0.25
    }
    
    start_d = date(2026, 7, 28)
    end_d = date(2026, 7, 30)
    
    run_backtest_for_period(start_d, end_d, default_weights)
    print("🚀 [5/5] すべて完了")
