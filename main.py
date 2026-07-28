from datetime import date
import os
import requests
from pyjpboatrace import PyJPBoatrace

# -----------------------------------------
# 1. 設定
# -----------------------------------------
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
TARGET_JCD = 11  # びわこ競走場
TARGET_DATE = date.today()

# -----------------------------------------
# 2. ファクター抽出・本格スコアリング関数
# -----------------------------------------
def get_factor_score(boat_data, assigned_course):
    """
    各選手のデータから、当地成績、平均ST、
    および「割り当てられたコース（assigned_course）」における実績・決まり手を抽出する
    """
    # 基本指標
    local_3ren = float(boat_data.get('local_in3rd', 0.0))
    ave_st = float(boat_data.get('aveST', 0.20))
    
    # 【本格実装】枠番実績（例: そのコースでの1着率や2連対率データを取得、ない場合はデフォルト値）
    # pyjpboatrace等のデータ構造に合わせてキー名を調整可能です（例: course_2nd_rate等）
    course_key = f"course_{assigned_course}_2nd_rate"
    course_record_score = float(boat_data.get(course_key, 30.0)) # デフォルト30%
    
    # 【本格実装】決まり手傾向（例: まくり・差し・逃げの得意度を評価）
    # 艇番や選手タイプに応じた決まり手スコア
    kimarite_type = boat_data.get('primary_kimarite', 'normal')
    if kimarite_type in ['makuri', 'tsuki_makuri'] and assigned_course in [4, 5, 6]:
        kimarite_score = 45.0  アートな外枠まくり加点
    elif kimarite_type == 'sashi' and assigned_course in [2, 3]:
        kimarite_score = 45.0  # 差し巧者加点
    elif kimarite_type == 'nige' and assigned_course == 1:
        kimarite_score = 50.0  # イン逃げ信頼度
    else:
        kimarite_score = 35.0

    return local_3ren, ave_st, course_record_score, kimarite_score

def calculate_score(odds_val, avg_local_3ren, avg_st, avg_course, avg_kimarite):
    """
    各ファクターの重み付けによる総合スコア算出
    """
    # ① 当地適性（重視: 0.7）
    score = avg_local_3ren * 0.7 
    
    # ② スタート力（速いほどプラス：基準0.18秒）
    score += (0.18 - avg_st) * 180 
    
    # ③ 枠番実績（そのコース巧者であるほどプラス: 0.3）
    score += avg_course * 0.3
    
    # ④ 決まり手適性（展開が向く場合のボーナス: 0.2）
    score += avg_kimarite * 0.2
    
    # ⑤ オッズ妙味（15〜35倍のうまみゾーンにボーナス）
    score += odds_val * 0.25

    return score

# -----------------------------------------
# 3. メイン処理（全12レース自動ループ）
# -----------------------------------------
def main():
    boatrace = PyJPBoatrace()
    
    report_message = f"🏆 **【びわこSG 枠番・決まり手連動スコア分析】**\n({TARGET_DATE.strftime('%Y-%m-%d')})\n\n"

    for rno in range(1, 13):
        try:
            odds_info = boatrace.get_odds_trifecta(d=TARGET_DATE, stadium=TARGET_JCD, race=rno)
            race_info = boatrace.get_race_info(d=TARGET_DATE, stadium=TARGET_JCD, race=rno)
        except Exception as e:
            print(f"第{rno}Rのデータ取得に失敗しました: {e}")
            continue
        
        scored_bets = []
        
        for combo, odds in odds_info.items():
            try:
                odds_val = float(odds)
            except (ValueError, TypeError):
                continue
            
            # 15.0〜35.0倍のうまみゾーンに絞る
            if not (15.0 <= odds_val <= 35.0):
                continue
            
            # 三連単の組み合わせ（例: '1-2-3' なら 1着=1コース, 2着=2コース, 3着=3コースとして評価）
            boats = [int(b) for b in combo.split('-')]
            
            total_l3, total_st, total_cr, total_kim = 0, 0, 0, 0
            
            # 各着順のポジション（1着〜3着）にいる選手が、そのコースでどういう実績・決まり手を持つか評価
            for idx, b in enumerate(boats):
                assigned_course = idx + 1 # 1着位置=1コース想定、2着=2コース想定...
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
            
            score = calculate_score(odds_val, avg_l3, avg_st, avg_cr, avg_kim)
            
            scored_bets.append({
                'combo': combo,
                'odds': odds_val,
                'score': score,
            })
        
        scored_bets.sort(key=lambda x: x['score'], reverse=True)
        
        report_message += f"・第{rno}R: "
        if scored_bets:
            top_bets_str = []
            for bet in scored_bets[:3]:
                top_bets_str.append(f"{bet['combo']}({bet['odds']}倍, SC:{bet['score']:.1f})")
            report_message += ", ".join(top_bets_str) + "\n"
        else:
            report_message += "対象の買い目なし\n"

    print(report_message)

    # -----------------------------------------
    # 4. Discord通知
    # -----------------------------------------
    if DISCORD_WEBHOOK_URL:
        headers = {'Content-Type': 'application/json'}
        payload = {"content": report_message}
        try:
            response = requests.post(DISCORD_WEBHOOK_URL, headers=headers, json=payload)
            response.raise_for_status()
            print("Discordへの通知が完了しました。")
        except requests.exceptions.RequestException as e:
            print(f"Discordへの送信に失敗しました: {e}")
    else:
        print("Webhook URLが設定されていません。")

if __name__ == "__main__":
    main()
