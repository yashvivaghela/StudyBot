# StudyBot
 
A full-stack AI study assistant that builds a personalized study plan, adapts it as you learn, and detects when you're missing the background knowledge needed to understand what you're asking about.

## Stack
 
**Backend:** FastAPI, SQLAlchemy, SQLite, Qdrant (local), LangChain, Groq API, Gemini embeddings
 
**Frontend:** Next.js, Tailwind, ReactMarkdown

## Features
 
- **RAG chat with streaming** — chat responses stream token-by-token, grounded in retrieved past conversation history (Qdrant) and recent messages (SQLite)
- **Prerequisite detection** — before answering a question that depends on foundational concepts, checks whether those concepts have already been studied (via the plan's task status and past chat history), and asks whether to cover the gap first. Points to the relevant week if the prerequisite is already scheduled in the plan
- **Prior-context-aware plan generation** — an optional field at topic creation lets the student describe what they already know or any preferences (e.g. "skip basic syntax," "more practice problems, less theory"); the generated plan skips/compresses accordingly
- **Adaptive roadmap** — preview-then-apply plan adjustment based on a detected change in intent (e.g. "I only have 2 weeks left")
- **Weak spots** — tasks marked "struggling" surface in a dedicated section, styled and clickable to prefill a re-explain request in chat
- **Session brief** — a short pre-session summary of recent progress and struggles, cached for 30 minutes
- **Concept connections** — the assistant references prior related questions when relevant (prompt-driven)
- **Collapsible plan dashboard** — checkboxes for task completion, per-week collapse, progress bar
- **Topic deletion** — full cascade cleanup across SQLite (plan/weeks/tasks/messages) and Qdrant (embedded messages)
- **Error handling** — graceful fallback messaging for LLM rate limits / overload

## Setting up project
 
```
# Clone repo
git clone https://github.com/yashvivaghela/StudyBot.git
cd StudyBot
 
# Backend setup
cd backend
python3 -m venv venv
source venv/bin/activate        # venv\Scripts\activate on Windows
pip install -r requirements.txt
 
# Add your API keys to backend/.env
echo "GROQ_API_KEY=your_key_here" >> .env
echo "GEMINI_API_KEY=your_key_here" >> .env
 
uvicorn main:app --reload --port 8000
 
# Frontend setup (in new terminal)
cd ../frontend
npm install
npm run dev
```
 
Backend runs at `http://localhost:8000`, frontend at `http://localhost:3000`.
On first run, the backend creates `studybot.db` (SQLite) and a local `qdrant_storage/` folder automatically — no external database setup needed.
