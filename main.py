import os
import pandas as pd
import asyncio
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

PRICE_LIMIT = 15.0
OUTPUT_FILE = "result.txt"

def save_combined_data(message, price_csv):
    """文章と数値を確実にセットで保存する"""
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(message + "\n")
        f.write(price_csv + "\n")
    print(f"✅ {OUTPUT_FILE} を更新しました。")

async def main_logic():
    print("処理を開始します...", flush=True)
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    correct_csv_path = None
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1920, "height": 1080})
            await page.goto("https://www.jepx.jp/electricpower/market-data/spot/", wait_until="networkidle")
            await page.wait_for_timeout(3000)

            # ダウンロードボタンを探す
            buttons = page.locator('button:has-text("ダウンロード"), a:has-text("ダウンロード")')
            for i in range(await buttons.count()):
                try:
                    async with page.expect_download(timeout=15000) as dl_info:
                        await buttons.nth(i).evaluate("node => node.click()")
                    download = await dl_info.value
                    temp_path = f"jepx_data.csv"
                    await download.save_as(temp_path)
                    correct_csv_path = temp_path
                    break
                except: continue
            await browser.close()
    except Exception as e:
        print(f"Browser Error: {e}")
        return

    if not correct_csv_path: return

    try:
        df = pd.read_csv(correct_csv_path, encoding="shift_jis")
        target_area = next((col for col in df.columns if "東京" in col and "プライス" in col), None)
        
        target_date = tomorrow.strftime("%Y/%m/%d")
        df_target = df[df["受渡日"].str.contains(target_date, na=False)].copy()
        date_label = "明日"
        if df_target.empty:
            target_date = now.strftime("%Y/%m/%d")
            df_target = df[df["受渡日"].str.contains(target_date, na=False)].copy()
            date_label = "今日"

        # グラフ用データ
        prices = df_target[target_area].astype(str).tolist()
        price_csv = ",".join(prices)

        # レポート文
        min_p = df_target[target_area].min()
        avg_p = round(df_target[target_area].mean(), 2)
        message = f"【{date_label}のJEPX情報】平均:{avg_p}円 最安:{min_p}円。詳細は画像を確認！"

        save_combined_data(message, price_csv)
    except Exception as e:
        print(f"Analysis Error: {e}")

if __name__ == "__main__":
    asyncio.run(main_logic())
