import os
import requests
from dotenv import load_dotenv
from html import unescape


# ======================================================
# UTILIDADES
# ======================================================

def extract_job_id(job_url: str) -> str:
    """
    Extrae el job_id desde una URL tipo:
    https://www.linkedin.com/jobs/view/4327226302/
    """
    job_url = job_url.rstrip("/")
    return job_url.split("/")[-1]


def clean_text(text: str) -> str:
    """
    Limpia entidades HTML y espacios innecesarios.
    """
    if not text:
        return ""
    text = unescape(text)
    text = text.replace("\r", "\n")
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip()


# ======================================================
# FUNCIÓN PRINCIPAL (VOYAGER API)
# ======================================================

def get_offer_description(job_url: str, timeout: int = 20) -> str:
    """
    Obtiene el contenido de 'Acerca del empleo' usando la API interna
    Voyager de LinkedIn.

    REQUISITOS (.env SIN ESPACIOS):
      LINKEDIN_LI_AT=...
      LINKEDIN_JSESSIONID="ajax:..."

    Esta es la ÚNICA forma fiable actualmente.
    """

    load_dotenv()

    li_at = os.getenv("LINKEDIN_LI_AT")
    jsessionid = os.getenv("LINKEDIN_JSESSIONID")

    if not li_at or not jsessionid:
        raise RuntimeError(
            "❌ Cookies faltantes.\n"
            "Tu .env debe contener (SIN espacios):\n"
            "LINKEDIN_LI_AT=...\n"
            'LINKEDIN_JSESSIONID="ajax:..."'
        )

    # Limpieza defensiva
    li_at = li_at.strip().strip('"').strip("'")
    jsessionid_raw = jsessionid.strip()

    # JSESSIONID debe ir con comillas como cookie
    if not (jsessionid_raw.startswith('"') and jsessionid_raw.endswith('"')):
        jsessionid_cookie = f'"{jsessionid_raw.strip("\'\'").strip("\'")}"'
    else:
        jsessionid_cookie = jsessionid_raw

    csrf_token = jsessionid_cookie.strip('"')

    job_id = extract_job_id(job_url)

    voyager_url = f"https://www.linkedin.com/voyager/api/jobs/jobPostings/{job_id}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "x-restli-protocol-version": "2.0.0",
        "csrf-token": csrf_token,
        "Referer": job_url,
    }

    cookies = {
        "li_at": li_at,
        "JSESSIONID": jsessionid_cookie,
    }

    response = requests.get(
        voyager_url,
        headers=headers,
        cookies=cookies,
        timeout=timeout,
    )

    # ======================================================
    # ERRORES REALES DE LINKEDIN
    # ======================================================

    if response.status_code == 999:
        raise RuntimeError("❌ LinkedIn bloqueó la request (999). Reduce velocidad.")

    if response.status_code == 403:
        raise RuntimeError("❌ 403 Forbidden. Cookies inválidas o CSRF incorrecto.")

    if response.status_code != 200:
        raise RuntimeError(f"❌ HTTP {response.status_code} desde Voyager API.")

    data = response.json()

    description = (
        data
        .get("description", {})
        .get("text")
    )

    if not description or len(description) < 100:
        raise RuntimeError(
            "❌ No se encontró una descripción válida en el payload Voyager."
        )

    return clean_text(description)



