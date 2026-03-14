'use client';

import { FormEvent, useEffect, useState } from 'react';
import {
  createAdminUser,
  getAdminClient,
  issueAdminInvitation,
  issueAdminPasswordReset,
  listAdminAudit,
  listAdminClients,
  listAdminRoles,
  listAdminUsers,
  onboardAdminClient,
  updateAdminClient,
  updateAdminUser,
} from '@/lib/api/admin';
import { useAuth } from '@/components/auth/auth-provider';
import { isSuperAdmin } from '@/lib/rbac';
import type {
  AdminAuditItem,
  AdminClient,
  AdminOnboardClientInput,
  AdminRole,
  AdminUser,
} from '@/types/admin';

type WizardStep = 1 | 2 | 3 | 4;

type CredentialBundle = {
  title: string;
  lines: string[];
};

type UserDraft = {
  name: string;
  role_code: string;
  is_active: boolean;
};

const EMPTY_ONBOARD_FORM: AdminOnboardClientInput = {
  business_name: '',
  contact_name: '',
  primary_email: '',
  primary_phone: '',
  owner_name: '',
  owner_email: '',
  address: '',
  website_url: '',
  facebook_url: '',
  instagram_url: '',
  whatsapp_number: '',
  notes: '',
  timezone: 'UTC',
  currency_code: 'USD',
  currency_symbol: '$',
  default_location_name: 'Main Warehouse',
  additional_users: [],
};

const EMPTY_NEW_USER = {
  name: '',
  email: '',
  role_code: 'CLIENT_STAFF',
};

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return 'Not yet';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function buildInviteBundle(title: string, users: AdminUser[]) {
  return {
    title,
    lines: users.flatMap((user) => {
      if (!user.invitation_token) {
        return [];
      }
      return [
        `${user.name} (${user.user_code})`,
        `Invite token: ${user.invitation_token}`,
        `Expires: ${formatDateTime(user.invitation_expires_at)}`,
      ];
    }),
  };
}

