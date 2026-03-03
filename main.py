import os
import pandas as pd
import asyncio
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

async def get_jepx_data():
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    target_date_str = tomorrow.strftime("%Y/%m/%d")
    csv_file = "jepx_data.csv"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        print("JEPXサイトにアクセス中...")
        await page.goto("https://www.jepx.jp/electricpower/market-data/spot/", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # ダウンロードボタンを探して、成功するまでループ
        buttons = page.locator('button:has-text("ダウンロード"), a:has-text("ダウンロード")')
        success = False
        for i in range(await buttons.count()):
            try:
                print(f"ボタン {i+1} を試行中...")
                async with page.expect_download(timeout=30000) as dl_info:
                    await buttons.nth(i).click()
                download = await dl_info.value
                await download.save_as(csv_file)
                
                # 東京のデータが含まれているかチェック
                df_test = pd.read_csv(csv_file, encoding="shift_jis")
                if any("東京" in col for col in df_test.columns):
                    print("✅ 正しいCSVを取得しました")
                    success = True
                    break
            except:
                continue
        
        await browser.close()
        if not success: return None, None

    # データ解析
    df = pd.read_csv(csv_file, encoding="shift_jis")
    area_col = next(c for c in df.columns if "東京" in c and "プライス" in c)
    df_day = df[df["受渡日"] == target_date_str].copy()
    
    if df_day.empty:
        # 明日がなければ今日を取得
        target_date_str = now.strftime("%Y/%m/%d")
        df_day = df[df["受渡日"] == target_date_str].copy()

    prices = df_day[area_col].tolist()
    avg = round(sum(prices)/len(prices), 2)
    min_p = min(prices)
    
    report = f"【{target_date_str}の価格】平均:{avg}円 / 最安:{min_p}円"
    price_csv = ",".join(map(str, prices))
    
    return report, price_csv

async def main():
    report, prices = await get_jepx_data()
    if report:
        with open("result.txt", "w", encoding="utf-8") as f:
            f.write(report + "\n" + prices)
        print("✅ result.txt を更新しました")
    else:
        print("❌ データの取得に失敗しました")

if __name__ == "__main__":
    asyncio.run(main())
