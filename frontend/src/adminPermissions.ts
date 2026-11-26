import type { PermissionKey } from "./types";

export type AdminPermissionLeaf = {
  key: PermissionKey;
  label: string;
  hint?: string;
  /** 树中不展示，由父级/兄弟勾选同步（如 portal.account.manage） */
  treeHidden?: boolean;
};

export type AdminPermissionModule = {
  id: string;
  label: string;
  description?: string;
  children: AdminPermissionLeaf[];
};

export type AdminPermissionSection = {
  title: string;
  modules: AdminPermissionModule[];
};

/** 管理后台权限树：分区 → 模块 → 动作 */
export const ADMIN_PERMISSION_TREE: AdminPermissionSection[] = [
  {
    title: "业务经营",
    modules: [
      {
        id: "dashboard",
        label: "总览",
        description: "工作台与提醒",
        children: [{ key: "dashboard.view", label: "查看" }],
      },
      {
        id: "project",
        label: "项目",
        description: "商品/服务项目全流程",
        children: [
          { key: "project.view", label: "查看" },
          { key: "project.create", label: "新建" },
          { key: "project.edit", label: "编辑" },
        ],
      },
      {
        id: "entity",
        label: "客户基础信息",
        description: "组织与客户档案",
        children: [
          { key: "entity.view", label: "查看" },
          { key: "entity.create", label: "维护" },
        ],
      },
      {
        id: "product",
        label: "商品及价格",
        description: "商品目录、价格与服务权限包",
        children: [
          { key: "product.view", label: "查看" },
          { key: "product.manage", label: "管理" },
          { key: "product.entitlement.manage", label: "配置服务权限包" },
        ],
      },
      {
        id: "purchase",
        label: "采购履约",
        children: [{ key: "purchase.manage", label: "管理" }],
      },
      {
        id: "onboarding",
        label: "入驻服务",
        children: [{ key: "onboarding.manage", label: "管理" }],
      },
      {
        id: "platformAccount",
        label: "平台账号",
        children: [
          { key: "platformAccount.view", label: "查看" },
          { key: "platformAccount.manage", label: "管理" },
        ],
      },
      {
        id: "trademark",
        label: "商标管理",
        children: [
          { key: "trademarkCertificate.view", label: "查看" },
          { key: "trademarkCertificate.manage", label: "管理" },
        ],
      },
      {
        id: "lead",
        label: "商机",
        children: [{ key: "lead.manage", label: "管理" }],
      },
      {
        id: "library",
        label: "政企客户资料库",
        children: [
          { key: "library.view", label: "查看" },
          { key: "library.manage", label: "管理" },
        ],
      },
      {
        id: "mallCustomer",
        label: "资料库",
        children: [
          { key: "mallCustomer.view", label: "查看" },
          { key: "mallCustomer.manage", label: "管理" },
        ],
      },
    ],
  },
  {
    title: "订单与财务",
    modules: [
      {
        id: "serviceOrder",
        label: "服务订单",
        children: [
          { key: "serviceOrder.view", label: "查看" },
          { key: "serviceOrder.manage", label: "管理" },
        ],
      },
      {
        id: "salesOrder",
        label: "销售订单",
        children: [
          { key: "salesOrder.view", label: "查看" },
          { key: "salesOrder.manage", label: "管理" },
        ],
      },
      {
        id: "purchaseOrder",
        label: "采购订单",
        children: [
          { key: "purchaseOrder.view", label: "查看" },
          { key: "purchaseOrder.manage", label: "管理" },
        ],
      },
      {
        id: "finance",
        label: "财务",
        children: [
          { key: "finance.view", label: "查看" },
          { key: "finance.manage", label: "管理流水" },
          { key: "invoice.manage", label: "管理发票" },
          { key: "profit.view", label: "查看利润" },
          { key: "sensitive.view", label: "查看敏感信息" },
        ],
      },
    ],
  },
  {
    title: "公告中心",
    modules: [
      {
        id: "notice",
        label: "公告",
        children: [
          { key: "notice.view", label: "查看" },
          { key: "notice.manage", label: "管理" },
          { key: "notice.stats.view", label: "统计" },
        ],
      },
      {
        id: "noticeTag",
        label: "公告标签",
        children: [
          { key: "notice.tag.view", label: "查看" },
          { key: "notice.tag.manage", label: "修正" },
        ],
      },
      {
        id: "noticeOrgType",
        label: "公告类型",
        children: [
          { key: "notice.orgType.view", label: "查看" },
          { key: "notice.orgType.manage", label: "管理" },
        ],
      },
      {
        id: "noticeNature",
        label: "性质",
        children: [
          { key: "notice.nature.view", label: "查看" },
          { key: "notice.nature.manage", label: "管理" },
        ],
      },
      {
        id: "noticeSite",
        label: "站点管理",
        children: [
          { key: "notice.site.view", label: "查看" },
          { key: "notice.site.manage", label: "管理" },
        ],
      },
      {
        id: "noticeCategoryMap",
        label: "分类映射",
        children: [
          { key: "notice.categoryMap.view", label: "查看" },
          { key: "notice.categoryMap.manage", label: "管理" },
        ],
      },
    ],
  },
  {
    title: "客户门户",
    modules: [
      {
        id: "portalContent",
        label: "公告与数据",
        description: "门户公告、统计与订阅",
        children: [
          { key: "portal.notice.view", label: "公告列表" },
          { key: "portal.stats.view", label: "数据统计" },
          { key: "portal.notice.subscribe", label: "订阅消息" },
        ],
      },
      {
        id: "portalBiz",
        label: "企业业务",
        description: "订单、发票、合同只读",
        children: [
          { key: "portal.order.view", label: "企业订单" },
          { key: "portal.invoice.view", label: "企业发票" },
          { key: "portal.contract.view", label: "企业合同" },
        ],
      },
      {
        id: "portalAccount",
        label: "企业账号",
        description: "同企业门户账号增删改查",
        children: [
          { key: "portal.account.view", label: "查看" },
          { key: "portal.account.create", label: "新增" },
          { key: "portal.account.edit", label: "编辑" },
          { key: "portal.account.delete", label: "删除" },
          {
            key: "portal.account.manage",
            label: "全部管理",
            hint: "兼容旧配置",
            treeHidden: true,
          },
        ],
      },
      {
        id: "customerAccount",
        label: "登录账号（后台）",
        description: "管理后台维护客户门户登录账号",
        children: [
          { key: "customerAccount.view", label: "查看" },
          { key: "customerAccount.manage", label: "管理" },
        ],
      },
    ],
  },
  {
    title: "站点与运营",
    modules: [
      {
        id: "site",
        label: "前端网站配置",
        children: [
          { key: "site.view", label: "查看" },
          { key: "site.manage", label: "管理" },
        ],
      },
      {
        id: "menu",
        label: "菜单配置",
        children: [
          { key: "menu.view", label: "查看" },
          { key: "menu.manage", label: "管理" },
        ],
      },
      {
        id: "sms",
        label: "短信",
        children: [
          { key: "sms.view", label: "查看日志" },
          { key: "sms.manage", label: "管理" },
        ],
      },
      {
        id: "wechatMp",
        label: "微信公众号",
        children: [
          { key: "wechatMp.view", label: "查看" },
          { key: "wechatMp.manage", label: "管理" },
        ],
      },
    ],
  },
  {
    title: "系统与安全",
    modules: [
      {
        id: "assistant",
        label: "智能助手",
        children: [
          { key: "assistant.view", label: "查看" },
          { key: "assistant.use", label: "使用" },
          { key: "assistant.manage", label: "管理" },
        ],
      },
      {
        id: "devOps",
        label: "定时任务",
        children: [
          { key: "dev.ops.view", label: "查看" },
          { key: "dev.ops.manage", label: "管理" },
        ],
      },
      {
        id: "mcpLog",
        label: "MCP 调用日志",
        children: [{ key: "mcpLog.view", label: "查看" }],
      },
      {
        id: "user",
        label: "用户权限",
        children: [{ key: "user.manage", label: "管理" }],
      },
    ],
  },
];

