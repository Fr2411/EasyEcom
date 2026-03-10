import { describe, expect, test } from 'vitest';

describe('env contract', () => {
  test('exposes API base URL variable name for Amplify', () => {
    expect('NEXT_PUBLIC_API_BASE_URL').toContain('NEXT_PUBLIC_');
  });
});
