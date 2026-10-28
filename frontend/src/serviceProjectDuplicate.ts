import type { Project, ProjectStatus } from "./types";

/** 已终止类状态：不参与服务项目重复查重。 */
export const TERMINATED_SERVICE_PROJECT_STATUSES: ReadonlySet<ProjectStatus> = new Set([
  "终止",
  "终止合作",
  "项目终止",
]);

export type ServiceProjectDuplicateKey = {
  customerOrgId: string;
  ownCompanyOrgId: string;
  sourcePlatform: string;
  serviceProductId: string;
  serviceEndDate: string;
};

export function isTerminatedServiceProject(project: Pick<Project, "status">): boolean {
  return TERMINATED_SERVICE_PROJECT_STATUSES.has(project.status);
}

/** 到期日统一为 YYYY-MM-DD，便于比较。 */
export function normalizeServiceEndDate(value?: string | null): string {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  return raw.slice(0, 10);
}

export function findDuplicateServiceProjects(
  projects: Project[],
  key: ServiceProjectDuplicateKey,
  options?: { excludeProjectId?: string },
): Project[] {
  const customerOrgId = key.customerOrgId.trim();
  const ownCompanyOrgId = key.ownCompanyOrgId.trim();
  const sourcePlatform = key.sourcePlatform.trim();
  const serviceProductId = key.serviceProductId.trim();
  const serviceEndDate = normalizeServiceEndDate(key.serviceEndDate);
  if (!customerOrgId || !ownCompanyOrgId || !sourcePlatform || !serviceProductId || !serviceEndDate) {
    return [];
  }
  const excludeId = options?.excludeProjectId;
  return projects.filter((project) => {
    if (project.type !== "服务项目") return false;
    if (excludeId && project.id === excludeId) return false;
    if (isTerminatedServiceProject(project)) return false;
    return (
      project.customerOrgId === customerOrgId
      && (project.ownCompanyOrgId || "") === ownCompanyOrgId
      && (project.sourcePlatform || "") === sourcePlatform
      && (project.serviceProductId || "") === serviceProductId
      && normalizeServiceEndDate(project.serviceEndDate) === serviceEndDate
    );
  });
}

export function buildServiceProjectDuplicateConfirmMessage(
  duplicates: Project[],
  actionLabel: "创建" | "保存",
): string {
  const lines = duplicates.slice(0, 8).map((project) => {
    const end = normalizeServiceEndDate(project.serviceEndDate) || "未设置";
    return `· ${project.projectNo} ${project.name}（到期 ${end}，状态 ${project.status}）`;
  });
  if (duplicates.length > 8) {
    lines.push(`…等共 ${duplicates.length} 条`);
  }
  return [
    "发现疑似重复服务项目（同客户、签约主体、平台、服务、到期日）：",
    ...lines,
    "",
    `是否仍要${actionLabel}？`,
  ].join("\n");
}
