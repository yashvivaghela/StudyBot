from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# llm = ChatGoogleGenerativeAI(
#     model="gemini-2.5-flash-lite",
#     google_api_key=os.getenv("GEMINI_API_KEY"),
#     streaming=True,
#     temperature=0.7
# )
def get_llm(model_name: str):
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=os.getenv("GEMINI_API_KEY"),
        disable_streaming=False,
        temperature=0.7
    )


def build_prompt(
    user_message: str,
    topic_name: str,
    recent_messages: list,
    retrieved_context: list,
) -> list:
    """
    Builds the full prompt we send to Gemini.
    Combines: system instructions + retrieved past context + recent chat history + new message.
    """

    # --- System instruction ---
    system_content = f"""You are StudyBot, a personalized study assistant for the topic: "{topic_name}".

You have access to the student's past study history for this topic.
Use it to:
- Avoid re-explaining things they already understand
- Acknowledge if they've struggled with something before
- Tailor your explanation to their level
- Be encouraging but honest

FORMATTING RULES — always follow these:
# - If retrieved past context contains related concepts the student has asked about before, explicitly mention the connection — e.g. "This is similar to what you asked about two pointers last week"
- Use headers (##) to break up long responses into clear sections
- Use bullet points or numbered lists for steps, examples, or multiple points
- Use **bold** for key terms and important concepts
- Use code blocks for any code, algorithms, or pseudocode
- Keep paragraphs short — max 2-3 sentences each
- Add a blank line between sections for breathing room
- For explanations: start with a 1-sentence summary, then go deeper
- Never write walls of text — if a response is long, structure it with headers

Keep responses clear, focused and well structured. Use examples where helpful."""

    # --- Retrieved past context (from Qdrant) ---
    context_block = ""
    if retrieved_context:
        context_block = "\n\nRelevant past context from this student's history:\n"
        for item in retrieved_context:
            role_label = "Student" if item["role"] == "user" else "You (StudyBot)"
            context_block += f"- {role_label} previously said: \"{item['text']}\" (similarity: {item['score']})\n"

    # --- Recent messages (from SQLite, last N messages) ---
    recent_block = ""
    if recent_messages:
        recent_block = "\n\nRecent conversation:\n"
        for msg in recent_messages:
            role_label = "Student" if msg["role"] == "user" else "StudyBot"
            recent_block += f"{role_label}: {msg['content']}\n"

    full_system = system_content + context_block + recent_block

    return [
        SystemMessage(content=full_system),
        HumanMessage(content=user_message)
    ]


MODELS = [
    "models/gemini-2.5-flash-lite",
    "models/gemini-2.0-flash-lite",
    "models/gemini-2.0-flash",
]

async def stream_response(
    user_message: str,
    topic_name: str,
    recent_messages: list,
    retrieved_context: list,
):
    messages = build_prompt(
        user_message=user_message,
        topic_name=topic_name,
        recent_messages=recent_messages,
        retrieved_context=retrieved_context,
    )

    last_error = None
    for model_name in MODELS:
        try:
            llm = get_llm(model_name)
            async for chunk in llm.astream(messages):
                if chunk.content:
                    yield chunk.content
            return  # success — stop trying other models
        except Exception as e:
            print(f"Model {model_name} failed: {e}, trying next...")
            last_error = e
            continue

    raise Exception(f"All models failed. Last error: {last_error}")