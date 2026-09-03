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
TRADINGVIEW_SESSION_ID = os.getenv("TRADINGVIEW_SESSION_ID")

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
"""

CSS_CLEANUP = """
.tv-header,
.layout__area--left,
.layout__area--right,
.layout__area--bottom,
#header-toolbar-screenshot,
div[class*="cookie"],
div[class*="banner"],
div[class*="modal"],
div[class*="dialog"],
div[id*="overlap-manager"],
.js-dialog {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
}
"""

async def capture_tradingview_chart(url: str, output_path: str = "chart.png"):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu",
                "--hide-scrollbars",
                "--mute-audio",
                "--disable-infobars"
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=2,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="Asia/Jakarta",
            color_scheme="dark"
        )

        # Injeksi Session Cookie TradingView agar login otomatis
        if TRADINGVIEW_SESSION_ID:
            logging.info("Menyuntikkan TradingView Session Cookie...")
            await context.add_cookies([
                {
                    "name": "sessionid",
                    "value": TRADINGVIEW_SESSION_ID,
                    "domain": ".tradingview.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "Lax"
                }
            ])

        page = await context.new_page()
        await page.add_init_script(STEALTH_SCRIPT)

        try:
            logging.info(f"Membuka URL TradingView: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=90000)

            logging.info("Menunggu elemen canvas TradingView...")
            await page.wait_for_selector("canvas", timeout=45000)

            # Jeda 20 detik agar indikator kustom selesai kalkulasi
            logging.info("Menunggu render indikator kustom selesai (20s)...")
            await page.wait_for_timeout(20000)

            await page.add_style_tag(content=CSS_CLEANUP)
            await page.wait_for_timeout(1000)

            chart_element = page.locator(".layout__area--center")
            if await chart_element.count() > 0 and await chart_element.is_visible():
                await chart_element.screenshot(path=output_path, timeout=15000)
            else:
                await page.screenshot(path=output_path, full_page=False)

            logging.info(f"Screenshot berhasil disimpan: {output_path}")
            return True

        except Exception as e:
            logging.error(f"Gagal mengambil screenshot: {str(e)}")
            return False
        finally:
            await browser.close()

async def send_telegram_photo(token: str, chat_id: str, image_path: str, caption: str):
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
