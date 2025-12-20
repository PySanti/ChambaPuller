# utils/get_computrabajo_description.py
from __future__ import annotations

import re
import json
from html import unescape
from urllib.parse import urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup


_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


# ======================================================
# UTILIDADES
# ======================================================

def clean_text(text: str) -> str:
    """Limpia entidades HTML y espacios innecesarios."""
    if not text:
        return ""
    text = unescape(text)
    text = text.replace("\r", "\n")
    # colapsa demasiadas líneas en blanco
    text = re.sub(r"\n{3,}", "\n\n", text)
    # limpia espacios
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    return text.strip()


def _unwrap_tracking(url: str) -> str:
    """
    Desenvuelve wrappers típicos:
      ...?url=<ENCODED>
      ...?redirect=<ENCODED>
      ...?u=<ENCODED>
      ...?target=<ENCODED>
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


def _is_computrabajo_job_url(url: str) -> bool:
    """
    Computrabajo (VE) suele usar:
      https://ve.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-...
    """
    try:
        p = urlparse(url)
        host = (p.netloc or "").lower()
        if "computrabajo" not in host:
            return False
        path = p.path or ""
        return ("/ofertas-de-trabajo/" in path) and ("oferta-de-trabajo" in path)
    except Exception:
        return False


def _safe_get(url: str, timeout: int) -> requests.Response:
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


def _resolve_to_job_url(url: str, timeout: int = 20) -> str:
    """
    - Si llega una URL de tracking (go.computrabajo.com) o wrapper con ?url=,
      intenta llegar a la URL real de la oferta.
    - Si termina en un listado, intenta sacar el primer link de oferta del HTML.
    """
    url = _unwrap_tracking(url)

    if _is_computrabajo_job_url(url):
        return url

    host = (urlparse(url).netloc or "").lower()

    # Tracking de Computrabajo
    if "go.computrabajo.com" in host:
        resp = _safe_get(url, timeout=timeout)
        final_url = str(resp.url)

        if _is_computrabajo_job_url(final_url):
            return final_url

        # Si cayó en listado, buscar primer link de oferta
        soup = BeautifulSoup(resp.text or "", "html.parser")
        a = soup.select_one('a[href*="oferta-de-trabajo"]')
        if a:
            href = (a.get("href") or "").strip()
            if href.startswith("/"):
                # usa el host final si existe; si no, el VE por defecto
                final_host = (urlparse(final_url).netloc or "ve.computrabajo.com")
                return f"https://{final_host}{href}"
            if href.startswith("http"):
                return href

        # si no encontró nada, se queda con el final_url
        return final_url

    # Último intento: seguir redirects generales
    try:
        resp = _safe_get(url, timeout=timeout)
        if _is_computrabajo_job_url(str(resp.url)):
            return str(resp.url)
        return str(resp.url)
    except Exception:
        return url


def _extract_description_from_job_html(html: str) -> str:
    """
    Extrae descripción de la página de oferta.
    Estrategias:
      1) JSON-LD JobPosting (description)
      2) Selectores frecuentes de contenedores
      3) Heurística por sección "Descripción"
    """
    soup = BeautifulSoup(html or "", "html.parser")

    # 1) JSON-LD (schema.org JobPosting)
    for s in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        try:
            raw = (s.string or s.get_text() or "").strip()
            if not raw:
                continue
            data = json.loads(raw)
            objs = data if isinstance(data, list) else [data]
            for obj in objs:
                if not isinstance(obj, dict):
                    continue
                if obj.get("@type") == "JobPosting" and isinstance(obj.get("description"), str):
                    # puede traer HTML dentro
                    desc_html = obj["description"]
                    desc_text = BeautifulSoup(desc_html, "html.parser").get_text("\n")
                    desc_text = clean_text(desc_text)
                    if len(desc_text) >= 120:
                        return desc_text
        except Exception:
            pass

    # 2) Selectores comunes (cambian por país/plantilla; ponemos varios)
    selectors = [
        "#jobDescriptionText",
        ".box_detail .box_detail_text",
        ".box_detail .text",
        ".box_detail",
        ".detalle_oferta",
        ".detalle",
        "section#detail",
        "div#detail",
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

    # 3) Heurística: recortar desde “Descripción”
    if not best or len(best) < 120:
        whole = clean_text(soup.get_text("\n"))
        m = re.search(r"\bDescripci[oó]n\b[:\s]*\n(.+)", whole, flags=re.IGNORECASE | re.DOTALL)
        if m:
            candidate = clean_text(m.group(1))
            # corta en headings típicos
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

def slice_description(desc, job_url):
    """
    Recorta la descripcion a solo el contenido importante

    Desde "Descripción de oferta" hasta "Postularme"

    Si se encuentran varias palabras claves delimitadoras ("Descripcion ..." y/o "Postu ...")
    solo se quedaran con la primera.
    """
    idx = desc.find("Descripción de la oferta")
    if idx != -1:
        desc = desc[idx:]
    else:
        raise RuntimeError(f"No se logro encontrar **Descripción de la oferta** dentro de la descripcion de {job_url[:20]}")


    idx = desc.find("Aptitudes asociadas a esta oferta")
    if idx != -1:
        desc = desc[:idx]
    else:
        idx = desc.find("Postularme")
        if idx != -1:
            desc = desc[:idx]
        else:
            raise RuntimeError("No se logro encontrar **Postularme** dentro de la descripcion de {job_url[:20]}")

    return desc




# ======================================================
# FUNCIÓN PRINCIPAL
# ======================================================

def get_computrabajo_description(job_url: str, timeout: int = 20) -> str:
    """
    Devuelve la descripción de una oferta de Computrabajo a partir del link.

    Acepta:
      - URL directa de oferta (recomendada)
      - URL de tracking go.computrabajo.com
      - URL wrapper con ?url=...

    Lanza RuntimeError si no obtiene una descripción válida.
    """
    resolved = _resolve_to_job_url(job_url, timeout=timeout)

    if not _is_computrabajo_job_url(resolved):
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

    desc = _extract_description_from_job_html(resp.text or "")

    if not desc or len(desc) < 120:
        raise RuntimeError("❌ No se pudo extraer una descripción válida desde Computrabajo.")

    return slice_description(desc, job_url)
