from datetime import date
import json
import os
import requests
from pyjpboatrace import PyJPBoatrace

WEBHOOK_URL = "https://discord.com/api/webhooks/1529073836958552134/BqehrTUCsPbcOc5ppWK-pzq2F5I-s5WkUKX9F4H9p6MUrWlr7vm2Zke4qRwVs5mhKYUs"
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

def send_discord_notification(message):
    payload = {"content": message}
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Discord通知に失敗しました: {e}")

def check_past_results(boatrace):
    print("▶ 過去の未確定レースの結果をチェック中...")
    history = load_history()
    updated = False
    
    for item in history:
        if item.get("status") == "pending":
            target_date = item["date"]
            stadium = item["stadium"]
            rno = item["rno"]
            
            try:
                result_info = boatrace.get_result(d=target_date, stadium=stadium, race=rno)
                if result_info and "trifecta" in result_info:
                    actual_win = result_info["trifecta"]
                    predicted_win = item["combo"]
                    
                    if actual_win == predicted_win:
                        item["status"] = "win"
                        print(f"🎉 的中！ ({target_date} 第{rno}R: {predicted_win})")
                    else:
                        item["status"] = "lose"
                        print(f"❌ 不的中 ({target_date} 第{rno}R: 予想={predicted_win}, 結果={actual_win})")
                    
                    updated = True
            except Exception:
                pass
                
    if updated:
        save_history(history)
    print("▶ 過去の結果チェック完了")

def predict_and_notify_race(target_date, stadium, rno, weights):
    boatrace = PyJPBoatrace()
    
    # 1. 過去結果チェック
    check_past_results(boatrace)
    
    try:
        print(f"▶ オッズ情報（3連単）を取得中 (会場:{stadium}, レース:{rno})...")
        odds_info = boatrace.get_odds_trifecta(d=target_date, stadium=stadium, race=rno)
        print("▶ オッズ情報の取得成功")
        
        print("▶ レース詳細情報を取得中...")
        race_info = boatrace.get_race_info(d=target_date, stadium=stadium, race=rno)
        print("▶ レース情報の取得成功")
        
    except Exception as e:
        print(f"❌ データの取得に失敗しました: {e}")
        return
    
    if not odds_info or not race_info:
        print("❌ オッズまたはレース情報が存在しません（データ未公開の可能性）。")
        return
    
    print("▶ スコアリング計算中...")
    scored_bets = []
    
    for combo, odds in odds_info.items():
        try:
            odds_val = float(odds)
        except (ValueError, TypeError):
            continue
        
        boats = [int(b) for b in combo.split('-')]
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
        
        scored_bets.append({
            'combo': combo,
            'odds': odds_val,
            'score': score,
        })
    
    scored_bets.sort(key=lambda x: x['score'], reverse=True)
    
    if scored_bets:
        top_bet = scored_bets[0]
        
        history = load_history()
        history.append({
            "date": str(target_date),
            "stadium": stadium,
            "rno": rno,
            "combo": top_bet['combo'],
            "odds": top_bet['odds'],
            "score": top_bet['score'],
            "status": "pending"
        })
        save_history(history)
        
        msg = (
            f"🎯 **【びわこ競艇 予想通知（学習機能付き）】**\n"
            f"📅 開催日: {target_date} / 第{rno}レース\n"
            f"------------------------------------\n"
            f"🔥 **推奨買い目 (3連単):** `{top_bet['combo']}`\n"
            f"💰 **想定オッズ:** {top_bet['odds']:.1f}倍\n"
            f"📊 **評価スコア:** {top_bet['score']:.2f}\n"
            f"------------------------------------"
        )
        
        send_discord_notification(msg)
        print("✅ 予想をDiscordに通知し、履歴に保存しました。")
    else:
        print("❌ 条件に合致する買い目がありませんでした。")

if __name__ == "__main__":
    default_weights = {
        'local_3ren': 0.7,
        'st': 180,
        'course': 0.3,
        'kimarite': 0.2,
        'odds': 0.25
    }
    
    today = date.today()
    race_number = 11
    
    predict_and_notify_race(today, TARGET_JCD, race_number, default_weights)

