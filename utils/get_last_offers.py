import os
import re
import ssl
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, parse_qs, unquote
from html import unescape
from dotenv import load_dotenv

def _decode_mime_header(value: str) -> str:
    """Decode RFC2047 headers safely (Subject, etc.)."""
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for part, enc in parts:
        if isinstance(part, bytes):
            out.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(part)
    return "".join(out)

def _extract_body(msg ) -> tuple[str, str]:
    """
    Returns (text, html) best-effort from an email message.
    Prefers the largest html part if present.
    """
    text_parts = []
    html_parts = []

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

    # Pick "best" parts
    text = "\n\n".join(text_parts).strip()
    html = max(html_parts, key=len).strip() if html_parts else ""
    return text, html

_URL_RE = re.compile(r"""https?://[^\s"'<>]+""", re.IGNORECASE)

def _extract_urls_from_html(html: str) -> list[str]:
    """
    Extract URLs from HTML using:
    - href="..."
    - fallback: raw url regex
    """
    urls = []
    if html:
        # href extraction
        hrefs = re.findall(r"""href\s*=\s*["']([^"']+)["']""", html, flags=re.IGNORECASE)
        for h in hrefs:
            if h.startswith("http://") or h.startswith("https://"):
                urls.append(h)

        # fallback raw
        urls.extend(_URL_RE.findall(html))

    # de-dupe preserving order
    seen = set()
    out = []
    for u in urls:
        u = unescape(u).strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out

def _extract_urls_from_text(text: str) -> list[str]:
    urls = _URL_RE.findall(text or "")
    seen = set()
    out = []
    for u in urls:
        u = u.strip()
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
                candidate = qs[key][0]
                candidate = unquote(candidate)
                if candidate.startswith("http://") or candidate.startswith("https://"):
                    return candidate
    except Exception:
        pass
    return url

def _is_direct_linkedin_job(url: str) -> bool:
    """
    "Direct to LinkedIn" job link heuristic.
    Accepts:
    - linkedin.com/jobs/view/...
    - linkedin.com/jobs/search/...
    - linkedin.com/jobs/collections/...
    - lnkd.in short links can be allowed if you want, but those are not "direct".
      (We exclude lnkd.in by default.)
    """
    try:
        p = urlparse(url)
        host = (p.netloc or "").lower()

        # Exclude shortener if you want strictly direct
        if host.endswith("lnkd.in"):
            return False

        if "linkedin.com" not in host:
            return False

        path = (p.path or "").lower()
        return path.startswith("/jobs/") or "/jobs/" in path
    except Exception:
        return False

# ----------------------------
# Main function
# ----------------------------

def get_last_offers(
    mailbox: str = "INBOX",
    limit: int = 50,
    unseen_only: bool = False,
) -> list[dict]:
    """
    Reads LinkedIn Job Alerts emails (From: jobalerts-noreply@linkedin.com),
    extracts direct LinkedIn job links from each email.

    Requires .env with:
      IMAP_HOST=...
      IMAP_PORT=993   (optional, default 993)
      IMAP_USER=...
      IMAP_PASSWORD=...   (or IMAP_PASS)

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
        raise RuntimeError("Faltan credenciales IMAP en .env: IMAP_HOST, IMAP_USER, IMAP_PASSWORD (o IMAP_PASS).")

    context = ssl.create_default_context()
    mail = imaplib.IMAP4_SSL(host, port, ssl_context=context)

    try:
        mail.login(user, password)
        mail.select(mailbox)

        # IMAP search: from LinkedIn alerts.
        # NOTE: IMAP 'FROM' matches header substring (not strict equality).
        # We add UNSEEN optionally.
        criteria = ['FROM', '"jobalerts-noreply@linkedin.com"']
        if unseen_only:
            criteria = ["UNSEEN"] + criteria

        status, data = mail.search(None, *criteria)
        if status != "OK":
            raise RuntimeError(f"IMAP search failed: {status} {data}")

        ids = data[0].split()
        # Process newest first
        ids = list(reversed(ids))[: max(0, limit)]

        results = []
        for msg_id in ids:
            status, msg_data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue

            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            subject = _decode_mime_header(msg.get("Subject", ""))
            print(f"Procesando : {subject}")
            message_id = msg.get("Message-ID", "").strip()

            date_raw = msg.get("Date", "")
            try:
                dt = parsedate_to_datetime(date_raw) if date_raw else None
                date_iso = dt.isoformat() if dt else ""
            except Exception:
                date_iso = ""

            text, html = _extract_body(msg)
            urls = []
            urls.extend(_extract_urls_from_html(html))
            urls.extend(_extract_urls_from_text(text))

            # Unwrap tracking & filter for direct LinkedIn job urls
            cleaned = []
            for u in urls:
                u2 = _unwrap_tracking(u)
                if _is_direct_linkedin_job(u2):
                    cleaned.append(u2)

            # de-dupe links per email
            seen = set()
            links = []
            for u in cleaned:
                if u not in seen:
                    seen.add(u)
                    links.append(u)

            results.append({
                "message_id": message_id,
                "subject": subject,
                "date": date_iso,
                "links": links,
            })

        return results

    finally:
        try:
            mail.close()
        except Exception:
            pass
        try:
            mail.logout()
        except Exception:
            pass

