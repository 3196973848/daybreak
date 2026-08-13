from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    plan: Mapped["Plan"] = relationship(back_populates="goal", uselist=False)


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
