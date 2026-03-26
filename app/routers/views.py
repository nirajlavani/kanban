from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import TEMPLATES_DIR
from app.database import get_db
from app.models import Agent, CollabPost, Comment, Feature, Guide, Notification, Post, PostReply, Project, Story, StoryTransitionLog

router = APIRouter(tags=["views"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

COLUMNS = ["todo", "in_progress", "testing", "review", "done"]


@router.get("/")
async def board_view(
    request: Request,
    project_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    pid: int | None = None
    if project_id and project_id.strip():
        try:
            pid = int(project_id)
        except ValueError:
            pid = None

    q = select(Story).options(
        selectinload(Story.feature).selectinload(Feature.project),
        selectinload(Story.comments),
    )
    if pid:
        q = q.join(Feature).where(Feature.project_id == pid)
    q = q.order_by(Story.created_at.asc())
    result = await db.execute(q)
    all_stories = result.scalars().all()

    grouped: dict[str, list] = {col: [] for col in COLUMNS}
    for story in all_stories:
        if story.status in grouped:
            grouped[story.status].append(story)

    columns = [{"status": col, "stories": grouped[col]} for col in COLUMNS]

    projects_result = await db.execute(select(Project).order_by(Project.name))
    projects = projects_result.scalars().all()

    return templates.TemplateResponse(request, "board.html", {
        "columns": columns,
        "projects": projects,
        "selected_project": pid,
        "active": "board",
    })


@router.get("/projects")
async def projects_view(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Project).options(selectinload(Project.features)).order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()

    projects_data = []
    for p in projects:
        story_count = 0
        for f in p.features:
            count_result = await db.execute(
                select(func.count()).select_from(Story).where(Story.feature_id == f.id)
            )
            story_count += count_result.scalar() or 0
        projects_data.append({
            "id": p.id,
            "name": p.name,
            "slug": p.slug,
            "description": p.description,
            "feature_count": len(p.features),
            "story_count": story_count,
        })

    return templates.TemplateResponse(request, "projects.html", {
        "projects": projects_data,
        "active": "projects",
    })


@router.get("/projects/{project_id}")
async def project_detail_view(
    request: Request,
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.features))
    )
    project = result.scalar_one_or_none()
    if not project:
        return templates.TemplateResponse(request, "projects.html", {
            "projects": [],
            "active": "projects",
        })

    features_data = []
    for f in project.features:
        count_result = await db.execute(
            select(func.count()).select_from(Story).where(Story.feature_id == f.id)
        )
        done_result = await db.execute(
            select(func.count()).select_from(Story).where(Story.feature_id == f.id, Story.status == "done")
        )
        features_data.append({
            "id": f.id,
            "title": f.title,
            "description": f.description,
            "status": f.status,
            "story_count": count_result.scalar() or 0,
            "done_count": done_result.scalar() or 0,
        })

    return templates.TemplateResponse(request, "project_detail.html", {
        "project": project,
        "features": features_data,
        "active": "projects",
    })


@router.get("/agents")
async def agents_view(request: Request, db: AsyncSession = Depends(get_db)):
    agents_result = await db.execute(select(Agent).order_by(Agent.agent_id))
    agents = agents_result.scalars().all()

    agents_data = []
    for agent in agents:
        stories_result = await db.execute(
            select(Story)
            .where(Story.assigned_to == agent.agent_id)
            .where(Story.status != "done")
            .order_by(Story.created_at.desc())
        )
        stories = stories_result.scalars().all()

        post_count_result = await db.execute(
            select(func.count()).select_from(Post).where(Post.author == agent.agent_id)
        )
        post_count = post_count_result.scalar() or 0

        reply_count_result = await db.execute(
            select(func.count()).select_from(PostReply).where(PostReply.author == agent.agent_id)
        )
        reply_count = reply_count_result.scalar() or 0

        agents_data.append({
            "agent_id": agent.agent_id,
            "name": agent.name,
            "role": agent.role,
            "specialty": agent.specialty,
            "llm_model": agent.llm_model,
            "active_stories": len(stories),
            "stories": stories,
            "post_count": post_count,
            "reply_count": reply_count,
        })

    return templates.TemplateResponse(request, "agents.html", {
        "agents": agents_data,
        "active": "agents",
    })


@router.get("/features")
async def features_view(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Feature)
        .options(selectinload(Feature.project), selectinload(Feature.stories))
        .order_by(Feature.created_at.desc())
    )
    features = result.scalars().all()

    features_data = []
    for f in features:
        stories = f.stories or []
        done_count = sum(1 for s in stories if s.status == "done")
        features_data.append({
            "id": f.id,
            "title": f.title,
            "description": f.description,
            "status": f.status,
            "project_name": f.project.name if f.project else "—",
            "project_id": f.project_id,
            "story_count": len(stories),
            "done_count": done_count,
            "completed_at": f.completed_at,
            "stories": stories,
        })

    return templates.TemplateResponse(request, "features.html", {
        "features": features_data,
        "active": "features",
    })


