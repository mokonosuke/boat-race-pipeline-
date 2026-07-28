# -----------------------------------------
# 3. メイン処理（全12レースループ）
# -----------------------------------------
def main():
    # boatrace = PyJPBoatrace() # インスタンス化
    
    report_message = f"🏆 **【びわこSG 全レース うまみ＆適性スコア分析】**\n({TARGET_DATE})\n\n"

    for rno in range(1, 13):
        try:
            # 実際のAPI / ライブラリから各レースのデータを取得
            # odds_info = boatrace.get_odds_trifecta(d=TARGET_DATE, jcd=TARGET_JCD, rno=rno)
            # race_info = boatrace.get_program(d=TARGET_DATE, jcd=TARGET_JCD, rno=rno)
            
            # --- テスト用データ（API連携時は上記コメントアウトを解除してください） ---
            odds_info = {'1-2-3': 17.1, '2-1-3': 32.8, '1-4-5': 45.0, '3-1-2': 29.9}
            race_info = {
                'racers': [
                    {'local_win_rate_3': 45.2, 'ave_st': 0.14},
                    {'local_win_rate_3': 32.1, 'ave_st': 0.16},
                    {'local_win_rate_3': 50.4, 'ave_st': 0.12},
                    {'local_win_rate_3': 28.0, 'ave_st': 0.18},
                    {'local_win_rate_3': 35.5, 'ave_st': 0.15},
                    {'local_win_rate_3': 20.0, 'ave_st': 0.19},
                ]
            }
            # ------------------------------------------------------------------

        except Exception as e:
            print(f"第{rno}Rのデータ取得に失敗しました: {e}")
            continue
        
        scored_bets = []
        
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

    # -----------------------------------------
    # 4. Discordへ通知（Webhook）
    # -----------------------------------------
    print(report_message)

    if DISCORD_WEBHOOK_URL and DISCORD_WEBHOOK_URL != 'ここに直接URLを貼ることも可能':
        headers = {'Content-Type': 'application/json'}
        payload = {"content": report_message}
        try:
            response = requests.post(DISCORD_WEBHOOK_URL, headers=headers, json=payload)
            response.raise_for_status()
            print("Discordへの通知が完了しました。")
        except requests.exceptions.RequestException as e:
            print(f"Discordへの送信に失敗しました: {e}")
    else:
        print("Webhook URLが設定されていないため、通知はスキップされました。")
