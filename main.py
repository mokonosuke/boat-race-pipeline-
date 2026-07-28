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
# 2. ファクター抽出・気象補正関数
# -----------------------------------------
def get_factor_score(boat_data, assigned_course):
    """
    各選手のデータから当地成績、平均ST、枠番実績、決まり手を抽出
    """
    local_3ren = float(boat_data.get('local_in3rd', 0.0))
    ave_st = float(boat_data.get('aveST', 0.20))
    
    course_key = f"course_{assigned_course}_2nd_rate"
    course_record_score = float(boat_data.get(course_key, 30.0))
    
    kimarite_type = boat_data.get('primary_kimarite', 'normal')
    if kimarite_type in ['makuri', 'tsuki_makuri'] and assigned_course in [4, 5, 6]:
        kimarite_score = 45.0  # 外枠まくり加点
    elif kimarite_type == 'sashi' and assigned_course in [2, 3]:
        kimarite_score = 45.0  # 差し巧者加点
    elif kimarite_type == 'nige' and assigned_course == 1:
        kimarite_score = 50.0  # イン逃げ信頼度
    else:
        kimarite_score = 35.0

    return local_3ren, ave_st, course_record_score, kimarite_score

def get_weather_adjustment(race_info):
    """
    【新規実装】気象条件（風速・波高）から荒れ度合いに応じた補正値を算出
    """
    weather_info = race_info.get('weather', {})
    
    # 風速の文字列から数値への変換（例: "5m" -> 5.0）
    wind_speed_str = str(weather_info.get('wind_speed', '0')).replace('m', '').strip()
    try:
        wind_speed = float(wind_speed_str)
    except ValueError:
        wind_speed = 0.0
        
    # 波高の文字列から数値への変換（例: "3cm" -> 3.0）
    wave_height_str = str(weather_info.get('wave_height', '0')).replace('cm', '').strip()
    try:
        wave_height = float(wave_height_str)
    except ValueError:
        wave_height = 0.0

    # 補正ロジック: 風速が5m以上または波高が5cm以上の場合は「荒れ水面」と判定してボーナスを付与
    adjustment = 0.0
    if wind_speed >= 5.0:
        adjustment += 4.0  # 強風補正
    if wave_height >= 5.0:
        adjustment += 3.0  # 高波補正

    return adjustment, wind_speed, wave_height

def calculate_score(odds_val, avg_local_3ren, avg_st, avg_course, avg_kimarite, weather_adj):
    """
    気象補正を含めた総合スコア算出
    """
    score = avg_local_3ren * 0.7 
    score += (0.18 - avg_st) * 180 
    score += avg_course * 0.3
    score += avg_kimarite * 0.2
    score += odds_val * 0.25
    
    # 気象による荒れ度合いボーナスを加算
    score += weather_adj

    return score

# -----------------------------------------
# 3. メイン処理（全12レース自動ループ）
# -----------------------------------------
def main():
    boatrace = PyJPBoatrace()
    
    report_message = f"🏆 **【びわこSG 気象連動スコア分析】**\n({TARGET_DATE.strftime('%Y-%m-%d')})\n\n"

    for rno in range(1, 13):
        try:
            odds_info = boatrace.get_odds_trifecta(d=TARGET_DATE, stadium=TARGET_JCD, race=rno)
            race_info = boatrace.get_race_info(d=TARGET_DATE, stadium=TARGET_JCD, race=rno)
        except Exception as e:
            print(f"第{rno}Rのデータ取得に失敗しました: {e}")
            continue
        
        # 気象データの取得と補正値計算
        weather_adj, wind_spd, wave_ht = get_weather_adjustment(race_info)
        
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
            
            score = calculate_score(odds_val, avg_l3, avg_st, avg_cr, avg_kim, weather_adj)
            
            scored_bets.append({
                'combo': combo,
                'odds': odds_val,
                'score': score,
            })
        
        scored_bets.sort(key=lambda x: x['score'], reverse=True)
        
        report_message += f"・第{rno}R (風:{wind_spd}m/波:{wave_ht}cm): "
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
