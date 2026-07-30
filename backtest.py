from datetime import date
from pyjpboatrace import PyJPBoatrace

# -----------------------------------------
# 1. 設定
# -----------------------------------------
TARGET_JCD = 11  # びわこ競走場
TEST_DATES = [
    date(2024, 5, 1),
    date(2024, 5, 2),
    date(2024, 5, 3),
]

# -----------------------------------------
# 2. 改善版スコアリング関数（モーター性能を追加）
# -----------------------------------------
def get_factor_score(boat_data, assigned_course):
    local_3ren = float(boat_data.get('local_in3rd', 0.0))
    ave_st = float(boat_data.get('aveST', 0.20))
    motor_2nd = float(boat_data.get('motor_2nd_rate', 30.0)) # モーター2連率
    
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

    return local_3ren, ave_st, motor_2nd, course_record_score, kimarite_score

def calculate_score(odds_val, avg_l3, avg_st, avg_motor, avg_course, avg_kim, weights):
    score = avg_l3 * weights['local_3ren']
    score += (0.18 - avg_st) * weights['st']
    score += avg_motor * weights['motor']  # モーター評価の反映
    score += avg_course * weights['course']
    score += avg_kim * weights['kimarite']
    score += odds_val * weights['odds']
    return score

# -----------------------------------------
# 3. バックテスト実行メイン関数
# -----------------------------------------
def run_backtest(weights):
    boatrace = PyJPBoatrace()
    
    total_investment = 0  
    total_return = 0      
    hit_count = 0         
    total_bets_count = 0  
    
    for target_date in TEST_DATES:
        for rno in range(1, 13):
            try:
                odds_info = boatrace.get_odds_trifecta(d=target_date, stadium=TARGET_JCD, race=rno)
                race_info = boatrace.get_race_info(d=target_date, stadium=TARGET_JCD, race=rno)
                result_info = boatrace.get_race_result(d=target_date, stadium=TARGET_JCD, race=rno)
            except Exception as e:
                continue
            
            if not odds_info or not race_info:
                continue
            
            scored_bets = []
            
            for combo, odds in odds_info.items():
                try:
                    odds_val = float(odds)
                except (ValueError, TypeError):
                    continue
                
                # 狙うオッズ帯（15.0〜35.0倍）
                if not (15.0 <= odds_val <= 35.0):
                    continue
                
                boats = [int(b) for b in combo.split('-')]
                tot_l3, tot_st, tot_motor, tot_cr, tot_kim = 0, 0, 0, 0, 0
                
                for idx, b in enumerate(boats):
                    assigned_course = idx + 1
                    boat_key = f"boat{b}"
                    boat_data = race_info.get(boat_key, {})
                    
                    l3, st, motor, cr, kim = get_factor_score(boat_data, assigned_course)
                    tot_l3 += l3
                    tot_st += st
                    tot_motor += motor
                    tot_cr += cr
                    tot_kim += kim
                
                avg_l3 = tot_l3 / 3
                avg_st = tot_st / 3
                avg_motor = tot_motor / 3
                avg_cr = tot_cr / 3
                avg_kim = tot_kim / 3
                
                score = calculate_score(odds_val, avg_l3, avg_st, avg_motor, avg_cr, avg_kim, weights)
                
                scored_bets.append({
                    'combo': combo.strip(),
                    'odds': odds_val,
                    'score': score,
                })
            
            scored_bets.sort(key=lambda x: x['score'], reverse=True)
            
            if scored_bets:
                top_bet = scored_bets[0]
                total_investment += 100  
                total_bets_count += 1
                
                winning_combo = ""
                payout = 0.0
                
                if isinstance(result_info, dict):
                    payoff_dict = result_info.get('payoff', {})
                    if isinstance(payoff_dict, dict):
                        trifecta_all = payoff_dict.get('trifecta_all', [])
                        if isinstance(trifecta_all, list) and len(trifecta_all) > 0:
                            item = trifecta_all[0]
                            if isinstance(item, dict):
                                winning_combo = str(item.get('result', '')).strip()
                                try:
                                    payout = float(item.get('payoff', 0))
                                except (ValueError, TypeError):
                                    payout = 0.0
                
                is_hit = (top_bet['combo'] == winning_combo)
                print(f"CHECK [{target_date} R{rno}] 予想: {top_bet['combo']} | 結果: {winning_combo} | 一致: {is_hit} | 払戻: {payout}")
                
                if is_hit:
                    hit_count += 1
                    total_return += payout

    recovery_rate = (total_return / total_investment * 100) if total_investment > 0 else 0.0
    hit_rate = (hit_count / total_bets_count * 100) if total_bets_count > 0 else 0.0
    
    return recovery_rate, hit_rate, total_investment, total_return

if __name__ == "__main__":
    # チューニング用ウェイト（モーター性能を重視に調整）
    optimized_weights = {
        'local_3ren': 0.5,
        'st': 150.0,
        'motor': 0.8,     # 新たに追加したモーター評価の係数
        'course': 0.3,
        'kimarite': 0.2,
        'odds': 0.1
    }
    
    print("最適化ウェイトでのバックテストを実行中...")
    rec_rate, h_rate, inv, ret = run_backtest(optimized_weights)
    
    print("--- バックテスト結果 ---")
    print(f"総投資額: {inv}円")
    print(f"総払戻金: {ret}円")
    print(f"的中率: {h_rate:.2f}%")
    print(f"回収率: {rec_rate:.2f}%")
