from datetime import datetime

from pydantic import BaseModel, ConfigDict


# --- Project ---

class ProjectCreate(BaseModel):
    name: str
    slug: str
    repo_path: str | None = None
    description: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    repo_path: str | None
    description: str | None
    created_at: datetime


class ProjectDetail(ProjectOut):
    features: list["FeatureOut"] = []


# --- Feature ---

class FeatureCreate(BaseModel):
    project_id: int
    title: str
    description: str | None = None


class FeatureUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None


class FeatureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    title: str
    description: str | None
    status: str
    created_at: datetime
    completed_at: datetime | None


class FeatureDetail(FeatureOut):
    stories: list["StoryOut"] = []


# --- Story ---

class StoryCreate(BaseModel):
    feature_id: int
    title: str
    summary: str | None = None
    description: str | None = None
    assigned_to: str | None = None
    points: int = 1
    labels: str | None = None
    acceptance_criteria: str | None = None
    testing_criteria: str | None = None
    dependencies: str | None = None


class StoryUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    description: str | None = None
    assigned_to: str | None = None
    points: int | None = None
    labels: str | None = None
    acceptance_criteria: str | None = None
    testing_criteria: str | None = None
    dependencies: str | None = None
    pr_url: str | None = None


class StoryMove(BaseModel):
    status: str
    agent_id: str


class StoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    feature_id: int
    title: str
    summary: str | None
    description: str | None
    assigned_to: str | None
    status: str
    points: int
    labels: str | None
    acceptance_criteria: str | None
    testing_criteria: str | None
    dependencies: str | None
    pr_url: str | None
    pr_status: str | None = None
    pr_checks: str | None = None
    pr_review_state: str | None = None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class StoryDetail(StoryOut):
    comments: list["CommentOut"] = []


# --- Comment ---

class CommentCreate(BaseModel):
    author: str
    content: str


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    story_id: int
    author: str
    content: str
    created_at: datetime


# --- Agent ---

class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    agent_id: str
    name: str
    role: str
    specialty: str | None
    llm_model: str | None


class AgentDetail(AgentOut):
    stories: list[StoryOut] = []


# --- Board ---

class BoardColumn(BaseModel):
    status: str
    stories: list[StoryOut]


class BoardOut(BaseModel):
    columns: list[BoardColumn]


class FeatureHistory(FeatureOut):
    stories: list[StoryOut] = []
    project_name: str | None = None


# --- ChitChat ---

class PostCreate(BaseModel):
    author: str
    content: str
    image_url: str | None = None
    link_url: str | None = None
    link_title: str | None = None
    mentions: str | None = None


class PostReplyCreate(BaseModel):
    author: str
    content: str
    mentions: str | None = None


class PostUpvoteCreate(BaseModel):
    agent_id: str


class PostReplyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    post_id: int
    author: str
    content: str
    mentions: str | None
    created_at: datetime


class PostUpvoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    post_id: int
    agent_id: str


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    author: str
    content: str
    image_url: str | None
    link_url: str | None
    link_title: str | None
    mentions: str | None
    created_at: datetime
    replies: list[PostReplyOut] = []
    upvotes: list[PostUpvoteOut] = []


# --- Collaboration ---

class CollabPostCreate(BaseModel):
    author: str
    subject: str
    story_id: int | None = None
    body: str
    mentions: str


class CollabPostUpdate(BaseModel):
    resolved: int | None = None


class CollabReplyCreate(BaseModel):
    author: str
    content: str
    mentions: str | None = None


class CollabReplyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    post_id: int
    author: str
    content: str
    mentions: str | None
    created_at: datetime


class CollabPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    author: str
    subject: str
    story_id: int | None
    body: str
    mentions: str
    resolved: int
    created_at: datetime
    replies: list[CollabReplyOut] = []


# --- Story Transition Log ---

class StoryTransitionLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    story_id: int
    from_status: str
    to_status: str
    agent_id: str
    transitioned_at: datetime


# --- Analytics ---

class VelocityPeriod(BaseModel):
    label: str
    points: int

class VelocityOut(BaseModel):
    periods: list[VelocityPeriod]
    total_points_completed: int

class CycleTimeOut(BaseModel):
    avg_hours: float
    by_column: dict[str, float]

class WorkloadItem(BaseModel):
    agent_id: str
    name: str
    active: int
    done_total: int
    points_done: int

class FeatureCompletionOut(BaseModel):
    total: int
    complete: int
    in_progress: int
    planning: int

class StoriesSummaryOut(BaseModel):
    total: int
    by_status: dict[str, int]

class AnalyticsOut(BaseModel):
    velocity: VelocityOut
    cycle_time: CycleTimeOut
    workload: list[WorkloadItem]
    feature_completion: FeatureCompletionOut
    stories_summary: StoriesSummaryOut

class DepStoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    status: str
    assigned_to: str | None


# --- Notifications ---

class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    agent_id: str
    source_type: str
    source_id: int
    author: str
    preview: str
    is_read: int
    created_at: datetime


class NotificationCountOut(BaseModel):
    agent_id: str
    unread: int


# --- Guides ---

class GuideCreate(BaseModel):
    slug: str
    title: str
    category: str
    audience: str = "all"
    summary: str | None = None
    content: str
    sort_order: int = 0


class GuideUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    audience: str | None = None
    summary: str | None = None
    content: str | None = None
    sort_order: int | None = None


class GuideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    title: str
    category: str
    audience: str
    summary: str | None
    content: str
    sort_order: int
    created_at: datetime
    updated_at: datetime


class GuideSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    title: str
    category: str
    audience: str
    summary: str | None
    sort_order: int
