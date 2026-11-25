import { describe, expect, it, vi } from "vitest";
import { api, ApiError, request } from "./api";
import { categoryOf, fmt, shortStation } from "./format";

describe("AQI helpers", () => {
  it.each([[10, "Good"], [30, "Good"], [45, "Satisfactory"], [75, "Moderate"], [100, "Poor"], [200, "Very Poor"], [400, "Severe"]])(
    "categorises %s µg/m³ as %s", (v, cat) => expect(categoryOf(v)).toBe(cat));
  it("returns null for missing values", () => {
    expect(categoryOf(null)).toBeNull();
    expect(categoryOf(Number.NaN)).toBeNull();
  });
});

describe("formatting", () => {
  it("formats in IST regardless of the machine timezone", () => {
    expect(fmt.time("2026-11-19T17:00:00Z")).toBe("22:30");
    expect(fmt.dateTime("2026-11-19T17:00:00Z")).toContain("IST");
  });
  it("handles empty values", () => {
    expect(fmt.num(null)).toBe("—");
    expect(fmt.pct(0.734)).toBe("73%");
  });
  it("shortens station names", () => expect(shortStation("Panchawati_Pashan, Pune - IITM")).toBe("Panchawati Pashan"));
});

describe("API client", () => {
  it("parses the backend error envelope into ApiError", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      error: { code: "validation_error", message: "Invalid request.", details: [{ field: "email", message: "Value error, bad email" }] },
      request_id: "abc123",
    }), { status: 422 }));
    const err = (await request("/x").catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.code).toBe("validation_error");
    expect(err.fieldMessage).toBe("bad email");
    expect(err.requestId).toBe("abc123");
  });

  it("maps network failures to a friendly ApiError instead of fake data", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    const err = (await api.current().catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
  });

  it("serialises array query params and skips empty ones", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]", { status: 200 }));
    await api.compare([1, 2], "pm25", "day", undefined);
    expect(spy.mock.calls[0][0]).toBe("/api/v1/air-quality/compare?station_ids=1&station_ids=2&parameter=pm25&resolution=day");
  });

  it("sends JSON bodies with credentials", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response('{"access_token":"t"}', { status: 200 }));
    await api.login("a@b.com", "pw");
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("same-origin");
    expect(JSON.parse(init.body as string)).toEqual({ email: "a@b.com", password: "pw" });
  });
});
