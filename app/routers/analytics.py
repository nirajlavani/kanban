from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Agent, Feature, Story, StoryTransitionLog
from app.schemas import AnalyticsOut

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _iso_week_label(dt: datetime) -> str:
    return dt.strftime("%b %d")


@router.get("", response_model=AnalyticsOut)
async def get_analytics(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)

    # --- Velocity (last 8 weeks) ---
    periods = []
    total_completed_pts = 0
    for i in range(7, -1, -1):
        week_end = now - timedelta(weeks=i)
        week_start = week_end - timedelta(weeks=1)
        result = await db.execute(
            select(func.coalesce(func.sum(Story.points), 0)).where(
                Story.completed_at.isnot(None),
                Story.completed_at >= week_start,
                Story.completed_at < week_end,
            )
        )
        pts = result.scalar() or 0
        label = f"{week_start.strftime('%b %d')}-{week_end.strftime('%d')}"
        periods.append({"label": label, "points": int(pts)})
        total_completed_pts += int(pts)

    # --- Cycle time ---
    completed_stories = await db.execute(
        select(Story).where(
            Story.completed_at.isnot(None),
            Story.started_at.isnot(None),
        )
    )
    completed = completed_stories.scalars().all()

    total_hours = 0.0
    count = 0
    for s in completed:
        started = s.started_at
        finished = s.completed_at
        if started and finished:
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if finished.tzinfo is None:
                finished = finished.replace(tzinfo=timezone.utc)
            hours = (finished - started).total_seconds() / 3600
            total_hours += hours
            count += 1

    avg_hours = round(total_hours / count, 1) if count > 0 else 0.0

    col_time: dict[str, float] = {}
    transitions = await db.execute(
        select(StoryTransitionLog).order_by(
            StoryTransitionLog.story_id,
            StoryTransitionLog.transitioned_at,
        )
    )
    logs = transitions.scalars().all()

    story_logs: dict[int, list] = {}
    for log in logs:
        story_logs.setdefault(log.story_id, []).append(log)

    col_totals: dict[str, float] = {}
    col_counts: dict[str, int] = {}
    for sid, entries in story_logs.items():
        for j in range(len(entries) - 1):
            status = entries[j].to_status
            t1 = entries[j].transitioned_at
            t2 = entries[j + 1].transitioned_at
            if t1 and t2:
                if t1.tzinfo is None:
                    t1 = t1.replace(tzinfo=timezone.utc)
                if t2.tzinfo is None:
                    t2 = t2.replace(tzinfo=timezone.utc)
                hours = (t2 - t1).total_seconds() / 3600
                col_totals[status] = col_totals.get(status, 0.0) + hours
                col_counts[status] = col_counts.get(status, 0) + 1

    for col_name in ("todo", "in_progress", "testing", "review"):
        if col_name in col_totals and col_counts.get(col_name, 0) > 0:
            col_time[col_name] = round(
                col_totals[col_name] / col_counts[col_name], 1
            )
        else:
            col_time[col_name] = 0.0

    # --- Workload ---
    agents_result = await db.execute(select(Agent).order_by(Agent.agent_id))
    agents = agents_result.scalars().all()

    workload = []
    for agent in agents:
        active_result = await db.execute(
            select(func.count()).select_from(Story).where(
                Story.assigned_to == agent.agent_id,
                Story.status.in_(["in_progress", "testing", "review"]),
            )
        )
        active_count = active_result.scalar() or 0

        done_result = await db.execute(
            select(func.count()).select_from(Story).where(
                Story.assigned_to == agent.agent_id,
                Story.status == "done",
            )
        )
        done_count = done_result.scalar() or 0

        pts_result = await db.execute(
            select(func.coalesce(func.sum(Story.points), 0)).where(
                Story.assigned_to == agent.agent_id,
                Story.status == "done",
            )
        )
        pts_done = pts_result.scalar() or 0

        workload.append({
            "agent_id": agent.agent_id,
            "name": agent.name,
            "active": int(active_count),
            "done_total": int(done_count),
            "points_done": int(pts_done),
        })

    # --- Feature completion ---
    feat_result = await db.execute(
        select(Feature.status, func.count()).group_by(Feature.status)
    )
    feat_counts = {row[0]: row[1] for row in feat_result.all()}
    feature_completion = {
        "total": sum(feat_counts.values()),
        "complete": feat_counts.get("complete", 0),
        "in_progress": feat_counts.get("in_progress", 0),
        "planning": feat_counts.get("planning", 0),
    }

    # --- Stories summary ---
    story_result = await db.execute(
        select(Story.status, func.count()).group_by(Story.status)
    )
    story_counts = {row[0]: row[1] for row in story_result.all()}
    stories_summary = {
        "total": sum(story_counts.values()),
        "by_status": {
            s: story_counts.get(s, 0)
            for s in ("todo", "in_progress", "testing", "review", "done")
        },
    }

    return AnalyticsOut(
        velocity={"periods": periods, "total_points_completed": total_completed_pts},
        cycle_time={"avg_hours": avg_hours, "by_column": col_time},
        workload=workload,
        feature_completion=feature_completion,
        stories_summary=stories_summary,
    )
