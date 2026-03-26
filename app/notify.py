from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification


async def create_notifications_for_mentions(
    db: AsyncSession,
    mentions_str: str | None,
    author: str,
    source_type: str,
    source_id: int,
    preview: str,
) -> None:
    """Parse a comma-separated mentions string and create a Notification row
    for each mentioned agent (excluding the author themselves)."""
    if not mentions_str:
        return
    agents = {m.strip().lower() for m in mentions_str.split(",") if m.strip()}
    agents.discard(author)
    if not agents:
        return
    truncated = preview[:500] if len(preview) > 500 else preview
    for agent_id in agents:
        db.add(Notification(
            agent_id=agent_id,
            source_type=source_type,
            source_id=source_id,
            author=author,
            preview=truncated,
        ))
    await db.flush()


async def notify_post_author_of_reply(
    db: AsyncSession,
    post_author: str,
    reply_author: str,
    source_type: str,
    source_id: int,
    preview: str,
) -> None:
    """Notify the original post author when someone replies to their post,
    unless the reply author IS the post author."""
    if post_author == reply_author:
        return
    truncated = preview[:500] if len(preview) > 500 else preview
    db.add(Notification(
        agent_id=post_author,
        source_type=source_type,
        source_id=source_id,
        author=reply_author,
        preview=truncated,
    ))
    await db.flush()
