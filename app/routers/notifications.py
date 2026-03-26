from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Notification
from app.schemas import NotificationCountOut, NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    agent_id: str,
    unread: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Notification)
        .where(Notification.agent_id == agent_id)
        .order_by(Notification.created_at.desc())
    )
    if unread is True:
        q = q.where(Notification.is_read == 0)
    elif unread is False:
        q = q.where(Notification.is_read == 1)
    q = q.offset(offset).limit(min(limit, 200))
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/count", response_model=list[NotificationCountOut])
async def notification_counts(
    db: AsyncSession = Depends(get_db),
):
    """Unread notification counts for all agents (useful for UI badges)."""
    result = await db.execute(
        select(Notification.agent_id, func.count().label("unread"))
        .where(Notification.is_read == 0)
        .group_by(Notification.agent_id)
    )
    return [
        NotificationCountOut(agent_id=row.agent_id, unread=row.unread)
        for row in result.all()
    ]


@router.patch("/{notif_id}/read", response_model=NotificationOut)
async def mark_read(
    notif_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(Notification.id == notif_id)
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(404, "Notification not found")
    notif.is_read = 1
    await db.commit()
    await db.refresh(notif)
    return notif


@router.patch("/read-all", status_code=200)
async def mark_all_read(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Notification)
        .where(Notification.agent_id == agent_id, Notification.is_read == 0)
        .values(is_read=1)
    )
    await db.commit()
    return {"status": "ok", "agent_id": agent_id}
