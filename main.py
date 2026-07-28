from pyjpboatrace import PyJPBoatrace
from datetime import datetime
import os
import requests

DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
TARGET_JCD = 11  # びわこ
TARGET_DATE = datetime.now().strftime('%Y-%m-%d')

def get_factor_score(racer_data, boat_num):
    # pyjpboatraceから取得できる実際のキー名に合わせて調整
    local_3ren = float(racer_data.get('local_win_rate_3', 0.0))
    ave_st = float(racer_data.get('ave_st', 0.20))
    
    course_record_score = 50.0 
    kimarite_score = 50.0

    return local_3ren, ave_st, course_record_score, kimarite_score

def calculate_score(odds, avg_local_3ren, avg_st, avg_course, avg_kimarite):
    score = avg_local_3ren * 0.8 
    score += (0.18 - ave_st) * 200 
    score += float(odds) * 0.3
    score += (avg_course + avg_kimarite) * 0.1
    return score

def main():
    boatrace = PyJPBoatrace() # ライブラリのインスタンス化
    
    report_message = f"🏆 **【びわこSG 全レース うまみ＆適性スコア分析】**\n({TARGET_DATE})\n\n"

    for rno in range(1, 13):
        try:
            # 実際のAPI / ライブラリから各レースのオッズと出走表を取得
            odds_info = boatrace.get_odds_trifecta(d=TARGET_DATE, jcd=TARGET_JCD, rno=rno)
            race_info = boatrace.get_program(d=TARGET_DATE, jcd=TARGET_JCD, rno=rno)
            
        except Exception as e:
            print(f"第{rno}Rのデータ取得に失敗しました: {e}")
            continue
        
        scored_bets = []
        
        # 取得したオッズ辞書をループ（構造に合わせてキー・値を取り出す）
        for combo, odds in odds_info.items():
            if not (15.0 <= odds <= 35.0):
                continue
            
            boats = [int(b) for b in combo.split('-')]
            total_l3, total_st, total_cr, total_kim = 0, 0, 0, 0
            
            for b in boats:
                racer_data = race_info['racers'][b - 1]
                l3, st, cr, kim = get_factor_score(racer_data, b)
                total_l3 += l3
                total_st += st
                total_cr += cr
                total_kim += kim
            
            avg_l3 = total_l3 / 3
            avg_st = total_st / 3
            avg_cr = total_cr / 3
            avg_kim = total_kim / 3
            
            score = calculate_score(odds, avg_l3, avg_st, avg_cr, avg_kim)
            
            scored_bets.append({
                'combo': combo,
                'odds': odds,
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

    if DISCORD_WEBHOOK_URL:
        headers = {'Content-Type': 'application/json'}
        payload = {"content": report_message}
        try:
            response = requests.post(DISCORD_WEBHOOK_URL, headers=headers, json=payload)
            response.raise_for_status()
            print("Discordへの通知が完了しました。")
        except requests.exceptions.RequestException as e:
            print(f"Discordへの送信に失敗しました: {e}")

if __name__ == "__main__":
    main()
