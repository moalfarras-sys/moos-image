import type { ServerStatus } from "../types";

const TOKEN_KEY = "mo_remote_token";
const DEVICE_ID_KEY = "mo_remote_device_id";
const DEVICE_TOKEN_KEY = "mo_remote_device_token";
const CONTROL_REQUEST_TIMEOUT_MS = 15_000;

const storageGet = (key: string) => { try { return localStorage.getItem(key) || ""; } catch { return ""; } };
const storageSet = (key: string, value: string) => { try { localStorage.setItem(key, value); } catch { /* private mode */ } };
const storageRemove = (key: string) => { try { localStorage.removeItem(key); } catch { /* private mode */ } };

export const tokenStore = {
  get: () => storageGet(TOKEN_KEY),
  set: (t: string) => storageSet(TOKEN_KEY, t),
  clear: () => storageRemove(TOKEN_KEY),
};

export const deviceStore = {
  get: () => ({
    id: storageGet(DEVICE_ID_KEY),
    token: storageGet(DEVICE_TOKEN_KEY),
  }),
  set: (id: string, token: string) => {
    storageSet(DEVICE_ID_KEY, id);
    storageSet(DEVICE_TOKEN_KEY, token);
  },
  clear: () => {
    storageRemove(DEVICE_ID_KEY);
    storageRemove(DEVICE_TOKEN_KEY);
  },
};

/** Bound short control-plane requests without imposing a deadline on file upload or media. */
export async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs = CONTROL_REQUEST_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const upstream = init.signal;
  const relayAbort = () => controller.abort(upstream?.reason);
  if (upstream?.aborted) relayAbort();
  else upstream?.addEventListener("abort", relayAbort, { once: true });
  const timeout = globalThis.setTimeout(() => {
    controller.abort(new DOMException("control request timed out", "TimeoutError"));
  }, timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    globalThis.clearTimeout(timeout);
    upstream?.removeEventListener("abort", relayAbort);
  }
}

