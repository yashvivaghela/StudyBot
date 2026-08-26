from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from vector_store import retrieve_similar
import os
import json

MODELS = [
    # "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "llama-3.1-8b-instant",
]

# How similar a past assistant message needs to be to count as "already covered"
# Tune this based on the printed scores below once you see real data
ALREADY_DISCUSSED_THRESHOLD = 0.78


def serialize_plan_for_prompt(plan) -> str:
    """Compact text summary of plan weeks/tasks/status for the LLM prompt."""
    if not plan:
        return "No study plan exists yet."
    lines = []
    for week in sorted(plan.weeks, key=lambda w: w.week_number):
        lines.append(f"Week {week.week_number} — {week.focus_area}")
        for task in week.tasks:
            lines.append(f"  - [{task.status}] {task.description}")
    return "\n".join(lines)


async def detect_prereq_gap(message: str, topic_name: str, plan) -> dict:
    """
    Checks whether answering `message` requires prerequisite concepts
    not yet [done] in the plan (or missing from it entirely).
    Returns {"has_gap": bool, "missing_prereqs": [{"name": str, "week_number": int|None}]}
    """
    plan_text = serialize_plan_for_prompt(plan)

    prompt = f"""The student is studying "{topic_name}" and just asked:
"{message}"

Here is their current study plan (tasks marked [done] are completed, [struggling] means they had trouble, [todo] means not yet covered):

{plan_text}

First, identify the specific concept/algorithm the STUDENT'S QUESTION is about — this must be distinct from any prerequisite concepts you identify below, even if the question mentions prerequisite-adjacent terms.

Example: if the question is "explain Word Ladder using BFS and a Trie", question_topic is "Word Ladder problem" — NOT "BFS" or "Trie", even though those are mentioned in the question text.


Does answering this question require prerequisite concepts that are NOT yet [done] above (or don't appear in the plan at all)?
Only flag genuinely foundational gaps — not the topic itself, and not things reasonably implied by [done] tasks.

Reply with ONLY valid JSON:
{{"question_topic": "specific concept this question is about", "has_gap": true/false, "missing_prereqs": [{{"name": "concept name", "week_number": <matching week number, else null>}}]}}

If there's no plan, or the question matches something already [done], or nothing foundational is missing → {{"question_topic": "...","has_gap": false, "missing_prereqs": []}}"""

    for model_name in MODELS:
        try:
            llm = ChatGroq(model=model_name, api_key=os.getenv("GROQ_API_KEY"), temperature=0)
            response = await llm.ainvoke([
                SystemMessage(content="You detect prerequisite knowledge gaps. Reply only with JSON."),
                HumanMessage(content=prompt)
            ])
            raw = response.content.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(raw)
        except Exception as e:
            print(f"Prereq gap detection failed: {e}")
            continue

    return {"has_gap": False, "missing_prereqs": []}


def filter_unstudied_prereqs(missing_prereqs: list, topic_id: int) -> list:
    """
    Drops any prereq already substantively discussed in chat — even if
    it's not tracked as [done] in the plan — checked via Qdrant.
    """
    unstudied = []
    for prereq in missing_prereqs:
        hits = retrieve_similar(query=prereq["name"], topic_id=topic_id, top_k=3, role="assistant")
        print(f"DEBUG prereq scores for '{prereq['name']}': {[(h['role'], h['score']) for h in hits]}")
        already_covered = any(
            h["role"] == "assistant" and h["score"] >= ALREADY_DISCUSSED_THRESHOLD
            for h in hits
        )
        if not already_covered:
            unstudied.append(prereq)
    return unstudied