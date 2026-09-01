// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PublicReview, ReviewEligibility } from "@/lib/types";
import { HomeReviews } from "./home-reviews";
import { I18nProvider } from "./i18n-provider";
import { ReviewForm } from "./review-form";
import { ReviewPrompt } from "./review-prompt";
import { ReviewsPage } from "./reviews-page";

const getPublicReviewSummary = vi.fn();
const getPublicReviews = vi.fn();
const recordCustomerReviewOpen = vi.fn();
const submitCustomerReview = vi.fn();

vi.mock("@/lib/api", () => ({
  getPublicReviewSummary: (...args: unknown[]) => getPublicReviewSummary(...args),
  getPublicReviews: (...args: unknown[]) => getPublicReviews(...args),
  recordCustomerReviewOpen: (...args: unknown[]) => recordCustomerReviewOpen(...args),
  submitCustomerReview: (...args: unknown[]) => submitCustomerReview(...args),
}));
vi.mock("./auth-provider", () => ({
  useAuth: () => ({
    user: { id: "customer-1", user_metadata: {} },
    loading: false,
    logout: vi.fn(),
  }),
}));
vi.mock("next/navigation", () => ({ usePathname: () => "/reviews" }));

const highReview: PublicReview = {
  id: "review-high",
  rating: 5,
  comment: "Careful and professional.",
  reviewer_display_name: "Ahmad H.",
  service_name: "Standard Wash",
  service_date: "2026-08-01T09:00:00Z",
  published_at: "2026-08-01T12:00:00Z",
  verified: true,
};
const lowReview: PublicReview = {
  ...highReview,
  id: "review-low",
  rating: 2,
  comment: "The team arrived late.",
  reviewer_display_name: "Noor A.",
};
const eligibility: ReviewEligibility = {
  eligible: true,
  booking_id: "booking-1",
  booking_reference: "AW-12345678",
  service_name: "Standard Wash",
  service_date: "2026-08-01T09:00:00Z",
  existing_review: null,
};

beforeEach(() => {
  window.sessionStorage.clear();
  getPublicReviewSummary.mockResolvedValue({
    average_rating: 3.5,
    total_count: 2,
    featured_reviews: [highReview],
  });
  getPublicReviews.mockResolvedValue({
    average_rating: 3.5,
    total_count: 2,
    reviews: [highReview, lowReview],
  });
  recordCustomerReviewOpen.mockResolvedValue({ show_prompt: true, eligibility });
  submitCustomerReview.mockResolvedValue(highReview);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("verified customer reviews", () => {
  it("renders homepage summary from the API with safe public fields", async () => {
    render(<I18nProvider><HomeReviews /></I18nProvider>);
    expect(await screen.findByText(/Careful and professional\./)).toBeTruthy();
    expect(screen.getByText("Ahmad H.")).toBeTruthy();
    expect(screen.getByText("Based on 2 verified reviews")).toBeTruthy();
    expect(getPublicReviewSummary).toHaveBeenCalledOnce();
  });

  it("keeps legitimate lower ratings visible on the full reviews page", async () => {
    render(<I18nProvider><ReviewsPage /></I18nProvider>);
    expect(await screen.findByText(/The team arrived late\./)).toBeTruthy();
    expect(screen.getByText("Noor A.")).toBeTruthy();
    expect(
      screen
        .getAllByRole("link", { name: "Review us" })
        .every((link) => link.getAttribute("href") === "/reviews/leave"),
    ).toBe(true);
  });

  it("requires a star rating and accepts an optional comment", async () => {
    const submit = vi.fn().mockResolvedValue(highReview);
    render(<I18nProvider><ReviewForm eligibility={eligibility} onSubmit={submit} /></I18nProvider>);
    await userEvent.click(screen.getByRole("button", { name: "Submit review" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Choose a star rating");
    await userEvent.click(screen.getByRole("radio", { name: "5 star rating" }));
    await userEvent.click(screen.getByRole("button", { name: "Submit review" }));
    await waitFor(() => expect(submit).toHaveBeenCalledWith(5, ""));
    expect(await screen.findByText("Thanks for your feedback")).toBeTruthy();
  });

  it("records one genuine session open and never subscribes to focus events", async () => {
    const addEventListener = vi.spyOn(window, "addEventListener");
    const view = render(<I18nProvider><ReviewPrompt /></I18nProvider>);
    expect(await screen.findByRole("dialog")).toBeTruthy();
    expect(recordCustomerReviewOpen).toHaveBeenCalledOnce();
    view.rerender(<I18nProvider><ReviewPrompt /></I18nProvider>);
    expect(recordCustomerReviewOpen).toHaveBeenCalledOnce();
    expect(addEventListener).not.toHaveBeenCalledWith("focus", expect.anything());
    addEventListener.mockRestore();
  });

  it("renders new review content naturally in Arabic RTL", async () => {
    window.localStorage.setItem("trifecta-language", "ar");
    render(<I18nProvider><HomeReviews /></I18nProvider>);
    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
    expect(await screen.findByText("ماذا يقول عملاؤنا")).toBeTruthy();
    expect(screen.queryByText("reviews.whatCustomersSay")).toBeNull();
  });
});
