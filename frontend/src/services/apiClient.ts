/**
 * Extract CSRF token from document.cookie for state-changing calls
 */
export function getCsrfToken(): string {
  if (typeof document === 'undefined') return '';
  const match = document.cookie
    .split('; ')
    .find((row) => row.startsWith('csrf_token='));
  return match ? decodeURIComponent(match.split('=')[1]) : '';
}

/**
 * Common API client wrapper:
 * - Automatically injects 'X-CSRF-Token' header for POST/PUT/PATCH/DELETE
 * - Includes credentials ('include') so HttpOnly auth_token & csrf_token cookies are sent
 */
export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase();
  const headers = new Headers(options.headers || {});

  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const csrfToken = getCsrfToken();
    if (csrfToken && !headers.has('X-CSRF-Token')) {
      headers.set('X-CSRF-Token', csrfToken);
    }
  }

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(endpoint, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'API request failed';
    try {
      const text = await response.text();
      try {
        const errorJson = JSON.parse(text);
        errorDetail = errorJson.detail || errorJson.message || text;
      } catch {
        errorDetail = text || errorDetail;
      }
    } catch {
      // Failed reading response text
    }
    throw new Error(`${response.status}: ${errorDetail}`);
  }

  return response.json() as Promise<T>;
}
