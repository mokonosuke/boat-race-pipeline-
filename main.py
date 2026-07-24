from datetime import datetime
from bs4 import BeautifulSoup
import requests

def test_single_race():
    # テストする日付とレース情報（2026年5月1日 桐生 第1R）
    target_ymd = "20260501"
    venue_name = "桐生"
    jcd = "01"
    rno = 1

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    # 出走表と結果ページのURL
    url_list = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={rno}&jcd={jcd}&hd={target_ymd}"
    url_res = f"https://www.boatrace.jp/owpc/pc/race/result?rno={rno}&jcd={jcd}&hd={target_ymd}"

    print(f"--- テスト取得開始: {venue_name} 第{rno}R ({target_ymd}) ---")

    # 1. 出走表の取得テスト
    try:
        res_list = requests.get(url_list, headers=headers, timeout=10)
        print(f"出走表ステータスコード: {res_list.status_code}")
        soup_list = BeautifulSoup(res_list.text, "html.parser")
        racer_rows = soup_list.select(".table1 tbody tr")
        print(f"出走表の選手行数: {len(racer_rows)}行")
    except Exception as e:
        print(f"出走表取得エラー: {e}")

    # 2. 結果ページの取得テスト
    try:
        res_res = requests.get(url_res, headers=headers, timeout=10)
        print(f"結果ページステータスコード: {res_res.status_code}")
        print(f"結果ページHTML文字数: {len(res_res.text)}文字")
        
        # HTMLが短すぎる場合は中身を表示
        if len(res_res.text) < 1000:
            print(f"【HTML中身】\n{res_res.text}")
        else:
            soup_res = BeautifulSoup(res_res.text, "html.parser")
            # すべてのテーブル行をチェック
            result_rows = soup_res.select("table tr")
            print(f"結果ページ table tr 行数: {len(result_rows)}行")
            
            # 見つかった行の内容をいくつか表示
            for i, row in enumerate(result_rows[:10]):
                text = row.get_text(separator=" ", strip=True)
                print(f"  [行 {i+1}] {text}")

    except Exception as e:
        print(f"結果取得エラー: {e}")

if __name__ == "__main__":
    test_single_race()

