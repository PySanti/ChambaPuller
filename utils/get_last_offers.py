
import os
import re
import ssl
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, parse_qs, unquote
from dotenv import load_dotenv

# Requiere: pip install beautifulsoup4
from bs4 import BeautifulSoup

from utils.Offer import Offer


# ----------------------------
# Helpers
# ----------------------------

def _decode_mime_header(value: str) -> str:
    """Decode RFC2047 headers safely (Subject, etc.)."""
    if not value:
        return ""
    parts = decode_header(value)
    out: list[str] = []
    for part, enc in parts:
        if isinstance(part, bytes):
            out.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(part)
    return "".join(out)


def _extract_body(msg) -> tuple[str, str]:
    """
    Returns (text, html) best-effort from an email message.
    Prefers the largest html part if present.
    """
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
            content = payload.decode(charset, errors="replace")

            if ctype == "text/plain":
                text_parts.append(content)
            elif ctype == "text/html":
                html_parts.append(content)
    else:
        ctype = (msg.get_content_type() or "").lower()
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        content = payload.decode(charset, errors="replace")
        if ctype == "text/html":
            html_parts.append(content)
        else:
            text_parts.append(content)

    text = "\n\n".join(text_parts).strip()
    html = max(html_parts, key=len).strip() if html_parts else ""
    return text, html


_URL_RE = re.compile(r"""https?://[^\s"'<>]+""", re.IGNORECASE)


def _extract_urls_from_text(text: str) -> list[str]:
    """Extract raw URLs from plain text."""
    urls = _URL_RE.findall(text or "")
    seen, out = set(), []
    for u in urls:
        u = u.strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _extract_urls_from_html(html: str) -> list[str]:
    """
    HTML: SOLO extrae links desde <a href="...">.
    (No hacemos regex global dentro del HTML para evitar links "basura" de tracking/recursos/pixels)
    """
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
    """
    Attempts to unwrap common tracking wrappers:
    - ...?url=<ENCODED>
    - ...?redirect=<ENCODED>
    - ...?u=<ENCODED>
    - ...?target=<ENCODED>
    """
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


def _canonical_linkedin_job_url(url: str) -> str | None:
    """
    Devuelve una URL canónica del empleo si se puede inferir el Job ID,
    o None si no parece link directo de empleo.
    """
    try:
        u = _unwrap_tracking(url)
        p = urlparse(u)
        host = (p.netloc or "").lower()

        # "directo": linkedin.com (excluye lnkd.in)
        if host.endswith("lnkd.in"):
            return None
        if "linkedin.com" not in host:
            return None

        path = p.path or ""
        q = parse_qs(p.query)

        # Caso 1: /jobs/view/<id>
        m = re.search(r"/jobs/view/(\d+)", path)
        if m:
            job_id = m.group(1)
            return f"https://www.linkedin.com/jobs/view/{job_id}/"

        # Caso 2: parámetros frecuentes
        for key in ("currentJobId", "jobId"):
            if key in q and q[key]:
                job_id = q[key][0]
                if job_id.isdigit():
                    return f"https://www.linkedin.com/jobs/view/{job_id}/"

        return None
    except Exception:
        return None


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


# ----------------------------
# Main function
# ----------------------------

def get_last_offers(
    mailbox: str = "INBOX",
    limit: int = 50,
    unseen_only: bool = False,
) -> list[Offer]:
    """
    Reads LinkedIn Job Alerts emails (From: jobalerts-noreply@linkedin.com),
    extracts *job* links (deduped by Job ID) from each email.

    Requires .env with:
      IMAP_SERVER=...
      IMAP_PORT=993 (optional)
      GMAIL_USER=...
      GMAIL_APP_PASSWORD=...

    Returns:
      [
        {
          "message_id": "...",
          "subject": "...",
          "date": "2025-12-13T08:00:00+01:00",
          "links": ["https://www.linkedin.com/jobs/view/....", ...]
        },
        ...
      ]
    """
    load_dotenv()

    host = os.getenv("IMAP_SERVER")
    port = int(os.getenv("IMAP_PORT", "993"))
    user = os.getenv("GMAIL_USER")
    password = os.getenv("GMAIL_APP_PASSWORD")

    if not host or not user or not password:
        raise RuntimeError(
            "Faltan credenciales IMAP en .env: IMAP_SERVER, GMAIL_USER, GMAIL_APP_PASSWORD."
        )

    context = ssl.create_default_context()
    mail = imaplib.IMAP4_SSL(host, port, ssl_context=context)

    try:
        mail.login(user, password)
        mail.select(mailbox)

        criteria = ['FROM', '"jobalerts-noreply@linkedin.com"']
        if unseen_only:
            criteria = ["UNSEEN"] + criteria

        status, data = mail.search(None, *criteria)
        if status != "OK":
            raise RuntimeError(f"IMAP search failed: {status} {data}")

        ids = data[0].split()
        ids = list(reversed(ids))[: max(0, limit)]  # newest first

        results: list[dict] = []
        for msg_id in ids:
            status, msg_data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue

            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            subject = _decode_mime_header(msg.get("Subject", ""))
            print(f"Procesando: {subject}")

            message_id = (msg.get("Message-ID", "") or "").strip()

            date_raw = msg.get("Date", "")
            try:
                dt = parsedate_to_datetime(date_raw) if date_raw else None
                date_iso = dt.isoformat() if dt else ""
            except Exception:
                date_iso = ""

            text, html = _extract_body(msg)

            # URLs: HTML solo <a href>, texto con regex
            urls: list[str] = []
            urls.extend(_extract_urls_from_html(html))
            urls.extend(_extract_urls_from_text(text))

            # Canonicaliza y filtra SOLO empleos, deduplicando por Job ID
            job_links: list[str] = []
            for u in urls:
                canon = _canonical_linkedin_job_url(u)
                if canon:
                    job_links.append(canon)

            links = _dedupe_keep_order(job_links)

            results.append({
                "message_id": message_id,
                "subject": subject,
                "date": date_iso,
                "links": links,
            })
        
        offers = []
        for mail in results:
            for link in mail['links']:
                new_offer = Offer(link, mail['date'], mail['subject'])
                offers.append(new_offer)
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



