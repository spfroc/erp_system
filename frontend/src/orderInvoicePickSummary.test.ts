import { describe, expect, it } from "vitest";

import { orderInvoicePickSummary } from "./App";
import { seedData } from "./seed";

describe("orderInvoicePickSummary", () => {
  it("shows sales order items with quantity, unit price and quantity times unit price", () => {
    const summary = orderInvoicePickSummary(seedData, "so-1", "sales");
    expect(summary.orderNo).toBe("SO-XM20260619001-01");
    expect(summary.items).toEqual([
      {
        productName: "KFR-26GW/G3-1 示例品牌挂机 大1匹 1级",
        quantity: 1,
        unitPrice: 1830,
        lineAmount: 1830,
      },
    ]);
    expect(summary.amount).toBe(1830);
  });

  it("shows purchase order items with unit cost", () => {
    const summary = orderInvoicePickSummary(seedData, "po-1", "purchase");
    expect(summary.orderNo).toBe("PO-XM20260619001-01");
    expect(summary.items[0]).toMatchObject({
      productName: "KFR-26GW/G3-1 示例品牌挂机 大1匹 1级",
      quantity: 1,
      unitPrice: 1730,
      lineAmount: 1730,
    });
    expect(summary.amount).toBe(1730);
  });
});
