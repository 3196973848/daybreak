"""桌面提醒模块"""
import threading
from datetime import datetime, time
from typing import Callable

from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Goal, Task
from .models_settings import Settings


def get_today_tasks(db: Session) -> list[dict]:
    """获取今天有任务的所有目标"""
    today = datetime.now().date()
    goals_with_tasks = []

    goals = db.query(Goal).all()
    for goal in goals:
        if not goal.plan:
            continue

        today_tasks = []
        for milestone in goal.plan.milestones:
            for task in milestone.tasks:
                if task.scheduled_date == today and task.status != "done":
                    today_tasks.append(task)

        if today_tasks:
            total_effort = sum(t.effort for t in today_tasks)
            first_task = today_tasks[0]
            goals_with_tasks.append({
                "goal_id": goal.id,
                "goal_title": goal.title,
                "task_count": len(today_tasks),
                "total_effort": total_effort,
                "first_task_title": first_task.title,
                "first_task_effort": first_task.effort,
            })

    return goals_with_tasks


def send_notification(title: str, message: str) -> None:
    """发送系统通知"""
    try:
        # Windows
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=10, threaded=True)
    except ImportError:
        try:
            # macOS
            import subprocess
            subprocess.run([
                "osascript", "-e",
                f'display notification "{message}" with title "{title}"'
            ], check=True)
        except Exception:
            # Linux 或其他系统
            try:
                import subprocess
                subprocess.run([
                    "notify-send", title, message
                ], check=True)
            except Exception:
                print(f"[提醒] {title}: {message}")


def check_and_remind() -> None:
    """检查并发送提醒"""
    db = SessionLocal()
    try:
        # 获取设置
        settings = db.query(Settings).first()
        if not settings or not settings.reminder_enabled:
            return

        # 检查是否到了提醒时间
        now = datetime.now()
        reminder_time = datetime.strptime(settings.reminder_time, "%H:%M").time()
        current_time = now.time()

        # 允许 1 分钟的误差
        reminder_minutes = reminder_time.hour * 60 + reminder_time.minute
        current_minutes = current_time.hour * 60 + current_time.minute
        if abs(reminder_minutes - current_minutes) > 1:
            return

        # 获取今天的任务
        today_tasks = get_today_tasks(db)
        if not today_tasks:
            return

        # 构建提醒消息
        total_tasks = sum(g["task_count"] for g in today_tasks)
        total_effort = sum(g["total_effort"] for g in today_tasks)

        if len(today_tasks) == 1:
            g = today_tasks[0]
            message = f"今天有 {g['task_count']} 个任务，第一个是 {g['first_task_title']}（预计 {g['first_task_effort']:.1f} 小时）"
        else:
            first_goal = today_tasks[0]
            message = f"今天有 {total_tasks} 个任务（{len(today_tasks)} 个目标），总预计 {total_effort:.1f} 小时"

        send_notification("Daybreak 每日提醒", message)

    finally:
        db.close()


def start_reminder_scheduler() -> None:
    """启动提醒调度器"""
    def scheduler_loop():
        while True:
            try:
                check_and_remind()
            except Exception as e:
                print(f"[提醒错误] {e}")
            # 每分钟检查一次
            import time
            time.sleep(60)

    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
