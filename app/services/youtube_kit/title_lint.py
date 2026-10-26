"""Lint a YouTube title, and optionally its thumbnail text, before publishing.

Adapted from title.py in Jake Schincariol's youtube-agent-skill (MIT, see LICENSE in this folder):
https://github.com/Jakeschincariol/youtube-agent-skill

YouTube truncates around 60 characters in desktop search and around 40 on a mobile home feed. Both
are reported because they fail differently: desktop loses the tail, mobile can lose the subject.
"""

import re

DESKTOP, MOBILE, HARD = 60, 40, 100
VAGUE = {"amazing", "incredible", "insane", "crazy", "huge", "massive", "ultimate", "best",
         "powerful", "secret", "revolutionary", "mindblowing", "epic", "perfect", "complete",
         "everything"}
STOP = {"the", "a", "an", "of", "for", "to", "in", "on", "and", "or", "is", "are", "with", "your",
        "you", "my", "i", "this", "that", "it", "how", "what", "why"}


def words(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def lint_title(title: str, thumb: str | None = None) -> dict:
    t = (title or "").strip()
    n = len(t)
    issues, good = [], []
    if n > HARD:
        issues.append(("length", f"{n} characters - YouTube's hard limit is {HARD}"))
    elif n > DESKTOP:
        issues.append(("length", f"{n} characters - desktop search cuts near {DESKTOP}"))
    else:
        good.append(f"{n} characters, inside the {DESKTOP}-character desktop cut")
    if n > MOBILE:
        head = t[:MOBILE].rsplit(" ", 1)[0]
        issues.append(("mobile", f'a mobile feed shows about "{head}..." - check the subject survives'))
    caps = [w for w in t.split() if len(w) > 2 and w.isupper()]
    if len(caps) > 2:
        issues.append(("shouting", f"{len(caps)} all-caps words - two is the ceiling before it reads as spam"))
    elif caps:
        good.append(f"{len(caps)} all-caps word for emphasis")
    vague = [w for w in words(t) if w in VAGUE]
    if vague:
        issues.append(("vague", f"{', '.join(sorted(set(vague)))} - swap for a number, a name or a date"))
    nums = re.findall(r"\d[\d,.]*%?", t)
    if nums:
        good.append(f"carries a concrete figure ({', '.join(nums[:3])})")
    else:
        issues.append(("no-number", "no number, date or name - the most reliable single fix"))
    if t.endswith("?"):
        good.append("open question in the title")
    if not [w for w in words(t)[:3] if w not in STOP]:
        issues.append(("front-load", "the first three words are all filler - move the subject forward"))
    if thumb and thumb.strip():
        shared = (set(words(t)) - STOP) & (set(words(thumb)) - STOP)
        if shared:
            issues.append(("duplicate", f"thumbnail repeats the title on {', '.join(sorted(shared))} - "
                                        "the thumbnail should say what the title does not"))
        else:
            good.append("thumbnail and title carry different words")
        if len(words(thumb)) > 4:
            issues.append(("thumb-length", f"{len(words(thumb))} words on the thumbnail - three is the ceiling at feed size"))
    score = max(0, min(100, 100 - 14 * len(issues) + 4 * len(good)))
    return {"title": t, "chars": n, "score": score, "issues": issues, "good": good}
