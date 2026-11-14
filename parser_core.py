"""Privacy-first extraction of URLs from Instagram JSON/ZIP exports."""
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

URL_PATTERN = re.compile(r'https?://[^\s<>"\'\\]+', re.IGNORECASE)
INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com", "m.instagram.com", "instagr.am", "www.instagr.am"}
MAX_ARCHIVE_BYTES = 800 * 1024 * 1024
MAX_JSON_BYTES = 150 * 1024 * 1024  # liked_posts.json can exceed 80 MB
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

# share_text: caption of a post/reel shared in a chat (Instagram message export).
CAPTION_KEYS = ("caption", "description", "alt_text", "accessibility_caption", "share_text")
# original_content_owner: account that posted the shared reel/post.
CREATOR_KEYS = ("creator_username", "owner_username", "media_owner_username", "original_content_owner")

# Fine-grained origin derived from the export path (first match wins).
SOURCE_TYPES = (
    ("/message_requests/", "message_request"), ("/inbox/", "chat"), ("/messages/", "chat"),
    ("/saved/", "saved"), ("liked_posts", "liked"), ("/likes/", "liked_other"),
    ("/story_interactions/", "story_interaction"), ("/comments/", "comment"),
    ("/followers_and_following/", "connection"), ("/link_history/", "link_history"),
    ("/ads_information/", "ads"), ("/your_instagram_activity/media/", "own_media"),
)

def source_type(filename):
    s = "/" + str(filename).lower().replace("\\", "/")
    return next((name for marker, name in SOURCE_TYPES if marker in s), "other")
def caption_string(value):
    if isinstance(value, str):
        return value[:5000]
    if isinstance(value, dict):
        # Some Instagram exports wrap captions in {"text": "..."}.
        for key in ("text", "value"):
            if isinstance(value.get(key), str):
                return value[key][:5000]
    return ""

# Newer saved/liked exports: entries with "label_values" (labels are localised).
LV_CAPTION = ("untertitel", "subtitle", "caption", "titel", "title")
LV_CREATOR = ("benutzername", "username", "user name", "nombre de usuario")

def label_entries(node):
    """Yield (label, value, href) from a label_values structure, recursing into "dict" lists."""
    for entry in node if isinstance(node, list) else []:
        if not isinstance(entry, dict):
            continue
        if isinstance(entry.get("label"), str):
            yield entry["label"].strip().casefold(), entry.get("value"), entry.get("href")
        yield from label_entries(entry.get("dict"))

def label_values_item(node):
    """Post URL, caption and owner username of one label_values entry.

    Only the top-level URL is the post; nested URLs belong to the owner's
    profile (e.g. their website) and are deliberately not imported as links.
    """
    top = [e for e in node["label_values"] if isinstance(e, dict)]
    url = next((e.get("href") or e.get("value") for e in top
                if str(e.get("label", "")).strip().casefold() == "url"), "")
    pairs = list(label_entries(top))
    captions = {label: value for label, value, _ in pairs if isinstance(value, str) and value.strip()}
    caption = next((captions[k] for k in LV_CAPTION if k in captions), "")
    creator = next((v for label, v, _ in pairs if label in LV_CREATOR and isinstance(v, str) and v.strip()), "")
    return url if isinstance(url, str) else "", caption[:5000], creator.strip().lstrip("@")[:100]

def chat_meta(doc):
    """Chat name and participant count from a message file (empty if not a chat file)."""
    if not isinstance(doc, dict) or not isinstance(doc.get("participants"), list):
        return "", 0
    title = doc.get("title") if isinstance(doc.get("title"), str) else ""
    return title.strip()[:200], len(doc["participants"])

def collect(doc, source):
    category = categorise(source)
    chat = conversation(source)
    chat_title, participants = chat_meta(doc) if chat else ("", 0)
    owner_titles = source_type(source) in ("saved", "liked")
    results = []
    def emit(raw, sender, date, caption, creator, reactions):
        for match in URL_PATTERN.findall(raw):
            url = url_normalize(match)
            if url:
                results.append({"area": category, "chat": chat, "sender": sender,
                                "date": date, "kind": classify(url), "url": url,
                                "source": source, "caption": caption, "creator": creator,
                                "chat_title": chat_title, "participants": participants,
                                "reactions": reactions})
    def walk(node, sender="", date="", caption="", creator="", reactions=0):
        if isinstance(node, dict) and isinstance(node.get("label_values"), list):
            url, lv_caption, lv_creator = label_values_item(node)
            lv_date = format_time(node.get("timestamp")) or date
            if url:
                emit(url, sender, lv_date, lv_caption or caption, lv_creator or creator, reactions)
            return
        if isinstance(node, dict):
            for k in ("sender_name", "sender", "username", "author"):
                if isinstance(node.get(k), str):
                    sender = node[k]
                    break
            for k in ("timestamp_ms", "timestamp", "creation_timestamp", "saved_at", "date", "time"):
                if k in node:
                    date = format_time(node[k]) or date
                    break
            if isinstance(node.get("reactions"), list):
                reactions = len(node["reactions"])
            # Older saved/liked format: {"title": "<owner>", "string_map_data"|"string_list_data": ...}
            if (owner_titles and isinstance(node.get("title"), str) and node["title"].strip()
                    and ("string_map_data" in node or "string_list_data" in node)):
                creator = node["title"].strip().lstrip("@")[:100]
            for key in CREATOR_KEYS:
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
                        walk(value, sender, date, caption, creator, reactions)
                    continue
                walk(value, sender, date, caption, creator, reactions)
        elif isinstance(node, list):
            for value in node:
                walk(value, sender, date, caption, creator, reactions)
        elif isinstance(node, str):
            emit(node, sender, date, caption, creator, reactions)
    walk(doc)
    return results

def process_bytes(data, name):
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError(f"Datei zu groß (maximal {MAX_ARCHIVE_BYTES // (1024 * 1024)} MB).")
    files = []
    errors = 0
    if name.lower().endswith(".json"):
        if len(data) > MAX_JSON_BYTES:
            raise ValueError(f"JSON-Datei zu groß (maximal {MAX_JSON_BYTES // (1024 * 1024)} MB).")
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
