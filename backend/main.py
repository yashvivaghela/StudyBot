from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pathlib import Path
from dotenv import load_dotenv
from planner import generate_plan, save_plan
from datetime import datetime
import json

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

from db import SessionLocal, init_db, Topic, Message, Plan, PlanWeek, PlanTask
from vector_store import embed_and_store, retrieve_similar, init_vector_store
from chain import stream_response
from planner import generate_plan, save_plan


app = FastAPI()

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
    """
    Main chat endpoint. Retrieves context, streams Gemini response,
    saves both messages to SQLite and Qdrant.
    """
    db = SessionLocal()
    topic = db.query(Topic).filter(Topic.id == req.topic_id).first()
    if not topic:
        db.close()
        raise HTTPException(status_code=404, detail="Topic not found")

    # Get last 6 messages for short-term context
    recent = db.query(Message).filter(
        Message.topic_id == req.topic_id
    ).order_by(Message.created_at.desc()).limit(6).all()
    recent_messages = [
        {"role": m.role, "content": m.content}
        for m in reversed(recent)
    ]

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
        async for token in stream_response(
            user_message=req.message,
            topic_name=topic.name,
            recent_messages=recent_messages,
            retrieved_context=retrieved_context
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