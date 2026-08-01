import assert from "node:assert/strict";
import {uploadFile} from "../src/lib/api.ts";

const values = new Map<string, string>();
Object.defineProperty(globalThis, "localStorage", { configurable: true, value: {
  getItem: (key: string) => values.get(key) ?? null,
  setItem: (key: string, value: string) => { values.set(key, value); },
  removeItem: (key: string) => { values.delete(key); },
}});

const calls: string[] = [];
let chunk = 0;
const originalFetch = globalThis.fetch;
globalThis.fetch = async (input) => {
  const url = String(input);
  calls.push(url);
  if (url.endsWith("/api/files/upload/start"))
    return Response.json({id: "upload-1", offset: 0, chunkBytes: 4});
  if (url.includes("/api/files/upload/chunk")) {
    chunk++;
    if (chunk === 1) throw new TypeError("response lost after server accepted bytes");
    return Response.json({offset: 6});
  }
  if (url.includes("/api/files/upload/status")) return Response.json({offset: 4});
  if (url.endsWith("/api/files/upload/commit")) return Response.json({ok: true, saved: "report.bin"});
  throw new Error("unexpected request " + url);
};

try {
  const progress: number[] = [];
  const file = new File(["abcdef"], "report.bin", {lastModified: 1234});
  await uploadFile("access", "/tmp", file, sent => progress.push(sent));
  assert.deepEqual(progress, [0, 4, 6], "client resumes at the server offset after a lost response");
  assert.equal(chunk, 2, "accepted first chunk is not uploaded twice");
  assert.equal(calls.filter(url => url.includes("upload/status")).length, 1,
    "a failed chunk consults one authoritative server offset");
  assert.equal(values.has("mo_remote_pending_upload_v2"), false,
    "atomic commit clears the persisted resume marker");
} finally {
  globalThis.fetch = originalFetch;
}

console.log("PASS: chunk upload resumes from the authoritative offset and commits once");
