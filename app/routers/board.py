from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Feature, Story
from app.schemas import BoardColumn, BoardOut, FeatureHistory, StoryOut

router = APIRouter(prefix="/api", tags=["board"])

COLUMNS = ["todo", "in_progress", "testing", "review", "done"]


@router.get("/board", response_model=BoardOut)
async def get_board(
    project_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Story)
    if project_id:
        q = q.join(Feature).where(Feature.project_id == project_id)
    q = q.order_by(Story.created_at.asc())
    result = await db.execute(q)
    all_stories = result.scalars().all()

    grouped: dict[str, list] = {col: [] for col in COLUMNS}
    for story in all_stories:
        if story.status in grouped:
            grouped[story.status].append(StoryOut.model_validate(story))

    return BoardOut(
        columns=[BoardColumn(status=col, stories=grouped[col]) for col in COLUMNS]
    )


@router.get("/history", response_model=list[FeatureHistory])
async def get_history(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Feature)
        .where(Feature.status == "complete")
        .options(selectinload(Feature.stories), selectinload(Feature.project))
        .order_by(Feature.completed_at.desc())
    )
    features = result.scalars().all()

    output = []
    for f in features:
        data = FeatureHistory.model_validate(f)
        data.project_name = f.project.name if f.project else None
        output.append(data)
    return output
