import os
import sys
import asyncio
import logging
from playwright.async_api import async_playwright
from telegram import Bot
from telegram.error import TelegramError

# Setup Logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TRADINGVIEW_URL = os.getenv("TRADINGVIEW_URL")

async def capture_tradingview_chart(url: str, output_path: str = "chart.png"):
    """Membuka TradingView, menunggu indikator render, lalu mengambil screenshot."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=2
        )
        page = await context.new_page()

        try:
            logging.info(f"Membuka URL TradingView: {url}")
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Tunggu elemen canvas dimuat
            await page.wait_for_selector("canvas", timeout=30000)
            
            # Jeda 10 detik agar indikator kustom selesai merender
            logging.info("Menunggu render indikator kustom...")
            await page.wait_for_timeout(10000)

            # Inject CSS aman (sebaris tanpa newline)
            css_hide = ".tv-header, .layout__area--left { display: none !important; visibility: hidden !important; }"
            await page.add_style_tag(content=css_hide)

            # Ambil screenshot dari elemen center atau full page
            chart_element = page.locator(".layout__area--center")
            if await chart_element.count() > 0:
                await chart_element.screenshot(path=output_path)
            else:
                await page.screenshot(path=output_path)

            logging.info(f"Screenshot berhasil disimpan ke {output_path}")
            return True

        except Exception as e:
            logging.error(f"Gagal mengambil screenshot: {str(e)}")
            return False
        finally:
            await browser.close()

async def send_telegram_photo(token: str, chat_id: str, image_path: str, caption: str):
    """Mengirim file gambar ke Telegram."""
    bot = Bot(token=token)
    try:
        with open(image_path, "rb") as photo:
            await bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
        logging.info("Foto berhasil terkirim ke Telegram.")
    except TelegramError as e:
        logging.error(f"Gagal mengirim pesan ke Telegram: {str(e)}")
        raise e

async def main():
    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TRADINGVIEW_URL]):
        logging.error("Environment variables belum diatur secara lengkap!")
        sys.exit(1)

    image_file = "xauusd_chart.png"
    caption = "📊 **Update Chart XAUUSD (1 Jam)**\nRender otomatis via GitHub Actions."

    success = await capture_tradingview_chart(TRADINGVIEW_URL, image_file)

    if success and os.path.exists(image_file):
        try:
            await send_telegram_photo(
                TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, image_file, caption
            )
        except Exception as e:
            logging.error(f"Error pada pengiriman Telegram: {e}")
    else:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID, 
            text="⚠️ **Warning Bot Chart:** Gagal mengambil screenshot TradingView pada jam ini."
        )

if __name__ == "__main__":
    asyncio.run(main())
