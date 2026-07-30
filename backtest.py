from datetime import date, timedelta
from pyjpboatrace import PyJPBoatrace

# -----------------------------------------
# 1. 設定（検証期間を1週間に拡大）
# -----------------------------------------
TARGET_JCD = 11  # びわこ競走場
START_DATE = date(2024, 5, 1)
TEST_DATES = [START_DATE + timedelta(days=i) for i in range(7)]

# -----------------------------------------
# 2. 実力・機力重視のスコアリング関数
# -----------------------------------------
def get_factor_score(boat_data, assigned_course):
    local_3ren = float(boat_data.get('local_in3rd', 0.0))
    ave_st = float(boat_data.get('aveST', 0.20))
    motor_2nd = float(boat_data.get('motor_2nd_rate', 30.0))
    
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

def calculate_score(avg_l3, avg_st, avg_motor, avg_course, avg_kim, weights):
    score = avg_l3 * weights['local_3ren']
    score += (0.18 - avg_st) * weights['st']
    score += avg_motor * weights['motor']
    score += avg_course * weights['course']
    score += avg_kim * weights['kimarite']
    return score

# -----------------------------------------
# 2.5 展開・見立てを再現するボーナス関数（追加）
# -----------------------------------------
def get_tactical_bonus(boats, race_info):
    """
    外枠（4号艇・5号艇など）の機力やSTが優れている場合、
    それらの艇が絡む買い目にボーナス点を加算して「展開の利」を再現する
    """
    bonus = 0.0
    b1, b2, b3 = boats[0], boats[1], boats[2]
    
    # 4号艇のデータを取得（機力・ST）
    boat4_data = race_info.get('boat4', {})
    motor4 = float(boat4_data.get('motor_2nd_rate', 30.0))
    st4 = float(boat4_data.get('aveST', 0.20))
    
    # 条件A：4号艇が「機力上位（例: 40超え）かつ 鋭いST（例: 0.16以下）」の場合
    if motor4 >= 40.0 and st4 <= 0.16:
        if b2 == 4 or b3 == 4:
            bonus += 15.0
        if b1 == 4:
            bonus += 25.0

    # 5号艇のデータを取得
    boat5_data = race_info.get('boat5', {})
    motor5 = float(boat5_data.get('motor_2nd_rate', 30.0))
    
    # 条件B：5号艇の機力が高く、2・3着に飛び込む形を優遇
    if motor5 >= 40.0 and (b2 == 5 or b3 == 5):
        bonus += 10.0
        
    return bonus

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
                
                # 基本スコア計算
                score = calculate_score(avg_l3, avg_st, avg_motor, avg_cr, avg_kim, weights)
                
                # 展開見立て（タクティカル・ボーナス）を加算
                tactical_bonus = get_tactical_bonus(boats, race_info)
                score += tactical_bonus
                
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
                if is_hit:
                    hit_count += 1
                    total_return += payout
                
                print(f"CHECK [{target_date} R{rno}] 予想: {top_bet['combo']} | 結果: {winning_combo} | 一致: {is_hit} | 払戻: {payout}")

    # --- 集計結果の表示 ---
    print(f"\n--- バックテスト結果 ---")
    print(f"総投資額: {total_investment}円")
    print(f"総払戻金: {total_return}円")
    if total_investment > 0:
        recovery_rate = (total_return / total_investment) * 100
        print(f"回収率: {recovery_rate:.2f}%")

if __name__ == "__main__":
    sample_weights = {
        'local_3ren': 1.0,
        'st': 100.0,
        'motor': 1.0,
        'course': 1.0,
        'kimarite': 1.0
    }
    run_backtest(sample_weights)

