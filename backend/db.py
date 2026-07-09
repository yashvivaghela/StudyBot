from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

# This creates a local file-based database: studybot.db
engine = create_engine("sqlite:///studybot.db", echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)          # e.g. "LeetCode Prep"
    goal = Column(Text, nullable=True)               # original user description
    created_at = Column(DateTime, default=datetime.utcnow)

    messages = relationship("Message", back_populates="topic")
    plans = relationship("Plan", back_populates="topic")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    role = Column(String, nullable=False)            # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    topic = relationship("Topic", back_populates="messages")


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    title = Column(String, nullable=False)
    duration_weeks = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    topic = relationship("Topic", back_populates="plans")
    weeks = relationship("PlanWeek", back_populates="plan")


class PlanWeek(Base):
    __tablename__ = "plan_weeks"

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    week_number = Column(Integer, nullable=False)
    focus_area = Column(String, nullable=False)      # e.g. "Arrays & Two Pointers"

    plan = relationship("Plan", back_populates="weeks")
    tasks = relationship("PlanTask", back_populates="week")


class PlanTask(Base):
    __tablename__ = "plan_tasks"

    id = Column(Integer, primary_key=True)
    week_id = Column(Integer, ForeignKey("plan_weeks.id"), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="todo")           # "todo" | "done" | "struggling"

    week = relationship("PlanWeek", back_populates="tasks")


def init_db():
    """Creates all tables if they don't already exist."""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database initialized: studybot.db created with all tables.")