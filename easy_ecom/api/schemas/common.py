from pydantic import BaseModel


class OverviewMetric(BaseModel):
    label: str
    value: str
    hint: str | None = None


class ModuleOverviewResponse(BaseModel):
    module: str
    status: str
    summary: str
    metrics: list[OverviewMetric]