export function AdminWorkspace() {
  const { user, loading } = useAuth();
  const [clients, setClients] = useState<AdminClient[]>([]);
  const [roles, setRoles] = useState<AdminRole[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [selectedClient, setSelectedClient] = useState<AdminClient | null>(null);
  const [clientDraft, setClientDraft] = useState<AdminClient | null>(null);
  const [clientUsers, setClientUsers] = useState<AdminUser[]>([]);
  const [userDrafts, setUserDrafts] = useState<Record<string, UserDraft>>({});
  const [auditItems, setAuditItems] = useState<AdminAuditItem[]>([]);
  const [search, setSearch] = useState('');
  const [workspaceLoading, setWorkspaceLoading] = useState(true);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [busyLabel, setBusyLabel] = useState<string | null>(null);
  const [wizardStep, setWizardStep] = useState<WizardStep>(1);
  const [onboardForm, setOnboardForm] = useState<AdminOnboardClientInput>(EMPTY_ONBOARD_FORM);
  const [newUserForm, setNewUserForm] = useState(EMPTY_NEW_USER);
  const [credentialBundle, setCredentialBundle] = useState<CredentialBundle | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  async function loadClientDirectory(currentSearch = search) {
    const response = await listAdminClients(currentSearch);
    setClients(response.items);
    if (!selectedClientId && response.items[0]) {
      setSelectedClientId(response.items[0].client_id);
    }
    if (selectedClientId && !response.items.some((item) => item.client_id === selectedClientId)) {
      setSelectedClientId(response.items[0]?.client_id ?? null);
    }
  }

  async function loadSelectedClient(clientId: string) {
    const [client, users, audit] = await Promise.all([
      getAdminClient(clientId),
      listAdminUsers(clientId),
      listAdminAudit(clientId),
    ]);

    setSelectedClient(client);
    setClientDraft(client);
    setClientUsers(users.items);
    setAuditItems(audit.items);
    setUserDrafts(
      Object.fromEntries(
        users.items.map((item) => [
          item.user_id,
          {
            name: item.name,
            role_code: item.role_code,
            is_active: item.is_active,
          },
        ])
      )
    );
  }

  async function loadWorkspace() {
    setWorkspaceLoading(true);
    setWorkspaceError(null);
    try {
      const [clientResponse, roleResponse, auditResponse] = await Promise.all([
        listAdminClients(),
        listAdminRoles(),
        listAdminAudit(),
      ]);
      setClients(clientResponse.items);
      setRoles(roleResponse.items);
      setAuditItems(auditResponse.items);
      if (!selectedClientId && clientResponse.items[0]) {
        setSelectedClientId(clientResponse.items[0].client_id);
      }
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : 'Unable to load the admin workspace.');
    } finally {
      setWorkspaceLoading(false);
    }
  }

  useEffect(() => {
    if (!loading && isSuperAdmin(user?.roles)) {
      void loadWorkspace();
    } else if (!loading) {
      setWorkspaceLoading(false);
    }
  }, [loading, user]);

  useEffect(() => {
    if (!selectedClientId || !isSuperAdmin(user?.roles)) {
      return;
    }
    void loadSelectedClient(selectedClientId);
  }, [selectedClientId, user]);

  function resetMessages() {
    setWorkspaceError(null);
    setSuccessMessage(null);
  }

  function canAdvanceWizard(step: WizardStep) {
    if (step === 1) {
      return Boolean(
        onboardForm.business_name.trim() &&
          onboardForm.contact_name.trim() &&
          onboardForm.primary_email.trim() &&
          onboardForm.primary_phone.trim()
      );
    }
    if (step === 2) {
      return Boolean(onboardForm.owner_name.trim() && onboardForm.owner_email.trim());
    }
    return true;
  }

  async function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    resetMessages();
    try {
      await loadClientDirectory(search);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : 'Unable to refresh clients.');
    }
  }

  async function handleOnboardSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (wizardStep < 4) {
      setWizardStep((current) => (Math.min(4, current + 1) as WizardStep));
      return;
    }

    resetMessages();
    setBusyLabel('Onboarding client');
    try {
      const response = await onboardAdminClient(onboardForm);
      setCredentialBundle(buildInviteBundle(`Setup links for ${response.client.business_name}`, response.users));
      setSuccessMessage(`Client ${response.client.business_name} was onboarded successfully.`);
      setOnboardForm(EMPTY_ONBOARD_FORM);
      setWizardStep(1);
      await loadWorkspace();
      setSelectedClientId(response.client.client_id);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : 'Unable to onboard the client.');
    } finally {
      setBusyLabel(null);
    }
  }

  async function handleClientSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedClient || !clientDraft) {
      return;
    }

    resetMessages();
    setBusyLabel('Saving client profile');
    try {
      const updated = await updateAdminClient(selectedClient.client_id, {
        business_name: clientDraft.business_name,
        contact_name: clientDraft.contact_name,
        owner_name: clientDraft.owner_name,
        email: clientDraft.email,
        phone: clientDraft.phone,
        address: clientDraft.address,
        website_url: clientDraft.website_url,
        facebook_url: clientDraft.facebook_url,
        instagram_url: clientDraft.instagram_url,
        whatsapp_number: clientDraft.whatsapp_number,
        notes: clientDraft.notes,
        timezone: clientDraft.timezone,
        currency_code: clientDraft.currency_code,
        currency_symbol: clientDraft.currency_symbol,
        status: clientDraft.status,
        default_location_name: clientDraft.default_location_name,
      });
      setSelectedClient(updated);
      setClientDraft(updated);
      setClients((items) => items.map((item) => (item.client_id === updated.client_id ? updated : item)));
      setSuccessMessage(`Client ${updated.business_name} was updated.`);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : 'Unable to save the client profile.');
    } finally {
      setBusyLabel(null);
    }
  }

  async function handleCreateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedClient) {
      return;
    }

    resetMessages();
    setBusyLabel('Adding user');
    try {
      const created = await createAdminUser(selectedClient.client_id, newUserForm);
      setClientUsers((items) => [created, ...items]);
      setUserDrafts((drafts) => ({
        ...drafts,
        [created.user_id]: {
          name: created.name,
          role_code: created.role_code,
          is_active: created.is_active,
        },
      }));
      setCredentialBundle(buildInviteBundle(`Setup link for ${created.name}`, [created]));
      setNewUserForm(EMPTY_NEW_USER);
      setSuccessMessage(`User ${created.name} was added under ${selectedClient.business_name}.`);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : 'Unable to create the user.');
    } finally {
      setBusyLabel(null);
    }
  }

  async function handleSaveUser(userId: string) {
    const draft = userDrafts[userId];
    if (!draft) {
      return;
    }

    resetMessages();
    setBusyLabel(`Saving user ${draft.name}`);
    try {
      const updated = await updateAdminUser(userId, draft);
      setClientUsers((items) => items.map((item) => (item.user_id === updated.user_id ? updated : item)));
      setUserDrafts((drafts) => ({
        ...drafts,
        [userId]: {
          name: updated.name,
          role_code: updated.role_code,
          is_active: updated.is_active,
        },
      }));
      setSuccessMessage(`User ${updated.name} was updated.`);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : 'Unable to update the user.');
    } finally {
      setBusyLabel(null);
    }
  }

  async function handleIssueInvite(userId: string) {
    resetMessages();
    setBusyLabel('Issuing invitation');
    try {
      const updated = await issueAdminInvitation(userId);
      setClientUsers((items) => items.map((item) => (item.user_id === updated.user_id ? updated : item)));
      setCredentialBundle(buildInviteBundle(`Setup link for ${updated.name}`, [updated]));
      setSuccessMessage(`A fresh invitation was issued for ${updated.name}.`);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : 'Unable to issue the invitation.');
    } finally {
      setBusyLabel(null);
    }
  }

  async function handleIssueReset(userId: string) {
    resetMessages();
    setBusyLabel('Issuing password reset');
    try {
      const updated = await issueAdminPasswordReset(userId);
      setClientUsers((items) => items.map((item) => (item.user_id === updated.user_id ? updated : item)));
      if (updated.password_reset_token) {
        setCredentialBundle({
          title: `Password reset for ${updated.name}`,
          lines: [
            `${updated.name} (${updated.user_code})`,
            `Reset token: ${updated.password_reset_token}`,
            `Expires: ${formatDateTime(updated.password_reset_expires_at)}`,
          ],
        });
      }
      setSuccessMessage(`A password reset link was issued for ${updated.name}.`);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : 'Unable to issue the password reset.');
    } finally {
      setBusyLabel(null);
    }
  }

  const potentialMatches = clients.filter((client) => {
    const businessMatch =
      onboardForm.business_name.trim() &&
      client.business_name.toLowerCase() === onboardForm.business_name.trim().toLowerCase();
    const emailMatch =
      onboardForm.primary_email.trim() &&
      client.email.toLowerCase() === onboardForm.primary_email.trim().toLowerCase();
    const websiteMatch =
      onboardForm.website_url.trim() &&
      client.website_url.toLowerCase() === onboardForm.website_url.trim().toLowerCase();
    return Boolean(businessMatch || emailMatch || websiteMatch);
  });

  if (loading || workspaceLoading) {
    return (
      <div className="admin-card">
        <p className="eyebrow">Super Admin</p>
        <h3>Loading control panel</h3>
        <p className="admin-muted">Pulling clients, roles, users, and audit activity from the live auth foundation.</p>
      </div>
    );
  }

  if (!isSuperAdmin(user?.roles)) {
    return (
      <div className="admin-card">
        <p className="eyebrow">Access Restricted</p>
        <h3>Super admin access is required</h3>
        <p className="admin-muted">This workspace is reserved for global onboarding, tenant administration, and password assistance.</p>
      </div>
    );
  }

  return (
    <div className="admin-workspace">
      {workspaceError ? <p className="admin-error">{workspaceError}</p> : null}
      {successMessage ? <p className="admin-success">{successMessage}</p> : null}
      {busyLabel ? <p className="admin-muted">{busyLabel}…</p> : null}

      <div className="admin-grid-shell">
        <section className="admin-card">
          <div className="admin-header-row">
            <div>
              <p className="eyebrow">Client Directory</p>
              <h3>Tenant list</h3>
            </div>
            <form className="customers-toolbar" onSubmit={handleSearchSubmit}>
              <input
                type="search"
                aria-label="Search clients"
                placeholder="Search by business, code, contact, or email"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
              <button type="submit">Search</button>
            </form>
          </div>
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Business</th>
                  <th>Client Code</th>
                  <th>Contact</th>
                  <th>Status</th>
                  <th>Owner</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {clients.map((client) => (
                  <tr
                    key={client.client_id}
                    className={selectedClientId === client.client_id ? 'admin-row-active' : undefined}
                    onClick={() => setSelectedClientId(client.client_id)}
                  >
                    <td>
                      <strong>{client.business_name}</strong>
                      <p className="admin-muted">{client.email}</p>
                    </td>
                    <td>{client.client_code}</td>
                    <td>{client.contact_name}</td>
                    <td>
                      <span className={client.status === 'active' ? 'status-pill status-pill-active' : 'status-pill'}>
                        {client.status}
                      </span>
                    </td>
                    <td>{client.owner_name}</td>
                    <td>{formatDateTime(client.created_at)}</td>
                  </tr>
                ))}
                {!clients.length ? (
                  <tr>
                    <td colSpan={6}>
                      <div className="reports-deferred">
                        <h4>No clients found</h4>
                        <p>Onboard the first client from the wizard to open the tenant workspace.</p>
                      </div>
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>

        <section className="admin-card">
          <div className="admin-header-row">
            <div>
              <p className="eyebrow">Onboarding Wizard</p>
              <h3>New client account</h3>
            </div>
            <span className="page-shell-chip">Step {wizardStep} / 4</span>
          </div>
          <form className="admin-form" onSubmit={handleOnboardSubmit}>
            {wizardStep === 1 ? (
              <div className="settings-grid">
                <label>
                  Business name
                  <input
                    value={onboardForm.business_name}
                    onChange={(event) => setOnboardForm({ ...onboardForm, business_name: event.target.value })}
                  />
                </label>
                <label>
                  Primary contact name
                  <input
                    value={onboardForm.contact_name}
                    onChange={(event) => setOnboardForm({ ...onboardForm, contact_name: event.target.value })}
                  />
                </label>
                <label>
                  Primary email
                  <input
                    type="email"
                    value={onboardForm.primary_email}
                    onChange={(event) => setOnboardForm({ ...onboardForm, primary_email: event.target.value })}
                  />
                </label>
                <label>
                  Primary phone
                  <input
                    value={onboardForm.primary_phone}
                    onChange={(event) => setOnboardForm({ ...onboardForm, primary_phone: event.target.value })}
                  />
                </label>
              </div>
            ) : null}

            {wizardStep === 2 ? (
              <div className="admin-stack">
                <div className="settings-grid">
                  <label>
                    Owner name
                    <input
                      value={onboardForm.owner_name}
                      onChange={(event) => setOnboardForm({ ...onboardForm, owner_name: event.target.value })}
                    />
                  </label>
                  <label>
                    Owner email
                    <input
                      type="email"
                      value={onboardForm.owner_email}
                      onChange={(event) => setOnboardForm({ ...onboardForm, owner_email: event.target.value })}
                    />
                  </label>
                </div>

                <div className="admin-inline-head">
                  <h4>Additional users</h4>
                  <button
                    type="button"
                    onClick={() =>
                      setOnboardForm({
                        ...onboardForm,
                        additional_users: [
                          ...onboardForm.additional_users,
                          { name: '', email: '', role_code: 'CLIENT_STAFF' },
                        ],
                      })
                    }
                  >
                    + Add user
                  </button>
                </div>

                <div className="admin-stack">
                  {onboardForm.additional_users.map((entry, index) => (
                    <div key={`${index}-${entry.email}`} className="admin-inline-grid">
                      <input
                        placeholder="Full name"
                        value={entry.name}
                        onChange={(event) => {
                          const next = [...onboardForm.additional_users];
                          next[index] = { ...entry, name: event.target.value };
                          setOnboardForm({ ...onboardForm, additional_users: next });
                        }}
                      />
                      <input
                        type="email"
                        placeholder="Email"
                        value={entry.email}
                        onChange={(event) => {
                          const next = [...onboardForm.additional_users];
                          next[index] = { ...entry, email: event.target.value };
                          setOnboardForm({ ...onboardForm, additional_users: next });
                        }}
                      />
                      <select
                        value={entry.role_code}
                        onChange={(event) => {
                          const next = [...onboardForm.additional_users];
                          next[index] = { ...entry, role_code: event.target.value };
                          setOnboardForm({ ...onboardForm, additional_users: next });
                        }}
                      >
                        <option value="CLIENT_STAFF">Client Staff</option>
                        <option value="FINANCE_STAFF">Finance Staff</option>
                        <option value="CLIENT_OWNER">Client Owner</option>
                      </select>
                      <button
                        type="button"
                        onClick={() =>
                          setOnboardForm({
                            ...onboardForm,
                            additional_users: onboardForm.additional_users.filter((_, itemIndex) => itemIndex !== index),
                          })
                        }
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {wizardStep === 3 ? (
              <div className="settings-grid">
                <label>
                  Website
                  <input
                    value={onboardForm.website_url}
                    onChange={(event) => setOnboardForm({ ...onboardForm, website_url: event.target.value })}
                  />
                </label>
                <label>
                  Facebook
                  <input
                    value={onboardForm.facebook_url}
                    onChange={(event) => setOnboardForm({ ...onboardForm, facebook_url: event.target.value })}
                  />
                </label>
                <label>
                  Instagram
                  <input
                    value={onboardForm.instagram_url}
                    onChange={(event) => setOnboardForm({ ...onboardForm, instagram_url: event.target.value })}
                  />
                </label>
                <label>
                  WhatsApp
                  <input
                    value={onboardForm.whatsapp_number}
                    onChange={(event) => setOnboardForm({ ...onboardForm, whatsapp_number: event.target.value })}
                  />
                </label>
                <label>
                  Timezone
                  <input
                    value={onboardForm.timezone}
                    onChange={(event) => setOnboardForm({ ...onboardForm, timezone: event.target.value })}
                  />
                </label>
                <label>
                  Currency code
                  <input
                    value={onboardForm.currency_code}
                    onChange={(event) => setOnboardForm({ ...onboardForm, currency_code: event.target.value.toUpperCase() })}
                  />
                </label>
                <label>
                  Currency symbol
                  <input
                    value={onboardForm.currency_symbol}
                    onChange={(event) => setOnboardForm({ ...onboardForm, currency_symbol: event.target.value })}
                  />
                </label>
                <label>
                  Default warehouse
                  <input
                    value={onboardForm.default_location_name}
                    onChange={(event) => setOnboardForm({ ...onboardForm, default_location_name: event.target.value })}
                  />
                </label>
                <label className="field-span-2">
                  Address
                  <textarea
                    value={onboardForm.address}
                    onChange={(event) => setOnboardForm({ ...onboardForm, address: event.target.value })}
                  />
                </label>
                <label className="field-span-2">
                  Notes
                  <textarea
                    value={onboardForm.notes}
                    onChange={(event) => setOnboardForm({ ...onboardForm, notes: event.target.value })}
                  />
                </label>
              </div>
            ) : null}

            {wizardStep === 4 ? (
              <div className="admin-stack">
                <div className="settings-context">
                  <div><dt>Business</dt><dd>{onboardForm.business_name || 'Not provided'}</dd></div>
                  <div><dt>Client code</dt><dd>Generated from the business name on submit</dd></div>
                  <div><dt>Primary contact</dt><dd>{onboardForm.contact_name} / {onboardForm.primary_email}</dd></div>
                  <div><dt>Owner</dt><dd>{onboardForm.owner_name} / {onboardForm.owner_email}</dd></div>
                  <div><dt>Extra users</dt><dd>{onboardForm.additional_users.length}</dd></div>
                  <div><dt>Warehouse</dt><dd>{onboardForm.default_location_name || 'Main Warehouse'}</dd></div>
                </div>
                {potentialMatches.length ? (
                  <div className="reports-deferred">
                    <h4>Potential duplicate clients</h4>
                    <ul className="admin-match-list">
                      {potentialMatches.map((client) => (
                        <li key={client.client_id}>
                          <strong>{client.business_name}</strong> <span>{client.client_code}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="save-actions">
              {wizardStep > 1 ? (
                <button type="button" onClick={() => setWizardStep((current) => (Math.max(1, current - 1) as WizardStep))}>
                  Back
                </button>
              ) : null}
              {wizardStep < 4 ? (
                <button type="submit" disabled={!canAdvanceWizard(wizardStep)}>
                  Next
                </button>
              ) : (
                <button type="submit">Create client</button>
              )}
            </div>
          </form>
        </section>

        <section className="admin-card">
          <div className="admin-header-row">
            <div>
              <p className="eyebrow">Access Matrix</p>
              <h3>Preset roles</h3>
            </div>
          </div>
          <div className="admin-role-matrix">
            {roles.map((role) => (
              <article key={role.role_code} className="admin-role-card">
                <h4>{role.role_name}</h4>
                <p className="admin-muted">{role.description}</p>
                <ul className="admin-role-page-list">
                  {role.allowed_pages.map((page) => (
                    <li key={page}>{page}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>
      </div>

      {selectedClient && clientDraft ? (
        <div className="admin-layout">
          <section className="admin-card">
            <div className="admin-header-row">
              <div>
                <p className="eyebrow">Client Detail</p>
                <h3>{selectedClient.business_name}</h3>
              </div>
              <span className="page-shell-chip">{selectedClient.client_code}</span>
            </div>
            <form className="admin-form" onSubmit={handleClientSave}>
              <div className="settings-grid">
                <label>
                  Business name
                  <input
                    value={clientDraft.business_name}
                    onChange={(event) => setClientDraft({ ...clientDraft, business_name: event.target.value })}
                  />
                </label>
                <label>
                  Contact name
                  <input
                    value={clientDraft.contact_name}
                    onChange={(event) => setClientDraft({ ...clientDraft, contact_name: event.target.value })}
                  />
                </label>
                <label>
                  Owner name
                  <input
                    value={clientDraft.owner_name}
                    onChange={(event) => setClientDraft({ ...clientDraft, owner_name: event.target.value })}
                  />
                </label>
                <label>
                  Status
                  <select
                    value={clientDraft.status}
                    onChange={(event) => setClientDraft({ ...clientDraft, status: event.target.value })}
                  >
                    <option value="active">active</option>
                    <option value="inactive">inactive</option>
                  </select>
                </label>
                <label>
                  Email
                  <input
                    type="email"
                    value={clientDraft.email}
                    onChange={(event) => setClientDraft({ ...clientDraft, email: event.target.value })}
                  />
                </label>
                <label>
                  Phone
                  <input
                    value={clientDraft.phone}
                    onChange={(event) => setClientDraft({ ...clientDraft, phone: event.target.value })}
                  />
                </label>
                <label>
                  Website
                  <input
                    value={clientDraft.website_url}
                    onChange={(event) => setClientDraft({ ...clientDraft, website_url: event.target.value })}
                  />
                </label>
                <label>
                  WhatsApp
                  <input
                    value={clientDraft.whatsapp_number}
                    onChange={(event) => setClientDraft({ ...clientDraft, whatsapp_number: event.target.value })}
                  />
                </label>
                <label>
                  Facebook
                  <input
                    value={clientDraft.facebook_url}
                    onChange={(event) => setClientDraft({ ...clientDraft, facebook_url: event.target.value })}
                  />
                </label>
                <label>
                  Instagram
                  <input
                    value={clientDraft.instagram_url}
                    onChange={(event) => setClientDraft({ ...clientDraft, instagram_url: event.target.value })}
                  />
                </label>
                <label>
                  Timezone
                  <input
                    value={clientDraft.timezone}
                    onChange={(event) => setClientDraft({ ...clientDraft, timezone: event.target.value })}
                  />
                </label>
                <label>
                  Default warehouse
                  <input
                    value={clientDraft.default_location_name}
                    onChange={(event) => setClientDraft({ ...clientDraft, default_location_name: event.target.value })}
                  />
                </label>
                <label>
                  Currency code
                  <input
                    value={clientDraft.currency_code}
                    onChange={(event) => setClientDraft({ ...clientDraft, currency_code: event.target.value.toUpperCase() })}
                  />
                </label>
                <label>
                  Currency symbol
                  <input
                    value={clientDraft.currency_symbol}
                    onChange={(event) => setClientDraft({ ...clientDraft, currency_symbol: event.target.value })}
                  />
                </label>
                <label className="field-span-2">
                  Address
                  <textarea
                    value={clientDraft.address}
                    onChange={(event) => setClientDraft({ ...clientDraft, address: event.target.value })}
                  />
                </label>
                <label className="field-span-2">
                  Notes
                  <textarea
                    value={clientDraft.notes}
                    onChange={(event) => setClientDraft({ ...clientDraft, notes: event.target.value })}
                  />
                </label>
              </div>
              <div className="save-actions">
                <button type="submit">Save profile</button>
              </div>
            </form>

            <div className="admin-divider" />

            <div className="admin-header-row">
              <div>
                <p className="eyebrow">User Management</p>
                <h3>Tenant team</h3>
              </div>
            </div>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>User</th>
                    <th>User Code</th>
                    <th>Role</th>
                    <th>Active</th>
                    <th>Invite</th>
                    <th>Last Login</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {clientUsers.map((item) => {
                    const draft = userDrafts[item.user_id] ?? {
                      name: item.name,
                      role_code: item.role_code,
                      is_active: item.is_active,
                    };
                    return (
                      <tr key={item.user_id}>
                        <td>
                          <input
                            value={draft.name}
                            onChange={(event) =>
                              setUserDrafts({
                                ...userDrafts,
                                [item.user_id]: {
                                  ...draft,
                                  name: event.target.value,
                                },
                              })
                            }
                          />
                          <p className="admin-muted">{item.email}</p>
                        </td>
                        <td>{item.user_code}</td>
                        <td>
                          <select
                            value={draft.role_code}
                            onChange={(event) =>
                              setUserDrafts({
                                ...userDrafts,
                                [item.user_id]: {
                                  ...draft,
                                  role_code: event.target.value,
                                },
                              })
                            }
                          >
                            <option value="CLIENT_OWNER">Client Owner</option>
                            <option value="CLIENT_STAFF">Client Staff</option>
                            <option value="FINANCE_STAFF">Finance Staff</option>
                          </select>
                        </td>
                        <td>
                          <label className="admin-checkbox">
                            <input
                              type="checkbox"
                              checked={draft.is_active}
                              onChange={(event) =>
                                setUserDrafts({
                                  ...userDrafts,
                                  [item.user_id]: {
                                    ...draft,
                                    is_active: event.target.checked,
                                  },
                                })
                              }
                            />
                            <span>{draft.is_active ? 'Active' : 'Inactive'}</span>
                          </label>
                        </td>
                        <td>
                          <strong>{item.invitation_status}</strong>
                          <p className="admin-muted">{formatDateTime(item.invitation_expires_at)}</p>
                        </td>
                        <td>{formatDateTime(item.last_login_at)}</td>
                        <td>
                          <div className="admin-action-row">
                            <button type="button" onClick={() => void handleSaveUser(item.user_id)}>Save</button>
                            <button type="button" onClick={() => void handleIssueInvite(item.user_id)}>Invite</button>
                            <button type="button" onClick={() => void handleIssueReset(item.user_id)}>Reset</button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <form className="admin-form" onSubmit={handleCreateUser}>
              <div className="admin-inline-head">
                <h4>Add another user</h4>
              </div>
              <div className="admin-inline-grid">
                <input
                  placeholder="Full name"
                  value={newUserForm.name}
                  onChange={(event) => setNewUserForm({ ...newUserForm, name: event.target.value })}
                />
                <input
                  type="email"
                  placeholder="Email"
                  value={newUserForm.email}
                  onChange={(event) => setNewUserForm({ ...newUserForm, email: event.target.value })}
                />
                <select
                  value={newUserForm.role_code}
                  onChange={(event) => setNewUserForm({ ...newUserForm, role_code: event.target.value })}
                >
                  <option value="CLIENT_STAFF">Client Staff</option>
                  <option value="FINANCE_STAFF">Finance Staff</option>
                  <option value="CLIENT_OWNER">Client Owner</option>
                </select>
                <button type="submit">Add user</button>
              </div>
            </form>
          </section>

          <aside className="admin-stack">
            {credentialBundle ? (
              <section className="admin-card">
                <p className="eyebrow">Credential Hand-off</p>
                <h3>{credentialBundle.title}</h3>
                <pre className="admin-token-block">{credentialBundle.lines.join('\n')}</pre>
              </section>
            ) : null}

            <section className="admin-card">
              <p className="eyebrow">Recent Audit</p>
              <h3>Change history</h3>
              <ul className="integrations-events">
                {auditItems.map((item) => (
                  <li key={item.audit_log_id}>
                    <strong>{item.action.replaceAll('_', ' ')}</strong>
                    <p className="admin-muted">{item.entity_type} / {item.entity_id}</p>
                    <span>{formatDateTime(item.created_at)}</span>
                  </li>
                ))}
                {!auditItems.length ? (
                  <li>
                    <strong>No audit items yet</strong>
                    <p className="admin-muted">Client onboarding and user changes will show up here.</p>
                  </li>
                ) : null}
              </ul>
            </section>
          </aside>
        </div>
      ) : null}
    </div>
  );
}
