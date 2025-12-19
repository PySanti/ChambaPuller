
# utils/get_computrabajo_description.py
from __future__ import annotations

import re
import requests
from html import unescape
from urllib.parse import urlparse, parse_qs, unquote

from bs4 import BeautifulSoup


# ======================================================
# UTILIDADES
# ======================================================

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def clean_text(text: str) -> str:
    """Limpia entidades HTML y espacios innecesarios."""
    if not text:
        return ""
    text = unescape(text)
    text = text.replace("\r", "\n")
    # colapsar líneas vacías excesivas
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    # colapsar espacios
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    return text.strip()


def _unwrap_tracking(url: str) -> str:
    """
    Desenvuelve wrappers de tracking típicos:
    - ...?url=<encoded>
    - ...?redirect=<encoded>
    - ...?u=<encoded>
    - ...?target=<encoded>
    """
    try:
        p = urlparse(url)
        qs = parse_qs(p.query)
        for key in ("url", "redirect", "u", "target", "dest", "destination"):
            if key in qs and qs[key]:
                candidate = unquote(qs[key][0])
                if candidate.startswith("http://") or candidate.startswith("https://"):
                    return candidate
    except Exception:
        pass
    return url


def _safe_get(url: str, timeout: int = 20) -> requests.Response:
    return requests.get(
        url,
        timeout=timeout,
        allow_redirects=True,
        headers={
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )


def _extract_description_from_html(html: str) -> str:
    """
    Intenta extraer la descripción de una oferta Computrabajo desde HTML.
    Es robusto a cambios menores de layout.
    """
    soup = BeautifulSoup(html or "", "html.parser")

    # 1) JSON-LD (si existe)
    # Muchas páginas publican schema.org JobPosting con "description".
    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        try:
            content = (script.string or script.get_text() or "").strip()
            if not content:
                continue
            # puede ser objeto o lista; evitamos json import si no hace falta:
            import json  # local import
            data = json.loads(content)

            candidates = data if isinstance(data, list) else [data]
            for obj in candidates:
                if isinstance(obj, dict) and obj.get("@type") in ("JobPosting", ["JobPosting"]):
                    desc = obj.get("description")
                    if isinstance(desc, str) and len(desc.strip()) > 80:
                        # description suele venir con HTML
                        desc_text = BeautifulSoup(desc, "html.parser").get_text("\n")
                        return clean_text(desc_text)
        except Exception:
            pass

    # 2) Selectores comunes (pueden variar por país/plantilla)
    selectors = [
        # típicos contenedores de descripción
        "#jobDescriptionText",
        ".box_detail .box_detail_text",
        ".box_detail .text",
        ".box_detail",
        ".detalle_oferta",
        ".detalle",
        "section#detail",
        "div#detail",
        # fallback: bloques con "Descripción" cerca
        "article",
        "main",
    ]

    best = ""
    for sel in selectors:
        el = soup.select_one(sel)
        if not el:
            continue
        txt = clean_text(el.get_text("\n"))
        if len(txt) > len(best):
            best = txt

    # 3) Heurística: buscar el bloque alrededor de encabezados "Descripción"
    if not best or len(best) < 120:
        text = soup.get_text("\n")
        text = clean_text(text)

        # intenta recortar desde "Descripción" hacia abajo
        m = re.search(r"\bDescripci[oó]n\b[:\s]*\n(.+)", text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            candidate = clean_text(m.group(1))
            # cortar si llega a secciones típicas
            candidate = re.split(
                r"\n(?:Requisitos|Beneficios|Salario|Acerca de la empresa|"
                r"Sobre la empresa|Detalles|Postular|Inscribirse)\b",
                candidate,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            candidate = clean_text(candidate)
            if len(candidate) > len(best):
                best = candidate

    return best


def _is_job_url(url: str) -> bool:
    try:
        p = urlparse(url)
        host = (p.netloc or "").lower()
        if "computrabajo" not in host:
            return False
        path = p.path or ""
        return ("/ofertas-de-trabajo/" in path) and ("oferta-de-trabajo" in path)
    except Exception:
        return False


def _resolve_to_job_url(url: str, timeout: int = 20) -> str:
    """
    Si te llega un go.computrabajo.com/go/... o un wrapper con ?url=...,
    intenta resolverlo hasta un link real de oferta.
    """
    url = _unwrap_tracking(url)

    # Si ya es oferta, listo
    if _is_job_url(url):
        return url

    # Si es go.computrabajo.com, seguir redirects y luego buscar el primer link de oferta
    if "go.computrabajo.com" in (urlparse(url).netloc or "").lower():
        resp = _safe_get(url, timeout=timeout)
        final_url = str(resp.url)

        if _is_job_url(final_url):
            return final_url

        # si cayó en un listado, intentar sacar el primer link de oferta del HTML
        soup = BeautifulSoup(resp.text or "", "html.parser")
        a = soup.select_one('a[href*="oferta-de-trabajo"]')
        if a:
            href = (a.get("href") or "").strip()
            if href.startswith("/"):
                final_host = urlparse(final_url).netloc or "ve.computrabajo.com"
                return f"https://{final_host}{href}"
            if href.startswith("http"):
                return href

    # último intento: seguir redirects generales
    try:
        resp = _safe_get(url, timeout=timeout)
        if _is_job_url(str(resp.url)):
            return str(resp.url)
    except Exception:
        pass

    return url  # puede quedar como listado; el caller decide si es válido


# ======================================================
# FUNCIÓN PRINCIPAL
# ======================================================

def get_computrabajo_description(job_url: str, timeout: int = 20) -> str:
    """
    Obtiene la descripción de una oferta de Computrabajo a partir de su link.

    Acepta:
      - URL directa de oferta:
        https://ve.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-...-HASH
      - URL de tracking (go.computrabajo.com) o wrapper con ?url=...

    Lanza RuntimeError si no logra extraer una descripción razonable.
    """
    resolved = _resolve_to_job_url(job_url, timeout=timeout)

    if not _is_job_url(resolved):
        raise RuntimeError(
            "❌ La URL no parece ser una oferta directa de Computrabajo "
            f"(resuelta a: {resolved})."
        )

    resp = _safe_get(resolved, timeout=timeout)

    if resp.status_code == 403:
        raise RuntimeError("❌ 403 Forbidden al acceder a Computrabajo (posible bloqueo).")
    if resp.status_code == 404:
        raise RuntimeError("❌ 404 Not Found (oferta eliminada o link inválido).")
    if resp.status_code != 200:
        raise RuntimeError(f"❌ HTTP {resp.status_code} al acceder a Computrabajo.")

    desc = _extract_description_from_html(resp.text or "")

    # Validación mínima
    if not desc or len(desc) < 120:
        raise RuntimeError(
            "❌ No se pudo extraer una descripción válida desde la página de Computrabajo."
        )

    return desc
