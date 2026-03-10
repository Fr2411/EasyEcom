export type BusinessProfile = {
  client_id: string;
  business_name: string;
  display_name: string;
  phone: string;
  email: string;
  address: string;
  currency_code: string;
  timezone: string;
  tax_registration_no: string;
  logo_upload_supported: boolean;
  logo_upload_deferred_reason: string;
};

export type Preferences = {
  low_stock_threshold: number;
  default_sales_note: string;
  default_inventory_adjustment_reasons: string[];
  default_payment_terms_days: number;
  active_usage: {
    low_stock_threshold: boolean;
    default_sales_note: boolean;
    default_inventory_adjustment_reasons: boolean;
    default_payment_terms_days: boolean;
  };
};

export type Sequences = {
  sales_prefix: string;
  returns_prefix: string;
  purchases_prefix: string;
  active_usage: {
    sales_prefix: boolean;
    returns_prefix: boolean;
    purchases_prefix: boolean;
  };
};

export type TenantContext = {
  client_id: string;
  business_name: string;
  status: string;
  currency_code: string;
};
