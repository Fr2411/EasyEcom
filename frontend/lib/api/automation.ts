import { apiClient } from '@/lib/api/client';
import type { AutomationDecision, AutomationEvaluation, AutomationPolicy } from '@/types/automation';

export function getAutomationPolicy() {
  return apiClient<AutomationPolicy>('/automation/policies');
}

export function patchAutomationPolicy(payload: Partial<Pick<AutomationPolicy, 'automation_enabled' | 'auto_send_enabled' | 'emergency_disabled' | 'categories'>>) {
  return apiClient<AutomationPolicy>('/automation/policies', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function enableAutomation() {
  return apiClient<AutomationPolicy>('/automation/enable', { method: 'POST' });
}

export function disableAutomation(emergency = false) {
  return apiClient<AutomationPolicy>('/automation/disable', { method: 'POST', body: JSON.stringify({ emergency }) });
}

export function evaluateAutomation(conversationId: string) {
  return apiClient<AutomationEvaluation>(`/automation/evaluate/${conversationId}`, { method: 'POST' });
}

export function runAutomation(conversationId: string) {
  return apiClient<AutomationDecision>(`/automation/run/${conversationId}`, { method: 'POST' });
}

export function getAutomationHistory() {
  return apiClient<{ items: AutomationDecision[] }>('/automation/history');
}

export function getAutomationQueue() {
  return apiClient<{ items: AutomationDecision[] }>('/automation/queue');
}
