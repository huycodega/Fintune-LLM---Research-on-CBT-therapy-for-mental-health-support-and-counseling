"""
Hand-authored `chosen` responses for needs_chosen.jsonl — the turns where
EVERY sampled draft failed the quality detectors, so there was no on-policy
chosen to pair against. This is deliberately the only human-written slice of
the DPO set; everything else is the model's own output.

Authoring rules (mirror the production bar):
  - work with what the client already said (quote the named thought back)
  - deliver substance on delivery-asks: zero '?' anywhere
  - never address the client by a name they didn't give
  - end with a statement, concrete step where one fits

    python scripts/fill_needs_chosen.py   # -> dpo_data/needs_chosen_filled.jsonl
"""
import json
from pathlib import Path

OUT_DIR = Path(__file__).parent / "dpo_data"

# key = first 40 chars of the client message -> (technique, response)
AUTHORED = {
 "Everything feels like too much right now": (
  "Validation and grounding",
  "That's a heavy place to be, and saying it out loud already takes some of "
  "the weight off. When everything blurs into one big \"too much\", the mind "
  "loses track of the fact that it's really a pile of separate, smaller "
  "things. If you're up for it, name just one thing from the pile — not the "
  "biggest, any one — and we'll look at that piece together. One thing at a "
  "time is how \"too much\" becomes \"manageable\"."),
 "I'm afraid my group members think I'm th": (
  "Cognitive restructuring (mind-reading)",
  "That fear — \"they think I'm the useless one\" — is a mind-reading "
  "prediction, not something anyone has actually said. Notice the evidence: "
  "you're in the group, you show up, and no one has told you your work falls "
  "short; anxiety is filling the silence with the worst story. A fairer "
  "read: \"I don't actually know what they think — I only know what I fear "
  "they think.\" This week, pick one small visible contribution — "
  "summarizing notes, booking the room — and let actions answer the story."),
 "I keep thinking I only got into this pro": (
  "Cognitive restructuring (impostor thinking)",
  "What you're describing — \"I got in by luck and they'll find out\" — has "
  "a name: impostor thinking, and it's remarkably common in competitive "
  "programs. The evidence against it is structural: admissions reviewed your "
  "record, not a lottery ticket, and you've been passing work that can't be "
  "passed by luck. A steadier thought: \"I earned my seat with the same work "
  "everyone else did; feeling doubt doesn't make me a fraud.\" Keep a small "
  "evidence file — every passed assignment goes in — and open it whenever "
  "the impostor voice gets loud."),
 "I keep thinking that everyone in the lec": (
  "Cognitive restructuring (spotlight effect)",
  "That thought — \"everyone understands except me\" — is the spotlight "
  "effect working against you: you see your own confusion from the inside "
  "but only everyone else's calm surface. Lectures are full of quietly lost "
  "people nodding along; the questions that surface after class prove it. A "
  "more accurate version: \"some people get it, some don't, and faces don't "
  "tell me which.\" Next lecture, write down the exact minute you got lost "
  "and bring that one timestamp to office hours — confusion becomes a "
  "question you can actually ask."),
 "I'm afraid that if I take a gap semester": (
  "Cognitive restructuring (single-track timeline)",
  "The fear \"everyone will leave me behind\" treats life like a single race "
  "with one clock, but timelines diverge naturally after graduation anyway — "
  "within two years, almost nobody's path lines up with anyone else's. A gap "
  "semester taken for real reasons tends to read as intention, not failure. "
  "A steadier framing: \"I'd be choosing a different pace, not dropping out "
  "of the race.\" Before deciding, write two columns — what the semester off "
  "would protect, and what it would cost — and judge the decision on what's "
  "actually in them."),
 "I keep thinking my roommate secretly hat": (
  "Behavioral experiment (testing a prediction)",
  "\"My roommate secretly hates living with me\" is a story built from "
  "ambiguous clues — silence, a closed door, a short answer — and anxious "
  "minds fill ambiguity with rejection. The checkable facts: she still lives "
  "there, and nothing has actually been said. Rather than reading tea "
  "leaves, run one small experiment this week — a casual \"want anything "
  "from the store\" — and watch the real response. Data from one small "
  "interaction beats a week of mind-reading."),
 "Just tell me straight: is it normal to f": (
  "Psychoeducation (performance anxiety)",
  "Straight answer: yes — pre-quiz anxiety this frequent is common, and it's "
  "your threat system treating each quiz as high-stakes, not a sign that "
  "something is wrong with you. The level matters more than the presence: if "
  "it spikes beforehand and settles once you start, that's textbook "
  "performance arousal, and a moderate dose even sharpens focus. It becomes "
  "worth treating when it blocks sleep, eating, or starting the quiz itself. "
  "Two things flatten it reliably: a fixed ten-minute review ritual right "
  "before, and slow exhale breathing in the final minute — both signal "
  "routine, not danger, to your body."),
 "Walk me through how to stop overthinking": (
  "Stimulus control and worry scheduling",
  "Here's the walk-through. First, give your brain an earlier worry window: "
  "fifteen minutes in the evening where you write every loop down — thoughts "
  "repeat at night mainly because they're afraid of being forgotten. Second, "
  "build a shutdown ritual: the same three steps nightly — screens off, "
  "tomorrow's first task on paper, lights down — so the body learns the "
  "off-ramp. Third, in bed, swap arguing with thoughts for naming them: "
  "\"planning again\", \"replaying again\" — label it and let it pass. And "
  "past twenty minutes awake, get up and sit somewhere dim until drowsy; the "
  "bed stays a sleep place, not a debate hall."),
 "What small habit could help with my morn": (
  "Behavioral activation (morning ritual)",
  "A strong one: win the first five minutes. Before anything else — before "
  "the phone, which hands your morning to other people's demands — run one "
  "fixed tiny sequence: water, window open, one line written about the "
  "single thing that matters today. Dread feeds on the whole day arriving at "
  "once; a first-five-minutes ritual shrinks the day to one next step. Keep "
  "it boring and identical every morning — consistency is what tells your "
  "nervous system the day is safe to enter."),
 "Break it down for me — why do I freeze d": (
  "Psychoeducation (freeze response)",
  "Here's the breakdown. The freeze is your threat response reading the room "
  "as danger: heart rate spikes, working memory narrows, and rehearsed words "
  "become temporarily unreachable — biology, not incompetence. It peaks at "
  "the opening because uncertainty peaks there, which is why the fix is "
  "front-loaded: over-rehearse ONLY the first two sentences until they're "
  "automatic — they carry you through the spike while your system settles. "
  "Add one slow exhale before you step up, plant both feet, and let the "
  "first shaky seconds exist instead of fighting them. The freeze thaws once "
  "the automatic opening buys your brain those ten seconds."),
 "Help me decide whether to drop this elec": (
  "Structured decision-making",
  "Let's decide it with three questions on paper. One: this elective either "
  "serves your actual goal — requirement, skill, genuine interest — or it "
  "was a maybe from the start. Two: the realistic cost of staying, in hours "
  "per week, and which courses those hours are being taken from. Three: the "
  "cost of dropping — credits, timeline, refund deadline. If it serves no "
  "goal and drains hours from courses that do, drop it without guilt; if it "
  "serves a real one, lower its polish bar to \"pass acceptably\" and keep "
  "it. Make the call within forty-eight hours — the limbo is costing more "
  "energy than either option would."),
 "Just tell me what to do about my procras": (
  "Behavioral activation (starting protocol)",
  "Done — no questions, here's the plan. Procrastination is avoidance of the "
  "discomfort of starting, not laziness, so every fix targets the start. "
  "One: shrink the entry — open the document and write one ugly sentence, "
  "nothing more. Two: a ten-minute timer; you may stop after it rings, but "
  "you rarely will, because starting was the whole wall. Three: phone in "
  "another room for those ten minutes — willpower is for starting, distance "
  "handles the rest. Four: when you finish a session, write down the first "
  "move for next time so future-you starts mid-stride. Run it four days "
  "straight before judging it."),
 "How likely is it that one bad semester r": (
  "Psychoeducation (direct answer)",
  "Direct answer: very unlikely. One bad semester reads as a dip, not a "
  "definition — admissions offices and employers overwhelmingly look at "
  "trends, totals, and recency, and an upward curve after a rough term often "
  "reads as resilience rather than risk. Concrete moves that shrink its "
  "footprint: a strong following term, a one-line context note where "
  "applications allow it, and a retake where policy replaces the grade. The "
  "transcript records a semester; it doesn't sentence you to it."),
 "Lay it out for me: what does a healthy s": (
  "Psychoeducation (study architecture)",
  "Here it is, laid out. Anchor sleep first — fixed wake time, seven-plus "
  "hours — because every study hour counts double on a rested brain. Then "
  "blocks: fifty minutes focused, ten off, phone elsewhere; three to five "
  "blocks on a class day is plenty. The hardest subject gets the first "
  "block, never the last. Space your repetition — a topic touched twice a "
  "week beats one four-hour cram. Keep one full evening and one full day "
  "weekly genuinely off; recovery is part of the schedule, not a break from "
  "it. And each night, write tomorrow's first task — starting is where "
  "schedules usually die."),
 "Help me choose between retaking the cour": (
  "Structured decision-making",
  "Let's cut it to the two questions that matter. One: the C either blocks "
  "something concrete — a major requirement, a GPA cutoff for your "
  "scholarship or grad-school target — or it doesn't; if it blocks, retake, "
  "and the decision is made for you. If it doesn't: two — weigh what the "
  "retake costs in time against what that time could build elsewhere. A C "
  "that blocks nothing is usually cheaper to keep than a semester slot spent "
  "re-earning it, and one C on an otherwise solid record barely moves the "
  "needle. Check those two facts today and let the answer fall out of them."),
 "Sometimes I feel like I'm running on fum": (
  "Validation and one small step",
  "\"Running on fumes and nobody notices\" — that's two different pains in "
  "one sentence: exhaustion, and invisibility, and the second often hurts "
  "more. Being unseen usually doesn't mean people don't care; it means "
  "you've gotten skilled at looking fine, which is its own exhausting job. "
  "You noticed, and you said it here — that counts as the first person "
  "noticing. One step: pick one person and one honest sentence this week — "
  "\"I've been running on empty lately\" — and give someone the chance to "
  "see the real level of the tank."),
 "I've been grinding my teeth at night sin": (
  "Psychoeducation (somatic stress)",
  "Grinding since midterms is your body doing the worrying after your mind "
  "clocks out — jaw tension is one of the most common physical outlets for "
  "exam stress. Three things are worth doing: mention it at your next dental "
  "or health-center visit, since a simple night guard protects the teeth; "
  "wind the body down before bed with a warm shower or slow breathing so it "
  "enters sleep less armed; and catch daytime clenching early — lips "
  "together, teeth apart is the resting position to return to. The grinding "
  "is a stress gauge, and it should ease as the midterm pressure does."),
 "My stomach hurts every Sunday evening be": (
  "Psychoeducation (anticipatory anxiety)",
  "A stomach ache that arrives on schedule every Sunday evening is "
  "anticipatory anxiety in its most honest form — the body bracing for the "
  "week before it starts. Two angles help. Soften the cliff: twenty minutes "
  "of light prep on Sunday afternoon — glance at the calendar, set out the "
  "first morning — so Monday stops being a wall of unknowns. Then reclaim "
  "the evening: put something genuinely pleasant in those last free hours, "
  "because a week that begins in dread starts half-lost. If the stomach "
  "trouble spreads beyond Sundays, a health-center visit to rule out the "
  "physical side is worth it."),
 "bad day.": (
  "Validation (open door)",
  "Sounds like one of those days that just needs to be said out loud — and "
  "you did, which counts. I'm here for it. If you want to unpack it, tell me "
  "the moment the day turned. And if you'd rather leave it as \"bad day, "
  "noted, survived\", that's a complete answer too — some days only need a "
  "witness, not a work plan."),
 "I'm worried that my best friend is getti": (
  "Cognitive restructuring (feelings vs facts)",
  "\"My best friend is getting tired of me\" is a feeling wearing the "
  "costume of a fact. Look at what's checkable: she still replies, still "
  "shows up, and nothing has been said — the actual evidence is a change in "
  "vibe, which has a dozen boring explanations, her own stress first among "
  "them. A fairer thought: \"something feels different, and I don't yet know "
  "whether it's about me at all.\" One honest check-in — \"you've seemed "
  "quieter lately, everything okay with you\" — respects both of you more "
  "than silently drafting the ending."),
 "I'm scared that choosing this major was ": (
  "Cognitive restructuring (permanence framing)",
  "\"Choosing this major was a huge mistake\" lands hard because it frames "
  "one decision as permanent. The facts around it are softer: majors get "
  "changed, minors get added, and careers routinely wander far from the "
  "diploma line — the choice steers, it doesn't sentence. Separate the two "
  "possibilities: struggling with hard coursework, which visits every major, "
  "versus consistent emptiness about the subject itself. This week, write "
  "down which of the two your last month actually looks like, and take that "
  "page to your academic advisor — one hour of conversation against a year "
  "of quiet dread."),
 "My mind keeps saying I'm not smart enoug": (
  "Cognitive restructuring (verdict vs evidence)",
  "That voice — \"not smart enough for grad school\" — states a verdict, so "
  "hold it to a verdict's standard of proof. Its whole case is a feeling of "
  "doubt. The counter-case: your record carried you to the point where grad "
  "school is even on the table, and doubt before a big step is the norm "
  "among people who take it, not the exception — grad school selects for "
  "persistence at least as much as brilliance. A truer sentence: \"I don't "
  "feel ready, and readiness grows by applying, not by waiting to feel it.\" "
  "Draft the application and let the committee do the judging, not the "
  "voice."),
}


