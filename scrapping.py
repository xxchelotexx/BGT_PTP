import asyncio
from playwright.async_api import async_playwright
import json
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict

# Forzar codificación UTF-8 en consola para evitar errores de impresión
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# --- URLs Definidas ---
URL_VENTAS = "https://www.bitget.com/p2p-trade/sell?paymethodIds=-1&fiatName=BOB"
URL_COMPRAS = "https://www.bitget.com/p2p-trade?paymethodIds=-1&fiatName=BOB" # URL modificada para compras

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
    all_results = []
    MAX_PAGES = 2

    print(f"\n--- INICIANDO SCRAPE: {operation_type.upper()} ---")

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
            print(f"Navegando a {url}...")
            await page.goto(url, timeout=90000) 

            # --- Lógica de Cierre de Popups ---
            print("Intentando cerrar modales...")
            await page.wait_for_timeout(4000) 
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
            await page.mouse.click(50, 50)
            await page.wait_for_timeout(500)
            
            try: await page.locator('.bit-dialog__close').click(timeout=3000)
            except Exception: pass
            
            try: await page.get_by_test_id('MicroCookieAcceptButton').click(timeout=3000)
            except Exception: pass
            
            print("Esperando a que la lista de ofertas sea visible...")
            await page.wait_for_selector(".hall-list-item", state="visible", timeout=60000)
            
            # --- Bucle de Paginación y Scraping ---
            for page_num in range(1, MAX_PAGES + 1):
                page_str = str(page_num)

                # ⚠️ 1. NAVEGACIÓN (Solo hacer clic si no estamos en la página 1)
                if page_num > 1:
                    print(f"   -> Haciendo clic en el número de página {page_str}...")
                    
                    target_page_locator = page.get_by_text(page_str, exact=True)

                    if await target_page_locator.count() == 0:
                        print(f"   -> No se encontró el número de página {page_str}. Finalizando.")
                        break

                    await target_page_locator.click(force=True)
                    
                    # Esperamos a que la página se active
                    try:
                        await page.wait_for_selector(
                            f'.bit-pager li.number.active:has-text("{page_str}")',
                            timeout=10000 
                        )
                        await page.wait_for_timeout(1500) 
                    except Exception:
                        print(f"   -> Error: La página {page_str} no se activó a tiempo. Saltando la extracción de esta página.")
                        continue 

                # 📝 2. EXTRACCIÓN DE DATOS
                print(f"--- Escrapeando Página {page_num} ({operation_type}) ---")
                
                await page.wait_for_timeout(1000)
                cards = await page.query_selector_all(".hall-list-item")
                print(f"   -> Encontradas {len(cards)} ofertas.")

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
            print(f"Ocurrió un error en el scrapeo de {operation_type}: {e}")
            return all_results
        
        finally:
            await browser.close()
            print(f"--- SCRAPE COMPLETADO: {operation_type.upper()} ---")

# --- Ejecución Principal ---
async def main():
    # Lanzar ambas tareas asíncronamente
    ventas_task = scrape_bitget_p2p(URL_VENTAS, "ventas")
    compras_task = scrape_bitget_p2p(URL_COMPRAS, "compras")

    # Esperar a que ambas tareas finalicen
    results = await asyncio.gather(ventas_task, compras_task)
    
    # Asignar resultados a las variables solicitadas (data_ventas y data_compras)
    # ----------------------------------------------------------------------
    # 🔑 ESTO ES LO QUE SOLICITASTE
    data_ventas = results[1]
    data_compras = results[0]
    # ----------------------------------------------------------------------

    # --- Resumen y JSON para verificación ---
    
    print("\n" + "="*50)
    print("RESUMEN DE RESULTADOS")
    print("="*50)

    # Ventas
    total_v = len(data_ventas)
    paginas_v = len(set([d['pagina'] for d in data_ventas if 'pagina' in d]))
    print(f"VENTAS: Total registros: {total_v} | Páginas escaneadas: {paginas_v}")
    
    # Compras
    total_c = len(data_compras)
    paginas_c = len(set([d['pagina'] for d in data_compras if 'pagina' in d]))
    print(f"COMPRAS: Total registros: {total_c} | Páginas escaneadas: {paginas_c}")

    print("\n" + "="*50)
    print("IMPRESIÓN DE data_ventas")
    print("="*50)
    print(json.dumps(data_ventas, indent=4, ensure_ascii=False))

    print("\n" + "="*50)
    print("IMPRESIÓN DE data_compras")
    print("="*50)
    print(json.dumps(data_compras, indent=4, ensure_ascii=False))

    # NOTA: Después de esta función, las variables data_ventas y data_compras
    # ya tienen los datos asignados dentro del contexto asíncrono.
    # Si añades código adicional DENTRO de esta función 'main', puedes
    # usar esas variables para procesamiento posterior (ej: pandas).

    def procesar_datos(data, estado):
        """
        Procesa la lista de transacciones y genera el resultado con el formato
        de agrupación por precio y la barra de volumen.

        :param data: Lista de diccionarios con las transacciones.
        :param estado: 1 para 'ventas' (verde), 0 para 'compras' (rojo).
        """
        # 1. Preparar items: Mapeamos 'precio_bob' a 'price' y 'monto_usdt' a 'lastQuantity'
        items = []
        for item in data:
            items.append({
                "price": str(item["precio_bob"]),
                "lastQuantity": str(item["monto_usdt"])
            })

        # 2. Agrupación y Cálculo de Volumen Total
        agrupado = {}
        vol_total = 0.0
        
        for item in items:
            precio = float(item["price"])
            cantidad = float(item["lastQuantity"])
            
            vol_total += cantidad
            
            if precio not in agrupado:
                agrupado[precio] = {"suma": 0.0, "conteo": 0}

            agrupado[precio]["suma"] += cantidad
            agrupado[precio]["conteo"] += 1

        # 3. Mostrar resultados
        if estado == 0:  # Compras 🔴
            print(f"Volumen de 🔴 **compras**: {vol_total:.4f}")
            
            # Ordenar por precio de forma descendente (igual que la API para compras)
            for precio, valores in sorted(agrupado.items(), reverse=True):
                # La longitud de la barra es proporcional al volumen (20 es el factor de escala)
                modulo = int((valores['suma'] / vol_total) * 20)
                
                print(f"🔴: {precio:.2f}  | 👤: {valores['conteo']} | 💰: {valores['suma']:.4f} ")
                print("⬜" * modulo)

        if estado == 1:  # Ventas 🟢
            print(f"Volumen de 🟢 **ventas**: {vol_total:.4f}")
            
            # Ordenar por precio de forma ascendente (igual que la API para ventas)
            for precio, valores in sorted(agrupado.items(), reverse=False):
                # La longitud de la barra es proporcional al volumen
                modulo = int((valores['suma'] / vol_total) * 20)
                
                print(f"🟢: {precio:.2f}  | 👤: {valores['conteo']} | 💰: {valores['suma']:.4f} ")
                print("⬜" * modulo)
        
        print("-" * 30) # Separador visual

    # --- Ejecución principal ---
    # El bucle simula la lógica original de la API
    # estado 1: Ventas; estado 0: Compras
    estados = [1, 0] 

    for estado in estados:
        if estado == 1:
            # Procesar Ventas
            procesar_datos(data_ventas, estado)
        elif estado == 0:
            # Procesar Compras
            procesar_datos(data_compras, estado)


if __name__ == "__main__":
    asyncio.run(main())