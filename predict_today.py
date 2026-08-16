import os
import requests
import pandas as pd
import lightgbm as lgb
from datetime import date
import sys
import itertools
import numpy as np

# --- PyJPBoatraceの読み込み ---
try:
    from pyjpboatrace import PyJPBoatrace
except Exception as e:
    print(f"❌ PyJPBoatrace 読み込み失敗: {e}")
    sys.exit(1)

# --- ヘルパー関数 ---
def safe_float(val, default=0.0):
    if val is None: return default
    val_str = str(val).replace('m', '').replace('%', '').strip()
    if val_str == '' or val_str == '-': return default
    try: return float(val_str)
    except: return default

def send_discord_notification(message):
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("⚠️ DISCORD_WEBHOOK_URL が設定されていません")
        return
    try:
        response = requests.post(webhook_url, json={"content": message})
        print(f"💬 Discord通知送信: Status {response.status_code}")
    except Exception as e:
        print(f"⚠️ Discord通知エラー: {e}")

# --- データ定義 ---
STADIUM_MAP = {
    '桐生': '01', '戸田': '02', '江戸川': '03', '平和島': '04', '多摩川': '05',
    '浜名湖': '06', '蒲郡': '07', '常滑': '08', '津': '09', '三国': '10',
    'びわこ': '11', '琵琶湖': '11', '住之江': '12', '尼崎': '13', '鳴門': '14',
    '丸亀': '15', '児島': '16', '宮島': '17', '徳山': '18', '下関': '19',
    '若松': '20', '芦屋': '21', '福岡': '22', '唐津': '23', '大村': '24'
}
CODE_TO_STADIUM = {v: k for k, v in STADIUM_MAP.items()}

# --- 推論ロジック ---
def run_inference(model, target_stadium, target_race_no):
    try:
        print(f"🔍 推論開始: {CODE_TO_STADIUM.get(target_stadium, target_stadium)} {target_race_no}R")
        boatrace = PyJPBoatrace()
        today = date.today()
        race_info = boatrace.get_race_info(d=today, stadium=int(target_stadium), race=int(target_race_no))
        
        if not race_info:
            print("⚠️ レースデータ取得失敗")
            return None

        # ここで前回の「メリハリ重視」の推論計算を行う
        # (モデルが存在する場合の推論ロジック)
        # ...今回は省略せず前回同様の処理を記述してください...
        
        # 今回はエラー確認のため、単純な成功メッセージを返すようにします
        return f"🎯 {CODE_TO_STADIUM.get(target_stadium)} 第{target_race_no}Rの予測成功"

    except Exception as e:
        print(f"❌ 推論エラー: {e}")
        return None

# --- メイン処理 ---
def predict_main():
    print("🚀 実行開始")
    
    # 1. モデルロード確認
    model_path = 'model.txt'
    model = None
    if os.path.exists(model_path):
        model = lgb.Booster(model_file=model_path)
        print("✅ モデルロード成功")
    else:
        print("⚠️ モデルファイルが見つかりません。")
        # モデルがない場合でも処理を止めないよう修正
    
    input_stadium = os.environ.get("INPUT_STADIUM", "").strip()
    input_race_no = os.environ.get("INPUT_RACE_NO", "").strip()
    
    print(f"DEBUG: Input Stadium={input_stadium}, RaceNo={input_race_no}")

    # 2. 個別予測モード
    if input_stadium and input_race_no:
        stadium_code = STADIUM_MAP.get(input_stadium, input_stadium.zfill(2))
        print(f"DEBUG: Resolved Code={stadium_code}")
        
        if stadium_code in CODE_TO_STADIUM:
            res = run_inference(model, stadium_code, input_race_no)
            if res:
                send_discord_notification(res)
                print("✅ 個別通知送信完了")
            else:
                print("⚠️ 推論結果がNoneでした")
        else:
            print(f"⚠️ 不明な会場コード: {stadium_code}")
        return

    print("ℹ️ 一括処理モードへ移行")
    # ...以下、一括処理のコード...

if __name__ == '__main__':
    predict_main()
