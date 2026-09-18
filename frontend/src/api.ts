export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers
    }
  });
  if (!response.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const body = (await response.json()) as { detail?: unknown };
      message = errorDetail(body.detail, message);
    } catch {
      // The fallback message is intentionally human-readable.
    }
    if (response.status === 401 && path !== "/auth/login") {
      window.dispatchEvent(new Event("xassemble:unauthorized"));
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function download(path: string, init?: RequestInit): Promise<void> {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers }
  });
  if (!response.ok) {
    let message = "The document could not be downloaded.";
    try {
      const body = (await response.json()) as { detail?: unknown };
      message = errorDetail(body.detail, message);
    } catch {
      // Keep the useful fallback.
    }
    if (response.status === 401) window.dispatchEvent(new Event("xassemble:unauthorized"));
    throw new ApiError(message, response.status);
  }
  const disposition = response.headers.get("content-disposition") ?? "";
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] ?? "download";
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function errorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(item => {
    const field = Array.isArray(item?.loc) ? item.loc.filter((part: unknown) => part !== "body").join(".") : "Request";
    return `${field}: ${typeof item?.msg === "string" ? item.msg : "Invalid value"}`;
  }).join("; ") || fallback;
  return fallback;
}
