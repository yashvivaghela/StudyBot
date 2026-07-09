from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage
from dotenv import load_dotenv
from pathlib import Path
import os
import json

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.3  # lower than chat — we want consistent structured output, not creativity
)

MODELS = [
    "models/gemini-2.5-flash-lite",
    "models/gemini-2.0-flash-lite",
    "models/gemini-2.0-flash",
]

async def generate_plan(topic_name: str, goal: str) -> dict:
    last_error = None
    for model_name in MODELS:
        try:
            llm = ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=os.getenv("GEMINI_API_KEY"),
                temperature=0.3
            )
            system_message = SystemMessage(content="""You are a study plan generator.
Your job is to create structured, realistic study plans based on the student's goal.
You must ALWAYS respond with valid JSON only — no explanation, no markdown, no backticks.
Just raw JSON.""")

            human_message = HumanMessage(content=f"""
Create a study plan for the following:

Topic: {topic_name}
Goal: {goal}

Respond with this exact JSON structure:
{{
    "title": "plan title here",
    "duration_weeks": <number>,
    "weeks": [
        {{
            "week_number": 1,
            "focus_area": "focus area name",
            "tasks": [
                "task description 1",
                "task description 2",
                "task description 3"
            ]
        }}
    ]
}}

Rules:
- duration_weeks should match the number of weeks in the array
- Each week should have 3-5 specific, actionable tasks
- Tasks should be concrete not vague
- Return ONLY the JSON, nothing else
""")

            response = await llm.ainvoke([system_message, human_message])
            raw = response.content.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            return json.loads(raw)

        except Exception as e:
            print(f"Model {model_name} failed: {e}, trying next...")
            last_error = e
            continue

    raise Exception(f"All models failed. Last error: {last_error}")


async def save_plan(topic_id: int, plan_data: dict, db) -> dict:
    """
    Takes parsed plan data and saves it as real DB rows:
    Plan → PlanWeeks → PlanTasks
    Returns the saved plan as a dict for the API response.
    """
    from db import Plan, PlanWeek, PlanTask

    # Create the top-level plan
    plan = Plan(
        topic_id=topic_id,
        title=plan_data["title"],
        duration_weeks=plan_data["duration_weeks"]
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    weeks_result = []

    for week_data in plan_data["weeks"]:
        # Create each week
        week = PlanWeek(
            plan_id=plan.id,
            week_number=week_data["week_number"],
            focus_area=week_data["focus_area"]
        )
        db.add(week)
        db.commit()
        db.refresh(week)

        tasks_result = []

        for task_desc in week_data["tasks"]:
            # Create each task
            task = PlanTask(
                week_id=week.id,
                description=task_desc,
                status="todo"
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            tasks_result.append({
                "id": task.id,
                "description": task.description,
                "status": task.status
            })

        weeks_result.append({
            "id": week.id,
            "week_number": week.week_number,
            "focus_area": week.focus_area,
            "tasks": tasks_result
        })

    return {
        "id": plan.id,
        "title": plan.title,
        "duration_weeks": plan.duration_weeks,
        "weeks": weeks_result
    }