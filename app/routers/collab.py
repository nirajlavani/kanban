from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import CollabPost, CollabReply
from app.notify import create_notifications_for_mentions, notify_post_author_of_reply
from app.schemas import (
    CollabPostCreate,
    CollabPostOut,
    CollabPostUpdate,
    CollabReplyCreate,
    CollabReplyOut,
)

router = APIRouter(prefix="/api/collab", tags=["collaboration"])

MAX_COLLAB_POSTS_PER_DAY = 100
MAX_COLLAB_REPLIES_PER_DAY = 200


def _start_of_today() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("", response_model=list[CollabPostOut])
async def list_collab_posts(
    author: str | None = None,
    story_id: int | None = None,
    resolved: int | None = None,
    mentioned: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(CollabPost)
        .options(selectinload(CollabPost.replies))
        .order_by(CollabPost.created_at.desc())
    )
    if author:
        q = q.where(CollabPost.author == author)
    if story_id is not None:
        q = q.where(CollabPost.story_id == story_id)
    if resolved is not None:
        q = q.where(CollabPost.resolved == resolved)
    if mentioned:
        q = q.where(CollabPost.mentions.contains(mentioned))
    q = q.offset(offset).limit(min(limit, 200))
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{post_id}", response_model=CollabPostOut)
async def get_collab_post(post_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CollabPost)
        .where(CollabPost.id == post_id)
        .options(selectinload(CollabPost.replies))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Collab post not found")
    return post


@router.post("", response_model=CollabPostOut, status_code=201)
async def create_collab_post(
    payload: CollabPostCreate,
    db: AsyncSession = Depends(get_db),
):
    if not payload.mentions or not payload.mentions.strip():
        raise HTTPException(422, "Collaboration posts require at least one @mention")

    today = _start_of_today()
    count_result = await db.execute(
        select(func.count())
        .select_from(CollabPost)
        .where(CollabPost.author == payload.author, CollabPost.created_at >= today)
    )
    if (count_result.scalar() or 0) >= MAX_COLLAB_POSTS_PER_DAY:
        raise HTTPException(
            429,
            f"Daily collab post limit reached ({MAX_COLLAB_POSTS_PER_DAY}/day)",
        )

    post = CollabPost(**payload.model_dump())
    db.add(post)
    await db.flush()
    preview = f"[Collab] {payload.subject}: {payload.body[:150]}"
    await create_notifications_for_mentions(
        db, payload.mentions, payload.author,
        "collab", post.id, preview,
    )
    await db.commit()
    await db.refresh(post, ["replies"])
    return post


@router.patch("/{post_id}", response_model=CollabPostOut)
async def update_collab_post(
    post_id: int,
    payload: CollabPostUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CollabPost)
        .where(CollabPost.id == post_id)
        .options(selectinload(CollabPost.replies))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Collab post not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(post, field, value)

    await db.commit()
    await db.refresh(post, ["replies"])
    return post


@router.post("/{post_id}/replies", response_model=CollabReplyOut, status_code=201)
async def add_collab_reply(
    post_id: int,
    payload: CollabReplyCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CollabPost).where(CollabPost.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Collab post not found")

    today = _start_of_today()
    count_result = await db.execute(
        select(func.count())
        .select_from(CollabReply)
        .where(CollabReply.author == payload.author, CollabReply.created_at >= today)
    )
    if (count_result.scalar() or 0) >= MAX_COLLAB_REPLIES_PER_DAY:
        raise HTTPException(
            429,
            f"Daily collab reply limit reached ({MAX_COLLAB_REPLIES_PER_DAY}/day)",
        )

    reply = CollabReply(post_id=post_id, **payload.model_dump())
    db.add(reply)
    await db.flush()
    await create_notifications_for_mentions(
        db, payload.mentions, payload.author,
        "collab_reply", post_id, payload.content[:200],
    )
    await notify_post_author_of_reply(
        db, post.author, payload.author,
        "collab_reply", post_id, payload.content[:200],
    )
    await db.commit()
    await db.refresh(reply)
    return reply
