export type AdminRole = {
  role_code: string;
  role_name: string;
  description: string;
  allowed_pages: string[];
};

export type AdminRolesResponse = {
  items: AdminRole[];
};

export type AdminAuditItem = {
  audit_log_id: string;
  client_id: string | null;
  entity_type: string;
  entity_id: string;
  action: string;
  actor_user_id: string | null;
  created_at: string;
  metadata_json: Record<string, unknown> | null;
};

export type AdminAuditResponse = {
  items: AdminAuditItem[];
};

export type AdminClient = {
  client_id: string;
  client_code: string;
  business_name: string;
  contact_name: string;
  owner_name: string;
  email: string;
  phone: string;
  address: string;
  website_url: string;
  facebook_url: string;
  instagram_url: string;
  whatsapp_number: string;
  status: string;
  notes: string;
  timezone: string;
  currency_code: string;
  currency_symbol: string;
  default_location_name: string;
  created_at: string;
  updated_at: string;
};

export type AdminClientsResponse = {
  items: AdminClient[];
};

export type AdminUser = {
  user_id: string;
  user_code: string;
  client_id: string;
  client_code: string;
  name: string;
  email: string;
  role_code: string;
  role_name: string;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
};

export type AdminUsersResponse = {
  items: AdminUser[];
};

export type AdminUserAccessOverride = {
  page_code: string;
  is_allowed: boolean;
};

export type AdminUserAccess = {
  user_id: string;
  role_code: string;
  default_pages: string[];
  effective_pages: string[];
  overrides: AdminUserAccessOverride[];
};

export type AdminOnboardUserInput = {
  name: string;
  email: string;
  role_code: string;
  password: string;
};

export type AdminOnboardClientInput = {
  business_name: string;
  contact_name: string;
  primary_email: string;
  primary_phone: string;
  owner_name: string;
  owner_email: string;
  owner_password: string;
  address: string;
  website_url: string;
  facebook_url: string;
  instagram_url: string;
  whatsapp_number: string;
  notes: string;
  timezone: string;
  currency_code: string;
  currency_symbol: string;
  default_location_name: string;
  additional_users: AdminOnboardUserInput[];
};

export type AdminOnboardResponse = {
  client: AdminClient;
  users: AdminUser[];
  warnings: string[];
};

export type AdminClientUpdateInput = Partial<
  Pick<
    AdminClient,
    | 'business_name'
    | 'contact_name'
    | 'owner_name'
    | 'email'
    | 'phone'
    | 'address'
    | 'website_url'
    | 'facebook_url'
    | 'instagram_url'
    | 'whatsapp_number'
    | 'notes'
    | 'timezone'
    | 'currency_code'
    | 'currency_symbol'
    | 'status'
    | 'default_location_name'
  >
>;

export type AdminUserCreateInput = {
  name: string;
  email: string;
  role_code: string;
  password: string;
};

export type AdminUserUpdateInput = {
  name?: string;
  role_code?: string;
  is_active?: boolean;
};

export type AdminUserPasswordSetInput = {
  password: string;
};

export type AdminUserAccessUpdateInput = {
  overrides: AdminUserAccessOverride[];
};
