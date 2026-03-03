import os
import pandas as pd
import asyncio
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

PRICE_LIMIT = 15.0
SUPER_CHEAP_LIMIT = 5.0
OUTPUT_FILE = "result.txt"

def save_combined_data(message, price_csv):
    """文章と数値をセットで保存する"""
    print("=== 保存内容の確認 ===")
    print(message)
    print(f"数値データ(先頭): {price_csv[:30]}...")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        # 1. まず文章を書き込む
        f.write(message + "\n")
        # 2. 最後にグラフ用のカンマ区切り数値を書き込む
        f.write(price_csv)
    print(f"✅ {OUTPUT_FILE} に文章と数値を保存しました！")

async def main_logic():
    print("処理を開始します...", flush=True)
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    correct_csv_path = None
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1920, "height": 1080})
            page.set_default_timeout(30000)
            
            await page.goto("https://www.jepx.jp/electricpower/market-data/spot/")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(3000)

            # カレンダー操作
            try:
                cal_input = page.locator('input[placeholder*="日付"], .flatpickr-input').first
                await cal_input.click(timeout=5000)
                await page.wait_for_timeout(1000)
                day_cell = page.locator('.flatpickr-day:not(.prevMonthDay):not(.nextMonthDay)').last
                await day_cell.click(timeout=5000)
                await page.wait_for_timeout(1000)
            except Exception:
                pass 

            # ダウンロード
            buttons = page.locator('button:has-text("ダウンロード"), a:has-text("ダウンロード")')
            for i in range(await buttons.count()):
                try:
                    async with page.expect_download(timeout=15000) as dl_info:
                        await buttons.nth(i).evaluate("node => node.click()")
                    download = await dl_info.value
                    temp_path = f"jepx_candidate_{i}.csv"
                    await download.save_as(temp_path)
                    
                    df_temp = pd.read_csv(temp_path, encoding="shift_jis")
                    if any("東京" in col for col in df_temp.columns):
                        correct_csv_path = temp_path
                        break 
                except: continue
            await browser.close()
    except Exception as e:
        print(f"エラー発生: {e}")
        return

    if not correct_csv_path:
        print("CSVが見つかりませんでした。")
        return

    try:
        df = pd.read_csv(correct_csv_path, encoding="shift_jis")
        target_area = next((col for col in df.columns if "東京" in col and "プライス" in col), None)
        df = df.dropna(subset=["受渡日", target_area])
        
        # 日付特定（明日を優先、なければ今日）
        tomorrow_str = tomorrow.strftime("%Y/%m/%d")
        df_target = df[df["受渡日"].str.contains(tomorrow_str, na=False)].copy()
        target_date_str = "明日"
        if df_target.empty:
            today_str = now.strftime("%Y/%m/%d")
            df_target = df[df["受渡日"].str.contains(today_str, na=False)].copy()
            target_date_str = "今日"

        if df_target.empty:
            print("対象データがありません。")
            return

        # --- 1. グラフ用数値データの作成 ---
        prices = df_target[target_area].astype(str).tolist()
        price_csv = ",".join(prices)

        # --- 2. 文章レポートの作成 ---
        df_target['時刻コード'] = pd.to_numeric(df_target['時刻コード'])
        min_row = df_target.loc[df_target[target_area].idxmin()]
        min_price = min_row[target_area]
        tc = int(min_row['時刻コード'])
        hour, minute = (tc - 1) // 2, ("30" if tc % 2 == 0 else "00")

        cheap_count = len(df_target[df_target[target_area] <= PRICE_LIMIT])
        daytime_mask = (df_target['時刻コード'] >= 17) & (df_target['時刻コード'] <= 36)
        daytime_avg = round(df_target.loc[daytime_mask, target_area].mean(), 2)
        nighttime_avg = round(df_target.loc[~daytime_mask, target_area].mean(), 2)
        recommend = "日中" if daytime_avg < nighttime_avg else "夜間"

        message = (
            f"【{target_date_str}のJEPX価格情報】\n"
            f"👑 最安値: {min_price}円 ({hour:02d}:{minute}〜)\n"
            f"🔋 {PRICE_LIMIT}円以下のコマ数: {cheap_count}コマ\n"
            f"📊 平均単価比較\n"
            f"☀️ 日中: {daytime_avg}円 / 🌙 夜間: {nighttime_avg}円\n"
            f"💡 全体的に【{recommend}】の方が安いです！"
        )

        # --- 3. セットで保存 ---
        save_combined_data(message, price_csv)

    except Exception as e:
        print(f"解析エラー: {e}")

if __name__ == "__main__":
    asyncio.run(main_logic())
