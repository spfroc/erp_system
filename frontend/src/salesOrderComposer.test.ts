import { describe, expect, it } from "vitest";

import { parsePurchaserQuickText } from "./salesOrderComposer";

describe("parsePurchaserQuickText", () => {
  it("splits name, phone and shipping address, appending the bracket code to the phone", () => {
    expect(parsePurchaserQuickText("郑筱[3015]\n18400840905\n山东济南市历下区姚家街道-九宸赋营销中心[3015]")).toEqual({
      purchaserName: "郑筱",
      purchaserPhone: "18400840905-3015",
      purchaserAddress: "山东济南市历下区姚家街道-九宸赋营销中心",
    });
  });

  it("uses the code from either the name or the address and does not duplicate it", () => {
    expect(parsePurchaserQuickText("郑筱\n18400840905-3015\n山东济南市历下区姚家街道-九宸赋营销中心［3015］")).toEqual({
      purchaserName: "郑筱",
      purchaserPhone: "18400840905-3015",
      purchaserAddress: "山东济南市历下区姚家街道-九宸赋营销中心",
    });
  });

  it("returns null when the three lines are incomplete", () => {
    expect(parsePurchaserQuickText("郑筱[3015]\n18400840905")).toBeNull();
  });
});
