import sys
from datetime import date, timedelta
from pyjpboatrace import PyJPBoatrace

if __name__ == "__main__":
    print("🚀 APIデータの構造確認テスト開始")
    boatrace = PyJPBoatrace()
    target_date = date.today() - timedelta(days=1)
    
    # テストとして「1場・第1レース」だけを取得
    stadium = 1
    rno = 1
    
    try:
        race_info = boatrace.get_race_info(d=target_date, stadium=stadium, race=rno)
        just_before = boatrace.get_just_before_info(d=target_date, stadium=stadium, race=rno)
        
        print(f"\n--- 📅 対象日: {target_date} 場: {stadium} R{rno} ---")
        print("\n【race_info の中身】")
        print(race_info)
        
        print("\n【just_before の中身】")
        print(just_before)
        
    except Exception as e:
        print(f"❌ エラー発生: {e}")

