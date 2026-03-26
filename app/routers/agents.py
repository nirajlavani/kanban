from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Agent, Story
from app.schemas import AgentDetail, AgentOut, StoryOut

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[dict])
async def list_agents(db: AsyncSession = Depends(get_db)):
    agents_result = await db.execute(select(Agent).order_by(Agent.agent_id))
    agents = agents_result.scalars().all()

    output = []
    for agent in agents:
        count_result = await db.execute(
            select(func.count())
            .select_from(Story)
            .where(Story.assigned_to == agent.agent_id)
            .where(Story.status != "done")
        )
        active_count = count_result.scalar() or 0
        output.append({
            "id": agent.id,
            "agent_id": agent.agent_id,
            "name": agent.name,
            "role": agent.role,
            "specialty": agent.specialty,
            "active_stories": active_count,
        })
    return output


@router.get("/{agent_id}")
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.agent_id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")

    stories_result = await db.execute(
        select(Story)
        .where(Story.assigned_to == agent_id)
        .order_by(Story.created_at.desc())
    )
    stories = stories_result.scalars().all()

    agent_data = AgentOut.model_validate(agent).model_dump()
    agent_data["stories"] = [StoryOut.model_validate(s).model_dump() for s in stories]
    return agent_data
