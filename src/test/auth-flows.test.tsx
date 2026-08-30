import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  OtpPage,
  RegisterPage,
  ResetPasswordPage,
} from "../features/auth-pages";

afterEach(() => vi.unstubAllGlobals());

describe("authentication recovery flows", () => {
  it("validates a complete six-digit OTP before submission", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <OtpPage />
      </MemoryRouter>,
    );
    await user.type(screen.getByLabelText(/verification code/i), "123");
    await user.click(screen.getByRole("button", { name: /verify account/i }));
    expect(screen.getByRole("alert")).toHaveTextContent(/six-digit/i);
  });

  it("rejects mismatched reset passwords before calling the backend", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/reset-password?token=test-token"]}>
        <ResetPasswordPage />
      </MemoryRouter>,
    );
    await user.type(
      screen.getByLabelText(/^new password/i),
      "correct-password-1",
    );
    await user.type(
      screen.getByLabelText(/confirm new password/i),
      "different-password-1",
    );
    await user.click(screen.getByRole("button", { name: /update password/i }));
    expect(screen.getByRole("alert")).toHaveTextContent(/do not match/i);
  });

  it("submits registration consent fields as booleans", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) =>
      Promise.resolve(
        new Response(
          JSON.stringify(
            url.includes("/public/communities")
              ? {
                  data: [
                    {
                      id: "11111111-1111-4111-a111-111111111111",
                      name: "Music",
                      slug: "music",
                      type: "unit",
                    },
                    {
                      id: "22222222-2222-4222-a222-222222222222",
                      name: "Love Campus Fellowship",
                      slug: "love-campus-fellowship",
                      type: "campus_fellowship",
                    },
                  ],
                }
              : { data: { verificationRequired: true } },
          ),
          {
            status: url.includes("/public/communities") ? 200 : 201,
            headers: { "Content-Type": "application/json" },
          },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <RegisterPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await user.type(
      screen.getByLabelText(/university email/i),
      "student@example.edu.ng",
    );
    await user.type(screen.getByLabelText(/create password/i), "password-1");
    await user.click(screen.getByRole("button", { name: /continue/i }));
    await user.type(await screen.findByLabelText(/first name/i), "Ada");
    await user.type(screen.getByLabelText(/last name/i), "Okafor");
    await user.type(screen.getByLabelText(/matric number/i), "CU/26/101");
    await user.click(screen.getByRole("button", { name: /continue/i }));
    await screen.findByLabelText(/member type/i);
    await user.selectOptions(
      await screen.findByLabelText(/chapel unit/i),
      "11111111-1111-4111-a111-111111111111",
    );
    await user.selectOptions(
      screen.getByLabelText(/campus fellowship/i),
      "22222222-2222-4222-a222-222222222222",
    );
    await user.click(screen.getByRole("button", { name: /continue/i }));
    await user.click(await screen.findByLabelText(/read and accept/i));
    await user.click(
      screen.getByRole("button", { name: /submit registration/i }),
    );

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).includes("/auth/register"),
        ),
      ).toBe(true),
    );
    const [, request] = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/auth/register"),
    ) as [string, RequestInit];
    expect(JSON.parse(String(request.body))).toMatchObject({
      acceptedPolicies: true,
      programmeUpdates: false,
      unitCommunityId: "11111111-1111-4111-a111-111111111111",
      fellowshipCommunityId: "22222222-2222-4222-a222-222222222222",
    });
  });
});
