#!/usr/bin/env python3
"""
main.py
Script utama untuk mengambil screenshot chart TradingView (XAUUSD) dan mengirimkannya ke Telegram.
Menggunakan: playwright.async_api dan python-telegram-bot
"""
import os
import asyncio
import logging
from datetime import datetime

from playwright.async_api import async_playwright
from telegram import Bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TRADINGVIEW_URL = os.getenv("TRADINGVIEW_URL")
OUTPUT_FILE = "xauusd_chart.png"


async def send_telegram_photo(bot_token: str, chat_id: str, photo_path: str, caption: str):
    try:
        bot = Bot(token=bot_token)
        # Bot supports async context manager in recent versions
        async with bot:
            logger.info("Sending photo to Telegram chat_id=%s", chat_id)
            with open(photo_path, "rb") as photo:
                await bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
    except Exception:
        logger.exception("Failed to send photo to Telegram")
        raise


async def send_telegram_message(bot_token: str, chat_id: str, text: str):
    try:
        bot = Bot(token=bot_token)
        async with bot:
            logger.info("Sending message to Telegram chat_id=%s", chat_id)
            await bot.send_message(chat_id=chat_id, text=text)
    except Exception:
        logger.exception("Failed to send message to Telegram")
        raise


async def capture_chart(url: str, output_path: str):
    logger.info("Starting Playwright to capture %s", url)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=2)
        page = await context.new_page()

        # Navigate to page
        logger.info("Navigating to TradingView URL")
        await page.goto(url, wait_until="networkidle", timeout=60000)

        # Wait for canvas element (chart) to appear
        logger.info("Waiting for canvas element to appear")
        await page.wait_for_selector("canvas", timeout=60000)

        # Allow extra time for custom indicators to render
        logger.info("Waiting extra 10 seconds for indicators/render")
        await asyncio.sleep(10)

        # Inject CSS to hide distracting UI elements
        css = ".tv-header, .layout__area--left { display: none !important; visibility: hidden !important; }
.layout__area--center { background: transparent !important; }"
        logger.info("Injecting CSS to hide UI elements")
        await page.add_style_tag(content=css)

        # Locate center layout and screenshot
        logger.info("Locating .layout__area--center and capturing screenshot")
        locator = page.locator(".layout__area--center")
        await locator.scroll_into_view_if_needed()

        # Small wait to let CSS reflow
        await asyncio.sleep(1)

        await locator.screenshot(path=output_path)

        await context.close()
        await browser.close()
    logger.info("Screenshot saved to %s", output_path)


async def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or not TRADINGVIEW_URL:
        logger.error("Missing one or more required environment variables: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TRADINGVIEW_URL")
        raise SystemExit(1)

    try:
        await capture_chart(TRADINGVIEW_URL, OUTPUT_FILE)

        caption = f"XAUUSD chart update — {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        await send_telegram_photo(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, OUTPUT_FILE, caption)

    except Exception as e:
        logger.exception("Error occurred during capture or send: %s", e)
        # Try to notify via Telegram about the failure
        try:
            text = f"⚠️ Chart bot failed to capture/send chart. Error: {e}"
            await send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, text)
        except Exception:
            logger.exception("Failed to send error notification to Telegram")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        logger.exception("Unhandled exception in main")
        raise
