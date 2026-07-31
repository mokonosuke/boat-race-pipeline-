import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

print("🚀 [1/4] 最適化スクリプト開始")

import os
from datetime import date, timedelta
import json
import re
import itertools
import requests

print("🚀 [2/4] モジュールインポート完了")
try:
    from pyjpboatrace import PyJPBoatrace
    print("✅ PyJPBoatrace 読み込み成功")
except Exception as e:
    print(f"❌ 読み込み失敗: {e}")
    sys.exit(1)

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
TARGET_JCD = 11  # びわこ競走場
CACHE_FILE = "race_cache.json"

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

def extract_trifecta_result(result_data):
    """結果データの中から '1-2-3' のような三連単の組み合わせを自動的に探す"""
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

def fetch_and_cache_races(start_date, end_date):
    # キャッシュをクリアして確実に最新の抽出ロジックで再構築する
    if os.path.exists(CACHE_FILE):
        try:
            os.remove(CACHE_FILE)
        except Exception:
            pass

    print("🚀 APIからデータを取得してキャッシュを作成します...")
    try:
        boatrace = PyJPBoatrace()
    except Exception as e:
        print(f"❌ 初期化失敗: {e}")
        return []

    cache_data = []
    current_date = start_date
    
    while current_date <= end_date:
        date_str = str(current_date)
        print(f"📅 取得中: {date_str}")
        
        for rno in range(1, 13):
            try:
                odds_info = boatrace.get_odds_trifecta(d=current_date, stadium=TARGET_JCD, race=rno)
                race_info = boatrace.get_race_info(d=current_date, stadium=TARGET_JCD, race=rno)
                result_info = boatrace.get_race_result(d=current_date, stadium=TARGET_JCD, race=rno)
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
                
                race_combos.append({
                    'combo': combo,
                    'odds': odds_val,
                    'avg_l3': total_l3 / 3,
                    'avg_st': total_st / 3,
                    'avg_cr': total_cr / 3,
                    'avg_kim': total_kim / 3
                })
            
            if race_combos:
                cache_data.append({
                    'date': date_str,
                    'rno': rno,
                    'actual_win': actual_win,
                    'combos': race_combos
                })
                
        current_date += timedelta(days=1)

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=4)
    print(f"✅ キャッシュ保存完了: {len(cache_data)}レース")
    return cache_data

def optimize_weights(cache_data):
    print("🚀 [3/4] 重みの最適化（グリッドサーチ）を実行中...")
    
    param_grid = {
        'local_3ren': [0.3, 0.7, 1.0],
        'st': [100, 180, 250],
        'course': [0.1, 0.3, 0.5],
        'kimarite': [0.1, 0.2, 0.4],
        'odds': [0.1, 0.25, 0.5]
    }
    
    keys = param_grid.keys()
    values = param_grid.values()
    combinations = list(itertools.product(*values))
    
    best_recovery = -1
    best_weights = None
    best_stats = None
    
    total_races = len(cache_data)
    if total_races == 0:
        print("❌ 検証可能なレースデータがありません。")
        return None

    for combo_vals in combinations:
        weights = dict(zip(keys, combo_vals))
        
        investment = total_races * 100
        payout = 0
        wins = 0
        
        for race in cache_data:
            scored_bets = []
            for bet in race['combos']:
                score = calculate_score(
                    bet['odds'], 
                    bet['avg_l3'], 
                    bet['avg_st'], 
                    bet['avg_cr'], 
                    bet['avg_kim'], 
                    weights
                )
                scored_bets.append({'combo': bet['combo'], 'odds': bet['odds'], 'score': score})
            
            if not scored_bets:
                continue
            
            scored_bets.sort(key=lambda x: x['score'], reverse=True)
            top_bet = scored_bets[0]
            
            if top_bet['combo'] == race['actual_win']:
                wins += 1
                payout += top_bet['odds'] * 100
                
        recovery_rate = (payout / investment) * 100 if investment > 0 else 0
        hit_rate = (wins / total_races) * 100
        
        if recovery_rate > best_recovery:
            best_recovery = recovery_rate
            best_weights = weights
            best_stats = {'hits': wins, 'hit_rate': hit_rate, 'payout': payout, 'investment': investment}

    return best_weights, best_recovery, best_stats, total_races

if __name__ == "__main__":
    start_d = date(2026, 7, 28)
    end_d = date(2026, 7, 30)
    
    cache_data = fetch_and_cache_races(start_d, end_d)
    result = optimize_weights(cache_data)
    
    if result:
        best_w, best_rec, stats, total_r = result
        summary_text = (
            f"🎯 **【重み最適化結果（修正版）】**\n"
            f"・検証レース数: {total_r}\n"
            f"・最高回収率: **{best_rec:.2f}%**\n"
            f"・的中数 / 的中率: {stats['hits']}件 ({stats['hit_rate']:.2f}%)\n"
            f"・総投資 / 払戻: {stats['investment']}円 → {int(stats['payout'])}円\n\n"
            f"📌 **最適ウェイト設定:**\n"
            f"```json\n{json.dumps(best_w, indent=4, ensure_ascii=False)}\n```"
        )
        
        print("\n" + summary_text.replace("**", "").replace("```json", "").replace("```", ""))
        
        if WEBHOOK_URL:
            try:
                requests.post(WEBHOOK_URL, json={"content": summary_text})
                print("✅ Discordへ最適化結果を通知しました。")
            except Exception as e:
                print(f"⚠️ Discord通知失敗: {e}")
