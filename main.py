    for rno in range(1, 13):
        try:
            # 実際のAPI / ライブラリから各レースのデータを取得
            # ※pyjpboatraceの実際のメソッド名に合わせて調整してください
            odds_info = boatrace.get_odds_trifecta(d=TARGET_DATE, jcd=TARGET_JCD, rno=rno)
            race_info = boatrace.get_program(d=TARGET_DATE, jcd=TARGET_JCD, rno=rno)
            
        except Exception as e:
            print(f"第{rno}Rのデータ取得に失敗しました: {e}")
            continue
        
        scored_bets = []
        
        # オッズ一覧をループして評価
        # （※取得したodds_infoのデータ構造に合わせてループ処理を記述します）
        for combo, odds in odds_info.items():
            # 1. オッズのうまみ判定（15.0〜35.0倍）
            if not (15.0 <= odds <= 35.0):
                continue
            
            boats = [int(b) for b in combo.split('-')]
            
            total_l3, total_st, total_cr, total_kim = 0, 0, 0, 0
            
            for b in boats:
                # 出走表から各艇のデータを抽出
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
