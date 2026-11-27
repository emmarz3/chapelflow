export interface ScendeyWaitlistSignupPayload {
  name: string;
  email: string;
  audienceCategory: "student" | "staff" | "business" | "other";
  marketingConsent: boolean;
  brandName?: string;
  category?: string;
  website?: string;
}

export interface ScendeyWaitlistSignupResponse {
  data: { processed: boolean; message: string };
}

export class ScendeyWaitlistRequestError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "ScendeyWaitlistRequestError";
  }
}

export const scendeyWaitlistService = {
  async join(payload: ScendeyWaitlistSignupPayload): Promise<ScendeyWaitlistSignupResponse> {
    let response: Response;
    try {
      response = await fetch("/api/v1/public/scendey-waitlist/", {
        method: "POST",
        credentials: "include",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
    } catch {
      throw new ScendeyWaitlistRequestError(
        "We could not reach ChapelFlow. Check your connection and try again.",
        0,
      );
    }

    const result = await response.json().catch(() => null) as
      | ScendeyWaitlistSignupResponse
      | { message?: string; fieldErrors?: Record<string, string[]> }
      | null;

    if (!response.ok) {
      const message =
        result && "message" in result && typeof result.message === "string"
          ? result.message
          : "Waitlist registration is temporarily unavailable. Please try again.";
      throw new ScendeyWaitlistRequestError(message, response.status);
    }

    if (
      !result ||
      !("data" in result) ||
      result.data?.processed !== true ||
      typeof result.data.message !== "string"
    ) {
      throw new ScendeyWaitlistRequestError(
        "ChapelFlow received an unexpected response. Please try again.",
        502,
      );
    }

    return result as ScendeyWaitlistSignupResponse;
  },
};
