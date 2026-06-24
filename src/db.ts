import { openDB } from "idb";
import { seedData } from "./seed";
import type { AppData } from "./types";

const DB_NAME = "yicai-erp-prototype";
const STORE = "app";
const KEY = "data";

async function getDatabase() {
  return openDB(DB_NAME, 1, {
    upgrade(db) {
      db.createObjectStore(STORE);
    },
  });
}

export async function loadData(): Promise<AppData> {
  const db = await getDatabase();
  const current = await db.get(STORE, KEY);
  if (current) {
    const partial = current as Partial<AppData>;
    const organizationIds = new Set((partial.organizations ?? []).map((org) => org.id));
    const missingSeedOrganizations = seedData.organizations.filter((org) => !organizationIds.has(org.id));
    const migrated = {
      ...seedData,
      ...partial,
      organizations: [...(partial.organizations ?? []), ...missingSeedOrganizations],
      users: partial.users ?? seedData.users,
      roles: partial.roles ?? seedData.roles,
      operationLogs: partial.operationLogs ?? seedData.operationLogs,
    } as AppData;
    migrated.projects = migrated.projects.map((project) => ({
      ...project,
      ownCompanyOrgId: project.ownCompanyOrgId ?? seedData.projects.find((item) => item.id === project.id)?.ownCompanyOrgId ?? "org-7",
      platformOrderNo: project.platformOrderNo ?? seedData.projects.find((item) => item.id === project.id)?.platformOrderNo,
    }));
    migrated.invoices = migrated.invoices.map((invoice) => {
      const seedInvoice = seedData.invoices.find((item) => item.id === invoice.id);
      return { ...seedInvoice, ...invoice };
    });
    await db.put(STORE, migrated, KEY);
    return migrated;
  }
  await db.put(STORE, seedData, KEY);
  return seedData;
}

export async function saveData(data: AppData): Promise<void> {
  const db = await getDatabase();
  await db.put(STORE, data, KEY);
}

export async function resetData(): Promise<AppData> {
  const db = await getDatabase();
  await db.put(STORE, seedData, KEY);
  return seedData;
}

export function createId(prefix: string) {
  return `${prefix}-${crypto.randomUUID().slice(0, 8)}`;
}
