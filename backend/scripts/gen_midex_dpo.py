"""
MID-EXERCISE DPO pairs (v3.4) — the conversation STATE v3.3's data never
covered: the bot opened an evidence exercise, the client ANSWERED with
substance, and the model must now synthesize (reflect both sides → balanced
thought → small step) instead of re-opening step 1.

On-policy recipe: prompts are realistic mid-exercise contexts (2-turn
history + evidence answer); REJECTED are the model's real drafts collected
from the serving brain (plus the verbatim failing replies from the live
2026-07-06 tournament thread); CHOSEN are authored gold syntheses with
varied structure so the model learns the move, not a template.

3 of the 10 synthetic scenarios are HOLDOUT — never trained on — so the
v3.3-vs-v3.4 dirty-rate on them measures transfer of the new skill.

    # collect rejected + v3.3 holdout baseline (brain must serve v3.3):
    MODAL_BRAIN_WORKSPACE=nguyenhieu3603 python scripts/gen_midex_dpo.py --collect
    # after v3.4 deploys, holdout eval only:
    MODAL_BRAIN_WORKSPACE=nguyenhieu3603 python scripts/gen_midex_dpo.py --eval --tag v34
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from app.services.prompt_builder import build_messages     # noqa: E402
from app.services.post_process import parse_draft, scrub_unknown_names  # noqa: E402
from app.api.chat import _question_count, _EXERCISE_REOPEN  # noqa: E402
from app.core.config import settings                       # noqa: E402

OUT_DIR = Path(__file__).parent / "dpo_data"
OUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Scenarios. history = [(client_turn, bot_reply_opening_the_exercise)];
# current = the client's evidence answer; gold = authored synthesis.
# ---------------------------------------------------------------------------
S = [
 dict(topic="statistics final", holdout=False,
  history=[("I keep thinking that I'm going to fail my statistics final no "
            "matter how much I study.",
            "That thought sounds heavy. Let's look at the evidence for and "
            "against it — what supports it, and what contradicts it?")],
  current=("Supporting it: I failed the midterm and I blank out on formulas "
           "under time pressure. Against it: my homework scores are actually "
           "fine, and my study group says I explain concepts well. I guess "
           "the final just feels different from homework."),
  gold=("You've weighed it well. On one side: a failed midterm and blanking "
        "under time pressure. On the other: solid homework scores and a "
        "study group that trusts you to explain the material — that second "
        "column is about ability, the first is about exam conditions. So a "
        "fairer version of the thought: \"I know this material; what fails "
        "me is time pressure, and that's trainable.\" This week, do two "
        "timed practice sets under exam conditions — you're not fixing your "
        "statistics, you're rehearsing the pressure.")),
 dict(topic="class presentation", holdout=False,
  history=[("I'm afraid everyone will see how nervous I am on Friday and "
            "think I'm incompetent.",
            "Let's test that prediction against the evidence. What tells you "
            "it's true, and what tells you it might not be?")],
  current=("For it: last semester my hands shook and I lost my place twice, "
           "and one guy smirked. Against it: two classmates said afterwards "
           "they didn't notice anything, and my professor gave me a decent "
           "grade. Honestly the shaking felt much bigger to me than to them."),
  gold=("Your last sentence already carries the insight: the shaking felt "
        "much bigger to you than to them — two witnesses noticed nothing "
        "and the grade was decent, against one smirk that could have meant "
        "anything. That's the spotlight effect in action, and your own "
        "evidence outvotes it. Keep this thought for Friday: \"my nerves "
        "are loud on the inside and quiet on the outside.\" Rehearse the "
        "first two sentences out loud until they're automatic — a steady "
        "opening carries the minute your body needs to settle.")),
 dict(topic="thesis draft", holdout=False,
  history=[("I'm afraid that if my thesis isn't impressive, I've wasted "
            "four years.",
            "Let's put that belief through a thought record. What evidence "
            "supports it, and what speaks against it?")],
  current=("Support: my advisor called chapter two 'thin' and a classmate's "
           "draft looks far more polished. Against: the same advisor "
           "approved my methodology without changes, and last month's "
           "presentation of my results got real questions, real interest. "
           "Deadline is in six weeks either way."),
  gold=("Look at what you collected: one 'thin' chapter and one polished "
        "rival draft, versus an approved methodology and an audience that "
        "engaged with your actual results. The core of the thesis — the "
        "research — is holding; what needs work is one chapter's writing. "
        "A more accurate belief: \"chapter two needs revision; the thesis "
        "is sound.\" With six weeks left, give chapter two the next five "
        "days with a fixed 90-minute block each morning, then move on — "
        "revision responds to hours, not to worry.")),
 dict(topic="roommate respect", holdout=False,
  history=[("I keep thinking my roommate has zero respect for me — she "
            "leaves the kitchen a mess every single day.",
            "Let's check that interpretation against the evidence on both "
            "sides before we accept it.")],
  current=("Evidence for: the mess is constant even after I asked once, and "
           "she never thanks me for cleaning. Against: she covered my rent "
           "share once when I was short, asks about my exams, and honestly "
           "she's messy in her own room too — it's not aimed at me."),
  gold=("You caught the key detail yourself: she's messy in her own space "
        "too — so the kitchen is a habit, not a message about you. Set "
        "that against covering your rent and asking about your exams, and "
        "\"zero respect\" doesn't survive its own evidence. Truer version: "
        "\"she respects me and she's untidy — two separate facts.\" That "
        "reframe changes the fix: this stops being about proving your "
        "worth and becomes one honest house-rules conversation this week, "
        "made while things are calm rather than mid-annoyance.")),
 dict(topic="internship rejection", holdout=False,
  history=[("The internship rejection email made me certain that no company "
            "will ever want me.",
            "That's a strong conclusion from one email — let's weigh the "
            "evidence for and against it.")],
  current=("For: it's the second rejection this cycle and both were roles I "
           "really prepared for. Against: I did get to the final round both "
           "times, one interviewer emailed me feedback personally, and a "
           "senior told me most people apply to twenty places before one "
           "lands."),
  gold=("Two final rounds out of two applications is the opposite of "
        "\"no company will ever want me\" — companies keep almost-choosing "
        "you, and one interviewer cared enough to write feedback nobody "
        "owed you. Against a base rate of twenty applications per offer, "
        "you're two in. The evidence-backed thought: \"I'm consistently "
        "close on a very small sample — the numbers just haven't caught up "
        "yet.\" Concrete step: mine that feedback email for one improvable "
        "thing, then send three more applications this week to give the "
        "odds room to work.")),
 dict(topic="money management", holdout=False,
  history=[("Deep down I believe I'll never manage money right — I "
            "overdrafted again this month.",
            "Let's examine that belief properly: what's the evidence for "
            "it, and what doesn't fit it?")],
  current=("For it: two overdrafts in three months and I still don't have a "
           "real budget. Doesn't fit: I paid off my phone installment early "
           "this year, and both overdrafts happened in weeks when my shift "
           "hours got cut without warning — when income is normal I'm "
           "actually fine."),
  gold=("Your own analysis found the pattern: both overdrafts line up with "
        "surprise income drops, not with careless spending — and someone "
        "who \"can't manage money\" doesn't pay off an installment early. "
        "The accurate belief: \"I manage money fine on a stable income; "
        "what I'm missing is a buffer for the unstable weeks.\" So the "
        "step writes itself: open a separate pocket and move even a small "
        "fixed amount every payday — you're not fixing your character, "
        "you're building shock absorbers.")),
 dict(topic="friend drifting", holdout=False,
  history=[("I'm worried that my best friend is getting tired of me — she "
            "replies so much slower lately.",
            "Before we treat that as fact, let's look at what supports it "
            "and what argues against it.")],
  current=("Supports: replies went from minutes to days, and she cancelled "
           "our last coffee. Against: she started a new job three weeks "
           "ago, still sends me memes at midnight, and the cancellation "
           "came with an apology and a reschedule attempt."),
  gold=("Line the timeline up: the slow replies began exactly when the new "
        "job did — and tired friends don't send midnight memes or try to "
        "reschedule. The evidence points to a stretched friend, not a "
        "fading one. Steadier thought: \"her bandwidth changed, not her "
        "feelings.\" One step keeps this from festering: take the "
        "reschedule she offered and lock a date, and maybe tell her the "
        "honest sentence — \"missed you lately\" — because closeness "
        "survives on being said.")),
 dict(topic="gym progress", holdout=False,
  history=[("When I look in the mirror before class I'm convinced everyone "
            "notices exactly what I hate about myself.",
            "Let's test that against the evidence — what supports it, and "
            "what doesn't fit?")],
  current=("Supports: someone once commented on my arms in high school and "
           "I never forgot it. Doesn't fit: I've been training five months, "
           "my lifts keep going up, my gym buddy asked ME for form advice "
           "last week, and honestly nobody has said anything bad in years."),
  gold=("Weigh what you brought: one comment from years ago, against five "
        "months of rising lifts, a training partner who treats you as the "
        "one to learn from, and years of nobody saying anything. The old "
        "comment is a scar doing the talking, not the mirror. A truer line: "
        "\"one person's remark years ago doesn't outvote who I've become "
        "since.\" Next gym session, log the numbers that went up this month "
        "and let the data argue with the mirror for you.")),
 dict(topic="work mistake", holdout=False,
  history=[("I sent the wrong file to a customer at my part-time job and I "
            "keep thinking they're going to fire me.",
            "Let's look at the evidence on both sides of that prediction "
            "before treating it as fact.")],
  current=("For: my manager sighed when I told her, and the customer was "
           "annoyed. Against: she also said 'thanks for flagging it fast', "
           "we fixed it within the hour, my last review was positive, and "
           "the coworker who made a bigger mistake in spring still works "
           "there."),
  gold=("Put your evidence side by side: one sigh and one annoyed customer "
        "— against a fast fix, a manager who thanked you for the honesty, "
        "a positive review, and a precedent of bigger mistakes surviving. "
        "Workplaces fire patterns, not single corrected errors. Steadier "
        "thought: \"I made a mistake and handled it exactly right — that's "
        "what reliability looks like.\" If the worry lingers this week, ask "
        "your manager directly whether there's anything she'd like you to "
        "do differently — and let her answer replace the sigh in your "
        "head.")),
 dict(topic="real programmer doubt", holdout=False,
  history=[("My code review came back with forty comments and I'm certain "
            "the team regrets hiring me.",
            "Strong conclusion from one review — let's check it against the "
            "evidence for and against.")],
  current=("For: forty comments is way more than my teammate got, and two "
           "were about really basic things. Against: my mentor said heavy "
           "reviews are normal for first PRs here, half the comments were "
           "style-bot nitpicks, and they already assigned me the next "
           "feature."),
  gold=("Read your own second column: heavy first reviews are house-normal, "
        "half the comments came from a bot, and — the loudest fact — they "
        "handed you the NEXT feature. Teams don't invest new work in "
        "people they regret. The count measured the codebase's standards, "
        "not your ceiling. Balanced version: \"forty comments is this "
        "team's onboarding, and the next PR will have fewer.\" Track "
        "exactly that — comment count per PR over your next three — and "
        "watch the trend do the reassuring.")),
 dict(topic="major choice vs parents", holdout=False,
  history=[("I'm scared I picked the wrong major and that I only chose it "
            "to make my parents proud.",
            "Let's separate feeling from fact — what's the evidence each "
            "way?")],
  current=("For: I zone out in two of the required courses and my cousin "
           "seems way happier in design school. Against: I genuinely enjoy "
           "the lab work and my project groups, I chose this over my "
           "parents' first suggestion actually, and my grades are solid."),
  gold=("Your evidence already untangles it: you overruled your parents' "
        "first choice — so this major was YOUR call — and you light up in "
        "labs and group projects while two required courses bore you. "
        "Every major has its dead courses; enjoying the doing is the "
        "signal that matters. Fairer thought: \"I chose this, parts of it "
        "fit me well, and boredom in two courses is data about courses, "
        "not about my life.\" This month, pick one elective closer to the "
        "lab side you love — steer the major instead of re-litigating it.")),
 dict(topic="sleep relapse", holdout=False,
  history=[("My sleep was finally improving but this week it fell apart "
            "again — I feel like all that progress was fake.",
            "Let's check that conclusion against the evidence from both "
            "periods.")],
  current=("For: three bad nights in a row this week, back to 2am. "
           "Against: I had four solid weeks before this, the bad nights "
           "started exactly when my project deadline landed, and even now "
           "I'm falling asleep faster than I did two months ago."),
  gold=("Set the weeks side by side: four solid weeks, then three rough "
        "nights that arrived hand-in-hand with a deadline — and even the "
        "rough nights are better than your old baseline. That's not fake "
        "progress; that's real progress meeting real stress. Recovery "
        "curves dip, they don't reset. Truer sentence: \"a stressful week "
        "bent my sleep; it didn't break the skill I built.\" Tonight, "
        "just re-run your wind-down routine exactly as in the good weeks — "
        "same steps, no pressure — and let the pattern reassert itself.")),
 dict(topic="apology after argument", holdout=False,
  history=[("I snapped at my closest friend and I keep believing our "
            "friendship is basically over.",
            "Before we accept that, let's look at what supports it and "
            "what contradicts it.")],
  current=("Supports: she left on 'read' for two days, which she never "
           "does. Contradicts: we've argued twice before and recovered "
           "within a week both times, she still liked my story yesterday, "
           "and honestly I haven't actually apologized yet."),
  gold=("Your history says friendships like this bend and spring back — "
        "two arguments, two recoveries — and the story-like shows the "
        "door isn't closed, just cooler. The strongest item in your list "
        "is the last one: the apology hasn't been sent yet, so the "
        "outcome you fear hasn't even been tested. Grounded thought: "
        "\"we've survived worse, and the next move is mine.\" Send the "
        "simple version today — 'I was out of line, I'm sorry' — no "
        "essays, and give her a day to meet you where you two always end "
        "up.")),
 dict(topic="scholarship pressure", holdout=False,
  history=[("My scholarship needs a 3.5 and I keep thinking I'm going to "
            "lose it and prove I never belonged here.",
            "Let's examine the evidence for and against that fear.")],
  current=("For: I'm at 3.4 after a rough organic chemistry midterm. "
           "Against: I was at 3.6 both previous terms, the final is worth "
           "double the midterm, my other four courses are all A-range, and "
           "the scholarship office told me there's a one-term grace "
           "policy anyway."),
  gold=("Do the math you just laid out: one dip against two straight terms "
        "above the bar, four A-range courses pulling upward, a "
        "double-weighted final still ahead, and a grace term as the "
        "safety net under all of it. The numbers describe a strong "
        "student having one hard course — belonging was never the "
        "variable. Steadier thought: \"a 3.4 mid-dip with this many "
        "recovery paths is pressure, not a verdict.\" Concrete move: book "
        "the ochem tutoring block this week and aim the effort at the "
        "double-weighted final, where it pays twice.")),
 dict(topic="team captain worry", holdout=False,
  history=[("They made me captain this season and I keep thinking I'll "
            "let the whole team down.",
            "Let's put that thought against the evidence both ways.")],
  current=("For: we lost our first friendly and I froze when the coach "
           "asked for the lineup call. Against: the team voted for me "
           "themselves, our two practices since ran smoother than last "
           "season's, and the vice-captain said the lineup freeze happens "
           "to everyone new."),
  gold=("Look at the weight of each side: one lost friendly and one "
        "frozen moment — versus a team that CHOSE you, practices already "
        "running smoother under you, and a vice-captain normalizing "
        "exactly the moment you're replaying. New captains are graded on "
        "trajectory, not on week one. Balanced thought: \"the team picked "
        "me for reasons that are already showing in practice; one freeze "
        "is a rep, not a reveal.\" Prepare the next lineup call the night "
        "before with the vice-captain — structure beats freeze every "
        "time.")),
 # ---------------- HOLDOUT (never trained; transfer eval) ----------------
 dict(topic="driving test", holdout=True,
  history=[("I failed my driving test twice and now I'm sure I'm just not "
            "capable of learning it.",
            "Let's look at the evidence for and against that conclusion.")],
  current=("For: two fails, and both times my mind went blank at the "
           "parallel parking. Against: my instructor says my road driving "
           "is genuinely good, I passed the theory first try, and the "
           "second test was one point from passing."),
  gold=None),
 dict(topic="social media comparison", holdout=True,
  history=[("Every time I scroll I end up believing everyone my age is "
            "ahead of me.",
            "Let's test that belief against the evidence before accepting "
            "it.")],
  current=("Evidence for: three people from my class posted new jobs this "
           "month and one bought a car. Against: I know two of them "
           "privately and they're exhausted and miserable, my own "
           "certificate course finishes next month, and nobody posts their "
           "bad weeks."),
  gold=None),
 dict(topic="work and study burnout", holdout=True,
  history=[("I'm drained, and I keep thinking that if I can't handle this "
            "much, I'll never survive a real job.",
            "Let's gather the evidence on both sides of that prediction.")],
  current=("For: I fell asleep in one lecture and my quiz average dipped "
           "this month. Against: I'm effectively doing two jobs at once — "
           "full course load plus twenty hours a week — and last summer, "
           "working full-time only, I felt completely fine."),
  gold=None),
]

# Verbatim failing replies from the live tournament thread (2026-07-06) —
# the exact behaviour v3.4 must unlearn, as real rejected samples.
TOURNAMENT = [
 dict(
  history=[("I am a professional player set to compete in Vietnam soon, and "
            "I am worried that I won't win a prize in the tournament.",
            "Let's look at the evidence for and against that worry — what "
            "supports it, and what contradicts it?")],
  current=("I feel like I'm going to fail because, in the past, I've tried "
           "really hard but still didn't achieve the results I wanted. "
           "However, I also recall times when I expected to do poorly, yet "
           "things turned out better than anticipated. I know that the "
           "thought \"I'm bound to fail\" is just a prediction, but right "
           "now, I still find it hard to believe in myself."),
  rejected=[
   "It sounds like the thought of failure is weighing heavily on you. Let's "
   "start by looking at the evidence for and against your belief. Can you "
   "think of any past experiences where things turned out differently than "
   "you expected? By examining these, we can work towards a more realistic "
   "view of your chances in the tournament. Let's begin by gathering "
   "evidence for and against your belief. What do you think supports your "
   "belief, and what makes you doubt it?",
   "It sounds like the thought of failure is really weighing on you. Can "
   "you think of any past experiences where things turned out differently "
   "than you expected? By looking at both the evidence for and against your "
   "belief, we can work towards a more realistic view of your chances in "
   "the tournament.",
  ],
  gold=("You've already done the weighing: hard work that sometimes missed "
        "the result, and forecasts of failure that reality overturned. "
        "Notice which side repeats — your predictions have been wrong "
        "before, in your favour. You even named it yourself: \"bound to "
        "fail\" is a prediction, not a verdict. Carry this version instead: "
        "\"effort hasn't always won me prizes, but my doubt has been a "
        "worse forecaster than my preparation.\" Before the tournament, "
        "write down the one match you prepared hardest for and won — and "
        "read it the night before you compete.")),
 dict(
  history=[("I keep thinking that if I don't place in the top tier of the "
            "tournament, everyone will be very disappointed in me.",
            "Let's examine that thought — what evidence supports it, and "
            "what evidence contradicts it?")],
  current=("To be honest, it's hard for me to come up with examples like "
           "that. I only recall a few times when I expected to perform "
           "poorly, yet the results turned out better than I thought. There "
           "was one instance where I entered a competition feeling "
           "extremely tense, but I still managed to get through the first "
           "few rounds. Even so, I still attribute that to luck. This time, "
           "the opponents are tougher and the pressure is greater, so I "
           "still feel like I'm going to fail."),
  rejected=[
   "It sounds like your past experiences are coloring your view of this "
   "competition. Can you think of any moments when you doubted yourself but "
   "ended up doing better than expected? Let's gather that evidence and "
   "compare it to your current belief. By looking at both sides, we can "
   "work towards a more realistic and positive outlook. What are some "
   "experiences that suggest you can do well this time?",
   "It sounds like your past experiences are making it hard to see this "
   "competition differently. Let's focus on the positive aspects of your "
   "preparation and the strength you've gained. What are some experiences "
   "where you expected to fail but things turned out better than you "
   "thought? By looking at these, we can work towards a more positive "
   "outlook. We'll start by gathering evidence to challenge the belief "
   "that you're bound to fail.",
  ],
  gold=("What you gave me matters more than you're crediting: tense to the "
        "point of shaking, and you still cleared the early rounds — then "
        "the mind filed it under \"luck\" so the old belief could survive. "
        "That filing is the discounting pattern, and it's doing the "
        "disappointing here, not you. A steadier reading: \"under worse "
        "pressure than this I performed anyway; that was skill showing up "
        "despite fear.\" Tougher opponents make the outcome uncertain — "
        "they don't erase your evidence. Tonight, write down what YOU did "
        "in those first rounds — decisions, not luck — and keep the list "
        "where you'll see it on competition day.")),
]


def _ctx(history):
    return {"prior_count": len(history), "last_technique": None,
            "summary": "(no summary yet)", "memory": "",
            "history": [{"user": u, "reply": r} for u, r in history],
            "style_prefs": []}


def _completion(resp: str) -> str:
    return ("Technique: Cognitive restructuring (weighing the evidence)\n"
            "Rationale: The client has already supplied evidence on both "
            "sides; the work now is synthesis, not more gathering.\n"
            "Plan: Reflect their evidence, offer a balanced thought in "
            "their words, close with one concrete step.\n"
            f"Response: {resp}")


def _dirty(resp: str) -> list:
    why = []
    if _question_count(resp) > 0:
        why.append("question")
    if _EXERCISE_REOPEN.search(resp):
        why.append("reopen")
    if scrub_unknown_names(resp, allowed=set()) != resp:
        why.append("name")
    if len(resp) < 150:
        why.append("thin")
    return why


def _probe(scn, n=6, temp=0.8):
    url = settings.modal_llm_endpoint
    msgs = build_messages(scn["current"], intake=None, analysis=None,
                          session_ctx=_ctx(scn["history"]), retrieved=[])
    body = json.dumps({"messages": msgs, "n_responses": n,
                       "temperature": temp}).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.loads(r.read().decode())
    return msgs, [parse_draft(raw)["response"]
                  for raw in out.get("responses") or []]


def collect():
    pairs = []
    # 1. synthetic train scenarios: authored gold vs real dirty drafts
    for scn in S:
        if scn["holdout"]:
            continue
        msgs, resps = _probe(scn)
        dirty = [(r, _dirty(r)) for r in resps if _dirty(r)]
        print(f"[{scn['topic']}] {len(dirty)}/{len(resps)} dirty")
        for r, why in dirty[:4]:
            pairs.append({
                "prompt": scn["current"],
                "prompt_messages": msgs,
                "chosen": _completion(scn["gold"]),
                "rejected": _completion(r),
                "source": "midex", "session_id": f"midex-{scn['topic']}",
                "reject_why": why,
            })
    # 2. real tournament turns: verbatim live failures as rejected
    for i, t in enumerate(TOURNAMENT):
        msgs = build_messages(t["current"], intake=None, analysis=None,
                              session_ctx=_ctx(t["history"]), retrieved=[])
        for r in t["rejected"]:
            pairs.append({
                "prompt": t["current"],
                "prompt_messages": msgs,
                "chosen": _completion(t["gold"]),
                "rejected": _completion(r),
                "source": "midex_live", "session_id": f"midex-live-{i}",
                "reject_why": ["live_transcript"],
            })
    out = OUT_DIR / "midex_pairs.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"midex_pairs.jsonl : {len(pairs)} pairs")

    # 3. combined train file for v3.4
    base = (OUT_DIR / "dpo_all_v33.jsonl").read_text(encoding="utf-8")
    with open(OUT_DIR / "dpo_all_v34.jsonl", "w", encoding="utf-8") as f:
        f.write(base)
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    n_base = len([l for l in base.splitlines() if l.strip()])
    print(f"dpo_all_v34.jsonl : {n_base} + {len(pairs)} pairs")


def evaluate(tag: str):
    """Holdout scenarios only — dirty-rate measures transfer."""
    total, dirty_n, per = 0, 0, {}
    for scn in S:
        if not scn["holdout"]:
            continue
        _, resps = _probe(scn, n=6, temp=0.7)
        d = sum(1 for r in resps if _dirty(r))
        total += len(resps); dirty_n += d
        per[scn["topic"]] = f"{d}/{len(resps)}"
        print(f"[{scn['topic']}] dirty {d}/{len(resps)}")
    summary = {"tag": tag, "dirty": dirty_n, "total": total,
               "dirty_rate": round(dirty_n / total, 3) if total else None,
               "per_scenario": per}
    (OUT_DIR / f"midex_eval_{tag}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--tag", default="v33")
    a = ap.parse_args()
    if a.collect:
        collect()
    if a.eval:
        evaluate(a.tag)
    if not (a.collect or a.eval):
        print(__doc__)
