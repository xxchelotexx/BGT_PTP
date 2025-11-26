import asyncio
from playwright.async_api import async_playwright
import json
import re

URL = "https://www.bitget.com/p2p-trade/sell?fiatName=BOB"

def clean_number(text):
    """
    Limpia texto tipo '6.90 BOB', '1,234.56 USDT', '≈ 1000', ' 6.95 ' etc
    y devuelve float o None.
    """
    if not text:
        return None
    
    text = text.upper()
    text = text.replace("BOB", "").replace("USDT", "")
    text = text.replace("≈", "")
    text = text.replace(",", "")
    text = text.strip()

    # Extraer solo números, punto o coma
    match = re.findall(r"[0-9\.]+", text)
    if not match:
        return None
    
    try:
        return float(match[0])
    except:
        return None


async def scrap_bitget():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            java_script_enabled=True,
            locale="es-ES",
        )

        page = await context.new_page()

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        await page.goto(URL, timeout=0)

        await page.wait_for_selector(".hall-list-item", timeout=60000)

        cards = await page.query_selector_all(".hall-list-item")
        resultados = []

        for card in cards:
            # MERCHANT
            name_el = await card.query_selector(".list-item__nickname")
            name = await name_el.inner_text() if name_el else None
            if name:
                name = name.strip()

            # PRICE BOB
            price_el = await card.query_selector(".price-shower")
            raw_price = await price_el.inner_text() if price_el else None
            price_bob = clean_number(raw_price)

            # AMOUNT USDT
            amount_el = await card.query_selector(".list_limit span span:first-child")
            raw_amount = await amount_el.inner_text() if amount_el else None
            amount_usdt = clean_number(raw_amount)

            # LIMITS BOB (no se convierte porque son rangos ej: "300 - 1000")
            limit_el = await card.query_selector(".list_limit span span:last-child")
            raw_limits = await limit_el.inner_text() if limit_el else None
            limits_bob = raw_limits.strip() if raw_limits else None

            resultados.append({
                "merchant": name,
                "price_bob": price_bob,      # ahora es número float
                "amount_usdt": amount_usdt,  # ahora es número float
            })

        await browser.close()
        return resultados


if __name__ == "__main__":
    data = asyncio.run(scrap_bitget())
    print(json.dumps(data, indent=4, ensure_ascii=False))
