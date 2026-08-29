const DEFAULT_API_BASE_URL = "http://localhost:8000";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? DEFAULT_API_BASE_URL;

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    signal,
  });

  if (!response.ok) {
    throw new ApiError(`Request failed: ${path}`, response.status);
  }

  return response.json() as Promise<T>;
}
