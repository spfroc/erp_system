import { describe, expect, it } from "vitest";

import { seedData } from "./seed";
import {
  buildServiceProjectDuplicateConfirmMessage,
  findDuplicateServiceProjects,
  isTerminatedServiceProject,
  normalizeServiceEndDate,
} from "./serviceProjectDuplicate";
import type { Project } from "./types";

const base = seedData.projects.find((item) => item.id === "pj-2") as Project;

describe("serviceProjectDuplicate", () => {
  it("normalizes end dates to YYYY-MM-DD", () => {
    expect(normalizeServiceEndDate("2028-06-23T12:00:00")).toBe("2028-06-23");
    expect(normalizeServiceEndDate(" 2028-06-23 ")).toBe("2028-06-23");
    expect(normalizeServiceEndDate("")).toBe("");
  });

  it("treats 终止 / 终止合作 / 项目终止 as terminated", () => {
    expect(isTerminatedServiceProject({ status: "项目终止" })).toBe(true);
    expect(isTerminatedServiceProject({ status: "终止合作" })).toBe(true);
    expect(isTerminatedServiceProject({ status: "终止" })).toBe(true);
    expect(isTerminatedServiceProject({ status: "入驻中" })).toBe(false);
  });

  it("finds duplicates on the five keys and skips terminated projects", () => {
    const active: Project = { ...base, id: "pj-dup-a", status: "服务中" };
    const terminated: Project = { ...base, id: "pj-dup-b", status: "项目终止" };
    const otherProduct: Project = { ...base, id: "pj-dup-c", serviceProductId: "prd-other" };
    const projects = [active, terminated, otherProduct];

    const hits = findDuplicateServiceProjects(projects, {
      customerOrgId: base.customerOrgId,
      ownCompanyOrgId: base.ownCompanyOrgId!,
      sourcePlatform: base.sourcePlatform!,
      serviceProductId: base.serviceProductId!,
      serviceEndDate: base.serviceEndDate!,
    });

    expect(hits.map((item) => item.id)).toEqual(["pj-dup-a"]);
  });

  it("excludes the project being edited", () => {
    const hits = findDuplicateServiceProjects([base], {
      customerOrgId: base.customerOrgId,
      ownCompanyOrgId: base.ownCompanyOrgId!,
      sourcePlatform: base.sourcePlatform!,
      serviceProductId: base.serviceProductId!,
      serviceEndDate: base.serviceEndDate!,
    }, { excludeProjectId: base.id });
    expect(hits).toEqual([]);
  });

  it("returns empty when required key fields are missing", () => {
    expect(findDuplicateServiceProjects([base], {
      customerOrgId: base.customerOrgId,
      ownCompanyOrgId: "",
      sourcePlatform: base.sourcePlatform!,
      serviceProductId: base.serviceProductId!,
      serviceEndDate: base.serviceEndDate!,
    })).toEqual([]);
  });

  it("builds a confirm message with allow-continue wording", () => {
    const message = buildServiceProjectDuplicateConfirmMessage([base], "创建");
    expect(message).toContain(base.projectNo);
    expect(message).toContain("是否仍要创建？");
  });
});
