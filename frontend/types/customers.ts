export type Customer = {
  customer_id: string;
  full_name: string;
  phone: string;
  email: string;
  address_line1: string;
  city: string;
  notes: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type CustomerListResponse = {
  items: Customer[];
};

export type CustomerMutationResponse = {
  customer: Customer;
};

export type CustomerPayload = {
  full_name: string;
  phone: string;
  email: string;
  address_line1: string;
  city: string;
  notes: string;
};
