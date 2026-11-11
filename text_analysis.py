"""Extract hashtags and transparent keyword candidates from actual exported captions."""
import re
from collections import Counter

# Python's Unicode \w matches non-Latin letters too; exclude leading digits/underscores.
HASHTAG = re.compile(r"(?<![\w#])#([^\W\d_][\w]*)(?!\w)", re.UNICODE)
WORD = re.compile(r"[^\W\d_][^\W_]*", re.UNICODE)

STOPWORDS = frozenset("""
aber als also am an auch auf aus bei bin bis das dass dein deine dem den der des die dies diese dieser
doch du durch ein eine einem einen einer eines er es etwas für gegen haben hat hier ich ihr ihre im
in ins ist ja kann kein keine mit nach nicht noch nur oder ohne sehr sich sie sind so und uns
unser unsere unter über um von vor was weil wenn wer wie wir wird wo zu zum zur
a about after all also an and are as at be been before but by can did do does for from had has
have how i if in into is it its just me more my no not of on or our out over so some than
that the their them there these they this to too up us was we were what when where which who
why will with you your
reel reels instagram video videos post posts share shared link links www https http com
""".split())

def hashtags(text):
    if not isinstance(text, str):
        return []
    return sorted({m.group(1).casefold() for m in HASHTAG.finditer(text) if len(m.group(1)) <= 80})

def keywords(text, limit=12):
    """Simple interpretable words; not semantic classification or AI."""
    if not isinstance(text, str):
        return []
    text = HASHTAG.sub(" ", text)
    text = re.sub(r"https?://\S+", " ", text, flags=re.I)
    counts = Counter(
        word.casefold() for word in WORD.findall(text)
        if 3 <= len(word) <= 50 and word.casefold() not in STOPWORDS
    )
    return [word for word, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:limit]]