@router.get("/features/{feature_id}")
async def feature_detail_view(
    request: Request,
    feature_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Feature)
        .where(Feature.id == feature_id)
        .options(selectinload(Feature.project), selectinload(Feature.stories))
    )
    feature = result.scalar_one_or_none()
    if not feature:
        return templates.TemplateResponse(request, "features.html", {
            "features": [],
            "active": "features",
        })

    stories_data = []
    for story in feature.stories:
        comments_result = await db.execute(
            select(Comment).where(Comment.story_id == story.id).order_by(Comment.created_at)
        )
        comments = comments_result.scalars().all()
        stories_data.append({
            "id": story.id,
            "title": story.title,
            "summary": story.summary,
            "description": story.description,
            "assigned_to": story.assigned_to,
            "status": story.status,
            "points": story.points,
            "labels": story.labels,
            "pr_url": story.pr_url,
            "feature_id": story.feature_id,
            "comments": comments,
        })

    return templates.TemplateResponse(request, "feature_detail.html", {
        "feature": feature,
        "project_name": feature.project.name if feature.project else "—",
        "stories": stories_data,
        "active": "features",
    })


@router.get("/analytics")
async def analytics_view(request: Request, db: AsyncSession = Depends(get_db)):
    from app.routers.analytics import get_analytics
    data = await get_analytics(db)
    return templates.TemplateResponse(request, "analytics.html", {
        "analytics": data.model_dump(),
        "active": "analytics",
    })


@router.get("/history")
async def history_view(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Feature)
        .where(Feature.status == "complete")
        .options(selectinload(Feature.stories), selectinload(Feature.project))
        .order_by(Feature.completed_at.desc())
    )
    features = result.scalars().all()

    features_data = []
    for f in features:
        features_data.append({
            "title": f.title,
            "description": f.description,
            "project_name": f.project.name if f.project else None,
            "completed_at": f.completed_at,
            "stories": f.stories,
        })

    return templates.TemplateResponse(request, "history.html", {
        "features": features_data,
        "active": "history",
    })


AGENT_NAMES = {
    "alfred": "Alfred",
    "vio": "Vio",
    "neo": "Neo",
    "zeo": "Zeo",
    "seo": "Seo",
    "human": "Human",
}


def _time_ago(dt: "datetime") -> str:
    from datetime import datetime as _dt, timezone as _tz

    now = _dt.now(_tz.utc)
    if dt.tzinfo is None:
        from datetime import timezone as _tz2
        dt = dt.replace(tzinfo=_tz2.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    if days < 30:
        return f"{days}d"
    return dt.strftime("%b %d")


@router.get("/chitchat")
async def chitchat_view(
    request: Request,
    tab: str = "collaboration",
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post)
        .options(selectinload(Post.replies), selectinload(Post.upvotes))
        .order_by(Post.created_at.desc())
        .limit(50)
    )
    posts = result.scalars().all()

    posts_data = []
    for p in posts:
        replies_data = []
        for r in p.replies:
            replies_data.append({
                "author": r.author,
                "content": r.content,
                "mentions": r.mentions,
                "time_ago": _time_ago(r.created_at),
            })
        posts_data.append({
            "id": p.id,
            "author": p.author,
            "author_name": AGENT_NAMES.get(p.author, p.author.capitalize()),
            "content": p.content,
            "image_url": p.image_url,
            "link_url": p.link_url,
            "link_title": p.link_title,
            "mentions": p.mentions,
            "time_ago": _time_ago(p.created_at),
            "replies": replies_data,
            "upvotes": p.upvotes,
        })

    collab_result = await db.execute(
        select(CollabPost)
        .options(selectinload(CollabPost.replies))
        .order_by(CollabPost.created_at.desc())
        .limit(100)
    )
    collab_posts = collab_result.scalars().all()

    collab_data = []
    for cp in collab_posts:
        collab_replies = []
        for r in cp.replies:
            collab_replies.append({
                "id": r.id,
                "author": r.author,
                "content": r.content,
                "mentions": r.mentions,
                "time_ago": _time_ago(r.created_at),
            })
        collab_data.append({
            "id": cp.id,
            "author": cp.author,
            "author_name": AGENT_NAMES.get(cp.author, cp.author.capitalize()),
            "subject": cp.subject,
            "story_id": cp.story_id,
            "body": cp.body,
            "mentions": cp.mentions,
            "resolved": cp.resolved,
            "time_ago": _time_ago(cp.created_at),
            "replies": collab_replies,
        })

    return templates.TemplateResponse(request, "chitchat.html", {
        "posts": posts_data,
        "collab_posts": collab_data,
        "active_tab": tab,
        "active": "chitchat",
    })


