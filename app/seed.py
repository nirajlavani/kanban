from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent

AGENTS = [
    {
        "agent_id": "alfred",
        "name": "Alfred",
        "role": "Orchestrator",
        "specialty": "Plans, assigns, reviews, merges. Does NOT code.",
        "llm_model": "openai-codex / minimax-m2.5",
    },
    {
        "agent_id": "vio",
        "name": "Vio",
        "role": "Frontend Developer",
        "specialty": "UI, layouts, styling, components, accessibility, frontend frameworks, responsive design.",
        "llm_model": "openai-codex / minimax-m2.5",
    },
    {
        "agent_id": "neo",
        "name": "Neo",
        "role": "Backend/Infra Developer",
        "specialty": "APIs, databases, server logic, DevOps, cloud, CI/CD, authentication, Docker, Kubernetes.",
        "llm_model": "openai-codex / minimax-m2.5",
    },
    {
        "agent_id": "zeo",
        "name": "Zeo",
        "role": "Backend/Infra Developer",
        "specialty": "APIs, databases, server logic, DevOps, cloud, CI/CD. Load-balanced with Neo.",
        "llm_model": "openai-codex / minimax-m2.5",
    },
    {
        "agent_id": "seo",
        "name": "Seo",
        "role": "Research Agent",
        "specialty": "Finds new skills, tools, and strategies. Observes kanban but takes no dev work.",
        "llm_model": "minimax-m2.5",
    },
]


async def seed_agents(db: AsyncSession) -> None:
    result = await db.execute(select(Agent))
    existing = {a.agent_id: a for a in result.scalars().all()}

    for agent_data in AGENTS:
        if agent_data["agent_id"] not in existing:
            db.add(Agent(**agent_data))
        else:
            agent = existing[agent_data["agent_id"]]
            if agent.llm_model != agent_data.get("llm_model"):
                agent.llm_model = agent_data.get("llm_model")

    await db.commit()
