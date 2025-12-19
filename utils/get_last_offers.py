
from __future__ import annotations

import os
import re
import ssl
import socket
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, parse_qs, unquote, urlunparse
from dotenv import load_dotenv

from bs4 import BeautifulSoup

from utils.Offer import Offer
from utils.OfferTypeEnum import OfferTypeEnum


# evita bloqueos infinitos
socket.setdefaulttimeout(35)

_IMAP_ABORTS = (imaplib.IMAP4.abort, imaplib.IMAP4.error, socket.timeout, OSError)


# ----------------------------
# Helpers: decode / body
# ----------------------------

def _decode_mime_header(value: str) -> str:
    """Decode RFC2047 headers safely. Robust to unknown encodings (unknown-8bit)."""
    if not value:
        return ""
    parts = decode_header(value)
    out: list[str] = []
    for part, enc in parts:
        if isinstance(part, bytes):
            enc_norm = (enc or "utf-8").strip().lower()
            if enc_norm in ("unknown-8bit", "unknown", "x-unknown", ""):
                enc_norm = "utf-8"
            try:
                out.append(part.decode(enc_norm, errors="replace"))
            except LookupError:
                out.append(part.decode("utf-8", errors="replace"))
            except UnicodeDecodeError:
                out.append(part.decode("latin-1", errors="replace"))
        else:
            out.append(part)
    return "".join(out)


def _extract_body(msg) -> tuple[str, str]:
    """Return (text, html) best-effort from an email message."""
    text_parts: list[str] = []
    html_parts: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            ctype = (part.get_content_type() or "").lower()
            disp = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue

            try:
                payload = part.get_payload(decode=True)
            except Exception:
                payload = None

            if not payload:
                continue

            charset = part.get_content_charset() or "utf-8"
            try:
                content = payload.decode(charset, errors="replace")
            except LookupError:
                content = payload.decode("utf-8", errors="replace")

            if ctype == "text/plain":
                text_parts.append(content)
            elif ctype == "text/html":
                html_parts.append(content)
    else:
        ctype = (msg.get_content_type() or "").lower()
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        try:
            content = payload.decode(charset, errors="replace")
        except LookupError:
            content = payload.decode("utf-8", errors="replace")

        if ctype == "text/html":
            html_parts.append(content)
        else:
            text_parts.append(content)

    text = "\n\n".join(text_parts).strip()
    html = max(html_parts, key=len).strip() if html_parts else ""
    return text, html


# ----------------------------
# Helpers: url extraction
# ----------------------------

_URL_RE = re.compile(r"""https?://[^\s"'<>]+""", re.IGNORECASE)


def _extract_urls_from_text(text: str) -> list[str]:
    urls = _URL_RE.findall(text or "")
    seen, out = set(), []
    for u in urls:
        u = u.strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _extract_urls_from_html(html: str) -> list[str]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if href.startswith("http://") or href.startswith("https://"):
            urls.append(href)

    seen, out = set(), []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _unwrap_tracking(url: str) -> str:
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        for key in ("url", "redirect", "u", "target", "dest", "destination"):
            if key in qs and qs[key]:
                candidate = unquote(qs[key][0])
                if candidate.startswith("http://") or candidate.startswith("https://"):
                    return candidate
    except Exception:
        pass
    return url


# ----------------------------
# Helpers: canonical job links
# ----------------------------

def _canonical_linkedin_job_url(url: str) -> str | None:
    try:
        u = _unwrap_tracking(url)
        p = urlparse(u)
        host = (p.netloc or "").lower()

        if host.endswith("lnkd.in"):
            return None
        if "linkedin.com" not in host:
            return None

        path = p.path or ""
        q = parse_qs(p.query)

        m = re.search(r"/jobs/view/(\d+)", path)
        if m:
            job_id = m.group(1)
            return f"https://www.linkedin.com/jobs/view/{job_id}/"

        for key in ("currentjobid", "jobid", "currentJobId", "jobId"):
            if key in q and q[key]:
                job_id = q[key][0]
                if job_id.isdigit():
                    return f"https://www.linkedin.com/jobs/view/{job_id}/"

        return None
    except Exception:
        return None


def _canonical_computrabajo_job_url(url: str) -> str | None:
    try:
        u = _unwrap_tracking(url)
        p = urlparse(u)
        host = (p.netloc or "").lower()

        if "computrabajo" not in host:
            return None

        path = p.path or ""
        if "/ofertas-de-trabajo/" not in path:
            return None
        if "oferta-de-trabajo" not in path:
            return None

        return urlunparse((p.scheme or "https", p.netloc, p.path, "", "", ""))
    except Exception:
        return None


def _canonical_job_url(url: str) -> tuple[str | None, OfferTypeEnum | None]:
    canon = _canonical_linkedin_job_url(url)
    if canon:
        return canon, OfferTypeEnum.LINKEDIN

    canon = _canonical_computrabajo_job_url(url)
    if canon:
        return canon, OfferTypeEnum.COMPUTRABAJO

    return None, None


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _dedupe_keep_order_bytes(items: list[bytes]) -> list[bytes]:
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


