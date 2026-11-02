import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AssistantResultRenderer } from "./AssistantResultRenderer";

describe("AssistantResultRenderer", () => {
  it("opens notice modal from list action", () => {
    const onOpenNotice = vi.fn();
    render(
      <AssistantResultRenderer
        blocks={[
          {
            type: "notice_list",
            data: {
              total: 1,
              page: 1,
              items: [{ id: 42, title: "济南打印机采购", region: "济南", publish_time: "2026-01-01" }],
            },
          },
        ]}
        onOpenNotice={onOpenNotice}
      />
    );
    expect(screen.getByText("济南打印机采购")).toBeTruthy();
    screen.getByText("打开").click();
    expect(onOpenNotice).toHaveBeenCalledWith(42);
  });

  it("renders notice detail summary and open button", () => {
    const onOpenNotice = vi.fn();
    render(
      <AssistantResultRenderer
        blocks={[
          {
            type: "notice_detail",
            data: {
              notice_id: 61493,
              item: {
                id: 61493,
                title: "办公桌定点竞价成交公告",
                buyerName: "平度市财政局",
                regionName: "青岛",
                publishTime: "2026-10-28 09:04:41",
                goods: [{ id: 1 }],
              },
            },
          },
        ]}
        onOpenNotice={onOpenNotice}
      />
    );
    expect(screen.getByText("办公桌定点竞价成交公告")).toBeTruthy();
    screen.getByText("查看完整详情").click();
    expect(onOpenNotice).toHaveBeenCalledWith(61493);
  });

  it("renders navigation actions", () => {
    const onNavigate = vi.fn();
    render(
      <AssistantResultRenderer
        blocks={[
          {
            type: "navigation",
            data: { items: [{ id: "salesOrders", label: "销售订单" }] },
          },
        ]}
        onNavigate={onNavigate}
      />
    );
    screen.getByText("打开「销售订单」").click();
    expect(onNavigate).toHaveBeenCalledWith("salesOrders");
  });

  it("renders tool preview confirm button", () => {
    const onConfirmAction = vi.fn();
    render(
      <AssistantResultRenderer
        blocks={[
          {
            type: "tool_preview",
            data: {
              description: "运行助手白名单内的已授权安全定时任务（需确认）",
              execution_id: 8,
              confirmation_token: "tok",
              params: { job_id: 3 },
            },
          },
        ]}
        onConfirmAction={onConfirmAction}
      />
    );
    screen.getByText("确认执行").click();
    expect(onConfirmAction).toHaveBeenCalledWith(8, "tok");
  });

  it("renders invoice delete preview without raw json", () => {
    const onConfirmAction = vi.fn();
    render(
      <AssistantResultRenderer
        blocks={[
          {
            type: "tool_preview",
            data: {
              tool_name: "erp.invoice.delete",
              description: "删除发票「26372000005015205376」",
              execution_id: 9,
              confirmation_token: "tok2",
              params: { invoice_no: "26372000005015205376" },
            },
          },
        ]}
        onConfirmAction={onConfirmAction}
      />
    );
    expect(screen.getByText("26372000005015205376")).toBeTruthy();
    const buttons = screen.getAllByText("确认执行");
    buttons[buttons.length - 1].click();
    expect(onConfirmAction).toHaveBeenCalledWith(9, "tok2");
  });
});
