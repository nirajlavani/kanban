from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Comment, Story
from app.schemas import (
    CommentCreate,
    CommentOut,
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
        from app.models import Feature
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

    now = datetime.now(timezone.utc)
    story.status = payload.status

    if payload.status == "in_progress" and not story.started_at:
        story.started_at = now
    elif payload.status == "done":
        story.completed_at = now

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
