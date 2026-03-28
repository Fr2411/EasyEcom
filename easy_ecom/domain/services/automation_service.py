from __future__ import annotations

from easy_ecom.api.schemas.automation import (
    AutomationRuleResponse,
    AutomationRunsResponse,
    AutomationRulesResponse,
)
from easy_ecom.api.schemas.common import ModuleOverviewResponse, OverviewMetric
from easy_ecom.domain.models.auth import AuthenticatedUser


class AutomationService:
    def overview(self, user: AuthenticatedUser) -> ModuleOverviewResponse:
        del user
        return ModuleOverviewResponse(
            module="automation",
            status="skeleton",
            summary="Automation is mounted as a tenant-safe read-only skeleton while workflows are rebuilt.",
            metrics=[
                OverviewMetric(label="Rules", value="0", hint="No automation rules configured yet"),
                OverviewMetric(label="Active rules", value="0", hint="No enabled rules available"),
                OverviewMetric(label="Recent runs", value="0", hint="No execution history yet"),
            ],
        )

    def list_rules(self, user: AuthenticatedUser) -> AutomationRulesResponse:
        del user
        return AutomationRulesResponse(items=[])

    def get_rule(self, user: AuthenticatedUser, rule_id: str) -> AutomationRuleResponse:
        del user, rule_id
        raise LookupError("Automation rules are not yet configured")

    def list_rule_runs(self, user: AuthenticatedUser, rule_id: str) -> AutomationRunsResponse:
        del user, rule_id
        return AutomationRunsResponse(items=[])

    def list_runs(self, user: AuthenticatedUser) -> AutomationRunsResponse:
        del user
        return AutomationRunsResponse(items=[])
