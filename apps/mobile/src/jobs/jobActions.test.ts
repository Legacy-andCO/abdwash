import { describe, expect, it, vi } from "vitest";

vi.mock("expo-crypto", () => ({
  randomUUID: () => "123e4567-e89b-42d3-a456-426614174000",
}));

import type { Job } from "../lib";
import { ClientEventIdStore } from "../idempotency/clientEventId";
import { submitJobAction, type JobAction } from "./jobActions";

describe.each<JobAction>(["start-trip", "arrive", "start", "complete"])(
  "%s job action",
  (action) => {
    it("calls the mutation with the expected endpoint action and event ID", async () => {
      const result = { id: "job-1" } as Job;
      const mutate = vi.fn(async () => result);

      await expect(
        submitJobAction(mutate, new ClientEventIdStore(), "job-1", action),
      ).resolves.toBe(result);

      expect(mutate).toHaveBeenCalledWith({
        jobId: "job-1",
        action,
        body: expect.objectContaining({
          client_event_id: expect.stringMatching(/^[0-9a-f-]{36}$/i),
        }),
      });
    });
  },
);
