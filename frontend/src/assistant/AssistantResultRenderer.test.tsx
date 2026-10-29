import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AssistantResultRenderer } from "./AssistantResultRenderer";

describe("AssistantResultRenderer", () => {
  it("renders notice list and follow-up button", () => {
    const onFollowUp = vi.fn();
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
        onFollowUp={onFollowUp}
      />
    );
    expect(screen.getByText("济南打印机采购")).toBeTruthy();
    screen.getByText("打开").click();
    expect(onFollowUp).toHaveBeenCalledWith("打开公告 42");
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
});
