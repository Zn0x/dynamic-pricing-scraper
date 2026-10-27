import email
import imaplib
import os
import re
import time
from datetime import datetime
from pathlib import Path

import gspread
import pandas as pd
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

# --- Configuración General y Entorno ---
PORTAL_URL = os.getenv("PORTAL_URL", "https://portal-reservas-demo.com")
PORTAL_USER = os.getenv("PORTAL_USER")
PORTAL_PASS = os.getenv("PORTAL_PASS")
USER_PROFILE_LABEL = os.getenv("USER_PROFILE_LABEL", "Usuario")

# Configuración 2FA IMAP
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
MAIL_BOT = os.getenv("MAIL_BOT")
PASS_APP = os.getenv("PASS_APP")
AUTH_CODE_REGEX = os.getenv("AUTH_CODE_REGEX", r'(?:codigo|code|\d{6})[^\d]*(\d{6})')

# Google Sheets & Reporting
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS_FILE", "credentials.json")
HOJA_PANEL_CONTROL = os.getenv("HOJA_PANEL_CONTROL", "Execution_Logs")
HOJA_REPRICING = os.getenv("HOJA_REPRICING", "Dynamic_Repricing_Data")
NOMBRE_BOT = os.getenv("NOMBRE_BOT", "Dynamic_Pricing_Pipeline")


def registrar_timestamp_en_panel(estado="EXITOSO"):
    """Registra trazabilidad de la corrida en la pestaña de auditoría remota."""
    if not os.path.exists(GOOGLE_CREDS_FILE):
        print("[WARN] Archivo de credenciales de Google no encontrado. Omitiendo log.")
        return

    try:
        gc = gspread.service_account(filename=GOOGLE_CREDS_FILE)
        sh_control = gc.open(HOJA_PANEL_CONTROL)
        worksheet_logs = sh_control.get_worksheet(0)

        ahora = datetime.now()
        dia = ahora.strftime("%d/%m/%Y")
        hora = ahora.strftime("%H:%M:%S")

        datos_fila = [NOMBRE_BOT, dia, hora, estado]
        valores_columna_a = worksheet_logs.col_values(1)
        siguiente_fila = len(valores_columna_a) + 1
        rango_destino = f"A{siguiente_fila}:D{siguiente_fila}"

        worksheet_logs.update(values=[datos_fila], range_name=rango_destino)
        print(f"[INFO] Auditoría registrada con estado: {estado}")
    except Exception as e:
        print(f"[WARN] Error al registrar log de auditoría: {e}")


def obtener_codigo_2fa():
    """Conexión IMAP SSL para resolución desatendida del token OTP."""
    print("[INFO] Consultando bandeja de entrada para token 2FA...")
    if not MAIL_BOT or not PASS_APP:
        print("[WARN] Credenciales IMAP no configuradas.")
        return None

    try:
        servidor = imaplib.IMAP4_SSL(IMAP_SERVER)
        servidor.login(MAIL_BOT, PASS_APP)

        for _ in range(8):
            servidor.select("INBOX")
            status, datos = servidor.search(None, "(UNSEEN)")
            ids = datos[0].split()

            if ids:
                ultimo_id = ids[-1]
                _, data = servidor.fetch(ultimo_id, "(RFC822)")
                for respuesta in data:
                    if isinstance(respuesta, tuple):
                        mensaje = email.message_from_bytes(respuesta[1])
                        cuerpo = ""
                        if mensaje.is_multipart():
                            for part in mensaje.walk():
                                if part.get_content_type() in ["text/plain", "text/html"]:
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        cuerpo += payload.decode("utf-8", errors="ignore") + " "
                        else:
                            payload = mensaje.get_payload(decode=True)
                            if payload:
                                cuerpo = payload.decode("utf-8", errors="ignore")

                        cuerpo_limpio = re.sub(r"<[^>]+>", " ", cuerpo)
                        match = re.search(AUTH_CODE_REGEX, cuerpo_limpio, re.IGNORECASE)

                        if match:
                            codigo_real = match.group(1)
                            servidor.logout()
                            return codigo_real

            time.sleep(10)
        servidor.logout()
        return None
    except Exception as e:
        print(f"[ERROR] Error al procesar correo IMAP: {e}")
        return None


