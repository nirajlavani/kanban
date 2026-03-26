from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Guide
from app.schemas import GuideCreate, GuideOut, GuideSummaryOut, GuideUpdate

router = APIRouter(prefix="/api/guides", tags=["guides"])


@router.get("", response_model=list[GuideSummaryOut])
async def list_guides(
    category: str | None = None,
    audience: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Guide).order_by(Guide.sort_order, Guide.title)
    if category:
        q = q.where(Guide.category == category)
    if audience:
        q = q.where(Guide.audience.in_([audience, "all"]))
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{slug}", response_model=GuideOut)
async def get_guide(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Guide).where(Guide.slug == slug))
    guide = result.scalar_one_or_none()
    if not guide:
        raise HTTPException(404, "Guide not found")
    return guide


@router.post("", response_model=GuideOut, status_code=201)
async def create_guide(payload: GuideCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Guide).where(Guide.slug == payload.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Guide with slug '{payload.slug}' already exists")
    guide = Guide(**payload.model_dump())
    db.add(guide)
    await db.commit()
    await db.refresh(guide)
    return guide


@router.patch("/{slug}", response_model=GuideOut)
async def update_guide(
    slug: str,
    payload: GuideUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Guide).where(Guide.slug == slug))
    guide = result.scalar_one_or_none()
    if not guide:
        raise HTTPException(404, "Guide not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(guide, key, value)
    await db.commit()
    await db.refresh(guide)
    return guide
