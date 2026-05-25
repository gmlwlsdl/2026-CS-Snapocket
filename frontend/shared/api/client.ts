export const BASE_URL =
  typeof window === "undefined"
    ? (process.env.API_BASE_URL ?? "http://localhost:8000") // SSR: Next.js 서버 → FastAPI 직접
    : "/api"; // 브라우저: Next.js 서버를 거쳐 프록시

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly errorCode?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

export function saveAccessToken(token: string): void {
  localStorage.setItem("access_token", token);
  if (typeof window !== "undefined") {
    // 7일간 유지되는 access_token 쿠키 생성
    document.cookie = `access_token=${token}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax; Secure`;
  }
}

export function clearAccessToken(): void {
  localStorage.removeItem("access_token");
  if (typeof window !== "undefined") {
    // access_token 쿠키 즉시 소멸
    document.cookie = "access_token=; path=/; max-age=0; SameSite=Lax; Secure";
  }
}

function redirectToLogin(): never {
  clearAccessToken();
  if (typeof window !== "undefined") {
    window.location.href = "/login";
  }
  throw new ApiError(401, "Unauthorized");
}

/** 바이너리 응답을 받아 Blob Object URL을 반환. 사용 후 URL.revokeObjectURL() 호출 필요. */
export async function apiFetchBlobUrl(path: string): Promise<string> {
  const headers = new Headers();
  const token = getAccessToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${BASE_URL}${path}`, { headers });

  if (res.status === 401) redirectToLogin();
  if (!res.ok) throw new ApiError(res.status, res.statusText);

  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function apiClient<T>(
  path: string,
  options: RequestInit & { requireAuth?: boolean } = {}
): Promise<ApiResponse<T>> {
  const { requireAuth = false, headers: rawHeaders, ...fetchOptions } = options;

  const headers = new Headers(rawHeaders as HeadersInit | undefined);
  // FormData는 브라우저가 boundary를 포함한 Content-Type을 자동 설정하므로 제외
  if (!headers.has("Content-Type") && !(fetchOptions.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (requireAuth) {
    const token = getAccessToken();
    if (!token) redirectToLogin();
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...fetchOptions,
    headers,
  });

  if (res.status === 401) redirectToLogin();

  const body = await res.json().catch(() => null) as (ApiResponse<T> & { error_code?: string }) | null;

  if (!res.ok) {
    throw new ApiError(
      res.status,
      body?.message ?? res.statusText,
      body?.error_code
    );
  }

  if (!body) throw new ApiError(500, "Empty response");

  return body;
}
