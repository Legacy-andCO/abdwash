import { describe, expect, it } from "vitest";
import type { Service } from "@/lib/types";
import { serviceFeatureAdditions } from "./services-preview";

function service(id: string, features: string[]): Service {
  return {
    id,
    name: id,
    description: null,
    price_minor: 100,
    currency_code: "AED",
    estimated_duration_minutes: 60,
    included_features: features,
    prices: [],
  } as Service;
}

describe("mobile catalogue comparison", () => {
  it("preserves authoritative ordering while computing Gold and Premium additions", () => {
    const standard = service("standard", ["wash", "vacuum"]);
    const gold = service("gold", ["wash", "foam", "vacuum", "shine"]);
    const premium = service("premium", ["wash", "foam", "wax", "vacuum", "shine"]);
    expect(serviceFeatureAdditions(gold, standard)).toEqual(["foam", "shine"]);
    expect(serviceFeatureAdditions(premium, gold)).toEqual(["wax"]);
  });
});
