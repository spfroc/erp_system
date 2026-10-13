import "@testing-library/jest-dom/vitest";
import "fake-indexeddb/auto";
import { beforeEach, vi } from "vitest";

import { seedData } from "../seed";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/api/auth/login/")) {
      return new Response(JSON.stringify({ data: seedData.users[0] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.includes("/api/auth/me/")) {
      return new Response(JSON.stringify({ data: seedData.users[0] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.includes("/api/auth/logout/") || url.includes("/api/audit/sensitive-access/")) {
      return new Response(JSON.stringify({ data: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.includes("/api/app-data/") && (!init?.method || init.method === "GET")) {
      return new Response(JSON.stringify({ data: seedData }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : {};
    if (init?.method === "PUT" && body.partial) {
      return new Response(JSON.stringify({ ok: true, partial: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(JSON.stringify({ data: init?.method === "PUT" ? { ...seedData, ...body.data } : null }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }));
});
