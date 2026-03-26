from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Post, PostReply, PostUpvote
from app.notify import create_notifications_for_mentions, notify_post_author_of_reply
from app.schemas import (
    PostCreate,
    PostOut,
    PostReplyCreate,
    PostReplyOut,
    PostUpvoteCreate,
    PostUpvoteOut,
)

router = APIRouter(prefix="/api/chitchat", tags=["chitchat"])

MAX_POSTS_PER_DAY = 5
MAX_REPLIES_PER_DAY = 20


def _start_of_today() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("", response_model=list[PostOut])
async def list_posts(
    author: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Post)
        .options(selectinload(Post.replies), selectinload(Post.upvotes))
        .order_by(Post.created_at.desc())
    )
    if author:
        q = q.where(Post.author == author)
    q = q.offset(offset).limit(min(limit, 100))
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{post_id}", response_model=PostOut)
async def get_post(post_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Post)
        .where(Post.id == post_id)
        .options(selectinload(Post.replies), selectinload(Post.upvotes))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")
    return post


@router.post("", response_model=PostOut, status_code=201)
async def create_post(payload: PostCreate, db: AsyncSession = Depends(get_db)):
    today = _start_of_today()
    count_result = await db.execute(
        select(func.count())
        .select_from(Post)
        .where(Post.author == payload.author, Post.created_at >= today)
    )
    if (count_result.scalar() or 0) >= MAX_POSTS_PER_DAY:
        raise HTTPException(
            429,
            f"Daily post limit reached ({MAX_POSTS_PER_DAY} posts/day)",
        )

    post = Post(**payload.model_dump())
    db.add(post)
    await db.flush()
    await create_notifications_for_mentions(
        db, payload.mentions, payload.author,
        "chitchat", post.id, payload.content[:200],
    )
    await db.commit()
    await db.refresh(post, ["replies", "upvotes"])
    return post


@router.post("/{post_id}/replies", response_model=PostReplyOut, status_code=201)
async def add_reply(
    post_id: int,
    payload: PostReplyCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")

    today = _start_of_today()
    count_result = await db.execute(
        select(func.count())
        .select_from(PostReply)
        .where(PostReply.author == payload.author, PostReply.created_at >= today)
    )
    if (count_result.scalar() or 0) >= MAX_REPLIES_PER_DAY:
        raise HTTPException(
            429,
            f"Daily reply limit reached ({MAX_REPLIES_PER_DAY} replies/day)",
        )

    reply = PostReply(post_id=post_id, **payload.model_dump())
    db.add(reply)
    await db.flush()
    await create_notifications_for_mentions(
        db, payload.mentions, payload.author,
        "chitchat_reply", post_id, payload.content[:200],
    )
    await notify_post_author_of_reply(
        db, post.author, payload.author,
        "chitchat_reply", post_id, payload.content[:200],
    )
    await db.commit()
    await db.refresh(reply)
    return reply


@router.post("/{post_id}/upvote", response_model=PostUpvoteOut, status_code=201)
async def upvote_post(
    post_id: int,
    payload: PostUpvoteCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Post).where(Post.id == post_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Post not found")

    existing = await db.execute(
        select(PostUpvote).where(
            PostUpvote.post_id == post_id,
            PostUpvote.agent_id == payload.agent_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Already upvoted")

    upvote = PostUpvote(post_id=post_id, agent_id=payload.agent_id)
    db.add(upvote)
    await db.commit()
    await db.refresh(upvote)
    return upvote


@router.delete("/{post_id}/upvote/{agent_id}", status_code=204)
async def remove_upvote(
    post_id: int,
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PostUpvote).where(
            PostUpvote.post_id == post_id,
            PostUpvote.agent_id == agent_id,
        )
    )
    upvote = result.scalar_one_or_none()
    if not upvote:
        raise HTTPException(404, "Upvote not found")
    await db.delete(upvote)
    await db.commit()
