export type SettingsTenantContext = {
  client_id: string;
  business_name: string;
  status: string;
  currency_code: string;
};

export type SettingsProfile = {
  business_name: string;
  contact_name: string;
  owner_name: string;
  email: string;
  phone: string;
  address: string;
  website_url: string;
  whatsapp_number: string;
  timezone: string;
  currency_code: string;
  currency_symbol: string;
  notes: string;
};

export type SettingsDefaults = {
  default_location_name: string;
  low_stock_threshold: number;
  allow_backorder: boolean;
  require_discount_approval: boolean;
};

export type SettingsPrefixes = {
  sales_prefix: string;
  purchases_prefix: string;
  returns_prefix: string;
};

export type SettingsWorkspace = {
  tenant_context: SettingsTenantContext;
  profile: SettingsProfile;
  defaults: SettingsDefaults;
  prefixes: SettingsPrefixes;
};

export type SettingsWorkspaceUpdatePayload = {
  profile: SettingsProfile;
  defaults: SettingsDefaults;
  prefixes: SettingsPrefixes;
};
