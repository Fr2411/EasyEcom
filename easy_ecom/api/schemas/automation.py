from __future__ import annotations

from pydantic import BaseModel


class AutomationRuleResponse(BaseModel):
    automation_rule_id: str
    name: str
    status: str
    trigger_type: str
    schedule_rule: str | None = None
    timezone: str | None = None
    last_run_at: str | None = None
    next_run_at: str | None = None


class AutomationRulesResponse(BaseModel):
    items: list[AutomationRuleResponse]


class AutomationRunResponse(BaseModel):
    automation_run_id: str
    automation_rule_id: str
    status: str
    trigger_source: str
    started_at: str | None = None
    finished_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class AutomationRunsResponse(BaseModel):
    items: list[AutomationRunResponse]
