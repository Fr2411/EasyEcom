export type GuidedMatchState = 'idle' | 'exact' | 'likely' | 'new';

export type SuggestedActionTone = 'info' | 'success' | 'warning';

export type SuggestedAction = {
  title: string;
  detail: string;
  actionLabel?: string;
  secondaryLabel?: string;
  tone?: SuggestedActionTone;
};

export type LookupOutcome<TExact = unknown, TLikely = unknown, TNew = unknown> = {
  state: GuidedMatchState;
  query: string;
  exact: TExact[];
  likely: TLikely[];
  suggestedNew?: TNew | null;
};

export type StagedDraft<T> = {
  ready: boolean;
  summary: string;
  value: T;
};