const PORTAL_ACCOUNT_ACTIONS: PermissionKey[] = [
  "portal.account.view",
  "portal.account.create",
  "portal.account.edit",
  "portal.account.delete",
];

function allLeaves(): AdminPermissionLeaf[] {
  return ADMIN_PERMISSION_TREE.flatMap((section) => section.modules.flatMap((mod) => mod.children));
}

/** 完整权限文案（报错、个人中心等） */
export const permissionLabels: Record<PermissionKey, string> = (() => {
  const labels = {} as Record<PermissionKey, string>;
  for (const section of ADMIN_PERMISSION_TREE) {
    for (const mod of section.modules) {
      for (const leaf of mod.children) {
        labels[leaf.key] = leaf.treeHidden
          ? `${mod.label}（${leaf.label}）`
          : `${mod.label} · ${leaf.label}`;
      }
    }
  }
  return labels;
})();

/** 兼容旧「分区平铺」结构：分区 title + 该分区全部 key */
export const permissionGroups: Array<{ title: string; keys: PermissionKey[] }> = ADMIN_PERMISSION_TREE.map((section) => ({
  title: section.title,
  keys: section.modules.flatMap((mod) =>
    mod.children.filter((leaf) => !leaf.treeHidden).map((leaf) => leaf.key),
  ),
}));

