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
    expect(screen.getByText("暂无标签")).toBeTruthy();
    screen.getByText("打开").click();
    expect(onOpenNotice).toHaveBeenCalledWith(42);
  });

  it("renders notice tags in list", () => {
    render(
      <AssistantResultRenderer
        blocks={[
          {
            type: "notice_list",
            data: {
              total: 1,
              items: [
                {
                  id: 35991,
                  title: "德州市体育运动学校公务车保险采购项目成交公告",
                  noticeKind: "结果公告",
                  tagDealKind: "未识别",
                  tagOrgType: "教育",
                  tagNature: "事业单位",
                  tagProvince: "山东省",
                  tagCity: "德州市",
                  region: "德州",
                  publishTime: "2026-11-09 08:20:24",
                },
              ],
            },
          },
        ]}
      />
    );
    expect(screen.getByText("结果公告")).toBeTruthy();
    expect(screen.getByText("教育")).toBeTruthy();
    expect(screen.getByText("事业单位")).toBeTruthy();
    expect(screen.getByText("德州市")).toBeTruthy();
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

  it("renders platform account credentials and copy actions", async () => {
    const onNavigate = vi.fn();
    const onNotice = vi.fn();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(
      <AssistantResultRenderer
        blocks={[
          {
            type: "erp_record_list",
            data: {
              collection: "platformAccounts",
              total: 1,
              items: [
                {
                  id: "pa-1",
                  customerName: "山东云谷",
                  platform: "齐鲁云采",
                  accountName: "S_yunguxx",
                  accountPassword: "Secret@1",
                  actions: [
                    { type: "open_platform_accounts", label: "打开平台账号" },
                    { type: "copy_text", label: "复制账号", text: "S_yunguxx" },
                    { type: "copy_text", label: "复制密码", text: "Secret@1" },
                  ],
                },
              ],
            },
          },
        ]}
        onNavigate={onNavigate}
        onNotice={onNotice}
      />
    );
    expect(screen.getByText("山东云谷")).toBeTruthy();
    expect(screen.getByText("齐鲁云采")).toBeTruthy();
    expect(screen.getByText("S_yunguxx")).toBeTruthy();
    expect(screen.getByText("Secret@1")).toBeTruthy();
    screen.getByText("打开平台账号").click();
    expect(onNavigate).toHaveBeenCalledWith("platformAccounts");
    screen.getByText("复制账号").click();
    await vi.waitFor(() => {
      expect(onNotice).toHaveBeenCalledWith("已复制账号", "success");
    });
    screen.getByText("复制密码").click();
    await vi.waitFor(() => {
      expect(onNotice).toHaveBeenCalledWith("已复制密码", "success");
    });
  });

  it("renders customer expiry contacts and quick actions", () => {
    const onOpenProject = vi.fn();
    const onOpenOrganization = vi.fn();
    render(
      <AssistantResultRenderer
        blocks={[
          {
            type: "erp_record_list",
            data: {
              collection: "customerExpiry",
              total: 1,
              items: [
                {
                  id: "proj-1",
                  name: "测试服务项目",
                  customer_name: "济南测试公司",
                  contact_name: "张三",
                  contact_phone: "13800001111",
                  service_end_date: "2027-03-31",
                  invoice_status: "待开",
                  status: "服务中",
                  actions: [
                    { type: "open_project", label: "打开项目", project_id: "proj-1" },
                    { type: "open_customer", label: "客户资料", org_id: "org-1" },
                    { type: "copy_phone", label: "复制电话", text: "13800001111" },
                  ],
                },
              ],
            },
          },
        ]}
        onOpenProject={onOpenProject}
        onOpenOrganization={onOpenOrganization}
      />
    );
    expect(screen.getByText("张三")).toBeTruthy();
    expect(screen.getByText("13800001111")).toBeTruthy();
    screen.getByText("打开项目").click();
    expect(onOpenProject).toHaveBeenCalledWith("proj-1");
    screen.getByText("客户资料").click();
    expect(onOpenOrganization).toHaveBeenCalledWith("org-1");
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