# ----------------------------
# Helpers: IMAP safe ops
# ----------------------------

def _safe_search(mail: imaplib.IMAP4_SSL, criteria: list[str]) -> list[bytes]:
    status, data = mail.search(None, *criteria)
    if status != "OK":
        raise RuntimeError(f"IMAP search failed: {status} {data}")
    if not data or not data[0]:
        return []
    return data[0].split()


def _safe_fetch(mail: imaplib.IMAP4_SSL, msg_id: bytes, what: str, retries: int = 1):
    for attempt in range(retries + 1):
        try:
            return mail.fetch(msg_id, what)
        except _IMAP_ABORTS as e:
            if attempt >= retries:
                print(f"[WARN] fetch failed msg_id={msg_id!r} what={what} err={e}")
                return "NO", []
            print(f"[WARN] fetch error, retrying... msg_id={msg_id!r} err={e}")
    return "NO", []


def _fetch_email_bytes(mail: imaplib.IMAP4_SSL, msg_id: bytes) -> bytes:
    """
    Fetch liviano: primeros 200KB del mensaje.
    Esto suele incluir Subject/Date y los links.
    """
    status, data = _safe_fetch(mail, msg_id, "(BODY.PEEK[]<0.200000>)", retries=1)
    if status != "OK" or not data or not data[0]:
        return b""
    return data[0][1] if isinstance(data[0], tuple) else b""


# ----------------------------
# Main
# ----------------------------

def get_last_offers(
    mailbox: str = "INBOX",
    limit: int = 50,
    unseen_only: bool = False,
    sources: tuple[str, ...] = (
        "jobalerts-noreply@linkedin.com",
        "empleos_ve@computrabajo.com",
    ),
) -> list[Offer]:
    """
    Retorna ofertas de los últimos `limit` correos POR CADA remitente en `sources`.
    Luego mezcla, dedupe por ID de mensaje y parsea sin ordenar por Date (para evitar cuelgues).
    """

    load_dotenv()

    host = os.getenv("IMAP_SERVER") or os.getenv("imap_server")
    port = int(os.getenv("IMAP_PORT", os.getenv("imap_port", "993")))
    user = os.getenv("GMAIL_USER") or os.getenv("gmail_user")
    password = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("gmail_app_password")

    if not host or not user or not password:
        raise RuntimeError(
            "Faltan credenciales IMAP en .env. Usa: IMAP_SERVER, GMAIL_USER, GMAIL_APP_PASSWORD (y opcional IMAP_PORT)."
        )

    context = ssl.create_default_context()
    mail = imaplib.IMAP4_SSL(host, port, ssl_context=context)

    try:
        mail.login(user, password)
        mail.select(mailbox)

        # 1) IDs por remitente (tomamos últimos N por cada uno)
        all_ids: list[bytes] = []
        for sender in sources:
            criteria = ["FROM", f'"{sender}"']
            if unseen_only:
                criteria = ["UNSEEN"] + criteria

            ids = _safe_search(mail, criteria)
            if not ids:
                continue

            # ids vienen en orden ascendente (antiguos->nuevos), invertimos y cortamos
            ids = list(reversed(ids))[: max(0, limit)]
            all_ids.extend(ids)

        # 2) Dedupe de IDs (mezcla)
        all_ids = _dedupe_keep_order_bytes(all_ids)

        offers: list[Offer] = []

        # 3) Procesar cada correo
        for msg_id in all_ids:
            raw = _fetch_email_bytes(mail, msg_id)
            if not raw:
                continue

            try:
                msg = email.message_from_bytes(raw)
            except Exception as e:
                print(f"[WARN] cannot parse msg_id={msg_id!r}: {e}")
                continue

            subject = _decode_mime_header(msg.get("Subject", ""))
            date_raw = msg.get("Date", "")
            try:
                dt = parsedate_to_datetime(date_raw) if date_raw else None
                date_iso = dt.isoformat() if dt else ""
            except Exception:
                date_iso = ""

            text, html = _extract_body(msg)

            urls: list[str] = []
            urls.extend(_extract_urls_from_html(html))
            urls.extend(_extract_urls_from_text(text))

            found: list[tuple[str, OfferTypeEnum]] = []
            for u in urls:
                canon, typ = _canonical_job_url(u)
                if canon and typ:
                    found.append((canon, typ))

            # dedupe links manteniendo el primero
            seen_links = set()
            deduped: list[tuple[str, OfferTypeEnum]] = []
            for link, typ in found:
                if link not in seen_links:
                    seen_links.add(link)
                    deduped.append((link, typ))

            for link, typ in deduped:
                offers.append(
                    Offer(
                        link=link,
                        reception_date=date_iso,
                        father_mail_subject=subject,
                        type_=typ,
                    )
                )

            print(f"OK: {subject} | offers={len(deduped)}")

        return offers

    finally:
        try:
            mail.close()
        except Exception:
            pass
        try:
            mail.logout()
        except Exception:
            pass
