import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/app/(auth)/login/login-form";
import { AqiGauge } from "@/components/aq/widgets";
import { AqiBadge, ErrorState, Segmented } from "@/components/ui/primitives";
import { ApiError } from "@/lib/api";

function withQuery(ui: ReactNode) {
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>;
}

describe("UI primitives", () => {
  it("ErrorState shows the API message, request id and retries", async () => {
    const retry = vi.fn();
    render(<ErrorState error={new ApiError(503, "service_unavailable", "No trained model is available.", null, "req-42")} onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("No trained model is available.");
    expect(screen.getByText(/req-42/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("ErrorState explains connection problems", () => {
    render(<ErrorState error={new ApiError(0, "network_error", "Cannot reach the AirSense API.")} />);
    expect(screen.getByText("Connection problem")).toBeInTheDocument();
  });

  it("AqiBadge renders the category or a no-data state", () => {
    const { rerender } = render(<AqiBadge category="Poor" />);
    expect(screen.getByText("Poor")).toBeInTheDocument();
    rerender(<AqiBadge category={null} />);
    expect(screen.getByText("No data")).toBeInTheDocument();
  });

  it("Segmented is an accessible radio group", async () => {
    const onChange = vi.fn();
    render(<Segmented label="Horizon" value={6} onChange={onChange} options={[{ value: 6, label: "6 h" }, { value: 24, label: "24 h" }]} />);
    expect(screen.getByRole("radiogroup", { name: "Horizon" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "6 h" })).toHaveAttribute("aria-checked", "true");
    await userEvent.click(screen.getByRole("radio", { name: "24 h" }));
    expect(onChange).toHaveBeenCalledWith(24);
  });

  it("AqiGauge exposes an accessible label", () => {
    render(<AqiGauge aqi={107} category="Moderate" />);
    expect(screen.getByRole("img", { name: "AQI 107, Moderate" })).toBeInTheDocument();
  });
});

describe("Login form", () => {
  it("validates input client-side before calling the API", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(withQuery(<LoginForm />));
    await userEvent.type(screen.getByLabelText("Email"), "not-an-email");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("shows the server error for wrong credentials", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ error: { code: "unauthorized", message: "Incorrect email or password." } }), { status: 401 }));
    render(withQuery(<LoginForm />));
    await userEvent.type(screen.getByLabelText("Email"), "user@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrongpass1");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
  });
});
