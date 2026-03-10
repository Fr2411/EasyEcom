'use client';
import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '@/components/auth/auth-provider';
import { ApiError } from '@/lib/api/client';
import { getBusinessProfile, getPreferences, getSequences, getTenantContext, patchBusinessProfile, patchPreferences, patchSequences } from '@/lib/api/settings';

const ADMIN_ROLES = new Set(['SUPER_ADMIN', 'CLIENT_OWNER', 'CLIENT_MANAGER']);

export function SettingsWorkspace() {
  const { user } = useAuth();
  const canWrite = useMemo(() => Boolean(user?.roles?.some((role) => ADMIN_ROLES.has(role))), [user?.roles]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [profile, setProfile] = useState<any>(null);
  const [prefs, setPrefs] = useState<any>(null);
  const [sequences, setSequences] = useState<any>(null);
  const [tenant, setTenant] = useState<any>(null);

  async function load() {
    setLoading(true);
    setError('');
    try {
      const [businessProfile, preferences, sequenceData, tenantContext] = await Promise.all([getBusinessProfile(), getPreferences(), getSequences(), getTenantContext()]);
      setProfile(businessProfile);
      setPrefs(preferences);
      setSequences(sequenceData);
      setTenant(tenantContext);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);

  if (loading) return <div className="settings-card" data-testid="settings-loading">Loading settings…</div>;
  if (error) return <div className="settings-card" data-testid="settings-error">{error}</div>;
  if (!profile || !prefs || !sequences || !tenant) return <div className="settings-card" data-testid="settings-empty-state">Settings are not available for this tenant.</div>;

  return <div className="settings-layout">{!canWrite ? <div className="settings-card" data-testid="settings-access-denied">Read-only mode: only admin/manager roles can save tenant settings.</div> : null}{notice ? <div className="settings-card settings-notice">{notice}</div> : null}
    <section className="settings-card"><h3>Business profile</h3><div className="settings-grid">
      <label>Business name<input value={profile.business_name} onChange={(e) => setProfile({ ...profile, business_name: e.target.value })} /></label>
      <label>Trading / display name<input value={profile.display_name} onChange={(e) => setProfile({ ...profile, display_name: e.target.value })} /></label>
      <label>Phone<input value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} /></label>
      <label>Email<input value={profile.email} onChange={(e) => setProfile({ ...profile, email: e.target.value })} /></label>
      <label>Currency code<input value={profile.currency_code} onChange={(e) => setProfile({ ...profile, currency_code: e.target.value })} /></label>
      <label>Timezone<input value={profile.timezone} onChange={(e) => setProfile({ ...profile, timezone: e.target.value })} /></label>
      <label>Tax/VAT registration<input value={profile.tax_registration_no} onChange={(e) => setProfile({ ...profile, tax_registration_no: e.target.value })} /></label>
      <label className="field-span-2">Address<textarea value={profile.address} onChange={(e) => setProfile({ ...profile, address: e.target.value })} /></label>
    </div>
    <p className="settings-muted">Logo upload deferred: {profile.logo_upload_deferred_reason}</p>
    <button disabled={!canWrite} onClick={async () => { const saved = await patchBusinessProfile(profile); setProfile(saved); setNotice('Business profile saved.'); }}>Save business profile</button>
    </section>

    <section className="settings-card"><h3>Operational preferences</h3><div className="settings-grid">
      <label>Default low-stock threshold<input type="number" value={prefs.low_stock_threshold} onChange={(e) => setPrefs({ ...prefs, low_stock_threshold: Number(e.target.value) })} /></label>
      <label>Default payment terms (days)<input type="number" value={prefs.default_payment_terms_days} onChange={(e) => setPrefs({ ...prefs, default_payment_terms_days: Number(e.target.value) })} /></label>
      <label className="field-span-2">Default sales note<textarea value={prefs.default_sales_note} onChange={(e) => setPrefs({ ...prefs, default_sales_note: e.target.value })} /></label>
      <label className="field-span-2">Inventory adjustment reason presets<input value={prefs.default_inventory_adjustment_reasons.join(', ')} onChange={(e) => setPrefs({ ...prefs, default_inventory_adjustment_reasons: e.target.value.split(',').map((x:string)=>x.trim()).filter(Boolean) })} /></label>
    </div>
    <button disabled={!canWrite} onClick={async () => { const saved = await patchPreferences(prefs); setPrefs(saved); setNotice('Operational preferences saved.'); }}>Save operational preferences</button>
    </section>

    <section className="settings-card"><h3>Document / sequence preferences</h3><div className="settings-grid">
      <label>Sales prefix<input value={sequences.sales_prefix} onChange={(e) => setSequences({ ...sequences, sales_prefix: e.target.value })} /></label>
      <label>Returns prefix<input value={sequences.returns_prefix} onChange={(e) => setSequences({ ...sequences, returns_prefix: e.target.value })} /></label>
      <label>Purchases prefix<input value={sequences.purchases_prefix} onChange={(e) => setSequences({ ...sequences, purchases_prefix: e.target.value })} /></label>
    </div>
    <button disabled={!canWrite} onClick={async () => { const saved = await patchSequences(sequences); setSequences(saved); setNotice('Sequence preferences saved.'); }}>Save sequence preferences</button>
    </section>

    <section className="settings-card"><h3>Tenant context</h3><dl className="settings-context"><div><dt>Client ID</dt><dd>{tenant.client_id}</dd></div><div><dt>Business</dt><dd>{tenant.business_name}</dd></div><div><dt>Status</dt><dd>{tenant.status || 'active'}</dd></div><div><dt>Currency</dt><dd>{tenant.currency_code || 'not set'}</dd></div></dl></section>
  </div>;
}
