from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ConversationCreate(StrictRequest):
    title: str = Field(default="新的安全核查", min_length=1, max_length=100)


class RunCreate(StrictRequest):
    conversation_id: str = Field(min_length=1, max_length=100)
    incident_id: str = Field(min_length=1, max_length=100)
    instruction: str = Field(min_length=1, max_length=2000)
    evidence_snapshot_id: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("instruction")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("任务指令不能为空")
        return value


class EvidenceSourceSelection(StrictRequest):
    kind: Literal["incident", "device"]
    id: str = Field(min_length=1, max_length=100)


class EvidenceSnapshotCreate(StrictRequest):
    source_view: Literal["overview", "map", "coordination"] = "map"
    image_id: str | None = Field(default=None, min_length=1, max_length=100)
    source_selection: EvidenceSourceSelection | None = None


ExecutionTaskType = Literal["aerial_inspection", "ground_inspection", "remote_sensing"]


class ExecutionTaskCreate(StrictRequest):
    title: str = Field(min_length=1, max_length=160)
    incident_id: str = Field(min_length=1, max_length=100)
    task_type: ExecutionTaskType
    priority: Literal["high", "medium", "low"] = "medium"


class ExecutionFromRun(StrictRequest):
    run_id: str = Field(min_length=1, max_length=100)
    task_type: ExecutionTaskType = "aerial_inspection"


class ExecutionAssignment(StrictRequest):
    resource_id: str = Field(min_length=1, max_length=100)
