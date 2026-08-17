from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    goals: Mapped[list["Goal"]] = relationship(back_populates="owner")


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    owner: Mapped[User | None] = relationship(back_populates="goals")
    plan: Mapped["Plan"] = relationship(
        back_populates="goal", uselist=False, cascade="all, delete-orphan"
    )


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id"))
    strategy: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    goal: Mapped[Goal] = relationship(back_populates="plan")
    milestones: Mapped[list["Milestone"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    order: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="todo")
    plan: Mapped[Plan] = relationship(back_populates="milestones")
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="milestone", cascade="all, delete-orphan"
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    milestone_id: Mapped[int] = mapped_column(ForeignKey("milestones.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(String(20), default="learn")
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effort: Mapped[float] = mapped_column(Float, default=1.0)
    order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="todo")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    milestone: Mapped[Milestone] = relationship(back_populates="tasks")
    verifications: Mapped[list["VerificationRecord"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    learning_session: Mapped["LearningSession"] = relationship(
        back_populates="task", uselist=False, cascade="all, delete-orphan"
    )


class LearningSession(Base):
    __tablename__ = "learning_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), unique=True)
    stage: Mapped[str] = mapped_column(String(20), default="diagnose")
    session_summary: Mapped[str] = mapped_column(Text, default="")
    covered_points: Mapped[str] = mapped_column(Text, default="[]")
    weak_points: Mapped[str] = mapped_column(Text, default="[]")
    ready_for_verification: Mapped[bool] = mapped_column(Boolean, default=False)
    estimated_hours_snapshot: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    task: Mapped["Task"] = relationship(back_populates="learning_session")
    turns: Mapped[list["LearningTurn"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="LearningTurn.id",
    )


class LearningTurn(Base):
    __tablename__ = "learning_turns"
    __table_args__ = (
        UniqueConstraint("session_id", "client_turn_id", name="uq_learning_turn_client"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("learning_sessions.id"))
    client_turn_id: Mapped[str] = mapped_column(String(64))
    user_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    assistant_message: Mapped[str] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    session: Mapped[LearningSession] = relationship(back_populates="turns")


class VerificationRecord(Base):
    __tablename__ = "verification_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    mode: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text, default="")
    submission: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(Text, default="")
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    task: Mapped[Task] = relationship(back_populates="verifications")
