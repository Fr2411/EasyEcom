import { describe, expect, test } from 'vitest';
import { API_BASE_URL } from '../lib/api';

describe('api config', () => {
  test('has api base url', () => {
    expect(API_BASE_URL.length).toBeGreaterThan(0);
  });
});
