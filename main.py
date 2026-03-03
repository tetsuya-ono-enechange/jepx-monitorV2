import os
import pandas as pd
import asyncio
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

async def main_logic():
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    csv_file = "jepx_data.csv"
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            await page.goto("https://www.jepx.jp/electricpower/market-data/spot/", wait_until="networkidle")
            
            # ダウンロード成功までリトライ
            buttons = page.locator('button:has-text("ダウンロード"), a:has-text("ダウンロード")')
            success = False
            for i in range(await buttons.count()):
                try:
                    async with page.expect_download(timeout=30000) as dl_info:
                        await buttons.nth(i).click()
                    download = await dl_info.value
                    await download.save_as(csv_file)
                    df_test = pd.read_csv(csv_file, encoding="shift_jis")
                    if any("東京" in col for col in df_test.columns):
                        success = True
                        break
                except: continue
            await browser.close()
            if not success: return

        # 解析
        df = pd.read_csv(csv_file, encoding="shift_jis")
        area_col = next(c for c in df.columns if "東京" in c and "プライス" in c)
        
        target_date_str = tomorrow.strftime("%Y/%m/%d")
        df_day = df[df["受渡日"] == target_date_str].copy()
        if df_day.empty:
            target_date_str = now.strftime("%Y/%m/%d")
            df_day = df[df["受渡日"] == target_date_str].copy()

        # 48コマの数字を作成
        prices = df_day[area_col].astype(str).tolist()
        price_csv = ",".join(prices)

        # レポート文章（改行をすべて消して「1行目」を死守する）
        avg_p = round(df_day[area_col].mean(), 2)
        min_p = df_day[area_col].min()
        report = f"【{target_date_str}価格】 平均:{avg_p}円 最安:{min_p}円。詳細はグラフ参照。"

        # ★ここが最重要：result.txtを「2行」で作成
        with open("result.txt", "w", encoding="utf-8") as f:
            f.write(report + "\n") # 1行目
            f.write(price_csv)     # 2行目
            
        print("✅ result.txt を2行形式で保存しました")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main_logic())
