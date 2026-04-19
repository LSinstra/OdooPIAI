from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# ---- Auth ----------------------------------------------------------
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str | None = None

    class Config:
        from_attributes = True


# ---- Odoo connection -----------------------------------------------
class OdooConnectionCreate(BaseModel):
    label: str
    url: str
    db_name: str
    username: str
    api_key: str
    is_default: bool = True


class OdooConnectionOut(BaseModel):
    id: int
    label: str
    url: str
    db_name: str
    username: str
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Planner -------------------------------------------------------
class PlanRequest(BaseModel):
    project_id: int
    brief: str
    target_date: str | None = None


class PlannedTask(BaseModel):
    name: str
    description: str = ""
    estimated_hours: float = 0
    stage: str = "Backlog"
    depends_on: list[str] = []


class PlanResponse(BaseModel):
    stages: list[str]
    tasks: list[PlannedTask]
    risks: list[str] = []
    rationale: str = ""


class ApplyPlanRequest(BaseModel):
    project_id: int
    tasks: list[PlannedTask]


# ---- Breakdown -----------------------------------------------------
class BreakdownRequest(BaseModel):
    task_id: int
    extra_context: str = ""


class BreakdownResponse(BaseModel):
    subtasks: list[PlannedTask]


# ---- Chat ----------------------------------------------------------
class ChatRequest(BaseModel):
    project_id: int
    message: str
    post_to_chatter: bool = False


# ---- Stakeholder update -------------------------------------------
class StakeholderRequest(BaseModel):
    project_id: int
    tone: str = "exec"  # "exec" | "customer" | "internal"
    highlights: str = ""


class StakeholderResponse(BaseModel):
    subject: str
    body_md: str
