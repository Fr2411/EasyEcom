'use client';

import { FormEvent, Fragment, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import { useAuth } from '@/components/auth/auth-provider';
import {
  createAdminUser,
  getAdminClient,
  getAdminUserAccess,
  listAdminAudit,
  listAdminClients,
  listAdminUsers,
  onboardAdminClient,
  setAdminUserPassword,
  updateAdminClient,
  updateAdminUser,
  updateAdminUserAccess,
} from '@/lib/api/admin';
import { ApiError, ApiNetworkError } from '@/lib/api/client';
import { getPublicEnv } from '@/lib/env';
import { isSuperAdmin } from '@/lib/rbac';
import type { SuggestedAction } from '@/types/guided-workflow';
import type {
  AdminAuditItem,
  AdminClient,
  AdminOnboardClientInput,
  AdminUser,
  AdminUserAccess,
  AdminUserAccessUpdateInput,
} from '@/types/admin';
import {
  DraftRecommendationCard,
  IntentInput,
  MatchGroupList,
  StagedActionFooter,
  SuggestedNextStep,
  WorkspaceEmpty,
} from '@/components/commerce/workspace-primitives';

type UserDraft = {
  name: string;
  role_code: string;
  is_active: boolean;
};

type AccessState = 'default' | 'allow' | 'revoke';

const ACCESS_PAGE_OPTIONS = [
  { code: 'DASHBOARD', label: 'Dashboard' },
  { code: 'CATALOG', label: 'Catalog' },
  { code: 'INVENTORY', label: 'Inventory' },
  { code: 'PURCHASES', label: 'Purchases' },
  { code: 'SALES', label: 'Sales' },
  { code: 'SALES_AGENT', label: 'Sales Agent' },
  { code: 'CUSTOMERS', label: 'Customers' },
  { code: 'FINANCE', label: 'Finance' },
  { code: 'RETURNS', label: 'Returns' },
  { code: 'REPORTS', label: 'Reports' },
  { code: 'SETTINGS', label: 'Settings' },
] as const;

const EMPTY_ONBOARD_FORM: AdminOnboardClientInput = {
  business_name: '',
  contact_name: '',
  primary_email: '',
  primary_phone: '',
  owner_name: '',
  owner_email: '',
  owner_password: '',
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

const EMPTY_TEAM_USER_FORM = {
  name: '',
  email: '',
  role_code: 'CLIENT_STAFF',
  password: '',
};

function normalize(text: string) {
  return text.trim().toLowerCase();
}

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

function adminErrorMessage(error: unknown, fallback: string) {
  const { apiBaseUrl } = getPublicEnv();

  if (error instanceof ApiError && error.status === 404) {
    return `The connected API (${apiBaseUrl}) does not have the current admin routes yet. If you are developing locally, restart the backend on the latest code or point the frontend to https://api.easy-ecom.online.`;
  }

  if (error instanceof ApiNetworkError) {
    if (apiBaseUrl.includes('localhost')) {
      return `The admin panel is trying to reach ${apiBaseUrl}. Start the local API server or change NEXT_PUBLIC_API_BASE_URL to https://api.easy-ecom.online.`;
    }

    return `The admin panel could not reach ${apiBaseUrl}. Check that the API is running and that this browser origin is allowed by CORS.`;
  }

  return error instanceof Error ? error.message : fallback;
}

function toAccessDraft(access: AdminUserAccess) {
  const overrideMap = new Map(access.overrides.map((item) => [item.page_code, item.is_allowed]));
  return Object.fromEntries(
    ACCESS_PAGE_OPTIONS.map((item) => {
      if (!overrideMap.has(item.code)) {
        return [item.code, 'default'];
      }
      return [item.code, overrideMap.get(item.code) ? 'allow' : 'revoke'];
    })
  ) as Record<string, AccessState>;
}

function buildAccessPayload(drafts: Record<string, AccessState>): AdminUserAccessUpdateInput {
  return {
    overrides: Object.entries(drafts)
      .filter(([, state]) => state !== 'default')
      .map(([page_code, state]) => ({
        page_code,
        is_allowed: state === 'allow',
      })),
  };
}

function formatAccessCodes(pageCodes: string[]) {
  return pageCodes
    .map((code) => ACCESS_PAGE_OPTIONS.find((item) => item.code === code)?.label ?? code)
    .join(', ');
}

function seedOnboardFormFromQuery(query: string): AdminOnboardClientInput {
  const trimmed = query.trim();
  const seeded: AdminOnboardClientInput = {
    ...EMPTY_ONBOARD_FORM,
  };

  if (!trimmed) {
    return seeded;
  }

  if (trimmed.includes('@')) {
    seeded.primary_email = trimmed;
    seeded.owner_email = trimmed;
    return seeded;
  }

  if (/^https?:\/\//i.test(trimmed) || (trimmed.includes('.') && !trimmed.includes(' '))) {
    seeded.website_url = trimmed.startsWith('http') ? trimmed : `https://${trimmed}`;
    return seeded;
  }

  if (/^\+?[0-9][0-9\s-]{5,}$/.test(trimmed)) {
    seeded.primary_phone = trimmed;
    seeded.whatsapp_number = trimmed;
    return seeded;
  }

  seeded.business_name = trimmed;
  return seeded;
}

function deriveAdminIntentSuggestion(
  creatingClient: boolean,
  query: string,
  clients: AdminClient[]
): SuggestedAction & { kind: 'idle' | 'existing' | 'new' } {
  if (creatingClient) {
    return {
      kind: 'new',
      title: 'New tenant draft ready',
      detail: 'Complete the staged profile below, then create the tenant when the details are ready.',
      actionLabel: 'Review before creating',
      tone: 'success',
    };
  }

  const trimmed = query.trim();
  if (!trimmed) {
    return {
      kind: 'idle',
      title: 'Start with one tenant clue',
      detail: 'Type a business name, client code, contact name, email, phone, or website. The workspace will stage the right next step.',
      actionLabel: 'Interpret tenant intent',
      tone: 'info',
    };
  }

  const lower = normalize(trimmed);
  const exact = clients.find((client) =>
    [client.business_name, client.client_code, client.contact_name, client.email, client.phone, client.website_url]
      .filter(Boolean)
      .some((value) => normalize(value) === lower)
  );

  if (exact) {
    return {
      kind: 'existing',
      title: `Exact tenant found: ${exact.business_name}`,
      detail: 'The workspace can open this tenant directly and keep the existing profile and team editable.',
      actionLabel: 'Open tenant',
      secondaryLabel: 'Review other matches',
      tone: 'success',
    };
  }

  if (clients.length > 0) {
    return {
      kind: 'existing',
      title: `We found ${clients.length} likely tenant${clients.length === 1 ? '' : 's'}`,
      detail: 'Review the closest tenant first. If none are correct, the workspace can stage a new onboarding draft from the typed clue.',
      actionLabel: 'Open top match',
      secondaryLabel: 'Start onboarding',
      tone: 'warning',
    };
  }

  return {
    kind: 'new',
    title: 'No existing tenant found',
    detail: 'A new tenant draft can be staged with the typed clue prefilled into the onboarding form.',
    actionLabel: 'Start onboarding',
    tone: 'warning',
  };
}

export function AdminWorkspace() {
  const { user, loading } = useAuth();
  const searchParams = useSearchParams();
  const searchKey = searchParams?.toString?.() ?? '';
  const [clients, setClients] = useState<AdminClient[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [selectedClient, setSelectedClient] = useState<AdminClient | null>(null);
  const [clientDraft, setClientDraft] = useState<AdminClient | null>(null);
  const [clientUsers, setClientUsers] = useState<AdminUser[]>([]);
  const [userDrafts, setUserDrafts] = useState<Record<string, UserDraft>>({});
  const [passwordDrafts, setPasswordDrafts] = useState<Record<string, string>>({});
  const [auditItems, setAuditItems] = useState<AdminAuditItem[]>([]);
  const [search, setSearch] = useState('');
  const [workspaceLoading, setWorkspaceLoading] = useState(true);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [busyLabel, setBusyLabel] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [creatingClient, setCreatingClient] = useState(() => searchParams?.get?.('mode') === 'create');
  const [onboardForm, setOnboardForm] = useState<AdminOnboardClientInput>(EMPTY_ONBOARD_FORM);
  const [teamUserForm, setTeamUserForm] = useState(EMPTY_TEAM_USER_FORM);
  const [activeAccessUserId, setActiveAccessUserId] = useState<string | null>(null);
  const [accessRecord, setAccessRecord] = useState<AdminUserAccess | null>(null);
  const [accessDrafts, setAccessDrafts] = useState<Record<string, AccessState>>({});
  const [accessLoading, setAccessLoading] = useState(false);
  const [accessError, setAccessError] = useState<string | null>(null);
  async function loadClientDirectory(currentSearch = search) {
    const response = await listAdminClients(currentSearch);
    setClients(response.items);
    if (!creatingClient && !selectedClientId && response.items[0]) {
      setSelectedClientId(response.items[0].client_id);
    }
    if (
      !creatingClient &&
      selectedClientId &&
      !response.items.some((item) => item.client_id === selectedClientId)
    ) {
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
    setPasswordDrafts(Object.fromEntries(users.items.map((item) => [item.user_id, ''])));
  }

  async function loadWorkspace() {
    setWorkspaceLoading(true);
    setWorkspaceError(null);
    try {
      const clientResponse = await listAdminClients();
      setClients(clientResponse.items);
      const firstClientId = clientResponse.items[0]?.client_id ?? null;
      if (!creatingClient && firstClientId) {
        setSelectedClientId(firstClientId);
        await loadSelectedClient(firstClientId);
      }
    } catch (error) {
      setWorkspaceError(adminErrorMessage(error, 'Unable to load the admin workspace.'));
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
    if (creatingClient || !selectedClientId || !isSuperAdmin(user?.roles)) {
      return;
    }
    void loadSelectedClient(selectedClientId);
  }, [creatingClient, selectedClientId, user]);

  useEffect(() => {
    const mode = searchParams?.get?.('mode');
    if (mode !== 'create') {
      return;
    }
    startCreateMode(seedOnboardFormFromQuery(searchParams?.get?.('intent') ?? searchParams?.get?.('q') ?? ''));
  }, [searchKey]);

  function resetMessages() {
    setWorkspaceError(null);
    setSuccessMessage(null);
  }

  function startCreateMode(seed?: Partial<AdminOnboardClientInput>) {
    resetMessages();
    setCreatingClient(true);
    setSelectedClientId(null);
    setSelectedClient(null);
    setClientDraft(null);
    setClientUsers([]);
    setUserDrafts({});
    setPasswordDrafts({});
    setAuditItems([]);
    setOnboardForm({
      ...EMPTY_ONBOARD_FORM,
      ...seed,
      additional_users: [],
    });
    setTeamUserForm(EMPTY_TEAM_USER_FORM);
    setActiveAccessUserId(null);
    setAccessRecord(null);
    setAccessDrafts({});
    setAccessError(null);
  }

  function selectExistingClient(clientId: string) {
    resetMessages();
    setCreatingClient(false);
    setSelectedClientId(clientId);
    setTeamUserForm(EMPTY_TEAM_USER_FORM);
    setActiveAccessUserId(null);
    setAccessRecord(null);
    setAccessDrafts({});
    setAccessError(null);
  }

  function createClientReady() {
    const requiredDetails = Boolean(
      onboardForm.business_name.trim() &&
        onboardForm.contact_name.trim() &&
        onboardForm.primary_email.trim() &&
        onboardForm.primary_phone.trim() &&
        onboardForm.owner_name.trim() &&
        onboardForm.owner_email.trim() &&
        onboardForm.owner_password.length >= 6
    );
    const stagedUsersReady = onboardForm.additional_users.every(
      (entry) =>
        entry.name.trim() &&
        entry.email.trim() &&
        entry.role_code.trim() &&
        entry.password.length >= 6
    );
    return requiredDetails && stagedUsersReady;
  }

  async function runSearch(query: string) {
    resetMessages();
    try {
      const trimmed = query.trim();
      const response = await listAdminClients(trimmed);
      setClients(response.items);

      if (!trimmed) {
        if (response.items[0]) {
          selectExistingClient(response.items[0].client_id);
        }
        return;
      }

      const exact = response.items.find((client) =>
        [client.business_name, client.client_code, client.contact_name, client.email, client.phone, client.website_url]
          .filter(Boolean)
          .some((value) => normalize(value) === normalize(trimmed))
      );

      if (exact) {
        selectExistingClient(exact.client_id);
        setSuccessMessage(`Opened ${exact.business_name}.`);
        return;
      }

      if (response.items.length) {
        selectExistingClient(response.items[0].client_id);
        setSuccessMessage(`Showing ${response.items.length} likely tenant${response.items.length === 1 ? '' : 's'}.`);
        return;
      }

      startCreateMode(seedOnboardFormFromQuery(trimmed));
      setSuccessMessage(`No tenant matched "${trimmed}". A new onboarding draft was staged.`);
    } catch (error) {
      setWorkspaceError(adminErrorMessage(error, 'Unable to refresh clients.'));
    }
  }

  async function handleCreateClient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!createClientReady()) {
      setWorkspaceError('Complete the required client, owner, and staged user fields before creating the tenant.');
      return;
    }

    resetMessages();
    setBusyLabel('Creating client');
    try {
      const response = await onboardAdminClient(onboardForm);
      setCreatingClient(false);
      setOnboardForm(EMPTY_ONBOARD_FORM);
      setTeamUserForm(EMPTY_TEAM_USER_FORM);
      setSuccessMessage(`Client ${response.client.business_name} was onboarded successfully.`);
      await loadWorkspace();
      setSelectedClientId(response.client.client_id);
    } catch (error) {
      setWorkspaceError(adminErrorMessage(error, 'Unable to onboard the client.'));
    } finally {
      setBusyLabel(null);
    }
  }

  function handleStageUser() {
    if (
      !teamUserForm.name.trim() ||
      !teamUserForm.email.trim() ||
      !teamUserForm.role_code.trim() ||
      teamUserForm.password.length < 6
    ) {
      setWorkspaceError('Add a name, email, role, and password before staging a tenant team user.');
      return;
    }
    resetMessages();
    setOnboardForm({
      ...onboardForm,
      additional_users: [
        ...onboardForm.additional_users,
        {
          name: teamUserForm.name,
          email: teamUserForm.email,
          role_code: teamUserForm.role_code,
          password: teamUserForm.password,
        },
      ],
    });
    setTeamUserForm(EMPTY_TEAM_USER_FORM);
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
      setWorkspaceError(adminErrorMessage(error, 'Unable to save the client profile.'));
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
      const created = await createAdminUser(selectedClient.client_id, teamUserForm);
      setClientUsers((items) => [created, ...items]);
      setUserDrafts((drafts) => ({
        ...drafts,
        [created.user_id]: {
          name: created.name,
          role_code: created.role_code,
          is_active: created.is_active,
        },
      }));
      setPasswordDrafts((drafts) => ({ ...drafts, [created.user_id]: '' }));
      setTeamUserForm(EMPTY_TEAM_USER_FORM);
      setSuccessMessage(`User ${created.name} was added under ${selectedClient.business_name}.`);
    } catch (error) {
      setWorkspaceError(adminErrorMessage(error, 'Unable to create the user.'));
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
      if (activeAccessUserId === userId) {
        void openAccessDetails(userId);
      }
    } catch (error) {
      setWorkspaceError(adminErrorMessage(error, 'Unable to update the user.'));
    } finally {
      setBusyLabel(null);
    }
  }

  async function handleSetPassword(userId: string) {
    const password = passwordDrafts[userId] ?? '';
    if (password.length < 6) {
      setWorkspaceError('Enter at least 6 characters before setting a password.');
      return;
    }

    resetMessages();
    setBusyLabel('Saving password');
    try {
      const updated = await setAdminUserPassword(userId, { password });
      setClientUsers((items) => items.map((item) => (item.user_id === updated.user_id ? updated : item)));
      setPasswordDrafts((drafts) => ({ ...drafts, [userId]: '' }));
      setSuccessMessage(`Password was updated for ${updated.name}.`);
    } catch (error) {
      setWorkspaceError(adminErrorMessage(error, 'Unable to set the password.'));
    } finally {
      setBusyLabel(null);
    }
  }

  async function openAccessDetails(userId: string) {
    if (activeAccessUserId === userId) {
      setActiveAccessUserId(null);
      setAccessRecord(null);
      setAccessDrafts({});
      setAccessError(null);
      return;
    }

    resetMessages();
    setAccessLoading(true);
    setActiveAccessUserId(userId);
    setAccessError(null);
    try {
      const access = await getAdminUserAccess(userId);
      setAccessRecord(access);
      setAccessDrafts(toAccessDraft(access));
    } catch (error) {
      setAccessRecord(null);
      setAccessDrafts({});
      setAccessError(adminErrorMessage(error, 'Unable to load access details.'));
    } finally {
      setAccessLoading(false);
    }
  }

  async function handleSaveAccess(userId: string) {
    resetMessages();
    setAccessLoading(true);
    setAccessError(null);
    try {
      const updated = await updateAdminUserAccess(userId, buildAccessPayload(accessDrafts));
      setAccessRecord(updated);
      setAccessDrafts(toAccessDraft(updated));
      setSuccessMessage('User access details were updated.');
    } catch (error) {
      setAccessError(adminErrorMessage(error, 'Unable to save access details.'));
    } finally {
      setAccessLoading(false);
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
  const adminSuggestion = deriveAdminIntentSuggestion(creatingClient, search, clients);

  if (loading || workspaceLoading) {
    return (
      <div className="admin-card">
        <p className="eyebrow">Super Admin</p>
        <h3>Loading control panel</h3>
        <p className="admin-muted">Pulling clients, users, and audit activity from the live auth foundation.</p>
      </div>
    );
  }

  if (!isSuperAdmin(user?.roles)) {
    return (
      <div className="admin-card">
        <p className="eyebrow">Access Restricted</p>
        <h3>Super admin access is required</h3>
        <p className="admin-muted">This workspace is reserved for global onboarding and tenant administration.</p>
      </div>
    );
  }

  return (
    <div className="admin-workspace">
      {workspaceError ? <p className="admin-error">{workspaceError}</p> : null}
      {successMessage ? <p className="admin-success">{successMessage}</p> : null}
      {busyLabel ? <p className="admin-muted">{busyLabel}…</p> : null}

      <section className="admin-card">
        <div className="admin-header-row">
          <div>
            <p className="eyebrow">Tenant command center</p>
            <h3>Find or stage a tenant</h3>
          </div>
        </div>
        <IntentInput
          label="Find an existing tenant or begin onboarding"
          hint="Search by business name, code, contact, email, phone, or website. The workspace will stage the strongest existing tenant or a new tenant draft."
          value={search}
          placeholder="Business, code, contact, email, phone, or website"
          submitLabel="Interpret tenant intent"
          onChange={setSearch}
          onSubmit={() => void runSearch(search)}
        >
          <span className="guided-assist-chip">Exact matches open the tenant directly</span>
          <span className="guided-assist-chip">No match stages a new onboarding draft</span>
        </IntentInput>
        <SuggestedNextStep
          suggestion={adminSuggestion}
          onPrimary={() => {
            if (potentialMatches[0]) {
              selectExistingClient(potentialMatches[0].client_id);
              return;
            }
            startCreateMode(seedOnboardFormFromQuery(search));
          }}
          onSecondary={() => startCreateMode(seedOnboardFormFromQuery(search))}
        />
        <div className="admin-toolbar-actions">
          <button type="button" onClick={() => startCreateMode(seedOnboardFormFromQuery(search))}>
            Start new tenant
          </button>
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
                  className={!creatingClient && selectedClientId === client.client_id ? 'admin-row-active' : undefined}
                  onClick={() => selectExistingClient(client.client_id)}
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
                    <WorkspaceEmpty
                      title="No tenants found"
                      message="Use the intent bar above to stage a new tenant onboarding draft."
                    />
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      {creatingClient ? (
        <div className="admin-layout">
          <section className="admin-card">
            <div className="admin-header-row">
              <div>
                <p className="eyebrow">Onboarding draft</p>
                <h3>Stage new tenant</h3>
              </div>
              <span className="page-shell-chip">Guided mode</span>
            </div>
            <DraftRecommendationCard
              title={onboardForm.business_name || onboardForm.primary_email || onboardForm.primary_phone || 'New tenant draft'}
              summary="Complete the staged profile below, then create the tenant only when every required field is ready."
            >
              <div className="settings-context">
                <div><dt>Business</dt><dd>{onboardForm.business_name || 'Not provided'}</dd></div>
                <div><dt>Owner</dt><dd>{onboardForm.owner_name || 'Not provided'}</dd></div>
                <div><dt>Primary email</dt><dd>{onboardForm.primary_email || 'Not provided'}</dd></div>
                <div><dt>Team users</dt><dd>{onboardForm.additional_users.length}</dd></div>
              </div>
            </DraftRecommendationCard>
            <form className="admin-form" onSubmit={handleCreateClient}>
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
                <label className="field-span-2">
                  Owner password
                  <input
                    type="password"
                    value={onboardForm.owner_password}
                    onChange={(event) => setOnboardForm({ ...onboardForm, owner_password: event.target.value })}
                  />
                </label>
                <label>
                  Website
                  <input
                    value={onboardForm.website_url}
                    onChange={(event) => setOnboardForm({ ...onboardForm, website_url: event.target.value })}
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
                  Timezone
                  <input
                    value={onboardForm.timezone}
                    onChange={(event) => setOnboardForm({ ...onboardForm, timezone: event.target.value })}
                  />
                </label>
                <label>
                  Default warehouse
                  <input
                    value={onboardForm.default_location_name}
                    onChange={(event) => setOnboardForm({ ...onboardForm, default_location_name: event.target.value })}
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

              <div className="admin-divider" />

              <div className="admin-header-row">
                <div>
                  <p className="eyebrow">Tenant Team</p>
                  <h3>Stage users before creation</h3>
                </div>
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Role</th>
                      <th>Password</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {onboardForm.additional_users.map((entry, index) => (
                      <tr key={`${entry.email}-${index}`}>
                        <td>{entry.name}</td>
                        <td>{entry.email}</td>
                        <td>{entry.role_code}</td>
                        <td>Saved</td>
                        <td>
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
                        </td>
                      </tr>
                    ))}
                    {!onboardForm.additional_users.length ? (
                      <tr>
                        <td colSpan={5}>
                          <p className="admin-muted">No extra users staged yet. The owner account is created from the form above.</p>
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>

              <div className="admin-inline-head">
                <h4>Add staged user</h4>
              </div>
              <div className="admin-inline-grid admin-inline-grid-wide">
                <input
                  placeholder="Full name"
                  value={teamUserForm.name}
                  onChange={(event) => setTeamUserForm({ ...teamUserForm, name: event.target.value })}
                />
                <input
                  type="email"
                  placeholder="Email"
                  value={teamUserForm.email}
                  onChange={(event) => setTeamUserForm({ ...teamUserForm, email: event.target.value })}
                />
                <select
                  value={teamUserForm.role_code}
                  onChange={(event) => setTeamUserForm({ ...teamUserForm, role_code: event.target.value })}
                >
                  <option value="CLIENT_STAFF">Client Staff</option>
                  <option value="FINANCE_STAFF">Finance Staff</option>
                  <option value="CLIENT_OWNER">Client Owner</option>
                </select>
                <input
                  type="password"
                  placeholder="Password"
                  value={teamUserForm.password}
                  onChange={(event) => setTeamUserForm({ ...teamUserForm, password: event.target.value })}
                />
                <button type="button" onClick={handleStageUser}>
                  Stage user
                </button>
              </div>

              <StagedActionFooter summary="This action only creates the tenant when all required fields are complete.">
                <button type="button" onClick={() => startCreateMode(seedOnboardFormFromQuery(search))}>
                  Reset draft
                </button>
                <button type="submit" disabled={!createClientReady()}>
                  Review before creating
                </button>
              </StagedActionFooter>
            </form>
          </section>

          <aside className="admin-stack">
            <section className="admin-card">
              <p className="eyebrow">Tenant shell preview</p>
              <h3>What will be created</h3>
              <div className="settings-context">
                <div><dt>Business</dt><dd>{onboardForm.business_name || 'Not provided'}</dd></div>
                <div><dt>Owner</dt><dd>{onboardForm.owner_name || 'Not provided'}</dd></div>
                <div><dt>Team users</dt><dd>{onboardForm.additional_users.length}</dd></div>
                <div><dt>Warehouse</dt><dd>{onboardForm.default_location_name || 'Main Warehouse'}</dd></div>
              </div>
            </section>

            <section className="admin-card">
              <p className="eyebrow">Duplicate check</p>
              <h3>Potential matches</h3>
              {potentialMatches.length ? (
                <ul className="admin-match-list">
                  {potentialMatches.map((client) => (
                    <li key={client.client_id}>
                      <strong>{client.business_name}</strong> <span>{client.client_code}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="admin-muted">No close tenant match detected from the current business name, email, or website.</p>
              )}
            </section>
          </aside>
        </div>
      ) : selectedClient && clientDraft ? (
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
                <p className="eyebrow">Tenant Team</p>
                <h3>User management</h3>
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
                    <th>Last Login</th>
                    <th>New Password</th>
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
                      <Fragment key={item.user_id}>
                        <tr>
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
                          <td>{formatDateTime(item.last_login_at)}</td>
                          <td>
                            <input
                              type="password"
                              placeholder="Minimum 6 chars"
                              value={passwordDrafts[item.user_id] ?? ''}
                              onChange={(event) =>
                                setPasswordDrafts({
                                  ...passwordDrafts,
                                  [item.user_id]: event.target.value,
                                })
                              }
                            />
                          </td>
                          <td>
                            <div className="admin-action-row">
                              <button type="button" onClick={() => void handleSaveUser(item.user_id)}>Save</button>
                              <button
                                type="button"
                                disabled={(passwordDrafts[item.user_id] ?? '').length < 6}
                                onClick={() => void handleSetPassword(item.user_id)}
                              >
                                Set password
                              </button>
                              <button type="button" onClick={() => void openAccessDetails(item.user_id)}>
                                {activeAccessUserId === item.user_id ? 'Close Access' : 'Access Details'}
                              </button>
                            </div>
                          </td>
                        </tr>
                        {activeAccessUserId === item.user_id ? (
                          <tr key={`${item.user_id}-access`}>
                            <td colSpan={7}>
                              <div className="admin-inline-access">
                                <div className="admin-inline-head">
                                  <h4>Access details for {item.name}</h4>
                                  <span className="page-shell-chip">{item.role_name}</span>
                                </div>
                                {accessError ? <p className="admin-error">{accessError}</p> : null}
                                {accessLoading ? (
                                  <p className="admin-muted">Loading access details…</p>
                                ) : accessRecord ? (
                                  <>
                                    <div className="admin-access-summary">
                                      <div>
                                        <dt>Default pages</dt>
                                        <dd>{formatAccessCodes(accessRecord.default_pages) || 'None'}</dd>
                                      </div>
                                      <div>
                                        <dt>Effective pages</dt>
                                        <dd>{formatAccessCodes(accessRecord.effective_pages) || 'None'}</dd>
                                      </div>
                                    </div>
                                    <div className="admin-access-grid">
                                      {ACCESS_PAGE_OPTIONS.map((option) => {
                                        const defaultOn = accessRecord.default_pages.includes(option.code);
                                        const state = accessDrafts[option.code] ?? 'default';
                                        return (
                                          <div key={option.code} className="admin-access-row">
                                            <div>
                                              <strong>{option.label}</strong>
                                              <p className="admin-muted">
                                                Default: {defaultOn ? 'Allowed' : 'Blocked'}
                                              </p>
                                            </div>
                                            <select
                                              value={state}
                                              onChange={(event) =>
                                                setAccessDrafts({
                                                  ...accessDrafts,
                                                  [option.code]: event.target.value as AccessState,
                                                })
                                              }
                                            >
                                              <option value="default">Use default</option>
                                              <option value="allow">Allow</option>
                                              <option value="revoke">Revoke</option>
                                            </select>
                                          </div>
                                        );
                                      })}
                                    </div>
                                    <div className="save-actions">
                                      <button type="button" onClick={() => void handleSaveAccess(item.user_id)}>
                                        Save access
                                      </button>
                                    </div>
                                  </>
                                ) : null}
                              </div>
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <form className="admin-form" onSubmit={handleCreateUser}>
              <div className="admin-inline-head">
                <h4>Add another user</h4>
              </div>
              <div className="admin-inline-grid admin-inline-grid-wide">
                <input
                  placeholder="Full name"
                  value={teamUserForm.name}
                  onChange={(event) => setTeamUserForm({ ...teamUserForm, name: event.target.value })}
                />
                <input
                  type="email"
                  placeholder="Email"
                  value={teamUserForm.email}
                  onChange={(event) => setTeamUserForm({ ...teamUserForm, email: event.target.value })}
                />
                <select
                  value={teamUserForm.role_code}
                  onChange={(event) => setTeamUserForm({ ...teamUserForm, role_code: event.target.value })}
                >
                  <option value="CLIENT_STAFF">Client Staff</option>
                  <option value="FINANCE_STAFF">Finance Staff</option>
                  <option value="CLIENT_OWNER">Client Owner</option>
                </select>
                <input
                  type="password"
                  placeholder="Password"
                  value={teamUserForm.password}
                  onChange={(event) => setTeamUserForm({ ...teamUserForm, password: event.target.value })}
                />
                <button type="submit" disabled={teamUserForm.password.length < 6}>
                  Add user
                </button>
              </div>
            </form>
          </section>

          <aside className="admin-stack">
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
      ) : (
        <section className="admin-card">
          <p className="eyebrow">Workspace Ready</p>
          <h3>Select a tenant or start onboarding</h3>
          <p className="admin-muted">Use the intent bar to open an existing tenant or stage a new one without choosing search versus create first.</p>
          <button type="button" onClick={() => startCreateMode(seedOnboardFormFromQuery(search))}>
            Start onboarding
          </button>
        </section>
      )}
    </div>
  );
}
