import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdvertisePage, ApprovedAdPaymentNotice } from "../features/advertising";

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../lib/api", () => ({ api: { get: mocks.get, post: mocks.post, postForm: vi.fn() } }));

describe("advertiser payment dashboard", () => {
  beforeEach(() => { mocks.get.mockReset(); mocks.post.mockReset(); });

  it("shows a prominent payment link and enabled Paystack action for an approved campaign", async () => {
    mocks.get.mockImplementation(async (path: string) => path === "/ads/plans/"
      ? { plans: [], checkout_available: true, consent_text: "" }
      : [{ id: "campaign-1", brand_name: "Campus Studio", image_url: "https://example.test/creative.jpg",
        status: "APPROVED", program_name: "Campus Brand", applicant_community: "STUDENT",
        ad_category: "Fashion", monthly_price_ngn: 3500, impressions: 0, clicks: 0, payment_history: [] }]);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter><AdvertisePage /></MemoryRouter></QueryClientProvider>);
    expect(await screen.findByRole("link", { name: "Go to payment" })).toHaveAttribute("href", "#my-advertisements");
    expect(screen.getByRole("button", { name: "Continue to Paystack" })).toBeEnabled();
  });

  it("links an approved ad from the member dashboard to payment", async () => {
    mocks.get.mockResolvedValue([{ id: "campaign-1", brand_name: "Campus Studio", status: "APPROVED" }]);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter><ApprovedAdPaymentNotice /></MemoryRouter></QueryClientProvider>);
    expect(await screen.findByRole("link", { name: "Continue to payment" })).toHaveAttribute("href", "/app/advertise#my-advertisements");
  });

  it("shows a failed checkout request next to the clicked Paystack button", async () => {
    mocks.get.mockImplementation(async (path: string) => path === "/ads/plans/"
      ? { plans: [], checkout_available: true, consent_text: "" }
      : [{ id: "campaign-1", brand_name: "Campus Studio", image_url: "https://example.test/ad.jpg",
        status: "APPROVED", program_name: "Campus Brand", applicant_community: "STUDENT",
        ad_category: "Fashion", monthly_price_ngn: 3500, impressions: 0, clicks: 0, payment_history: [] }]);
    mocks.post.mockRejectedValue(new Error("Paystack rejected the monthly advertising plan."));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter><AdvertisePage /></MemoryRouter></QueryClientProvider>);
    fireEvent.click(await screen.findByRole("button", { name: "Continue to Paystack" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Payment could not open: Paystack rejected the monthly advertising plan.");
  });
});