@router.get("/notifications")
async def notifications_view(
    request: Request,
    agent_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    agents_result = await db.execute(select(Agent).order_by(Agent.agent_id))
    agents = agents_result.scalars().all()

    q = (
        select(Notification)
        .order_by(Notification.created_at.desc())
        .limit(200)
    )
    if agent_id:
        q = q.where(Notification.agent_id == agent_id)
    result = await db.execute(q)
    notifs = result.scalars().all()

    notifs_data = []
    for n in notifs:
        notifs_data.append({
            "id": n.id,
            "agent_id": n.agent_id,
            "agent_name": AGENT_NAMES.get(n.agent_id, n.agent_id.capitalize()),
            "source_type": n.source_type,
            "source_id": n.source_id,
            "author": n.author,
            "author_name": AGENT_NAMES.get(n.author, n.author.capitalize()),
            "preview": n.preview,
            "is_read": n.is_read,
            "time_ago": _time_ago(n.created_at),
        })

    count_result = await db.execute(
        select(Notification.agent_id, func.count().label("cnt"))
        .where(Notification.is_read == 0)
        .group_by(Notification.agent_id)
    )
    unread_counts = {row.agent_id: row.cnt for row in count_result.all()}
    total_unread = sum(unread_counts.values())

    return templates.TemplateResponse(request, "notifications.html", {
        "notifications": notifs_data,
        "agents": agents,
        "selected_agent": agent_id,
        "unread_counts": unread_counts,
        "total_unread": total_unread,
        "active": "notifications",
    })


def _md_to_html(text: str) -> str:
    """Minimal markdown to HTML for guide content."""
    import re
    import html as html_mod

    lines = text.split("\n")
    out: list[str] = []
    in_code = False
    in_table = False
    in_list = False
    list_type = ""

    for line in lines:
        if line.startswith("```"):
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                out.append("<pre><code>")
                in_code = True
            continue

        if in_code:
            out.append(html_mod.escape(line))
            continue

        stripped = line.strip()

        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(set(c) <= {"-", ":", " "} for c in cells):
                continue
            if not in_table:
                out.append("<table>")
                tag = "th"
                in_table = True
            else:
                tag = "td"
            row = "".join(f"<{tag}>{_inline_md(c)}</{tag}>" for c in cells)
            out.append(f"<tr>{row}</tr>")
            continue
        elif in_table:
            out.append("</table>")
            in_table = False

        if re.match(r"^#{1,3}\s", stripped):
            level = len(stripped.split(" ")[0])
            text_content = stripped[level + 1:]
            if in_list:
                out.append(f"</{list_type}>")
                in_list = False
            out.append(f"<h{level}>{_inline_md(text_content)}</h{level}>")
            continue

        if stripped.startswith("- [ ] ") or stripped.startswith("- [x] "):
            checked = "checked" if stripped.startswith("- [x]") else ""
            content = stripped[6:]
            if not in_list or list_type != "ul":
                if in_list:
                    out.append(f"</{list_type}>")
                out.append("<ul>")
                in_list = True
                list_type = "ul"
            out.append(f'<li><input type="checkbox" disabled {checked}>{_inline_md(content)}</li>')
            continue

        if stripped.startswith("- "):
            content = stripped[2:]
            if not in_list or list_type != "ul":
                if in_list:
                    out.append(f"</{list_type}>")
                out.append("<ul>")
                in_list = True
                list_type = "ul"
            out.append(f"<li>{_inline_md(content)}</li>")
            continue

        if re.match(r"^\d+\.\s", stripped):
            content = re.sub(r"^\d+\.\s", "", stripped)
            if not in_list or list_type != "ol":
                if in_list:
                    out.append(f"</{list_type}>")
                out.append("<ol>")
                in_list = True
                list_type = "ol"
            out.append(f"<li>{_inline_md(content)}</li>")
            continue

        if in_list and not stripped:
            out.append(f"</{list_type}>")
            in_list = False

        if stripped == "---":
            out.append("<hr>")
            continue

        if stripped:
            out.append(f"<p>{_inline_md(stripped)}</p>")

    if in_list:
        out.append(f"</{list_type}>")
    if in_table:
        out.append("</table>")
    if in_code:
        out.append("</code></pre>")

    return "\n".join(out)


def _inline_md(text: str) -> str:
    import re
    import html as html_mod

    text = html_mod.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    return text


@router.get("/guides")
async def guides_view(
    request: Request,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Guide).order_by(Guide.sort_order, Guide.title)
    if category:
        q = q.where(Guide.category == category)
    result = await db.execute(q)
    guides = result.scalars().all()

    return templates.TemplateResponse(request, "guides.html", {
        "guides": guides,
        "selected_category": category,
        "active": "guides",
    })


@router.get("/guides/{slug}")
async def guide_detail_view(
    request: Request,
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Guide).where(Guide.slug == slug))
    guide = result.scalar_one_or_none()
    if not guide:
        return templates.TemplateResponse(request, "guides.html", {
            "guides": [],
            "selected_category": None,
            "active": "guides",
        })

    return templates.TemplateResponse(request, "guide_detail.html", {
        "guide": {
            "slug": guide.slug,
            "title": guide.title,
            "category": guide.category,
            "audience": guide.audience,
            "summary": guide.summary,
            "content_html": _md_to_html(guide.content),
        },
        "active": "guides",
    })
