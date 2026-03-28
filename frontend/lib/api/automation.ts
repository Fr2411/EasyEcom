import { apiClient } from '@/lib/api/client';
import type { AutomationOverview, AutomationRule, AutomationRun } from '@/types/automation-workspace';

export async function getAutomationOverview() {
  return apiClient<AutomationOverview>('/automation/overview');
}

export async function getAutomationRules() {
  return apiClient<{ items: AutomationRule[] }>('/automation/rules');
}

export async function getAutomationRuns() {
  return apiClient<{ items: AutomationRun[] }>('/automation/runs');
}
