from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain.schema import HumanMessage, SystemMessage
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
import os
import json

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

from db import SessionLocal, init_db, Topic, Message, Plan, PlanWeek, PlanTask
from vector_store import embed_and_store, retrieve_similar, init_vector_store
from chain import stream_response
from planner import generate_plan, save_plan
from planner import generate_adjusted_plan


app = FastAPI()

# MODELS = [
    #     "models/gemini-2.5-flash-lite",
    #     "models/gemini-2.0-flash-lite",
    #     "models/gemini-2.0-flash",
    # ]

MODELS = [
    "llama-3.3-70b-versatile",  # smarter model for plan generation
    "llama-3.1-8b-instant",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB and vector store on startup
@app.on_event("startup")
async def startup():
    init_db()
    init_vector_store()
    print("StudyBot backend ready.")


# ---------- REQUEST MODELS ----------
class CreateTopicRequest(BaseModel):
    name: str
    goal: str

class ChatRequest(BaseModel):
    topic_id: int
    message: str

class UpdateTaskRequest(BaseModel):
    status: str  # "todo" | "done" | "struggling"

class AdjustPlanRequest(BaseModel):
    reason: str
    cached_weeks: list = None 
    summary: str = None


# ---------- TOPIC ROUTES ----------
@app.get("/topics")
def get_topics():
    """Returns all topics for the home page cards."""
    db = SessionLocal()
    topics = db.query(Topic).order_by(Topic.created_at.desc()).all()
    result = []
    for t in topics:
        plan = db.query(Plan).filter(Plan.topic_id == t.id).first()
        result.append({
            "id": t.id,
            "name": t.name,
            "goal": t.goal,
            "created_at": t.created_at.isoformat(),
            "has_plan": plan is not None
        })
    db.close()
    return result


@app.post("/topics")
def create_topic(req: CreateTopicRequest):
    """Creates a new topic and returns it."""
    db = SessionLocal()
    topic = Topic(name=req.name, goal=req.goal)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    result = {"id": topic.id, "name": topic.name, "goal": topic.goal}
    db.close()
    return result

@app.post("/topics/{topic_id}/plan")
async def create_plan(topic_id: int):
    """Generates a study plan for a topic using Gemini and saves it to DB."""
    db = SessionLocal()
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        db.close()
        raise HTTPException(status_code=404, detail="Topic not found")

    existing_plan = db.query(Plan).filter(Plan.topic_id == topic_id).first()
    if existing_plan:
        db.close()
        raise HTTPException(status_code=400, detail="Plan already exists for this topic")

    plan_data = await generate_plan(
        topic_name=topic.name,
        goal=topic.goal
    )

    saved_plan = await save_plan(
        topic_id=topic_id,
        plan_data=plan_data,
        db=db
    )
    db.close()
    return saved_plan


@app.get("/topics/{topic_id}")
def get_topic(topic_id: int):
    """Returns a single topic with its messages and plan."""
    db = SessionLocal()
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    messages = db.query(Message).filter(
        Message.topic_id == topic_id
    ).order_by(Message.created_at.asc()).all()

    plan = db.query(Plan).filter(Plan.topic_id == topic_id).first()
    plan_data = None
    if plan:
        weeks = []
        for week in plan.weeks:
            weeks.append({
                "id": week.id,
                "week_number": week.week_number,
                "focus_area": week.focus_area,
                "tasks": [
                    {
                        "id": t.id,
                        "description": t.description,
                        "status": t.status
                    }
                    for t in week.tasks
                ]
            })
        plan_data = {
            "id": plan.id,
            "title": plan.title,
            "duration_weeks": plan.duration_weeks,
            "weeks": weeks
        }

    result = {
        "id": topic.id,
        "name": topic.name,
        "goal": topic.goal,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ],
        "plan": plan_data
    }
    db.close()
    return result


