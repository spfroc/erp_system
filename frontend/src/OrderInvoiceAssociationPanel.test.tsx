import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { OrderInvoiceAssociationPanel } from "./App";
import { seedData } from "./seed";
import type { Invoice } from "./types";

afterEach(() => {
  cleanup();
});

const invoice: Invoice = {
  id: "inv-multi",
  type: "销项",
  counterpartyOrgId: "org-1",
  invoiceNo: "26372000003722683666",
  invoiceDate: "2026-06-17",
  amount: 90,
  status: "待确认",
  lineItems: [
    { productName: "拉链袋", unit: "个", quantity: 3, unitPrice: 15, amount: 39.82, taxAmount: 5.18 },
    { productName: "文件夹", unit: "个", quantity: 2, unitPrice: 22.5, amount: 39.82, taxAmount: 5.18 },
  ],
};

describe("OrderInvoiceAssociationPanel line pick", () => {
  it("shows current order items and totals at the top of the pick dialog", () => {
    render(
      <OrderInvoiceAssociationPanel
        linkedInvoices={[]}
        invoiceSelectOptions={[{ value: invoice.id, label: invoice.invoiceNo ?? "" }]}
        selectedInvoiceId={invoice.id}
        canManage
        invoices={[invoice]}
        organizations={seedData.organizations}
        defaultBuyer={{ name: "买方" }}
        defaultSeller={{ name: "卖方" }}
        existingHint="到本销售订单"
        ocrNewHint="识别完成"
        expectedInvoiceType="销项"
        orderId="so-1"
        orderType="sales"
        orderSummary={{
          orderNo: "SO-XM20260619001-01",
          amount: 1830,
          items: [
            { productName: "KFR-26GW/G3-1 示例品牌挂机 大1匹 1级", quantity: 1, unitPrice: 1830, lineAmount: 1830 },
          ],
        }}
        onSelectInvoice={() => undefined}
        onLink={() => undefined}
        onUnlink={() => undefined}
        onLinkExisting={async () => true}
        onCreateNew={async () => true}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "关联发票" }));

    expect(screen.getByRole("heading", { name: "选择关联商品" })).toBeInTheDocument();
    expect(screen.getByText(/当前订单 SO-XM20260619001-01/)).toBeInTheDocument();
    expect(screen.getAllByText(/订单总价/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("数量×单价").length).toBeGreaterThan(0);
    expect(screen.getByText(/已选发票价税合计/)).toBeInTheDocument();
    expect(screen.getByText("拉链袋")).toBeInTheDocument();
    expect(screen.getByText("文件夹")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "选择 拉链袋" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "选择 文件夹" })).not.toBeChecked();
  });

  it("prechecks invoice lines whose tax-inclusive total equals an order line amount", () => {
    render(
      <OrderInvoiceAssociationPanel
        linkedInvoices={[]}
        invoiceSelectOptions={[{ value: invoice.id, label: invoice.invoiceNo ?? "" }]}
        selectedInvoiceId={invoice.id}
        canManage
        invoices={[invoice]}
        organizations={seedData.organizations}
        defaultBuyer={{ name: "买方" }}
        defaultSeller={{ name: "卖方" }}
        existingHint="到本销售订单"
        ocrNewHint="识别完成"
        expectedInvoiceType="销项"
        orderId="so-1"
        orderType="sales"
        orderSummary={{
          orderNo: "SO-MATCH",
          amount: 45,
          items: [{ productName: "拉链袋", quantity: 3, unitPrice: 15, lineAmount: 45 }],
        }}
        onSelectInvoice={() => undefined}
        onLink={() => undefined}
        onUnlink={() => undefined}
        onLinkExisting={async () => true}
        onCreateNew={async () => true}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "关联发票" }));

    expect(screen.getByRole("checkbox", { name: "选择 拉链袋" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "选择 文件夹" })).not.toBeChecked();
    expect(screen.getByLabelText("拉链袋关联数量")).toHaveValue(3);
  });

  it("marks already linked invoice lines as associated and disables them", () => {
    const splitInvoice: Invoice = {
      ...invoice,
      lineItems: [
        { productName: "空调 KFR-35GW/KS2", quantity: 6, unitPrice: 1548.67, amount: 9292.02, taxAmount: 1207.98, salesOrderId: "so-other" },
        { productName: "空调 KFR-35GW/KS2", quantity: 16, unitPrice: 1548.67, amount: 24778.72, taxAmount: 3221.28, salesOrderId: "so-other-2" },
        { productName: "空调 KFR-35GW/KS2", quantity: 2, unitPrice: 1548.67, amount: 3097.34, taxAmount: 402.66 },
      ],
    };
    render(
      <OrderInvoiceAssociationPanel
        linkedInvoices={[]}
        invoiceSelectOptions={[{ value: splitInvoice.id, label: splitInvoice.invoiceNo ?? "" }]}
        selectedInvoiceId={splitInvoice.id}
        canManage
        invoices={[splitInvoice]}
        organizations={seedData.organizations}
        defaultBuyer={{ name: "买方" }}
        defaultSeller={{ name: "卖方" }}
        existingHint="到本销售订单"
        ocrNewHint="识别完成"
        expectedInvoiceType="销项"
        orderId="so-current"
        orderType="sales"
        orderNoById={{ "so-other": "PO-XM-01", "so-other-2": "PO-XM-02" }}
        orderSummary={{
          orderNo: "PO-XM-CURRENT",
          amount: 3500,
          items: [{ productName: "空调 KFR-35GW/KS2", quantity: 2, unitPrice: 1750, lineAmount: 3500 }],
        }}
        onSelectInvoice={() => undefined}
        onLink={() => undefined}
        onUnlink={() => undefined}
        onLinkExisting={async () => true}
        onCreateNew={async () => true}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "关联发票" }));

    const locked = screen.getAllByRole("checkbox", { name: "空调 KFR-35GW/KS2已关联" });
    expect(locked).toHaveLength(2);
    expect(locked[0]).toBeDisabled();
    expect(locked[1]).toBeDisabled();
    expect(screen.getByText("已关联 PO-XM-01")).toBeInTheDocument();
    expect(screen.getByText("已关联 PO-XM-02")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "选择 空调 KFR-35GW/KS2" })).not.toBeDisabled();
  });

  it("opens line pick dialog for single-item invoices", () => {
    const single: Invoice = {
      id: "inv-single",
      type: "销项",
      counterpartyOrgId: "org-1",
      invoiceNo: "26372000004486461376",
      invoiceDate: "2026-09-11",
      amount: 7400,
      status: "待确认",
      lineItems: [
        { productName: "*计算机配套产品*电脑", unit: "台", quantity: 2, unitPrice: 3274.34, amount: 6548.67, taxAmount: 851.33 },
      ],
    };
    render(
      <OrderInvoiceAssociationPanel
        linkedInvoices={[]}
        invoiceSelectOptions={[{ value: single.id, label: single.invoiceNo ?? "" }]}
        selectedInvoiceId={single.id}
        canManage
        invoices={[single]}
        organizations={seedData.organizations}
        defaultBuyer={{ name: "买方" }}
        defaultSeller={{ name: "卖方" }}
        existingHint="到本销售订单"
        ocrNewHint="识别完成"
        expectedInvoiceType="销项"
        orderId="so-1"
        orderType="sales"
        orderSummary={{
          orderNo: "SO-XM20260823070-01",
          amount: 3700,
          items: [{ productName: "电脑", quantity: 1, unitPrice: 3700, lineAmount: 3700 }],
        }}
        onSelectInvoice={() => undefined}
        onLink={() => undefined}
        onUnlink={() => undefined}
        onLinkExisting={async () => true}
        onCreateNew={async () => true}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "关联发票" }));

    expect(screen.getByRole("heading", { name: "选择关联商品" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "选择 *计算机配套产品*电脑" })).toBeChecked();
    expect(screen.getByLabelText("*计算机配套产品*电脑关联数量")).toHaveValue(2);
  });
});
