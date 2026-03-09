const DEFAULT_SESSION_COOKIE_NAME = 'easy_ecom_session';

function stripWrappingQuotes(value: string): string {
  const trimmed = value.trim();
  if (trimmed.length >= 2) {
    const first = trimmed[0];
    const last = trimmed[trimmed.length - 1];
    if ((first === '"' && last === '"') || (first === "'" && last === "'")) {
      return trimmed.slice(1, -1).trim();
    }
  }
  return trimmed;
}

export function getSessionCookieName(rawCookieName = process.env.NEXT_PUBLIC_SESSION_COOKIE_NAME): string {
  const normalized = rawCookieName ? stripWrappingQuotes(rawCookieName) : '';
  return normalized || DEFAULT_SESSION_COOKIE_NAME;
}

export function hasUsableSessionCookie(cookieValue: string | undefined): boolean {
  if (!cookieValue) {
    return false;
  }

  const normalized = stripWrappingQuotes(cookieValue);
  return normalized.length > 0;
}