export function adminPermissionMatrixRows(): Array<{
  section: string;
  moduleId: string;
  moduleLabel: string;
  key: PermissionKey;
  label: string;
  isFirstInModule: boolean;
}> {
  const rows: Array<{
    section: string;
    moduleId: string;
    moduleLabel: string;
    key: PermissionKey;
    label: string;
    isFirstInModule: boolean;
  }> = [];
  for (const section of ADMIN_PERMISSION_TREE) {
    for (const mod of section.modules) {
      const visible = mod.children.filter((leaf) => !leaf.treeHidden);
      visible.forEach((leaf, index) => {
        rows.push({
          section: section.title,
          moduleId: mod.id,
          moduleLabel: mod.label,
          key: leaf.key,
          label: leaf.label,
          isFirstInModule: index === 0,
        });
      });
    }
  }
  return rows;
}

function orderedKeys(set: Set<PermissionKey>): PermissionKey[] {
  return allLeaves().map((leaf) => leaf.key).filter((key) => set.has(key));
}

function syncPortalAccountManage(set: Set<PermissionKey>) {
  const all = PORTAL_ACCOUNT_ACTIONS.every((key) => set.has(key));
  if (all) set.add("portal.account.manage");
  else set.delete("portal.account.manage");
}

export function leafPermissionActive(selected: PermissionKey[], key: PermissionKey): boolean {
  if (selected.includes(key)) return true;
  if (PORTAL_ACCOUNT_ACTIONS.includes(key) && selected.includes("portal.account.manage")) return true;
  return false;
}

export function modulePermissionState(
  selected: PermissionKey[],
  module: AdminPermissionModule,
): "all" | "none" | "some" {
  const visible = module.children.filter((leaf) => !leaf.treeHidden);
  const active = visible.filter((leaf) => leafPermissionActive(selected, leaf.key));
  if (active.length === 0) return "none";
  if (active.length === visible.length) return "all";
  return "some";
}

export function toggleAdminPermissionLeaf(
  current: PermissionKey[],
  key: PermissionKey,
  checked: boolean,
): PermissionKey[] {
  const set = new Set(current);
  if (key === "portal.account.manage") {
    if (checked) {
      set.add("portal.account.manage");
      PORTAL_ACCOUNT_ACTIONS.forEach((item) => set.add(item));
    } else {
      set.delete("portal.account.manage");
      PORTAL_ACCOUNT_ACTIONS.forEach((item) => set.delete(item));
    }
    return orderedKeys(set);
  }
  if (checked) set.add(key);
  else set.delete(key);
  if (PORTAL_ACCOUNT_ACTIONS.includes(key)) syncPortalAccountManage(set);
  return orderedKeys(set);
}

export function toggleAdminPermissionModule(
  current: PermissionKey[],
  module: AdminPermissionModule,
  checked: boolean,
): PermissionKey[] {
  let next = [...current];
  for (const leaf of module.children) {
    if (leaf.treeHidden) continue;
    next = toggleAdminPermissionLeaf(next, leaf.key, checked);
  }
  return next;
}
