import asyncio
from playwright.async_api import async_playwright
import json
import re
import sys
from collections import defaultdict
from flask import Flask, render_template_string
import os
import nest_asyncio

# Aplica nest_asyncio para permitir la ejecución de asyncio.run anidado,
# lo cual es común cuando se ejecuta código asíncrono dentro de un entorno síncrono
# como el servidor de desarrollo de Flask.
nest_asyncio.apply()

# ----------------- CONFIGURACIÓN FLASK Y BÁSICA -----------------
app = Flask(__name__)
# Forzar codificación UTF-8 en consola para evitar errores de impresión (mantenemos la configuración original)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# --- URLs Definidas ---
# Cambiamos los nombres para mayor claridad en el contexto P2P:
# VENTA de USDT -> Compramos BOB (Side 1 en Bybit, Offer Side en Bitget)
# COMPRA de USDT -> Vendemos BOB (Side 0 en Bybit, Demand Side en Bitget)
URL_VENTAS = "https://www.bitget.com/p2p-trade/sell?paymethodIds=-1&fiatName=BOB" # La gente VENDE USDT, tu COMPRAS BOB
URL_COMPRAS = "https://www.bitget.com/p2p-trade?paymethodIds=-1&fiatName=BOB" # La gente COMPRA USDT, tu VENDES BOB

# --- Función Auxiliar ---
def clean_number(text):
    """Limpia texto y devuelve float."""
    if not text: return None
    text = text.upper().replace("BOB", "").replace("USDT", "").replace("≈", "").replace(",", "").strip()
    match = re.findall(r"[0-9\.]+", text)
    if not match: return None
    try: return float(match[0])
    except: return None

