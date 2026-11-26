export const PORTAL_PERMISSION_OPTIONS = [
  { id: "portal.notice.view", label: "公告列表", hint: "登录后可检索、筛选已采集公告", group: "公告与数据" },
  { id: "portal.stats.view", label: "数据统计", hint: "查看总量、平台分布、成交标签分析与近两周趋势", group: "公告与数据" },
  { id: "portal.notice.subscribe", label: "订阅消息", hint: "门户按标签/地区/关键词等订阅，微信服务号每日汇总推送", group: "公告与数据" },
  { id: "portal.order.view", label: "企业订单", hint: "查看本企业销售/服务订单", group: "企业业务" },
  { id: "portal.invoice.view", label: "企业发票", hint: "查看本企业作为买方的发票", group: "企业业务" },
  { id: "portal.contract.view", label: "企业合同", hint: "查看本企业相关合同附件", group: "企业业务" },
  { id: "portal.account.view", label: "查看", hint: "查看同企业可登录门户的账号", group: "企业账号" },
  { id: "portal.account.create", label: "新增", hint: "在门户新增同企业登录账号", group: "企业账号" },
  { id: "portal.account.edit", label: "编辑", hint: "修改同企业账号资料、状态与权限", group: "企业账号" },
  { id: "portal.account.delete", label: "删除", hint: "删除同企业其他门户账号", group: "企业账号" },
  /** 兼容旧数据；树状 UI 不单独展示，由「企业账号」父节点一键勾选同步 */
  { id: "portal.account.manage", label: "企业账号全部管理", hint: "兼容旧配置：蕴含查看/新增/编辑/删除", group: "企业账号", treeHidden: true },
] as const;

export const PORTAL_PERMISSION_GROUPS = [
  { title: "公告与数据", description: "公告检索、统计与订阅推送" },
  { title: "企业业务", description: "订单、发票、合同只读查看" },
  { title: "企业账号", description: "同企业门户账号的查看与增删改" },
] as const;

export const PORTAL_ACCOUNT_ACTION_IDS = [
  "portal.account.view",
  "portal.account.create",
  "portal.account.edit",
  "portal.account.delete",
] as const;

export const PORTAL_SITE_OPTIONS = [
  { id: "sd-ggzyjyzx", label: "山东网上商城" },
  { id: "jd-quan-yicai", label: "京东泉易采" },
  { id: "jd-qing-huicai", label: "京东青慧采" },
] as const;

export type PortalPermission = (typeof PORTAL_PERMISSION_OPTIONS)[number]["id"];

type PortalPermissionOption = (typeof PORTAL_PERMISSION_OPTIONS)[number];

function isTreeHidden(option: PortalPermissionOption) {
  return "treeHidden" in option && option.treeHidden === true;
}

export function portalPermissionTree() {
  return PORTAL_PERMISSION_GROUPS.map((group) => ({
    ...group,
    children: PORTAL_PERMISSION_OPTIONS.filter((item) => item.group === group.title && !isTreeHidden(item)),
  })).filter((group) => group.children.length > 0);
}

export function portalPermissionOptionsByGroup() {
  return portalPermissionTree().map((group) => ({
    title: group.title,
    description: group.description,
    options: group.children,
  }));
}

function orderedPermissions(set: Set<string>): string[] {
  return PORTAL_PERMISSION_OPTIONS.map((item) => item.id).filter((id) => set.has(id));
}

/** manage 与细分权限互相同步。 */
export function syncPortalAccountPermissions(
  current: string[],
  toggledId: string,
  checked: boolean,
): string[] {
  const set = new Set(current);
  if (toggledId === "portal.account.manage") {
    if (checked) {
      set.add("portal.account.manage");
      PORTAL_ACCOUNT_ACTION_IDS.forEach((id) => set.add(id));
    } else {
      set.delete("portal.account.manage");
      PORTAL_ACCOUNT_ACTION_IDS.forEach((id) => set.delete(id));
    }
    return orderedPermissions(set);
  }
  if (checked) set.add(toggledId);
  else set.delete(toggledId);
  if (PORTAL_ACCOUNT_ACTION_IDS.includes(toggledId as (typeof PORTAL_ACCOUNT_ACTION_IDS)[number])) {
    const allActions = PORTAL_ACCOUNT_ACTION_IDS.every((id) => set.has(id));
    if (allActions) set.add("portal.account.manage");
    else set.delete("portal.account.manage");
  }
  return orderedPermissions(set);
}

export function permissionLeafActive(selected: string[], id: string): boolean {
  if (selected.includes(id)) return true;
  if (PORTAL_ACCOUNT_ACTION_IDS.includes(id as (typeof PORTAL_ACCOUNT_ACTION_IDS)[number]) && selected.includes("portal.account.manage")) {
    return true;
  }
  return false;
}

export function permissionGroupState(selected: string[], childIds: string[]): "all" | "none" | "some" {
  const active = childIds.filter((id) => permissionLeafActive(selected, id));
  if (active.length === 0) return "none";
  if (active.length === childIds.length) return "all";
  return "some";
}

export function togglePortalPermissionGroup(
  current: string[],
  childIds: string[],
  checked: boolean,
  allowedIds?: string[] | null,
): string[] {
  let next = [...current];
  const allow = allowedIds == null ? null : new Set(allowedIds);
  for (const id of childIds) {
    if (allow && !allow.has(id) && !permissionLeafActive(current, id)) continue;
    next = syncPortalAccountPermissions(next, id, checked);
  }
  return next;
}
