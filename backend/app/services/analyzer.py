"""
Psychological analysis — emotion + cognitive distortion + technique hint.

English-only lexicon (project switched away from Vietnamese in v4).
This is intentionally lightweight — for higher precision in production
swap to a fine-tuned classifier (e.g. cardiffnlp/twitter-roberta-base-
emotion). Output contract is what the prompt builder + admin dashboard
consume, so the swap is drop-in.
"""
import re
from typing import Dict


_EMOTION_LEX = {
    "fear":    [r"afraid", r"scared", r"anxious", r"worried", r"nervous",
                r"panic"],
    "sadness": [r"sad", r"down", r"empty", r"hopeless", r"depressed",
                r"miserable"],
    "anger":   [r"angry", r"furious", r"resent", r"hate", r"rage"],
    "shame":   [r"guilt", r"shame", r"failure", r"unworthy", r"embarrass",
                r"humiliat"],
    "isolation": [r"alone", r"lonely", r"isolat", r"disconnect"],
}

_DISTORTION_LEX = {
    "catastrophizing":     [r"worst", r"disaster", r"ruin",
                            r"everything will go wrong"],
    "all-or-nothing":      [r"always", r"never", r"completely", r"totally",
                            r"absolutely"],
    "overgeneralization":  [r"everything", r"nobody", r"everyone",
                            r"no one ever"],
    "mind-reading":        [r"they think", r"everyone thinks",
                            r"they must be", r"they probably"],
    "labeling":            [r"i'?m a (loser|failure|burden|idiot|fraud)",
                            r"i am (worthless|incompetent|unloveable)"],
    "should-statements":   [r"i should", r"i must", r"i have to"],
    "personalization":     [r"my fault", r"because of me", r"i ruined"],
}


_TECH_HINT_MAP = {
    "catastrophizing":     "decatastrophizing",
    "all-or-nothing":      "alternative perspective",
    "overgeneralization":  "reality testing",
    "mind-reading":        "evidence-based questioning",
    "labeling":            "alternative perspective",
    "should-statements":   "changing rules to wishes",
    "personalization":     "reality testing",
}


def _hits(text: str, lex: Dict[str, list]) -> list:
    t = text.lower()
    return [label for label, pats in lex.items()
            if any(re.search(p, t) for p in pats)]


def analyze(text: str, severity: str = "moderate") -> Dict:
    emotions = _hits(text, _EMOTION_LEX) or ["unspecified distress"]
    distortions = _hits(text, _DISTORTION_LEX) or ["none clearly detected"]
    hint = next((_TECH_HINT_MAP[d] for d in distortions
                 if d in _TECH_HINT_MAP), "reality testing")
    return {
        "emotion": ", ".join(emotions),
        "severity": severity,
        "cognitive_distortions": ", ".join(distortions),
        "technique_hint": hint,
    }
