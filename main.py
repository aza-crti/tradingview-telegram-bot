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
    """Membuka TradingView dengan konfigurasi anti-bot, menunggu render, lalu screenshot."""
    async with async_playwright() as p:
        # Tambahkan argumen anti-bot & bypass keamanan cloud
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        
        # Gunakan User-Agent Desktop nyata agar tidak diblokir TradingView/Cloudflare
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=2,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            logging.info(f"Membuka URL TradingView: {url}")
            # Gunakan domcontentloaded agar tidak nyangkut selamanya di networkidle
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Beri jeda waktu yang cukup untuk WebSocket & indikator kustom merender data
            logging.info("Menunggu kalkulasi indikator kustom selesai...")
            await page.wait_for_timeout(15000)

            # Sembunyikan elemen UI TradingView yang mengganggu
            css_hide = ".tv-header, .layout__area--left, #header-toolbar-screenshot { display: none !important; visibility: hidden !important; }"
            await page.add_style_tag(content=css_hide)

            # Ambil screenshot area chart utama, fallback ke fullpage jika gagal
            chart_element = page.locator(".layout__area--center")
            if await chart_element.count() > 0:
                await chart_element.screenshot(path=output_path)
            else:
                await page.screenshot(path=output_path)

            logging.info(f"Screenshot berhasil disimpan ke {output_path}")
            return True

        except Exception as e:
            logging.error(f"GAGAL PLAYWRIGHT: {str(e)}")
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
    caption = "📊 **Update Chart XAUUSD (1 Jam)**\nIndikator kustom otomatis di-render."

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
            text="⚠️ **Warning Bot Chart:** Gagal mengambil screenshot TradingView pada jam ini. Cek log GitHub Actions."
        )

if __name__ == "__main__":
    asyncio.run(main())
