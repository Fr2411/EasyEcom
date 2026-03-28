import { apiClient } from '@/lib/api/client';

export type SignupInput = {
  business_name: string;
  name: string;
  email: string;
  phone: string;
  password: string;
};

export async function signup(payload: SignupInput) {
  return apiClient('/auth/signup', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
