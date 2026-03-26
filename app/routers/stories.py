from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.github import fetch_pr_status, parse_pr_url
from app.models import Comment, Feature, Story, StoryTransitionLog
from app.schemas import (
    CommentCreate,
    CommentOut,
    DepStoryOut,
    StoryCreate,
    StoryDetail,
    StoryMove,
    StoryOut,
    StoryUpdate,
)

router = APIRouter(prefix="/api/stories", tags=["stories"])

VALID_STATUSES = {"todo", "in_progress", "testing", "review", "done"}

ALLOWED_TRANSITIONS: dict[str, dict[str, str]] = {
    "todo->in_progress": "assigned",
    "in_progress->testing": "assigned",
    "testing->review": "assigned",
    "review->done": "alfred",
    "review->in_progress": "alfred",
}


def _check_transition(story: Story, new_status: str, agent_id: str) -> None:
    if agent_id == "human":
        return

    key = f"{story.status}->{new_status}"
    rule = ALLOWED_TRANSITIONS.get(key)

    if rule is None:
        raise HTTPException(
            400,
            f"Invalid transition: {story.status} -> {new_status}",
        )

    if rule == "alfred" and agent_id != "alfred":
        raise HTTPException(
            403,
            f"Only alfred can move stories from {story.status} to {new_status}",
        )

    if rule == "assigned" and agent_id != story.assigned_to:
        raise HTTPException(
            403,
            f"Only the assigned agent ({story.assigned_to}) can perform this transition",
        )


async def _check_dependencies(
    db: AsyncSession, story: Story, new_status: str, agent_id: str,
) -> None:
    if agent_id == "human":
        return
    if new_status != "in_progress":
        return
    if not story.dependencies or not story.dependencies.strip():
        return

    dep_ids: list[int] = []
    for raw in story.dependencies.split(","):
        raw = raw.strip()
        if raw.isdigit():
            dep_ids.append(int(raw))

    if not dep_ids:
        return

    result = await db.execute(
        select(Story.id, Story.status).where(Story.id.in_(dep_ids))
    )
    deps = result.all()
    blockers = [d.id for d in deps if d.status != "done"]
    if blockers:
        raise HTTPException(
            400,
            f"Blocked by unfinished dependencies: story IDs {blockers}",
        )


def _check_pr_status(story: Story, new_status: str, agent_id: str) -> None:
    if agent_id == "human":
        return
    if new_status != "done" or story.status != "review":
        return
    if not story.pr_url:
        return
    if story.pr_status != "merged":
        raise HTTPException(
            400,
            f"PR must be merged before marking story as done. "
            f"Current status: {story.pr_status or 'unknown'}. "
            f"Run POST /api/stories/{story.id}/pr-sync to refresh.",
        )


async def _maybe_update_feature_status(db: AsyncSession, feature_id: int) -> None:
    result = await db.execute(select(Feature).where(Feature.id == feature_id))
    feature = result.scalar_one_or_none()
    if not feature:
        return

    counts = await db.execute(
        select(Story.status, func.count()).where(
            Story.feature_id == feature_id,
        ).group_by(Story.status)
    )
    status_counts: dict[str, int] = {row[0]: row[1] for row in counts.all()}
    total = sum(status_counts.values())
    if total == 0:
        return

    done_count = status_counts.get("done", 0)
    todo_count = status_counts.get("todo", 0)

    if done_count == total and feature.status != "complete":
        feature.status = "complete"
        if not feature.completed_at:
            feature.completed_at = datetime.now(timezone.utc)
    elif feature.status == "planning" and todo_count < total:
        feature.status = "in_progress"