# ---------- CHAT ROUTE ----------
@app.post("/chat")
async def chat(req: ChatRequest):
    db = SessionLocal()
    topic = db.query(Topic).filter(Topic.id == req.topic_id).first()
    if not topic:
        db.close()
        raise HTTPException(status_code=404, detail="Topic not found")

    # Get last 6 messages
    recent = db.query(Message).filter(
        Message.topic_id == req.topic_id
    ).order_by(Message.created_at.desc()).limit(6).all()
    recent_messages = [
        {"role": m.role, "content": m.content}
        for m in reversed(recent)
    ]
    # Detect plan change intent
    plan_change = await detect_plan_change_intent(req.message)
    print(f"DEBUG intent: {plan_change}")
    plan_change_detected = None

    if plan_change.get("action") == "adjust_plan":
        plan_change_detected = {
            "reason": req.message
        }
    
    # Retrieve semantically similar past messages from Qdrant
    retrieved_context = retrieve_similar(
        query=req.message,
        topic_id=req.topic_id,
        top_k=3
    )

    # Save user message to SQLite
    user_msg = Message(
        topic_id=req.topic_id,
        role="user",
        content=req.message
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

   # Embed and store user message in Qdrant
    embed_and_store(
        text=req.message,
        topic_id=req.topic_id,
        message_id=user_msg.id,
        role="user"
    )
    # Collect full response for saving after streaming
    full_response = []

    async def generate():
        if plan_change_detected:
            signal = f"__PLAN_CHANGE__{json.dumps(plan_change_detected)}__PLANEND__\n"
            yield signal
        async for token in stream_response(
            user_message=req.message,
            topic_name=topic.name,
            recent_messages=recent_messages,
            retrieved_context=retrieved_context,
            plan_change_detected=plan_change_detected
        ):
            full_response.append(token)
            yield token

        # After streaming completes — save assistant response
        assistant_text = "".join(full_response)
        assistant_msg = Message(
            topic_id=req.topic_id,
            role="assistant",
            content=assistant_text
        )
        db.add(assistant_msg)
        db.commit()
        db.refresh(assistant_msg)

        # Embed and store assistant response in Qdrant too
        embed_and_store(
            text=assistant_text,
            topic_id=req.topic_id,
            message_id=assistant_msg.id,
            role="assistant"
        )
        db.close()

    return StreamingResponse(generate(), media_type="text/plain")


# ---------- PLAN ROUTES ----------
@app.patch("/tasks/{task_id}")
def update_task_status(task_id: int, req: UpdateTaskRequest):
    """Updates a task's status — todo / done / struggling."""
    if req.status not in ["todo", "done", "struggling"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    db = SessionLocal()
    task = db.query(PlanTask).filter(PlanTask.id == task_id).first()
    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = req.status
    db.commit()
    db.close()
    return {"success": True, "task_id": task_id, "status": req.status}


@app.get("/topics/{topic_id}/weakspots")
def get_weakspots(topic_id: int):
    """Returns tasks marked as struggling for this topic."""
    db = SessionLocal()
    plan = db.query(Plan).filter(Plan.topic_id == topic_id).first()
    if not plan:
        db.close()
        return []
    struggling = []
    for week in plan.weeks:
        for task in week.tasks:
            if task.status == "struggling":
                struggling.append({
                    "task_id": task.id,
                    "description": task.description,
                    "week": week.week_number,
                    "focus_area": week.focus_area
                })
    db.close()
    return struggling

@app.get("/topics/{topic_id}/brief")
async def get_session_brief(topic_id: int):
    db = SessionLocal()
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        db.close()
        raise HTTPException(status_code=404, detail="Topic not found")

    # Get last 10 messages
    recent = db.query(Message).filter(
        Message.topic_id == topic_id
    ).order_by(Message.created_at.desc()).limit(10).all()

    # Get struggling tasks
    plan = db.query(Plan).filter(Plan.topic_id == topic_id).first()
    struggling = []
    completed = []
    if plan:
        for week in plan.weeks:
            for task in week.tasks:
                if task.status == "struggling":
                    struggling.append(task.description)
                elif task.status == "done":
                    completed.append(task.description)

    db.close()

    if not recent:
        return {"brief": None}

    # Build context for Gemini
    messages_text = "\n".join([
        f"{m.role}: {m.content[:200]}"
        for m in reversed(recent)
    ])

    struggling_text = "\n".join(struggling) if struggling else "None"
    completed_text = f"{len(completed)} tasks completed so far"



    prompt = f"""Based on this student's recent study history for "{topic.name}", write a brief 3-line pre-session summary.

Recent messages:
{messages_text}

Struggling tasks:
{struggling_text}

Progress: {completed_text}

Write exactly 3 short lines:
1. What they covered last session (1 line)
2. What they're struggling with if anything (1 line, skip if nothing)
3. What to focus on today (1 line)

Be specific, encouraging, and concise. No bullet points, just 3 plain lines."""

    last_error = None
    for model_name in MODELS:
        try:

            llm = ChatGroq(
    model=model_name,
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.3
)
            response = await llm.ainvoke([
                SystemMessage(content="You are a concise study coach writing pre-session briefs."),
                HumanMessage(content=prompt)
            ])
            return {"brief": response.content.strip()}
        except Exception as e:
            last_error = e
            continue
    if len(recent) < 5:
        return {"brief": None, "error": False}

    return {"brief": None, "error": True, "message": "AI overloaded"}

async def detect_plan_change_intent(message: str) -> dict:
    """
    Checks if user wants to change their study plan.
    Returns {action: 'adjust_plan' | 'none', reason: str}
    """


    prompt = f"""The user said: "{message}"

Does the user want to change or adjust their study plan?
Reply with ONLY valid JSON:

If yes: {{"action": "adjust_plan", "reason": "brief reason why"}}
If no: {{"action": "none"}}

Examples that mean YES:
- "I only have 2 weeks left instead of 4"
- "Can we focus more on dynamic programming"
- "I want to add more tree problems"
- "adjust my plan"
- "change my schedule"
- "I'm running out of time"

Examples that mean NO:
- "explain binary search"
- "mark this as done"
- "what is a linked list"
- "Help me with this task: [any task description]"
- Any question or explanation request

If unsure → {{"action": "none"}}"""

    for model_name in MODELS:
        try:
            llm = ChatGroq(
                model=model_name,
                api_key=os.getenv("GROQ_API_KEY"),
                temperature=0
            )
            response = await llm.ainvoke([
                SystemMessage(content="You detect plan change intents. Reply only with JSON."),
                HumanMessage(content=prompt)
            ])
            raw = response.content.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(raw)
        except Exception as e:
            print(f"Plan intent detection failed: {e}")
            continue

    return {"action": "none"}


@app.post("/topics/{topic_id}/adjust-plan")
async def adjust_plan(topic_id: int, req: AdjustPlanRequest):
    """
    Generates new remaining weeks based on current progress and user request.
    Deletes uncompleted tasks and saves new ones.
    """
    db = SessionLocal()
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        db.close()
        raise HTTPException(status_code=404, detail="Topic not found")

    plan = db.query(Plan).filter(Plan.topic_id == topic_id).first()
    if not plan:
        db.close()
        raise HTTPException(status_code=404, detail="No plan found")

    # Categorize tasks
    completed_tasks = []
    struggling_tasks = []
    remaining_tasks = []
    weeks_to_delete = []

    for week in plan.weeks:
        has_any_done = any(t.status == "done" for t in week.tasks)
        
        if has_any_done:
            # Keep this week entirely — student has progress here
            for task in week.tasks:
                if task.status == "done":
                    completed_tasks.append(task.description)
                elif task.status == "struggling":
                    struggling_tasks.append(task.description)
                    remaining_tasks.append(task.description)
                else:
                    remaining_tasks.append(task.description)
            # Don't add to weeks_to_delete — keep it intact
        else:
            # No progress at all — safe to delete and replace
            for task in week.tasks:
                if task.status == "struggling":
                    struggling_tasks.append(task.description)
                    remaining_tasks.append(task.description)
                else:
                    remaining_tasks.append(task.description)
            weeks_to_delete.append(week)

    # user_request = req.get("reason", "User requested plan adjustment")
    user_request = req.reason
    if req.cached_weeks:
        new_plan_data = {
            "weeks": req.cached_weeks,
            "summary": req.summary or "Plan adjusted"
        }
    else:
        # Fall back to generating fresh — no preview was shown
        completed_tasks = []
        struggling_tasks = []
        remaining_tasks = []
        # Generate new plan
        current_week_count = len(plan.weeks) 
    
        new_plan_data = await generate_adjusted_plan(
            topic_name=topic.name,
            goal=topic.goal,
            completed_tasks=completed_tasks,
            struggling_tasks=struggling_tasks,
            remaining_tasks=remaining_tasks,
            user_request=user_request,
            current_week_count=current_week_count
        )

    # Delete uncompleted weeks
    for week in weeks_to_delete:
        for task in week.tasks:
            if task.status != "done":
                db.delete(task)
        db.commit()
        # Only delete week if all tasks deleted
        remaining = db.query(PlanTask).filter(PlanTask.week_id == week.id).all()
        if not remaining:
            db.delete(week)
    db.commit()

    # Find highest existing week number
    existing_weeks = db.query(PlanWeek).filter(PlanWeek.plan_id == plan.id).all()
    start_week = max([w.week_number for w in existing_weeks], default=0) + 1

    # Save new weeks
    saved_weeks = []
    for i, week_data in enumerate(new_plan_data["weeks"]):
        week = PlanWeek(
            plan_id=plan.id,
            week_number=start_week + i,
            focus_area=week_data["focus_area"]
        )
        db.add(week)
        db.commit()
        db.refresh(week)

        tasks = []
        for task_desc in week_data["tasks"]:
            task = PlanTask(
                week_id=week.id,
                description=task_desc,
                status="todo"
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            tasks.append({"id": task.id, "description": task.description, "status": task.status})

        saved_weeks.append({
            "id": week.id,
            "week_number": week.week_number,
            "focus_area": week.focus_area,
            "tasks": tasks
        })

    db.close()
    return {
        "success": True,
        "summary": new_plan_data.get("summary", "Plan adjusted"),
        "new_weeks": saved_weeks
    }

@app.post("/topics/{topic_id}/preview-plan")
async def preview_plan(topic_id: int, req: AdjustPlanRequest):
    """Generates adjusted plan preview WITHOUT saving to DB."""
    db = SessionLocal()
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        db.close()
        raise HTTPException(status_code=404, detail="Topic not found")

    plan = db.query(Plan).filter(Plan.topic_id == topic_id).first()
    if not plan:
        db.close()
        raise HTTPException(status_code=404, detail="No plan found")

    completed_tasks = []
    struggling_tasks = []
    remaining_tasks = []

    for week in plan.weeks:
        for task in week.tasks:
            if task.status == "done":
                completed_tasks.append(task.description)
            elif task.status == "struggling":
                struggling_tasks.append(task.description)
                remaining_tasks.append(task.description)
            else:
                remaining_tasks.append(task.description)

    db.close()

    current_week_count = len(plan.weeks) 
    new_plan_data = await generate_adjusted_plan(
        topic_name=topic.name,
        goal=topic.goal,
        completed_tasks=completed_tasks,
        struggling_tasks=struggling_tasks,
        remaining_tasks=remaining_tasks,
        user_request=req.reason,
        current_week_count=current_week_count

    )

    return {
        "preview": new_plan_data["weeks"],
        "summary": new_plan_data.get("summary", "Plan adjusted"),
        "reason": req.reason
    }
