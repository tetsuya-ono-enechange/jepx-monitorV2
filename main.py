import os
import pandas as pd
import asyncio
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

PRICE_LIMIT = 15.0
SUPER_CHEAP_LIMIT = 5.0
OUTPUT_FILE = "result.txt"

def save_combined_data(message, price_csv):
    """詳細文章と数値データをセットで保存する"""
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        # 詳細なレポート文章を書き込む
        f.write(message + "\n")
        # 最後にグラフ用のカンマ区切り数値を書き込む
        f.write(price_csv + "\n")
    print(f"✅ {OUTPUT_FILE} を詳細版で更新しました。")

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
        df = df.dropna(subset=["受渡日", target_area])
        
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

        # 文章レポートの作成（以前の豪華版を復元）
        df_target['時刻コード'] = pd.to_numeric(df_target['時刻コード'])
        min_row = df_target.loc[df_target[target_area].idxmin()]
        min_price = min_row[target_area]
        tc = int(min_row['時刻コード'])
        hour, minute = (tc - 1) // 2, ("30" if tc % 2 == 0 else "00")

        cheap_count = len(df_target[df_target[target_area] <= PRICE_LIMIT])
        
        # 5円以下の時間帯特定
        super_cheap = df_target[df_target[target_area] <= SUPER_CHEAP_LIMIT]
        sc_times = []
        for _, row in super_cheap.iterrows():
            h = (int(row['時刻コード'])-1)//2
            m = "30" if int(row['時刻コード'])%2==0 else "00"
            sc_times.append(f"{h:02d}:{m}")
        sc_str = "、".join(sc_times) if sc_times else "なし"

        daytime_mask = (df_target['時刻コード'] >= 17) & (df_target['時刻コード'] <= 36)
        day_avg = round(df_target.loc[daytime_mask, target_area].mean(), 2)
        night_avg = round(df_target.loc[~daytime_mask, target_area].mean(), 2)
        recommend = f"【{'日中' if day_avg < night_avg else '夜間'} (18時〜翌8時)】" if day_avg != night_avg else "どちらも同じ"

        message = (
            f"【{date_label}のJEPX価格情報】\n"
            f"👑 最安値: {min_price}円 ({hour:02d}:{minute}〜)\n"
            f"🔋 {PRICE_LIMIT}円以下のコマ数: {cheap_count}コマ\n"
            f"✨ {SUPER_CHEAP_LIMIT}円以下の時間帯:\n{sc_str}\n\n"
            f"📊 平均単価比較\n"
            f"☀️ 日中(8-18時): {day_avg}円\n"
            f"🌙 夜間(18-翌8時): {night_avg}円\n\n"
            f"💡 全体的に{recommend}の方が安いです！"
        )

        save_combined_data(message, price_csv)
    except Exception as e:
        print(f"Analysis Error: {e}")

if __name__ == "__main__":
    asyncio.run(main_logic())
