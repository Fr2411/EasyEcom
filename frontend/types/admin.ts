export type AdminUser = {
  user_id: string;
  client_id: string;
  name: string;
  email: string;
  is_active: boolean;
  created_at: string;
  roles: string[];
};

export type AdminUsersResponse = { items: AdminUser[] };
export type AdminRolesResponse = { roles: string[] };
export type AdminAuditResponse = { supported: boolean; deferred_reason: string; items: Array<Record<string, string>> };

export type AdminTenantCreateResponse = { client_id: string; business_name: string; owner_user: AdminUser };
