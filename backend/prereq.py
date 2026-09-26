from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from vector_store import retrieve_similar
import os
import json

MODELS = [
    # "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    # "llama-3.1-8b-instant",
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


async def detect_prereq_gap(message: str, topic_name: str, plan,prior_context: str = "",recent_messages: list = None) -> dict:
    """
    Checks whether answering `message` requires prerequisite concepts
    not yet [done] in the plan (or missing from it entirely).
    Returns {"has_gap": bool, "missing_prereqs": [{"name": str, "week_number": int|None}]}
    """
    plan_text = serialize_plan_for_prompt(plan)
    # Make sure recent_messages is always a list
    recent_messages = recent_messages or []

    # Build recent conversation context
    recent_conversation_block = ""

    if recent_messages:
        recent_conversation_block = """
Here is the recent conversation:

""" + "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in recent_messages
        )


    prior_knowledge_block = f"""
The student stated this about their existing knowledge when they created this topic:
"{prior_context}"
Do NOT flag anything the student has explicitly stated they already know as a missing prerequisite.
""" if prior_context.strip() else ""

    prompt = f"""The student is studying "{topic_name}" and just asked:
"{message}"
{prior_knowledge_block}
{recent_conversation_block}

Here is their current study plan (tasks marked [done] are completed, [struggling] means they had trouble, [todo] means not yet covered):

{plan_text}

First, identify the specific concept/algorithm the STUDENT'S QUESTION is about — this must be distinct from any prerequisite concepts you identify below, even if the question mentions prerequisite-adjacent terms.

Example: if the question is "explain Word Ladder using BFS and a Trie", question_topic is "Word Ladder problem" — NOT "BFS" or "Trie", even though those are mentioned in the question text.


Does answering this question require prerequisite concepts that are NOT yet [done] above (or don't appear in the plan at all)?
Only flag genuinely foundational gaps — not the topic itself, and not things reasonably implied by [done] tasks.

Only flag genuinely foundational gaps — not the topic itself, and not things reasonably implied by [done] tasks.

RECENT CONVERSATION RULE:
- Recent conversation is strong evidence of what was just discussed.
- If the student has already received an explanation of a concept in the recent conversation, do NOT flag that concept as an unmet prerequisite.
- If the student asks the same or substantially similar question again, do NOT show a prerequisite warning simply because the related plan task is still [todo].
- A [todo] task means the concept has not been formally completed in the roadmap. It does NOT mean the concept has never been discussed.

CRITICAL — do not flag a task as its own prerequisite: if the question is literally asking to be taught/explained/practiced a specific [todo] task from the plan above (e.g. the message starts with "Help me with this task: ..." or otherwise directly names a task's own wording), do NOT list that task's own subject matter as a "missing prerequisite" — even if you'd phrase it slightly differently or split it into parts. A task's own name is not a prerequisite of itself.
For example, if the task itself is "Implement functional component using JSX", do NOT report "JSX syntax" or "Functional component basics" as missing prerequisites — that IS the task, not something required before it. This applies to ANY task in the plan (first week or later): the specific concept a [todo] task exists to teach is never itself a valid entry in missing_prereqs for a question about that same task.
A genuine prerequisite must be a DIFFERENT, earlier concept the question depends on — typically something from an earlier week that hasn't been marked [done] yet — not a rewording or decomposition of the very thing being asked about.

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