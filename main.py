import os
import requests
from datetime import datetime
# pyjpboatraceのインポート（環境に合わせて調整してください）
# from pyjpboatrace import PyJPBoatrace

# -----------------------------------------
# 1. 設定・Webhookの準備
# -----------------------------------------
# GitHub Secrets等からDiscord Webhook URLを取得
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL', 'ここに直接URLを貼ることも可能')

TARGET_JCD = 11  # びわこ
TARGET_DATE = datetime.now().strftime('%Y-%m-%d') # 今日の日付

# -----------------------------------------
# 2. スコアリング用の関数定義
# -----------------------------------------
def get_factor_score(racer_data, boat_num):
    """
    各艇の各種ファクターを取得する関数
    ※race_data（出走表データ）の実際のキー名に合わせて変更してください。
    """
    # pyjpboatraceから取得できるキーを想定
    local_3ren = float(racer_data.get('local_win_rate_3', 0.0))  # 当地3連対率（%）
    ave_st = float(racer_data.get('ave_st', 0.20))               # 平均ST（秒）
    
    # 【拡張枠】枠番実績と展開（決まり手）のデータ
    # 将来的に外部サイト(Boaters等)からスクレイピングしたデータを辞書等で用意し、
    # 艇番(boat_num)をキーにしてここに紐付けることができます。
    # 今回はスコアリングの枠組みとして基本値(50.0)を置いています。
    course_record_score = 50.0 
    kimarite_score = 50.0

    return local_3ren, ave_st, course_record_score, kimarite_score

def calculate_score(odds, avg_local_3ren, avg_st, avg_course, avg_kimarite):
    """
    総合スコアを計算する関数（重み付けは好みに合わせて調整可能）
    """
    # ① 当地適性（高いほどプラス: 最大で約40〜50点）
    score = avg_local_3ren * 0.8 
    
    # ② スタート力（低い=速いほどプラス。基準0.18秒とし、それより速いと加点）
    # 例: 平均0.13秒なら (0.18 - 0.13) * 200 = 10点プラス
    score += (0.18 - avg_st) * 200 
    
    # ③ オッズ妙味（高いほどプラス: 15〜35倍なら 4.5〜10.5点）
    score += float(odds) * 0.3
    
    # ④ 枠番・決まり手（今後の外部データ連携用）
    score += (avg_course + avg_kimarite) * 0.1

    return score

# -----------------------------------------
# 3. メイン処理（全12レースループ）
# -----------------------------------------
def main():
    # boatrace = PyJPBoatrace() # インスタンス化
    
    report_message = f"🏆 **【びわこSG 全レース うまみ＆適性スコア分析】**\n({TARGET_DATE})\n\n"

    for rno in range(1, 13):
        # --------------------------------------------------
        # [ここに既存のデータ取得ロジックを配置]
        # race_info = boatrace.get_race_info(d=TARGET_DATE, jcd=TARGET_JCD, rno=rno)
        # odds_info = boatrace.get_odds_trifecta(d=TARGET_DATE, jcd=TARGET_JCD, rno=rno)
        # --------------------------------------------------
        
        # ※以下はテスト用のダミーデータです。上記で取得した変数に置き換えてください。
        odds_info = {'1-2-3': 17.1, '2-1-3': 32.8, '1-4-5': 45.0, '3-1-2': 29.9}
        race_info = {
            'racers': [
                {'local_win_rate_3': 45.2, 'ave_st': 0.14}, # 1号艇
                {'local_win_rate_3': 32.1, 'ave_st': 0.16}, # 2号艇
                {'local_win_rate_3': 50.4, 'ave_st': 0.12}, # 3号艇
                {'local_win_rate_3': 28.0, 'ave_st': 0.18}, # 4号艇
                {'local_win_rate_3': 35.5, 'ave_st': 0.15}, # 5号艇
                {'local_win_rate_3': 20.0, 'ave_st': 0.19}, # 6号艇
            ]
        }
        
        scored_bets = []
        
        # オッズ一覧をループして評価
        for combo, odds in odds_info.items():
            # 1. オッズのうまみ判定（15.0〜35.0倍）
            if not (15.0 <= odds <= 35.0):
                continue
            
            # '1-2-3' などの文字列を [1, 2, 3] の数値リストに変換
            boats = [int(b) for b in combo.split('-')]
            
            total_l3, total_st, total_cr, total_kim = 0, 0, 0, 0
            
            # 買い目に絡む3艇のデータを取り出して合計
            for b in boats:
                racer_data = race_info['racers'][b - 1] # 1号艇はindex 0
                l3, st, cr, kim = get_factor_score(racer_data, b)
                total_l3 += l3
                total_st += st
                total_cr += cr
                total_kim += kim
            
            # 3艇の平均値を算出
            avg_l3 = total_l3 / 3
            avg_st = total_st / 3
            avg_cr = total_cr / 3
            avg_kim = total_kim / 3
            
            # 総合スコア算出
            score = calculate_score(odds, avg_l3, avg_st, avg_cr, avg_kim)
            
            scored_bets.append({
                'combo': combo,
                'odds': odds,
                'score': score,
                'avg_l3': avg_l3,
                'avg_st': avg_st
            })
        
        # 総合スコアが高い順（降順）にソート
        scored_bets.sort(key=lambda x: x['score'], reverse=True)
        
        # レポート文面の作成（各レース上位3つの買い目を抽出）
        report_message += f"・第{rno}R: "
        if scored_bets:
            top_bets_str = []
            for bet in scored_bets[:3]:
                # フォーマット例: 1-2-3(17.1倍, Score: 45.2)
                top_bets_str.append(f"{bet['combo']}({bet['odds']}倍, SC:{bet['score']:.1f})")
            report_message += ", ".join(top_bets_str) + "\n"
        else:
            report_message += "対象の買い目なし\n"

    # -----------------------------------------
    # 4. Discordへ通知（Webhook）
    # -----------------------------------------
    print(report_message) # ログ確認用

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

if __name__ == "__main__":
    main()
