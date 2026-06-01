"""
Seed Qdrant collections with minimal CBT knowledge if they're empty.

Idempotent: skips upsert if either collection already has ≥10 points
(the user's existing data is then preserved untouched).

Run via:
    docker compose exec backend python scripts/seed_qdrant.py

With the local-mode Qdrant config the user shipped (2,824 + 19,537
points), this script will simply skip both collections — that's
expected and desired.
"""
import logging
import sys
import uuid
from typing import List

from qdrant_client.http.models import PointStruct

from app.core.config import settings
from app.services import embedder, qdrant_client as qd


log = logging.getLogger("seed")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


# ------------------------------------------------------------
# Minimal CBT knowledge — short technique cards + example dialogues
# Real corpus should be much larger; this is just enough to power the
# demo retrieval + reranking on a fresh boot.
# ------------------------------------------------------------
KNOWLEDGE: List[dict] = [
    {"text": ("Decatastrophizing: technique used when a client predicts an "
              "extreme worst-case outcome and treats it as certain. Steps: "
              "(1) name the feared outcome explicitly, (2) estimate its "
              "realistic probability, (3) construct a coping plan even "
              "for the worst case."),
     "technique": "decatastrophizing"},
    {"text": ("Reality testing (also evidence examination): the client's "
              "belief is stated as fact without examined evidence. The "
              "therapist invites the client to list evidence for and "
              "against the thought, weigh both sides, and form a more "
              "balanced alternative."),
     "technique": "reality testing"},
    {"text": ("Alternative perspective: helpful when an all-or-nothing or "
              "rigid frame narrows the client's options. The therapist "
              "surfaces the implicit rule, generates 2-3 alternative "
              "viewpoints, and invites the client to test one."),
     "technique": "alternative perspective"},
    {"text": ("Behavioral experiment: a structured test in which the "
              "client checks a prediction against reality (e.g., 'people "
              "will judge me if I speak up'). Useful for SOCIAL anxiety; "
              "contraindicated at critical severity."),
     "technique": "behavior experiment"},
    {"text": ("Evidence-based questioning is used when the client is "
              "mind-reading: assuming what others think without direct "
              "evidence. The therapist guides toward concrete, "
              "observable evidence for each assumption."),
     "technique": "evidence-based questioning"},
    {"text": ("Changing rules to wishes (should → prefer): targets "
              "should-statements that intensify self-criticism. The "
              "therapist helps reframe 'I should…' as 'I would prefer…' "
              "and explores trade-offs."),
     "technique": "changing rules to wishes"},
]

EXAMPLES: List[dict] = [
    {"text": ("Client: 'I avoid the shelter because I think the animals "
              "hate me for forgetting them.'  Therapist: 'That belief — "
              "that animals can hate — let's look at the evidence "
              "together. What concrete signs would tell you they're "
              "rejecting you vs. just being cautious as animals?'"),
     "technique": "reality testing",
     "tags": ["anxiety", "avoidance"]},
    {"text": ("Client: 'I'm sure I'll fail and everyone will think I'm a "
              "fraud.'  Therapist: 'You're predicting two things — that "
              "you'll fail, and that the consequence will be unbearable. "
              "Let's separate them. What's the realistic probability of "
              "the first? And if it happened, what would you actually "
              "do?'"),
     "technique": "decatastrophizing",
     "tags": ["impostor", "catastrophizing"]},
    {"text": ("Client: 'I always mess up at work.'  Therapist: 'Always — "
              "that's a strong word. Could we look at last month "
              "together? Pull out three days that went well, even a "
              "little, and three that didn't. What pattern do you see?'"),
     "technique": "alternative perspective",
     "tags": ["all-or-nothing"]},
]


def _seed(collection: str, items: List[dict]) -> None:
    cli = qd.get_qdrant()
    try:
        count = cli.count(collection_name=collection,
                            exact=True).count
    except Exception as e:
        log.warning("Cannot count %s — assuming empty (%s)", collection, e)
        count = 0

    if count >= 10:
        log.info("Skip %s: already has %d points (user's data preserved)",
                 collection, count)
        return

    log.info("Seeding %s (%d points)…", collection, len(items))
    vecs = embedder.embed([i["text"] for i in items])
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload={**item, "seed": True},
        )
        for item, vec in zip(items, vecs)
    ]
    qd.upsert(collection, points)
    log.info("  ✓ %s populated", collection)


def main():
    qd.ensure_collections()
    _seed(settings.qdrant_collection_kb, KNOWLEDGE)
    _seed(settings.qdrant_collection_dialogues, EXAMPLES)
    log.info("Qdrant seed complete.")


if __name__ == "__main__":
    main()
