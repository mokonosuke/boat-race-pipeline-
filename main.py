from datetime import date, timedelta
from pyjpboatrace import PyJPBoatrace

# -----------------------------------------
# 1. 設定（検証したい過去のびわこSG開催日を指定）
# -----------------------------------------
TARGET_JCD = 11  # びわこ競走場
# 例として、過去の開催日（適宜変更してください）
TEST_DATES = [
    date(2025, 7, 28),
    date(2025, 7, 29),
    date(2025, 7, 30),
]

# -----------------------------------------
# 2. スコアリング関数（係数を変数化して最適化に対応）
# -----------------------------------------
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
    """
    重み付け係数（weights）を辞書で受け取り、スコアを計算する
    """
    score = avg_local_3ren * weights['local_3ren']
    score += (0.18 - avg_st) * weights['st']
    score += avg_course * weights['course']
    score += avg_kimarite * weights['kimarite']
    score += odds_val * weights['odds']
    return score

# -----------------------------------------
# 3. バックテスト実行メイン関数
# -----------------------------------------
def run_backtest(weights):
    boatrace = PyJPBoatrace()
    
    total_investment = 0  # 総投資額（円）
    total_return = 0      # 総払戻金（円）
    hit_count = 0         # 的中回数
    total_bets_count = 0  # 買い目総数
    
    for target_date in TEST_DATES:
        for rno in range(1, 13):
            try:
                odds_info = boatrace.get_odds_trifecta(d=target_date, stadium=TARGET_JCD, race=rno)
                race_info = boatrace.get_race_info(d=target_date, stadium=TARGET_JCD, race=rno)
                # 実際のレース結果（三連単の的中組み合わせと払戻金）を取得
                result_info = boatrace.get_result_trifecta(d=target_date, stadium=TARGET_JCD, race=rno)
            except Exception:
                # データが存在しない過去日の場合はスキップ
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
            
            # スコア上位1点のみを「本命買い目」として購入するシミュレーション
            if scored_bets:
                top_bet = scored_bets[0]
                total_investment += 100  # 100円投資
                total_bets_count += 1
                
                # 実際のレース結果と一致するか判定
                # result_info に実際の的中コンボと配当が含まれていると仮定
                winning_combo = result_info.get('combo', '')
                payout = float(result_info.get('payout', 0)) # 100円あたりの払戻金
                
                if top_bet['combo'] == winning_combo:
                    hit_count += 1
                    total_return += payout

    # 回収率の計算
    recovery_rate = (total_return / total_investment * 100) if total_investment > 0 else 0.0
    hit_rate = (hit_count / total_bets_count * 100) if total_bets_count > 0 else 0.0
    
    return recovery_rate, hit_rate, total_investment, total_return

if __name__ == "__main__":
    # 初期係数モデル
    default_weights = {
        'local_3ren': 0.7,
        'st': 180,
        'course': 0.3,
        'kimarite': 0.2,
        'odds': 0.25
    }
    
    print("バックテストを実行中...")
    rec_rate, h_rate, inv, ret = run_backtest(default_weights)
    
    print("--- バックテスト結果 ---")
    print(f"総投資額: {inv}円")
    print(f"総払戻金: {ret}円")
    print(f"的中率: {h_rate:.2f}%")
    print(f"回収率: {rec_rate:.2f}%")

