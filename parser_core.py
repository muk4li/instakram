"""Privacy-first extraction of URLs from Instagram JSON/ZIP exports."""
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

URL_PATTERN = re.compile(r'https?://[^\s<>"\'\\]+', re.IGNORECASE)
INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com", "m.instagram.com", "instagr.am", "www.instagr.am"}
MAX_ARCHIVE_BYTES = 200 * 1024 * 1024
MAX_JSON_BYTES = 80 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 500 * 1024 * 1024
MAX_ENTRIES = 15000

def fix_mojibake(text):
    """Repair Instagram's UTF-8-as-Latin-1 escaping ("JÃ¼rgen" -> "Jürgen").

    Strings that are not such mojibake (plain ASCII, real "Café", emojis)
    fail the round trip and are returned unchanged.
    """
    try:
        return text.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return text

def fix_document(node):
    """Apply fix_mojibake to every string (values and keys) of a parsed JSON document."""
    if isinstance(node, str):
        return fix_mojibake(node)
    if isinstance(node, list):
        return [fix_document(v) for v in node]
    if isinstance(node, dict):
        return {fix_mojibake(k): fix_document(v) for k, v in node.items()}
    return node

def url_normalize(raw):
    raw = raw.replace("\\/", "/").replace("\\u0026", "&").rstrip(".,;:!?)]}")
    try:
        u = urlsplit(raw)
        if u.scheme not in ("http", "https") or not u.netloc or u.username or u.password:
            return None
        return urlunsplit(("https", u.netloc.lower(), u.path.rstrip("/") or "/", u.query, ""))
    except ValueError:
        return None

def classify(url):
    u = urlsplit(url)
    if (u.hostname or "").lower() not in INSTAGRAM_HOSTS:
        return "external"
    path = u.path.lower()
    if path.startswith(("/reel/", "/reels/")):
        return "reel"
    if path.startswith("/p/"):
        return "post"
    if path.startswith("/stories/"):
        return "story"
    return "instagram"

def categorise(filename):
    s = "/" + filename.lower().replace("\\", "/")
    if "/messages/" in s or "/inbox/" in s or "/message_requests/" in s:
        return "chat"
    if any(word in s for word in ("/saved", "saved_", "/collections", "gespeichert")):
        return "saved"
    if any(word in s for word in ("/archive", "/archived", "archiv", "/stories/", "/posts/")):
        return "archive"
    return "other"

def conversation(filename):
    parts = filename.replace("\\", "/").split("/")
    for i, part in enumerate(parts):
        if part.lower() in ("inbox", "message_requests") and i + 1 < len(parts):
            return parts[i+1]
    return ""

def format_time(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            sec = value / 1000 if value > 1e11 else value
            return datetime.fromtimestamp(sec, tz=timezone.utc).isoformat(timespec="seconds")
        except (ValueError, OverflowError, OSError):
            return ""
    if isinstance(value, str):
        return value
    return ""

CAPTION_KEYS = ("caption", "description", "alt_text", "accessibility_caption")
def caption_string(value):
    if isinstance(value, str):
        return value[:5000]
    if isinstance(value, dict):
        # Some Instagram exports wrap captions in {"text": "..."}.
        for key in ("text", "value"):
            if isinstance(value.get(key), str):
                return value[key][:5000]
    return ""

def collect(doc, source):
    category = categorise(source)
    chat = conversation(source)
    results = []
    def walk(node, sender="", date="", caption="", creator=""):
        if isinstance(node, dict):
            for k in ("sender_name", "sender", "username", "author"):
                if isinstance(node.get(k), str):
                    sender = node[k]
                    break
            for k in ("timestamp_ms", "timestamp", "creation_timestamp", "saved_at", "date", "time"):
                if k in node:
                    date = format_time(node[k]) or date
                    break
            for key in ("creator_username", "owner_username", "media_owner_username"):
                val = node.get(key)
                if isinstance(val, str) and 1 <= len(val.strip()) <= 100:
                    creator = val.strip().lstrip("@")
                    break
            # Only explicit description/caption fields are used. Do NOT interpret
            # nearby chat messages or filenames as a reel's description.
            local_caption = next((caption_string(node[k]) for k in CAPTION_KEYS
                                  if k in node and caption_string(node[k])), "")
            caption = local_caption or caption
            for key, value in node.items():
                if key in CAPTION_KEYS:
                    # A caption can itself contain a URL.
                    if isinstance(value, str):
                        walk(value, sender, date, caption, creator)
                    continue
                walk(value, sender, date, caption, creator)
        elif isinstance(node, list):
            for value in node:
                walk(value, sender, date, caption, creator)
        elif isinstance(node, str):
            for match in URL_PATTERN.findall(node):
                url = url_normalize(match)
                if url:
                    results.append({"area": category, "chat": chat, "sender": sender,
                                    "date": date, "kind": classify(url), "url": url,
                                    "source": source, "caption": caption, "creator": creator})
    walk(doc)
    return results

def process_bytes(data, name):
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("Datei zu groß (maximal 200 MB).")
    files = []
    errors = 0
    if name.lower().endswith(".json"):
        if len(data) > MAX_JSON_BYTES:
            raise ValueError("JSON-Datei zu groß.")
        files.append((name, data))
    elif name.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                infos = [x for x in archive.infolist() if not x.is_dir() and x.filename.lower().endswith(".json")]
                if len(infos) > MAX_ENTRIES or sum(x.file_size for x in infos) > MAX_TOTAL_UNCOMPRESSED:
                    raise ValueError("Archiv enthält zu viele oder zu große Dateien.")
                for info in infos:
                    if info.file_size > MAX_JSON_BYTES:
                        errors += 1
                        continue
                    try:
                        files.append((info.filename, archive.read(info)))
                    except (RuntimeError, zipfile.BadZipFile, OSError):
                        errors += 1
        except zipfile.BadZipFile as exc:
            raise ValueError("ZIP-Datei ist ungültig.") from exc
    else:
        raise ValueError("Bitte eine .zip- oder .json-Datei auswählen.")
    results = []
    for filename, content in files:
        try:
            results.extend(collect(fix_document(json.loads(content.decode("utf-8-sig"))), filename))
        except (UnicodeError, ValueError, RecursionError):
            errors += 1
    # Remove exact duplicates while preserving distinct occurrences/metadata.
    seen = set()
    unique = []
    for r in results:
        key = tuple(r[k] for k in ("area", "chat", "sender", "date", "url", "caption", "creator"))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    unique.sort(key=lambda x: (x["date"], x["url"]), reverse=True)
    return {"items": unique, "jsonFiles": len(files), "errors": errors}