# --- Función de Scraping Reutilizable ---
async def scrape_bitget_p2p(url: str, operation_type: str):
    """
    Función de scraping adaptada para devolver resultados silenciosamente.
    Se eliminan los print() excepto los de errores importantes.
    """
    all_results = []
    MAX_PAGES = 2 # Limitado a 2 páginas para el ejemplo

    async with async_playwright() as pw:
        # Configuración Anti-Detección
        browser = await pw.chromium.launch(
            headless=True,  
            args=["--disable-blink-features=AutomationControlled"]
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page = await context.new_page()

        try:
            # print(f"Navegando a {url}...")
            await page.goto(url, timeout=90000) 

            # Lógica de Cierre de Popups
            await page.wait_for_timeout(4000) 
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
            await page.mouse.click(50, 50)
            await page.wait_for_timeout(500)
            
            try: await page.locator('.bit-dialog__close').click(timeout=3000)
            except Exception: pass
            
            try: await page.get_by_test_id('MicroCookieAcceptButton').click(timeout=3000)
            except Exception: pass
            
            await page.wait_for_selector(".hall-list-item", state="visible", timeout=60000)
            
            # Bucle de Paginación y Scraping
            for page_num in range(1, MAX_PAGES + 1):
                page_str = str(page_num)

                # ⚠️ 1. NAVEGACIÓN (Solo hacer clic si no estamos en la página 1)
                if page_num > 1:
                    target_page_locator = page.get_by_text(page_str, exact=True)

                    if await target_page_locator.count() == 0:
                        break # No se encontró el número de página. Finalizando.

                    await target_page_locator.click(force=True)
                    
                    # Esperamos a que la página se active
                    try:
                        await page.wait_for_selector(
                            f'.bit-pager li.number.active:has-text("{page_str}")',
                            timeout=10000 
                        )
                        await page.wait_for_timeout(1500) 
                    except Exception:
                        continue # La página no se activó a tiempo. Saltando la extracción.

                # 📝 2. EXTRACCIÓN DE DATOS
                await page.wait_for_timeout(1000)
                cards = await page.query_selector_all(".hall-list-item")

                for card in cards:
                    name_el = await card.query_selector(".list-item__nickname")
                    name = await name_el.inner_text() if name_el else "N/A"

                    price_el = await card.query_selector(".price-shower")
                    raw_price = await price_el.inner_text() if price_el else None

                    amount_el = await card.query_selector(".list_limit span span:first-child")
                    raw_amount = await amount_el.inner_text() if amount_el else None
                    
                    all_results.append({
                        "tipo": operation_type,
                        "pagina": page_num,
                        "merchant": name.strip(),
                        "precio_bob": clean_number(raw_price),
                        "monto_usdt": clean_number(raw_amount),
                    })

            return all_results

        except Exception as e:
            # Imprimimos el error, pero permitimos que continúe
            print(f"Ocurrió un error en el scrapeo de {operation_type}: {e}")
            return all_results
        
        finally:
            await browser.close()


def procesar_datos_html(data, estado):
    """
    Procesa la lista de transacciones y genera el resultado en formato HTML.
    
    :param data: Lista de diccionarios con las transacciones.
    :param estado: 1 para 'ventas' (verde - Ofertas), 0 para 'compras' (rojo - Demandas).
    :return: String HTML con la tabla de resultados.
    """
    # 1. Agrupación y Cálculo de Volumen Total
    agrupado = defaultdict(lambda: {"suma": 0.0, "conteo": 0})
    vol_total = 0.0
    
    for item in data:
        precio = item.get("precio_bob")
        cantidad = item.get("monto_usdt")
        
        # Validar datos
        if precio is None or cantidad is None: continue
        if precio == 0 or cantidad == 0: continue
            
        vol_total += cantidad
        agrupado[precio]["suma"] += cantidad
        agrupado[precio]["conteo"] += 1

    # 2. Visualización
    
    # Adaptación a la nomenclatura de Bybit
    if estado == 0:
        titulo = "🔴 Ofertas de Venta (Demandas)"
        color = "red"
        reverse_sort = True # Precio alto primero
    else:
        titulo = "🟢 Ofertas de Compra (Ofertas)"
        color = "green"
        reverse_sort = False # Precio bajo primero
    
    # 3. Generación HTML
    output_html = f"<h2>{titulo}</h2>"
    output_html += f"<p style=font-size: 30px>Volumen: <strong>{vol_total:,.0f} USDT</strong></p>"
    output_html += "<table border='1' style='width: 100%; border-collapse: collapse;'>"
    output_html += f"<tr style='background-color: #f2f2f2; font-weight: bold;'><td>Precio</td><td>👤 Anuncios</td><td>💰 Volumen</td><td>Distribución</td></tr>"

    datos_ordenados = sorted(agrupado.items(), key=lambda x: x[0], reverse=reverse_sort)
    
    for precio, valores in datos_ordenados:
        # El factor de escala (30) es igual al ejemplo original de Bybit
        modulo = int((valores['suma'] / vol_total) * 30) if vol_total > 0 else 0
        barra = f"<span style='color: {color};'>{('⬛' * modulo)}</span>" # Usamos un carácter más grueso y coloreado

        output_html += f"<tr>"
        output_html += f"<td style='color: {color};'>{precio:,.2f}</td>"
        output_html += f"<td>{valores['conteo']}</td>"
        output_html += f"<td>{valores['suma']:,.0f}</td>"
        output_html += f"<td>{barra}</td>"
        output_html += f"</tr>"

    output_html += "</table><hr>"
    return output_html


async def main_async():
    """Ejecución asíncrona principal para el scraping."""
    # Lanzar ambas tareas asíncronamente
    ventas_task = scrape_bitget_p2p(URL_VENTAS, "ventas")
    compras_task = scrape_bitget_p2p(URL_COMPRAS, "compras")

    # Esperar a que ambas tareas finalicen
    results = await asyncio.gather(ventas_task, compras_task)
    
    # IMPORTANTE: Asegúrate de que el orden de los resultados es correcto
    # Tu código original tenía un intercambio:
    # data_ventas = results[1]
    # data_compras = results[0]
    # Lo he corregido para que coincida con el orden de las tareas lanzadas (ventas_task, compras_task).
    data_ventas = results[1]  # Venta de USDT (Side 1)
    data_compras = results[0] # Compra de USDT (Side 0)
    
    return data_ventas, data_compras


def obtener_datos_p2p_bitget():
    """Ejecuta la lógica de scraping asíncrono y genera el HTML."""
    output_html = "<h1>📈 Reporte P2P Bitget (USDT/BOB)</h1><p style=font-size: 10px; color: #666;>By: Chelotex</p>"
    
    try:
        # Ejecutar la función asíncrona dentro de la función síncrona de Flask
        data_ventas, data_compras = asyncio.run(main_async())
        
    except Exception as e:
        output_html += f"<p style='color: red;'>Error al ejecutar el scraping: {e}</p>"
        return output_html

    # El bucle simula la lógica original de la API de Bybit:
    # estado 1: Ventas/Ofertas; estado 0: Compras/Demandas
    estados = [1, 0] 

    for estado in estados:
        if estado == 1:
            # Procesar las 'Ofertas de Compra' (gente que vende USDT, Side 1)
            output_html += procesar_datos_html(data_ventas, estado)
        elif estado == 0:
            # Procesar las 'Ofertas de Venta' (gente que compra USDT, Side 0)
            output_html += procesar_datos_html(data_compras, estado)
            
    return output_html


@app.route('/')
def index():
    """Ruta principal que llama a la función de obtención de datos y renderiza el HTML."""
    html_content = obtener_datos_p2p_bitget()
    
    # Estructura HTML completa con auto-refresh y estilos, igual al ejemplo de Bybit
    full_html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Reporte P2P Bitget</title>
        <meta http-equiv="refresh" content="10"> 
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1, h2 {{ color: #333; }}
            table {{ margin-top: 15px; border: 1px solid #ccc; }}
            td, th {{ padding: 8px 12px; text-align: left; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            hr {{ border: 0; border-top: 1px solid #eee; margin: 20px 0; }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    return render_template_string(full_html)

if __name__ == '__main__':
    # Ejecuta el servidor Flask
    # El servidor se ejecutará en http://127.0.0.1:5000/
    port = int(os.environ.get('PORT', 5000)) 
    # Usar app.run con debug=False para evitar problemas de anidamiento de asyncio.run
    print(f"Iniciando servidor Flask en el puerto {port}...")
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)