def iniciar_automatizacion():
    """Ejecuta el pipeline de extracción de tarifas, toggling de columnas y procesamiento analítico."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            permissions=[],
            record_video_dir="artifacts/videos/",
            record_video_size={"width": 1280, "height": 720},
        )
        page = context.new_page()

        try:
            print(f"[INFO] Navegando al portal: {PORTAL_URL}")
            page.goto(PORTAL_URL)

            try:
                page.get_by_role("button", name=re.compile(r"Aceptar|Accept", re.I)).click(timeout=4000)
                time.sleep(1)
            except Exception:
                pass

            print("[INFO] Autenticando usuario...")
            page.get_by_text("Entrar", exact=False).first.click()
            page.wait_for_selector(".login-email-input")
            page.locator(".login-email-input").fill(PORTAL_USER)
            page.locator(".login-password-input").fill(PORTAL_PASS)
            time.sleep(1)
            page.locator(".signin-button").click(force=True)

            print("[INFO] Solicitando token de autenticación multifactor...")
            time.sleep(2)
            page.get_by_text("Enviar código", exact=False).click(force=True)
            time.sleep(10)

            codigo = obtener_codigo_2fa()
            if not codigo:
                raise RuntimeError("Código 2FA no recibido dentro del tiempo límite.")

            cajas_codigo = page.locator(".input-code-number-login")
            for i in range(min(6, len(codigo))):
                cajas_codigo.nth(i).click()
                page.keyboard.type(codigo[i], delay=120)

            time.sleep(2)
            page.keyboard.press("Enter")

            try:
                page.locator(".signin-button").click(force=True, delay=100)
            except Exception:
                pass

            print("[INFO] Accediendo a módulos de gestión...")
            page.locator("li:has-text('Admin'), a:has-text('Admin')").last.wait_for(state="visible", timeout=25000)
            page.locator("li:has-text('Admin'), a:has-text('Admin')").last.click(force=True)
            time.sleep(3)

            try:
                page.locator(".modal-close, button.close, [aria-label='Close']").first.click(timeout=3000)
            except Exception:
                pass

            # Búsqueda dinámica en panel lateral
            buscador_input = page.locator("#admin-sidebar-form input").first
            buscador_input.click()
            buscador_input.fill("")
            page.keyboard.type("Recotización", delay=100)
            time.sleep(3)

            page.locator("#admin-sidebar-form a, #admin-sidebar-form li").get_by_text(
                "Recotización", exact=False
            ).first.click(force=True)
            time.sleep(6)

            # Navegación a pestaña de historial procesado
            print("[INFO] Navegando a pestaña de tarifas procesadas...")
            page.get_by_text("Repricings hechos", exact=False).first.click(force=True)
            time.sleep(5)

            # Limpieza y aplicación de filtros
            try:
                page.locator("button:has-text('Filtros'), a:has-text('Filtros')").first.click(force=True)
                time.sleep(2)
                botones_borrar = page.get_by_text("Borrar", exact=True)
                for b_idx in range(min(2, botones_borrar.count())):
                    botones_borrar.nth(b_idx).click(force=True)
                    time.sleep(1)

                page.get_by_text("Aplicar", exact=True).last.click(force=True)
                time.sleep(8)
            except Exception as e_filtro:
                print(f"[WARN] Aviso en aplicación de filtros: {e_filtro}")

            # Gestión dinámica de visualización de columnas (DOM toggling)
            print("[INFO] Ajustando columnas requeridas en el DOM...")
            try:
                page.locator("[id*='commandtogglerdone'], button:has-text('Columns')").first.click(timeout=5000)
                time.sleep(2)

                id_menu = "repricing-search-form\\:tabView\\:repricingstable\\:toggler-done"
                page.wait_for_selector(f"div[id='{id_menu}'], .ui-columntoggler-items", state="visible", timeout=8000)

                reglas_desmarcar = ["operador", "microsite", "habitaciones", "regimen", "divisa", "%"]
                filas = page.locator(f"div[id='{id_menu}'] li, .ui-columntoggler-items li")

                for idx in range(filas.count()):
                    fila = filas.nth(idx)
                    label = fila.locator("label")
                    if label.count() == 0:
                        continue

                    nombre_col = label.text_content().strip().lower()
                    chk_box = fila.locator(".ui-chkbox-box")
                    marcado = "ui-state-active" in (chk_box.get_attribute("class") or "")

                    if "alojamiento" in nombre_col and not marcado:
                        chk_box.click(force=True)
                        time.sleep(0.5)
                    elif any(r in nombre_col for r in reglas_desmarcar) and marcado:
                        chk_box.click(force=True)
                        time.sleep(0.5)

                page.keyboard.press("Escape")
                time.sleep(3)
            except Exception as e_cols:
                print(f"[WARN] Toggling de columnas omitido o completado por default: {e_cols}")

            # Exportación de dataset
            carpeta_destino = Path("downloads")
            carpeta_destino.mkdir(exist_ok=True)

            print("[INFO] Exportando dataset a Excel...")
            ruta_final = None
            try:
                page.evaluate("""() => {
                    const btn = document.querySelector('button[id*="repricingstable"][id$="exportButton"]');
                    if (btn) btn.click();
                }""")
                time.sleep(3)

                with page.expect_download(timeout=60000) as download_info:
                    page.evaluate("""() => {
                        const links = Array.from(document.querySelectorAll('a, button, span'));
                        const target = links.find(el => el.textContent.trim().toLowerCase() === 'excel');
                        if (target) target.click();
                    }""")

                download = download_info.value
                nombre_archivo = f"repricing_dataset_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                ruta_final = carpeta_destino / nombre_archivo
                download.save_as(str(ruta_final))
                print(f"[INFO] Archivo descargado en: {ruta_final}")
            except Exception as e_desc:
                print(f"[ERROR] Error al descargar reporte: {e_desc}")

            # Transformación de datos con Pandas y sincronización Cloud
            if ruta_final and os.path.exists(ruta_final):
                print("[INFO] Procesando y normalizando dataset con Pandas...")
                df = pd.read_excel(ruta_final, dtype=str).fillna("")

                if not df.empty:
                    # Limpieza temporal y ordenamiento
                    col_fecha = df.columns[0]
                    df[col_fecha] = pd.to_datetime(df[col_fecha], dayfirst=True, errors="coerce")
                    df = df.sort_values(by=col_fecha, ascending=False)
                    df[col_fecha] = df[col_fecha].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")

                    # Selección de campos analíticos
                    df_final = df.iloc[:, : min(17, len(df.columns))]

                    # Conversión limpia de tipos numéricos
                    def limpiar_valor(v):
                        t = str(v).strip()
                        if re.match(r"^-?\d+(?:\.\d+)?$", t):
                            try:
                                return float(t)
                            except ValueError:
                                pass
                        return v

                    df_final = df_final.map(limpiar_valor)

                    if os.path.exists(GOOGLE_CREDS_FILE):
                        print("[INFO] Sincronizando con Google Sheets...")
                        gc = gspread.service_account(filename=GOOGLE_CREDS_FILE)
                        sh = gc.open(HOJA_REPRICING)
                        worksheet = sh.get_worksheet(0)

                        valores = df_final.values.tolist()
                        rango = f"A2:Q{1 + len(valores)}"
                        worksheet.update(values=valores, range_name=rango, value_input_option="USER_ENTERED")
                        print(f"[INFO] Sincronización exitosa: {len(valores)} registros actualizados.")
                    else:
                        print("[INFO] Pipeline finalizado localmente. Datos listos en carpeta 'downloads/'.")

            registrar_timestamp_en_panel(estado="EXITOSO")
            print("[INFO] Proceso concluido satisfactoriamente.")

        except Exception as error_global:
            print(f"[FATAL] Error durante la ejecución del pipeline: {error_global}")
            registrar_timestamp_en_panel(estado="FALLIDO")
            page.screenshot(path="artifacts/error_repricing.png")
            raise error_global

        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    iniciar_automatizacion()