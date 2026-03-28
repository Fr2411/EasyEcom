export type AutomationMetric = {
  label: string;
  value: string;
  hint?: string | null;
};

export type AutomationOverview = {
  module: string;
  status: string;
  summary: string;
  metrics: AutomationMetric[];
};

export type AutomationRule = {
  automation_rule_id: string;
  name: string;
  status: string;
  trigger_type: string;
  schedule_rule?: string | null;
  timezone?: string | null;
  last_run_at?: string | null;
  next_run_at?: string | null;
};

export type AutomationRun = {
  automation_run_id: string;
  automation_rule_id: string;
  status: string;
  trigger_source: string;
  started_at?: string | null;
  finished_at?: string | null;
  error_code?: string | null;
  error_message?: string | null;
};
