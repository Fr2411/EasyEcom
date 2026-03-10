import { apiClient } from '@/lib/api/client';
import type { BusinessProfile, Preferences, Sequences, TenantContext } from '@/types/settings';

export function getBusinessProfile() {
  return apiClient<BusinessProfile>('/settings/business-profile');
}

export function patchBusinessProfile(payload: Partial<BusinessProfile>) {
  return apiClient<BusinessProfile>('/settings/business-profile', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function getPreferences() {
  return apiClient<Preferences>('/settings/preferences');
}

export function patchPreferences(payload: Partial<Preferences>) {
  return apiClient<Preferences>('/settings/preferences', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function getSequences() {
  return apiClient<Sequences>('/settings/sequences');
}

export function patchSequences(payload: Partial<Sequences>) {
  return apiClient<Sequences>('/settings/sequences', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function getTenantContext() {
  return apiClient<TenantContext>('/settings/tenant-context');
}
