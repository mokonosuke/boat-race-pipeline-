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
# 2. ファクター抽出・スコアリング関数
# -----------------------------------------
def get_factor_score(boat_data):
    local_3ren = float(boat_data.get('local_in3rd', 0.0))
    ave_st = float(boat_data.get('aveST', 0.20))
    
    course_record_score = 50.0 
    kimarite_score = 50.0

    return local_3ren, ave_st, course_record_score, kimarite_score

def calculate_score(odds_val, avg_local_3ren, avg_st, avg_course, avg_kimarite):
    score = avg_local_3ren * 0.8 
    score += (0.18 - avg_st) * 200 
    score += odds_val * 0.3
    score += (avg_course + avg_kimarite) * 0.1
    return score

# -----------------------------------------
# 3. メイン処理（全12レース自動ループ）
# -----------------------------------------
def main():
    boatrace = PyJPBoatrace()
    
    report_message = f"🏆 **【びわこSG 全レース うまみ＆適性スコア分析】**\n({TARGET_DATE.strftime('%Y-%m-%d')})\n\n"

    for rno in range(1, 13):
        try:
            odds_info = boatrace.get_odds_trifecta(d=TARGET_DATE, stadium=TARGET_JCD, race=rno)
            race_info = boatrace.get_race_info(d=TARGET_DATE, stadium=TARGET_JCD, race=rno)
        except Exception as e:
            print(f"第{rno}Rのデータ取得に失敗しました: {e}")
            continue
        
        scored_bets = []
        
        for combo, odds in odds_info.items():
            # 文字列のオッズをfloatに安全変換（変換できない場合はスキップ）
            try:
                odds_val = float(odds)
            except (ValueError, TypeError):
                continue
            
            # 15.0〜35.0倍のうまみゾーンに絞る
            if not (15.0 <= odds_val <= 35.0):
                continue
            
            boats = [int(b) for b in combo.split('-')]
            total_l3, total_st, total_cr, total_kim = 0, 0, 0, 0
            
            for b in boats:
                boat_key = f"boat{b}"
                boat_data = race_info.get(boat_key, {})
                
                l3, st, cr, kim = get_factor_score(boat_data)
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
