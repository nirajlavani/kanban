from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Feature
from app.schemas import FeatureCreate, FeatureDetail, FeatureOut, FeatureUpdate

router = APIRouter(prefix="/api/features", tags=["features"])

VALID_STATUSES = {"planning", "in_progress", "complete"}


@router.get("", response_model=list[FeatureOut])
async def list_features(
    status: str | None = None,
    project_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Feature)
    if status:
        q = q.where(Feature.status == status)
    if project_id:
        q = q.where(Feature.project_id == project_id)
    q = q.order_by(Feature.created_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{feature_id}", response_model=FeatureDetail)
async def get_feature(feature_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Feature)
        .where(Feature.id == feature_id)
        .options(selectinload(Feature.stories))
    )
    feature = result.scalar_one_or_none()
    if not feature:
        raise HTTPException(404, "Feature not found")
    return feature


@router.post("", response_model=FeatureOut, status_code=201)
async def create_feature(payload: FeatureCreate, db: AsyncSession = Depends(get_db)):
    feature = Feature(**payload.model_dump())
    db.add(feature)
    await db.commit()
    await db.refresh(feature)
    return feature


@router.patch("/{feature_id}", response_model=FeatureOut)
async def update_feature(
    feature_id: int,
    payload: FeatureUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Feature).where(Feature.id == feature_id))
    feature = result.scalar_one_or_none()
    if not feature:
        raise HTTPException(404, "Feature not found")

    data = payload.model_dump(exclude_unset=True)

    if "status" in data and data["status"] not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status. Must be one of: {VALID_STATUSES}")

    for key, value in data.items():
        setattr(feature, key, value)

    if feature.status == "complete" and not feature.completed_at:
        feature.completed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(feature)
    return feature
