from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR
from app.database import Base, async_session, engine
from app.routers import agents, analytics, board, chitchat, collab, features, guides, notifications, projects, stories, views
from app.seed import seed_agents
from app.seed_guides import seed_guides


def _migrate_add_columns(connection):
    """Add columns that may be missing from older databases."""
    import sqlalchemy as sa

    inspector = sa.inspect(connection)
    story_cols = {c["name"] for c in inspector.get_columns("stories")}
    if "summary" not in story_cols:
        connection.execute(sa.text("ALTER TABLE stories ADD COLUMN summary VARCHAR(300)"))

    if "posts" in inspector.get_table_names():
        post_cols = {c["name"] for c in inspector.get_columns("posts")}
        if "mentions" not in post_cols:
            connection.execute(sa.text("ALTER TABLE posts ADD COLUMN mentions VARCHAR(500)"))

    if "post_replies" in inspector.get_table_names():
        reply_cols = {c["name"] for c in inspector.get_columns("post_replies")}
        if "mentions" not in reply_cols:
            connection.execute(sa.text("ALTER TABLE post_replies ADD COLUMN mentions VARCHAR(500)"))

    for col in ("pr_status", "pr_checks", "pr_review_state"):
        if col not in story_cols:
            connection.execute(sa.text(f"ALTER TABLE stories ADD COLUMN {col} VARCHAR(20)"))


def _ensure_chitchat_images_dir():
    images_dir = STATIC_DIR / "chitchat_images"
    images_dir.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_chitchat_images_dir()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_add_columns)
    async with async_session() as db:
        await seed_agents(db)
        await seed_guides(db)
    yield
    await engine.dispose()


app = FastAPI(
    title="LavanLabs Kanban",
    description="API-first kanban board for AI agents",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(projects.router)
app.include_router(features.router)
app.include_router(stories.router)
app.include_router(agents.router)
app.include_router(board.router)
app.include_router(analytics.router)
app.include_router(chitchat.router)
app.include_router(collab.router)
app.include_router(notifications.router)
app.include_router(guides.router)
app.include_router(views.router)
