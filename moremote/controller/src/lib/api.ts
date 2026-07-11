import type { ServerStatus } from "../types";

const TOKEN_KEY = "mo_remote_token";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY) || "",
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

async function post<T>(path: string, body: unknown, token?: string): Promise<{ status: number; data: T }> {
  const res = await fetch(path, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(token ? { authorization: "Bearer " + token } : {}),
    },
    body: JSON.stringify(body),
  });
  const data = (await res.json().catch(() => ({}))) as T;
  return { status: res.status, data };
}

export async function getStatus(): Promise<ServerStatus> {
  const res = await fetch("/api/status", { cache: "no-store" });
  return (await res.json()) as ServerStatus;
}

export interface AuthResult {
  ok: boolean;
  token?: string;
  error?: string;
  lockoutSeconds?: number;
}

export async function setupPin(pin: string): Promise<AuthResult> {
  const { status, data } = await post<any>("/api/setup", { pin });
  if (status === 200) return { ok: true, token: data.token };
  return { ok: false, error: data.error || "error" };
}

export async function login(pin: string): Promise<AuthResult> {
  const { status, data } = await post<any>("/api/login", { pin });
  if (status === 200) return { ok: true, token: data.token };
  if (status === 423) return { ok: false, error: "locked", lockoutSeconds: data.lockoutSeconds };
  return { ok: false, error: data.error || "invalid_pin" };
}

export async function changePin(token: string, currentPin: string, newPin: string): Promise<AuthResult> {
  const { status, data } = await post<any>("/api/pin", { currentPin, newPin }, token);
  if (status === 200) return { ok: true };
  return { ok: false, error: data.error || "error" };
}

export interface ClipResult {
  kind: "text" | "image" | "empty";
  text?: string;
  dataUrl?: string;
}

export async function getClipboard(token: string): Promise<ClipResult> {
  const res = await fetch("/api/clipboard", {
    headers: { authorization: "Bearer " + token },
    cache: "no-store",
  });
  if (!res.ok) throw new Error("clipboard read failed");
  return (await res.json()) as ClipResult;
}

export async function setClipboard(token: string, text: string): Promise<void> {
  const res = await fetch("/api/clipboard", {
    method: "POST",
    headers: { "content-type": "application/json", authorization: "Bearer " + token },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error("clipboard write failed");
}

export interface FileEntry {
  name: string;
  path: string;
  isDir: boolean;
  size: number;
}
export interface FileListing {
  title: string;
  path: string | null;
  parent: string | null;
  entries: FileEntry[];
}

export async function listFiles(token: string, path?: string | null): Promise<FileListing> {
  const url = "/api/files" + (path ? "?path=" + encodeURIComponent(path) : "");
  const res = await fetch(url, { headers: { authorization: "Bearer " + token }, cache: "no-store" });
  if (!res.ok) throw new Error("list failed");
  return (await res.json()) as FileListing;
}

export function fileDownloadUrl(token: string, path: string): string {
  return "/api/files/download?path=" + encodeURIComponent(path) + "&token=" + encodeURIComponent(token);
}

export async function uploadFile(token: string, dir: string, file: File): Promise<void> {
  const url = "/api/files/upload?dir=" + encodeURIComponent(dir) + "&name=" + encodeURIComponent(file.name);
  const res = await fetch(url, {
    method: "POST",
    headers: { authorization: "Bearer " + token, "content-type": "application/octet-stream" },
    body: file,
  });
  if (!res.ok) throw new Error("upload failed");
}

export async function setClipboardImage(token: string, blob: Blob): Promise<void> {
  const res = await fetch("/api/clipboard/image", {
    method: "POST",
    headers: { authorization: "Bearer " + token, "content-type": blob.type || "image/png" },
    body: blob,
  });
  if (!res.ok) throw new Error("clipboard image write failed");
}

export type PowerAction = "lock" | "sleep" | "restart" | "shutdown" | "signout";

export async function powerAction(token: string, action: PowerAction): Promise<boolean> {
  try {
    const { status } = await post<any>("/api/power", { action }, token);
    return status === 200;
  } catch {
    return false;
  }
}

export async function logout(token: string): Promise<void> {
  try {
    await post("/api/logout", {}, token);
  } catch {
    /* ignore */
  }
  tokenStore.clear();
}
