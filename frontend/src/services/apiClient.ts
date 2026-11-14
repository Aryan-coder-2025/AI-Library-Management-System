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

  // Inject patron BYOK multi-provider keys if configured (Groq, OpenAI, Anthropic, Gemini)
  if (typeof window !== 'undefined') {
    const groqKey = localStorage.getItem('patron_custom_groq_key');
    if (groqKey && !headers.has('X-Groq-API-Key')) {
      headers.set('X-Groq-API-Key', groqKey.trim());
    }
    const openaiKey = localStorage.getItem('patron_custom_openai_key');
    if (openaiKey && !headers.has('X-OpenAI-API-Key')) {
      headers.set('X-OpenAI-API-Key', openaiKey.trim());
    }
    const anthropicKey = localStorage.getItem('patron_custom_anthropic_key');
    if (anthropicKey && !headers.has('X-Anthropic-API-Key')) {
      headers.set('X-Anthropic-API-Key', anthropicKey.trim());
    }
    const geminiKey = localStorage.getItem('patron_custom_gemini_key');
    if (geminiKey && !headers.has('X-Gemini-API-Key')) {
      headers.set('X-Gemini-API-Key', geminiKey.trim());
    }
  }

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
        if (Array.isArray(errorJson.detail)) {
          errorDetail = errorJson.detail
            .map((d: any) => (d && typeof d === 'object' && d.msg ? d.msg : String(d)))
            .join('; ');
        } else if (typeof errorJson.detail === 'object' && errorJson.detail !== null) {
          errorDetail = JSON.stringify(errorJson.detail);
        } else {
          errorDetail = errorJson.detail || errorJson.message || text;
        }
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
