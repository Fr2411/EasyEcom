'use client';

import { useEffect, useMemo, useState } from 'react';
import { ApiError } from '@/lib/api/client';
import { createAdminTenant, createAdminUser, getAdminAudit, getAdminRoles, getAdminUsers, setAdminUserRoles, updateAdminUser } from '@/lib/api/admin';
import type { AdminUser } from '@/types/admin';
import { useAuth } from '@/components/auth/auth-provider';

const ADMIN_ROLES = new Set(['SUPER_ADMIN', 'CLIENT_OWNER', 'CLIENT_MANAGER']);

type TenantFormState = {
  business_name: string;
  owner_name: string;
  owner_email: string;
  owner_password: string;
  currency_code: string;
};

const defaultTenantForm: TenantFormState = {
  business_name: '',
  owner_name: '',
  owner_email: '',
  owner_password: '',
  currency_code: 'USD',
};

type FormState = {
  client_id?: string;
  name: string;
  email: string;
  password: string;
  role_codes: string[];
  is_active: boolean;
};

const defaultForm: FormState = {
  client_id: '',
  name: '',
  email: '',
  password: '',
  role_codes: ['CLIENT_EMPLOYEE'],
  is_active: true,
};

export function AdminWorkspace() {
  const { user } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [auditMessage, setAuditMessage] = useState('');
  const [search, setSearch] = useState('');
  const [form, setForm] = useState<FormState>(defaultForm);
  const [tenantForm, setTenantForm] = useState<TenantFormState>(defaultTenantForm);

  const canAccess = useMemo(() => Boolean(user?.roles?.some((role) => ADMIN_ROLES.has(role))), [user?.roles]);
  const isSuperAdmin = useMemo(() => Boolean(user?.roles?.includes('SUPER_ADMIN')), [user?.roles]);

  async function loadData() {
    setLoading(true);
    setError('');
    try {
      const [usersRes, rolesRes, auditRes] = await Promise.all([getAdminUsers(), getAdminRoles(), getAdminAudit()]);
      setUsers(usersRes.items);
      setRoles(rolesRes.roles);
      if (!auditRes.supported) {
        setAuditMessage(auditRes.deferred_reason);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError('Access denied. You need an admin role for this tenant.');
      } else {
        setError('Unable to load admin data. Please retry.');
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (canAccess) {
      void loadData();
    } else {
      setLoading(false);
    }
  }, [canAccess]);

  async function onCreateUser(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    try {
      const payload = isSuperAdmin
        ? form
        : { ...form, client_id: undefined };
      await createAdminUser(payload);
      setForm(defaultForm);
      await loadData();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Create user failed: ${err.message}`);
      } else {
        setError('Create user failed.');
      }
    }
  }



  async function onCreateTenant(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    try {
      const created = await createAdminTenant(tenantForm);
      setTenantForm(defaultTenantForm);
      setForm((prev) => ({ ...prev, client_id: created.client_id }));
      await loadData();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Create tenant failed: ${err.message}`);
      } else {
        setError('Create tenant failed.');
      }
    }
  }

  async function onToggleActive(item: AdminUser) {
    await updateAdminUser(item.user_id, { is_active: !item.is_active });
    await loadData();
  }

  async function onRoleChange(item: AdminUser, roleCode: string) {
    const nextRoles = item.roles.includes(roleCode)
      ? item.roles.filter((role) => role !== roleCode)
      : [...item.roles, roleCode];
    if (nextRoles.length === 0) {
      return;
    }
    await setAdminUserRoles(item.user_id, nextRoles);
    await loadData();
  }

  const filteredUsers = users.filter((item) => {
    const q = search.trim().toLowerCase();
    if (!q) {
      return true;
    }
    return item.name.toLowerCase().includes(q) || item.email.toLowerCase().includes(q);
  });

  if (!canAccess) {
    return (
      <div className="admin-card" data-testid="admin-access-denied">
        <h3>Admin access denied</h3>
        <p>Your account does not have permission to manage users and roles.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="admin-card" data-testid="admin-loading">
        <h3>Loading admin workspace…</h3>
      </div>
    );
  }

  return (
    <div className="admin-layout">
      <section className="admin-card">
        <div className="admin-header-row">
          <h3>Tenant users</h3>
          <input aria-label="Search users" placeholder="Search by name or email" value={search} onChange={(event) => setSearch(event.target.value)} />
        </div>
        {error ? <p className="admin-error">{error}</p> : null}
        {filteredUsers.length === 0 ? (
          <p data-testid="admin-empty-state">No users found for this tenant.</p>
        ) : (
          <table className="admin-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Status</th>
                <th>Roles</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((item) => (
                <tr key={item.user_id}>
                  <td>{item.name}</td>
                  <td>{item.email}</td>
                  <td>{item.is_active ? 'Active' : 'Inactive'}</td>
                  <td>
                    <div className="admin-role-list">
                      {roles.map((role) => (
                        <label key={`${item.user_id}-${role}`}>
                          <input type="checkbox" checked={item.roles.includes(role)} onChange={() => void onRoleChange(item, role)} />
                          {role}
                        </label>
                      ))}
                    </div>
                  </td>
                  <td>
                    <button type="button" onClick={() => void onToggleActive(item)}>
                      {item.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="admin-card">
        {isSuperAdmin ? (
          <>
            <h3>Create business tenant</h3>
            <form className="admin-form" onSubmit={onCreateTenant}>
              <label>
                Business name
                <input required value={tenantForm.business_name} onChange={(event) => setTenantForm((prev) => ({ ...prev, business_name: event.target.value }))} />
              </label>
              <label>
                Owner name
                <input required value={tenantForm.owner_name} onChange={(event) => setTenantForm((prev) => ({ ...prev, owner_name: event.target.value }))} />
              </label>
              <label>
                Owner email
                <input required type="email" value={tenantForm.owner_email} onChange={(event) => setTenantForm((prev) => ({ ...prev, owner_email: event.target.value }))} />
              </label>
              <label>
                Owner password
                <input required minLength={8} type="password" value={tenantForm.owner_password} onChange={(event) => setTenantForm((prev) => ({ ...prev, owner_password: event.target.value }))} />
              </label>
              <label>
                Currency code
                <input required minLength={3} maxLength={3} value={tenantForm.currency_code} onChange={(event) => setTenantForm((prev) => ({ ...prev, currency_code: event.target.value.toUpperCase() }))} />
              </label>
              <button type="submit">Create Business</button>
            </form>
            <hr />
          </>
        ) : null}
        <h3>Add user</h3>
        <form className="admin-form" onSubmit={onCreateUser}>
          {isSuperAdmin ? (
            <label>
              Client ID
              <input required value={form.client_id || ''} onChange={(event) => setForm((prev) => ({ ...prev, client_id: event.target.value }))} />
            </label>
          ) : null}
          <label>
            Full name
            <input required value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
          </label>
          <label>
            Email
            <input required type="email" value={form.email} onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))} />
          </label>
          <label>
            Password
            <input required minLength={8} type="password" value={form.password} onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))} />
          </label>
          <label>
            Default role
            <select value={form.role_codes[0]} onChange={(event) => setForm((prev) => ({ ...prev, role_codes: [event.target.value] }))}>
              {roles.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </select>
          </label>
          <label className="admin-checkbox">
            <input type="checkbox" checked={form.is_active} onChange={(event) => setForm((prev) => ({ ...prev, is_active: event.target.checked }))} />
            Active user
          </label>
          <button type="submit">Add User</button>
        </form>
        {auditMessage ? <p className="admin-muted">Audit visibility: {auditMessage}</p> : null}
      </section>
    </div>
  );
}
