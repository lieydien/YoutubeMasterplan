"""Score the opening line of a video script.

Adapted from hookscore.py in Jake Schincariol's youtube-agent-skill (MIT, see LICENSE in this
folder): https://github.com/Jakeschincariol/youtube-agent-skill

Five properties, 0-100 each, and a verdict that is 60% the mean and 40% the weakest one, so a hook
with one dead property cannot hide behind four strong ones. It is a heuristic calibrated on English
hooks: a low score is a reason to look again, a high score is not a promise.
"""

import json
import os
import re
from functools import lru_cache

HOOKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hooks.json")

FILLER = {"basically", "actually", "literally", "just", "really", "very", "so", "kind", "sort",
          "like", "guys", "hey", "welcome", "today", "video", "subscribe", "channel"}
VAGUE = {"amazing", "incredible", "insane", "crazy", "huge", "massive", "game", "changer", "secret",
         "powerful", "ultimate", "best", "revolutionary", "mind", "blowing", "unbelievable"}
CONCRETE = re.compile(r"\b(\d[\d,.]*\s?(%|k|m|x|s|m|h)?|\$\d|\d+\s?(second|minute|hour|day|week|month|year)s?)\b", re.I)
YOU = re.compile(r"\b(you|your|you're|youre|yourself)\b", re.I)
STAKE = re.compile(r"\b(lose|lost|wasting|waste|quit|fail|broke|cost|risk|before|stop|never|die|dying|dead)\b", re.I)
CURIOSITY = re.compile(r"\b(why|how|what|which|until|before|but|nobody|almost|except|reason|actually)\b", re.I)

# A spoken hook lands in 9-24 words at ~150 wpm; the opening is collected up to this band.
MIN_HOOK_WORDS = 9
MAX_HOOK_SENTENCES = 2
# The regexes above are English. Below this share of ASCII letters the score is noise.
MIN_ASCII_LETTER_RATIO = 0.8

FIX = {
    "SPECIFICITY": "swap one adjective for a number, a name or a date",
    "ADDRESS": "say 'you' in the first six words",
    "STAKES": "name what it costs them to keep doing it the current way",
    "CURIOSITY": "cut the half of the sentence that answers itself",
    "BREVITY": "9 to 24 words. Read it out loud and stop where you run out of breath",
}


@lru_cache(maxsize=1)
def load_formulas() -> tuple:
    with open(HOOKS_FILE, encoding="utf-8") as f:
        return tuple(json.load(f)["hooks"])


def words(text):
    return re.findall(r"[a-z0-9'%$.]+", text.lower())


def specificity(t):
    w = words(t)
    if not w:
        return 0
    nums = len(CONCRETE.findall(t))
    vague = sum(1 for x in w if x in VAGUE)
    filler = sum(1 for x in w if x in FILLER)
    s = 34 + nums * 22 - vague * 16 - filler * 5
    # proper nouns that are not sentence-initial read as named things
    s += min(18, 6 * sum(1 for x in t.split()[1:] if x[:1].isupper()))
    return max(0, min(100, s))


def address(t):
    n = len(YOU.findall(t))
    first = 30 if YOU.search(" ".join(t.split()[:6])) else 0
    return max(0, min(100, 26 + n * 20 + first))


def stakes(t):
    n = len(STAKE.findall(t))
    return max(0, min(100, 22 + n * 26 + (14 if CONCRETE.search(t) else 0)))


def curiosity(t):
    n = len(CURIOSITY.findall(t))
    q = 18 if t.strip().endswith("?") else 0
    # a hook that resolves itself has no gap left
    closed = -18 if re.search(r"\b(because|so that|which means)\b", t, re.I) else 0
    return max(0, min(100, 24 + n * 17 + q + closed))


def brevity(t):
    n = len(words(t))
    if n == 0:
        return 0
    if 9 <= n <= 24:
        return 100
    if n < 9:
        return max(30, 100 - (9 - n) * 11)
    return max(10, 100 - (n - 24) * 7)


PROPS = (("SPECIFICITY", specificity), ("ADDRESS", address), ("STAKES", stakes),
         ("CURIOSITY", curiosity), ("BREVITY", brevity))


def classify(text):
    best, hits = None, 0
    for formula in load_formulas():
        n = sum(1 for p in formula["match"] if re.search(p, text, re.I))
        if n > hits:
            best, hits = formula, n
    return (best["name"] if best else ""), hits


def band(verdict):
    return "STRONG" if verdict >= 72 else "WORKABLE" if verdict >= 55 else "WEAK"


def is_supported_text(text: str) -> bool:
    """True when the text is mostly Latin letters, which is what the heuristics were built on."""
    letters = [c for c in text or "" if c.isalpha()]
    if not letters:
        return False
    ascii_letters = sum(1 for c in letters if c.isascii())
    return ascii_letters / len(letters) >= MIN_ASCII_LETTER_RATIO


def extract_hook(script: str) -> str:
    """The opening the viewer hears first: the first sentence, or two if the first is too short."""
    text = " ".join((script or "").split())
    if not text:
        return ""
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s]
    hook = []
    for sentence in sentences[:MAX_HOOK_SENTENCES]:
        hook.append(sentence)
        if len(words(" ".join(hook))) >= MIN_HOOK_WORDS:
            break
    return " ".join(hook)


def score_hook(text: str) -> dict:
    text = (text or "").strip()
    properties = {name: fn(text) for name, fn in PROPS}
    values = list(properties.values())
    verdict = round(0.6 * (sum(values) / len(values)) + 0.4 * min(values))
    formula, matched = classify(text)
    weakest = min(properties, key=properties.get)
    return {
        "hook": text,
        "properties": properties,
        "verdict": verdict,
        "band": band(verdict),
        "formula": formula,
        "matched": matched,
        "weakest": weakest,
        "fix": FIX[weakest],
    }