@router.get("", response_model=list[StoryOut])
async def list_stories(
    status: str | None = None,
    assigned_to: str | None = None,
    feature_id: int | None = None,
    project_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Story)
    if status:
        q = q.where(Story.status == status)
    if assigned_to:
        q = q.where(Story.assigned_to == assigned_to)
    if feature_id:
        q = q.where(Story.feature_id == feature_id)
    if project_id:
        q = q.join(Feature).where(Feature.project_id == project_id)
    q = q.order_by(Story.created_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{story_id}", response_model=StoryDetail)
async def get_story(story_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Story)
        .where(Story.id == story_id)
        .options(selectinload(Story.comments))
    )
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(404, "Story not found")
    return story


@router.get("/{story_id}/deps", response_model=list[DepStoryOut])
async def get_story_deps(story_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Story).where(Story.id == story_id))
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(404, "Story not found")
    if not story.dependencies or not story.dependencies.strip():
        return []

    dep_ids: list[int] = []
    for raw in story.dependencies.split(","):
        raw = raw.strip()
        if raw.isdigit():
            dep_ids.append(int(raw))
    if not dep_ids:
        return []

    deps_result = await db.execute(select(Story).where(Story.id.in_(dep_ids)))
    return deps_result.scalars().all()


@router.post("", response_model=StoryOut, status_code=201)
async def create_story(payload: StoryCreate, db: AsyncSession = Depends(get_db)):
    if payload.points not in (1, 2, 3, 5, 8):
        raise HTTPException(400, "Points must be 1, 2, 3, 5, or 8")
    story = Story(**payload.model_dump())
    db.add(story)
    await db.commit()
    await db.refresh(story)
    return story


@router.patch("/{story_id}", response_model=StoryOut)
async def update_story(
    story_id: int,
    payload: StoryUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Story).where(Story.id == story_id))
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(404, "Story not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(story, key, value)

    await db.commit()
    await db.refresh(story)
    return story


@router.patch("/{story_id}/move", response_model=StoryOut)
async def move_story(
    story_id: int,
    payload: StoryMove,
    db: AsyncSession = Depends(get_db),
):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status. Must be one of: {VALID_STATUSES}")

    result = await db.execute(select(Story).where(Story.id == story_id))
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(404, "Story not found")

    _check_transition(story, payload.status, payload.agent_id)
    await _check_dependencies(db, story, payload.status, payload.agent_id)
    _check_pr_status(story, payload.status, payload.agent_id)

    old_status = story.status
    now = datetime.now(timezone.utc)
    story.status = payload.status

    if payload.status == "in_progress" and not story.started_at:
        story.started_at = now
    elif payload.status == "done":
        story.completed_at = now

    db.add(StoryTransitionLog(
        story_id=story.id,
        from_status=old_status,
        to_status=payload.status,
        agent_id=payload.agent_id,
        transitioned_at=now,
    ))

    await db.flush()
    await _maybe_update_feature_status(db, story.feature_id)

    await db.commit()
    await db.refresh(story)
    return story


@router.post("/{story_id}/pr-sync", response_model=StoryOut)
async def sync_pr_status(story_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Story).where(Story.id == story_id))
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(404, "Story not found")
    if not story.pr_url:
        raise HTTPException(400, "Story has no pr_url set")

    parsed = parse_pr_url(story.pr_url)
    if not parsed:
        raise HTTPException(400, f"Could not parse GitHub PR URL: {story.pr_url}")

    owner, repo, pr_number = parsed
    try:
        status_data = await fetch_pr_status(owner, repo, pr_number)
    except Exception as exc:
        raise HTTPException(502, f"GitHub API error: {exc}") from exc

    story.pr_status = status_data["pr_status"]
    story.pr_checks = status_data["pr_checks"]
    story.pr_review_state = status_data["pr_review_state"]

    await db.commit()
    await db.refresh(story)
    return story


@router.post("/{story_id}/comments", response_model=CommentOut, status_code=201)
async def add_comment(
    story_id: int,
    payload: CommentCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Story).where(Story.id == story_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Story not found")

    comment = Comment(story_id=story_id, **payload.model_dump())
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment
