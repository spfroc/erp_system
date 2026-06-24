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
    const migrated = {
      ...seedData,
      ...(current as Partial<AppData>),
      users: (current as Partial<AppData>).users ?? seedData.users,
      roles: (current as Partial<AppData>).roles ?? seedData.roles,
    } as AppData;
    if (!(current as Partial<AppData>).users || !(current as Partial<AppData>).roles) {
      await db.put(STORE, migrated, KEY);
    }
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