def main() -> None:
    needs = [json.loads(l) for l in
             (OUT_DIR / "needs_chosen.jsonl").read_text(encoding="utf-8")
             .splitlines() if l.strip()]
    filled, missing, seen_pair = [], set(), set()
    for row in needs:
        msg = (row["prompt"].split("[CURRENT CLIENT MESSAGE]")[1]
               .split("[CLINICAL TASK]")[0].strip())
        hit = next((v for k, v in AUTHORED.items() if msg.startswith(k)), None)
        if hit is None:
            missing.add(msg[:60])
            continue
        tech, resp = hit
        assert "?" not in resp, f"question mark in authored response: {msg[:40]}"
        assert len(resp) >= 150, f"too short: {msg[:40]}"
        key = (row["prompt"][:150], row["rejected"][:150])
        if key in seen_pair:
            continue
        seen_pair.add(key)
        filled.append({
            "prompt": row["prompt"],
            "chosen": (f"Technique: {tech}\n"
                       "Rationale: The client's message already contains "
                       "what's needed; the reply works with it directly "
                       "instead of asking again.\n"
                       "Plan: Validate briefly, then deliver the substance "
                       "in one cohesive reply.\n"
                       f"Response: {resp}"),
            "rejected": row["rejected"],
            "source": "needs_filled",
            "session_id": row["session_id"],
        })
    out = OUT_DIR / "needs_chosen_filled.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in filled:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"needs_chosen_filled.jsonl : {len(filled)} pairs "
          f"({len(AUTHORED)} authored responses)")
    for m in sorted(missing):
        print("  MISSING author for:", m)


if __name__ == "__main__":
    main()
