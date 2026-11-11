"""Local, deterministic topic clusters from actual export metadata.

No external API, no model calls and no claims about unseen video contents.
Clusters are discoverable views, not changes to the user's own folders.
"""
from collections import Counter, defaultdict
from hashlib import sha256
from itertools import combinations
from urllib.parse import urlsplit
from text_analysis import hashtags, keywords

MAX_TERMS = 250
MAX_CLUSTERS = 80
MAX_KEYWORDS_PER_CAPTION = 12
MIN_LINKS = 2


def cluster_topics(links, folders):
    """Return stable, overlapping clusters based on captions and folder evidence.

    Hashtag co-occurrence is clustered when at least two *distinct* links
    contain both tags and there is strong Jaccard overlap. Existing category
    folders form their own evidence-backed clusters. Words only form fallback
    clusters if they occur on >=3 distinct captioned links.
    """
    docs = {}
    tags_to_links = defaultdict(set)
    words_to_links = defaultdict(set)
    folder_to_links = defaultdict(set)
    creator_to_links = defaultdict(set)
    folder_info = {f["id"]: f for f in folders}

    for link in links:
        uid = link["id"]
        captions = link.get("captions", [])
        tags = set()
        words = set()
        for caption in captions:
            tags.update(hashtags(caption))
            words.update(keywords(caption, MAX_KEYWORDS_PER_CAPTION))
        words -= tags
        assigned = {fid for fid in link.get("folders", []) if fid in folder_info}
        docs[uid] = {"tags": tags, "words": words, "folders": assigned}
        # Creator can be inferred only from a real Instagram profile URL.
        # /reel/XYZ and /p/XYZ links contain no account identity.
        parsed = urlsplit(link.get("url", ""))
        if (parsed.hostname or "").lower() in ("instagram.com", "www.instagram.com", "m.instagram.com"):
            parts = [p for p in parsed.path.split("/") if p]
            reserved = {"reel","reels","p","stories","tv","explore","accounts","direct","share"}
            if len(parts) == 1 and parts[0].lower() not in reserved:
                creator_to_links[parts[0].casefold()].add(uid)
        for t in tags:
            tags_to_links[t].add(uid)
        for w in words:
            words_to_links[w].add(uid)
        for fid in assigned:
            folder_to_links[fid].add(uid)

    groups = []
    # Union frequent, very similar co-occurring hashtags into broad topics.
    frequent = sorted(
        (t for t, ids in tags_to_links.items() if len(ids) >= MIN_LINKS),
        key=lambda t: (-len(tags_to_links[t]), t)
    )[:MAX_TERMS]
    parent = {t: t for t in frequent}

    def find(tag):
        while parent[tag] != tag:
            parent[tag] = parent[parent[tag]]
            tag = parent[tag]
        return tag

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    # Inverted postings allow matching only hashtags that co-occur.
    tag_pairs = Counter()
    for doc in docs.values():
        common = sorted(doc["tags"].intersection(parent))
        for a, b in combinations(common[:30], 2):
            tag_pairs[(a, b)] += 1
    for (a, b), overlap in tag_pairs.items():
        combined = len(tags_to_links[a]) + len(tags_to_links[b]) - overlap
        if overlap >= 2 and overlap / combined >= 0.65:
            union(a, b)

    buckets = defaultdict(list)
    for tag in frequent:
        buckets[find(tag)].append(tag)

    for terms in buckets.values():
        matched = set().union(*(tags_to_links[t] for t in terms))
        if len(matched) >= MIN_LINKS:
            groups.append({"type": "hashtag", "title": "#" + max(terms, key=lambda t: (len(tags_to_links[t]), -len(t), t)),
                           "links": matched, "seed_terms": terms, "folder_ids": []})

    # Group associations are reliable only insofar as they were assigned by the user/rules.
    for fid, matched in folder_to_links.items():
        folder = folder_info[fid]
        if len(matched) >= MIN_LINKS and folder["path"].startswith("groups/"):
            groups.append({"type": "group", "title": folder["name"],
                           "links": matched, "seed_terms": [], "folder_ids": [fid]})

    # Profile-URL clusters (does not infer creators of Reel permalinks).
    for handle, matched in sorted(creator_to_links.items()):
        if len(matched) >= MIN_LINKS:
            groups.append({"type": "creator", "title": "@" + handle,
                           "links": matched, "seed_terms": [], "folder_ids": []})

    # Fallback keyword topics, but avoid topics identical to existing hashtag clusters.
    existing = [g["links"] for g in groups]
    ranked_words = sorted(words_to_links, key=lambda w: (-len(words_to_links[w]), w))[:MAX_TERMS]
    for word in ranked_words:
        matched = words_to_links[word]
        if len(matched) < 3:
            continue
        if any(len(matched & ids) / len(matched | ids) >= .85 for ids in existing):
            continue
        groups.append({"type": "keyword", "title": word, "links": set(matched),
                       "seed_terms": [], "folder_ids": []})
        existing.append(matched)

    # Aggregate corroborating terms and count unique linked items.
    output = []
    for group in groups:
        matched = group["links"]
        tag_counts = Counter(t for uid in matched for t in docs[uid]["tags"])
        word_counts = Counter(w for uid in matched for w in docs[uid]["words"])
        # Stable IDs across imports unless the cluster's defining terms change.
        identity = group["type"] + ":" + (
            ",".join(sorted(group["seed_terms"])) if group["seed_terms"]
            else str(group["folder_ids"][0]) if group["folder_ids"]
            else group["title"]
        )
        output.append({
            "id": sha256(identity.encode("utf-8")).hexdigest()[:16],
            "title": group["title"], "type": group["type"],
            "count": len(matched), "link_ids": sorted(matched),
            "hashtags": [{"term": t, "count": n} for t, n in sorted(tag_counts.items(), key=lambda x:(-x[1],x[0]))[:7]],
            "keywords": [{"term": t, "count": n} for t, n in sorted(word_counts.items(), key=lambda x:(-x[1],x[0]))[:7]],
            "folder_ids": group["folder_ids"],
            "explanation": ("Gemeinsame exportierte Hashtags" if group["type"] == "hashtag"
                            else "Vorhandene Gruppenzuordnungen" if group["type"] == "group"
                            else "Wiederkehrende Instagram-Profil-URLs" if group["type"] == "creator"
                            else "Häufige Wörter aus exportierten Beschreibungen")
        })

    output.sort(key=lambda g: (-g["count"], {"group":0,"hashtag":1,"creator":2,"keyword":3}[g["type"]], g["title"].casefold()))
    return output[:MAX_CLUSTERS]