async function post<T>(path: string, body: unknown, token?: string): Promise<{ status: number; data: T }> {
  const res = await fetchWithTimeout(path, {
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
  const res = await fetchWithTimeout("/api/status", { cache: "no-store" });
  if (!res.ok) throw new Error(`status failed: ${res.status}`);
  return (await res.json()) as ServerStatus;
}

export interface AuthResult {
  ok: boolean;
  token?: string;
  error?: string;
  lockoutSeconds?: number;
  deviceId?: string;
  deviceToken?: string;
}

export async function setupPin(pin: string, trustDevice = false, deviceName = ""): Promise<AuthResult> {
  const { status, data } = await post<any>("/api/setup", { pin, trustDevice, deviceName });
  if (status === 200) return { ok: true, token: data.token, deviceId: data.deviceId, deviceToken: data.deviceToken };
  return { ok: false, error: data.error || "error" };
}

export async function login(pin: string, trustDevice = false, deviceName = ""): Promise<AuthResult> {
  const { status, data } = await post<any>("/api/login", { pin, trustDevice, deviceName });
  if (status === 200) return { ok: true, token: data.token, deviceId: data.deviceId, deviceToken: data.deviceToken };
  if (status === 423) return { ok: false, error: "locked", lockoutSeconds: data.lockoutSeconds };
  return { ok: false, error: data.error || "invalid_pin" };
}

export async function validateSession(token: string): Promise<boolean> {
  const res = await fetchWithTimeout("/api/session", {
    cache: "no-store", headers: { authorization: "Bearer " + token },
  });
  if (res.status === 401) return false;
  if (!res.ok) throw new Error(`session validation failed: ${res.status}`);
  return true;
}

export async function resumeTrustedDevice(deviceId: string, deviceToken: string): Promise<AuthResult> {
  const { status, data } = await post<any>("/api/devices/resume", { deviceId, deviceToken });
  // Only a rejected credential may forget this device. An unavailable server is
  // recoverable and must not turn a brief outage into another PIN enrollment.
  if (status !== 200 && status !== 401 && status !== 403)
    throw new Error(`device resume failed: ${status}`);
  return status === 200 ? { ok: true, token: data.token } : { ok: false, error: data.error || "untrusted_device" };
}

export interface TrustedDeviceInfo {
  id: string;
  name: string;
  createdUnix: number;
  lastUsedUnix: number;
  expiresUnix: number;
  current: boolean;
}

export async function listTrustedDevices(token: string): Promise<TrustedDeviceInfo[]> {
  const res = await fetchWithTimeout("/api/devices", {
    cache: "no-store", headers: { authorization: "Bearer " + token },
  });
  if (!res.ok) throw new Error("device inventory failed");
  return ((await res.json()) as { devices?: TrustedDeviceInfo[] }).devices || [];
}

export async function revokeTrustedDevice(token: string, deviceId: string): Promise<boolean> {
  const { status } = await post("/api/devices/revoke", { deviceId }, token);
  return status === 200;
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
  const res = await fetchWithTimeout("/api/clipboard", {
    headers: { authorization: "Bearer " + token },
    cache: "no-store",
  });
  if (!res.ok) throw new Error("clipboard read failed");
  return (await res.json()) as ClipResult;
}

export async function setClipboard(token: string, text: string): Promise<void> {
  const res = await fetchWithTimeout("/api/clipboard", {
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
  truncated?: boolean;
}

export async function listFiles(token: string, path?: string | null): Promise<FileListing> {
  const url = "/api/files" + (path ? "?path=" + encodeURIComponent(path) : "");
  const res = await fetch(url, { headers: { authorization: "Bearer " + token }, cache: "no-store" });
  if (!res.ok) throw new Error("list failed");
  return (await res.json()) as FileListing;
}

export async function fileDownloadUrl(token: string, path: string): Promise<string> {
  const { status, data } = await post<{ ticket?: string }>("/api/files/download-ticket", { path }, token);
  if (status !== 200 || !data.ticket) throw new Error("download ticket failed");
  return "/api/files/download?ticket=" + encodeURIComponent(data.ticket);
}

export async function audioStreamUrl(token: string): Promise<string> {
  const { status, data } = await post<{ ticket?: string }>("/api/audio/ticket", {}, token);
  if (status !== 200 || !data.ticket) throw new Error("audio ticket failed");
  return "api/audio/stream.webm?ticket=" + encodeURIComponent(data.ticket);
}

interface PendingUpload {
  id: string;
  dir: string;
  name: string;
  size: number;
  lastModified: number;
  fingerprint: string;
  chunkBytes: number;
}
const PENDING_UPLOAD_KEY = "mo_remote_pending_upload_v2";

function readPendingUpload(): PendingUpload | null {
  try { return JSON.parse(localStorage.getItem(PENDING_UPLOAD_KEY) || "null") as PendingUpload | null; }
  catch { return null; }
}
function writePendingUpload(value: PendingUpload | null) {
  try {
    if (value) localStorage.setItem(PENDING_UPLOAD_KEY, JSON.stringify(value));
    else localStorage.removeItem(PENDING_UPLOAD_KEY);
  } catch { /* private mode: this run still resumes in memory */ }
}

async function uploadFingerprint(file: File): Promise<string> {
  const sampleBytes = 64 * 1024;
  const first = new Uint8Array(await file.slice(0, sampleBytes).arrayBuffer());
  const lastStart = Math.max(first.length, file.size - sampleBytes);
  const last = new Uint8Array(await file.slice(lastStart).arrayBuffer());
  const meta = new TextEncoder().encode(`${file.name}\0${file.size}\0${file.lastModified}\0`);
  const input = new Uint8Array(meta.length + first.length + last.length);
  input.set(meta); input.set(first, meta.length); input.set(last, meta.length + first.length);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", input));
  return Array.from(digest, byte => byte.toString(16).padStart(2, "0")).join("");
}

async function uploadStatus(token: string, id: string): Promise<number> {
  const res = await fetchWithTimeout("/api/files/upload/status?id=" + encodeURIComponent(id), {
    cache: "no-store", headers: { authorization: "Bearer " + token },
  });
  if (!res.ok) throw new Error("upload session unavailable");
  return Number(((await res.json()) as { offset?: number }).offset || 0);
}

export async function uploadFile(token: string, dir: string, file: File,
  onProgress?: (sent: number, total: number) => void): Promise<void> {
  const fingerprint = await uploadFingerprint(file);
  let pending = readPendingUpload();
  const matches = pending && pending.dir === dir && pending.name === file.name
    && pending.size === file.size && pending.lastModified === file.lastModified
    && pending.fingerprint === fingerprint;
  let offset = 0;
  if (matches && pending) {
    try { offset = await uploadStatus(token, pending.id); }
    catch { pending = null; writePendingUpload(null); }
  }
  if (!pending) {
    const { status, data } = await post<{ id?: string; offset?: number; chunkBytes?: number }>(
      "/api/files/upload/start", { dir, name: file.name, size: file.size }, token);
    if (status !== 200 || !data.id || !data.chunkBytes) throw new Error("upload start failed");
    pending = { id: data.id, dir, name: file.name, size: file.size,
      lastModified: file.lastModified, fingerprint, chunkBytes: data.chunkBytes };
    offset = Number(data.offset || 0);
    writePendingUpload(pending);
  }
  onProgress?.(offset, file.size);
  while (offset < file.size) {
    const end = Math.min(file.size, offset + pending.chunkBytes);
    const chunk = file.slice(offset, end);
    let advanced = false;
    for (let attempt = 0; attempt < 3 && !advanced; attempt++) {
      try {
        const res = await fetchWithTimeout(
          `/api/files/upload/chunk?id=${encodeURIComponent(pending.id)}&offset=${offset}`,
          { method: "PATCH", headers: { authorization: "Bearer " + token,
            "content-type": "application/octet-stream" }, body: chunk }, 180_000);
        const data = (await res.json().catch(() => ({}))) as { offset?: number };
        if (res.ok || res.status === 409) {
          const next = Number(data.offset);
          if (Number.isFinite(next) && next > offset && next <= file.size) {
            offset = next; advanced = true;
          }
        }
      } catch { /* query the authoritative offset below */ }
      if (!advanced) {
        try {
          const serverOffset = await uploadStatus(token, pending.id);
          if (serverOffset > offset && serverOffset <= file.size) {
            offset = serverOffset; advanced = true;
          }
        } catch { /* retry this chunk */ }
      }
    }
    if (!advanced) throw new Error("upload interrupted; select the same file to resume");
    onProgress?.(offset, file.size);
  }
  const { status } = await post("/api/files/upload/commit", { id: pending.id }, token);
  if (status !== 200) throw new Error("upload commit failed");
  writePendingUpload(null);
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
  deviceStore.clear();
}
