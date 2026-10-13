"""Build normalized initialization data from the legacy Excel workbooks.

The current backend models are not implemented yet, so this script writes a
stable JSON payload that can later be loaded by a Django management command.
It intentionally keeps raw source fields for auditability.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import ZipFile


SPREADSHEET_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


@dataclass(frozen=True)
class SheetRows:
    workbook: str
    sheet: str
    rows: list[dict[str, str]]


def col_to_index(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha())
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch.upper()) - ord("A") + 1)
    return max(index - 1, 0)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u3000", " ").strip()
    return re.sub(r"\s+", " ", text)


def normalize_key(value: str) -> str:
    return normalize_text(value).replace(" ", "").replace("\n", "")


def make_id(prefix: str, value: str) -> str:
    raw = normalize_key(value).lower()
    raw = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "-", raw).strip("-")
    return f"{prefix}_{raw[:80]}" if raw else f"{prefix}_unknown"


def first_value(row: dict[str, str], *keys: str) -> str:
    normalized = {normalize_key(k): v for k, v in row.items()}
    for key in keys:
        value = normalized.get(normalize_key(key), "")
        if normalize_text(value):
            return normalize_text(value)
    return ""


def resolve_xlsx_target(target: str) -> str:
    target = target.lstrip("/")
    if target.startswith("xl/"):
        return target
    return f"xl/{target}"


class XlsxReader:
    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> list[SheetRows]:
        with ZipFile(self.path) as archive:
            shared = self._shared_strings(archive)
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}

            sheets: list[SheetRows] = []
            for sheet in workbook.findall("a:sheets/a:sheet", SPREADSHEET_NS):
                name = sheet.attrib["name"]
                rel_id = sheet.attrib[f"{{{REL_NS}}}id"]
                sheet_path = resolve_xlsx_target(relmap[rel_id])
                rows = self._sheet_rows(archive, sheet_path, shared)
                dict_rows = self._dict_rows(rows)
                sheets.append(SheetRows(self.path.name, name, dict_rows))
            return sheets

    def _shared_strings(self, archive: ZipFile) -> list[str]:
        try:
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        except KeyError:
            return []

        values: list[str] = []
        for item in root.findall("a:si", SPREADSHEET_NS):
            text = "".join(node.text or "" for node in item.findall(".//a:t", SPREADSHEET_NS))
            values.append(text)
        return values

    def _cell_value(self, cell: ET.Element, shared: list[str]) -> str:
        value_type = cell.attrib.get("t")
        value_node = cell.find("a:v", SPREADSHEET_NS)

        if value_type == "s" and value_node is not None:
            try:
                return shared[int(value_node.text or "0")]
            except (IndexError, ValueError):
                return ""
        if value_type == "inlineStr":
            return "".join(node.text or "" for node in cell.findall(".//a:t", SPREADSHEET_NS))
        if value_node is not None and value_node.text is not None:
            return value_node.text
        return ""

    def _sheet_rows(self, archive: ZipFile, sheet_path: str, shared: list[str]) -> list[list[str]]:
        root = ET.fromstring(archive.read(sheet_path))
        parsed_rows: list[list[str]] = []
        for row in root.findall("a:sheetData/a:row", SPREADSHEET_NS):
            cells: list[str] = []
            for cell in row.findall("a:c", SPREADSHEET_NS):
                ref = cell.attrib.get("r", "")
                index = col_to_index(ref)
                while len(cells) <= index:
                    cells.append("")
                cells[index] = normalize_text(self._cell_value(cell, shared))
            parsed_rows.append(cells)
        return parsed_rows

    def _dict_rows(self, rows: list[list[str]]) -> list[dict[str, str]]:
        header_index = -1
        headers: list[str] = []
        for index, row in enumerate(rows[:20]):
            non_empty = [normalize_text(value) for value in row if normalize_text(value)]
            if len(non_empty) >= 2:
                header_index = index
                headers = [normalize_text(value) for value in row]
                break
        if header_index < 0:
            return []

        result: list[dict[str, str]] = []
        for row in rows[header_index + 1 :]:
            item: dict[str, str] = {}
            for index, header in enumerate(headers):
                if not header:
                    continue
                item[header] = normalize_text(row[index] if index < len(row) else "")
            if any(item.values()):
                result.append(item)
        return result


class ImportBuilder:
    def __init__(self) -> None:
        self.organizations: dict[str, dict[str, Any]] = {}
        self.products: dict[str, dict[str, Any]] = {}
        self.channel_prices: list[dict[str, Any]] = []
        self.projects: list[dict[str, Any]] = []
        self.orders: list[dict[str, Any]] = []
        self.platform_accounts: list[dict[str, Any]] = []
        self.report: dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "files": [],
            "warnings": [],
            "counts": {},
        }

    def add_file(self, path: Path, sheets: list[SheetRows]) -> None:
        self.report["files"].append(
            {
                "file": path.name,
                "sheets": [{"name": sheet.sheet, "rows": len(sheet.rows)} for sheet in sheets],
            }
        )
        for sheet in sheets:
            self.consume_sheet(sheet)

    def consume_sheet(self, sheet: SheetRows) -> None:
        name = normalize_key(sheet.sheet)
        if "客户信息" in name:
            self._organizations(sheet, "customer")
        elif "渠道信息" in name:
            self._organizations(sheet, "supplier")
        elif "使用单位信息" in name:
            self._organizations(sheet, "usage_unit")
        elif "价格体系" in name:
            self._products_and_prices(sheet)
        elif "渠道采购" in name:
            self._purchase_orders(sheet)
        elif "订单管理" in name:
            self._projects_and_sales_orders(sheet)
        elif "服务" in name or "客户" in name or "CA" in name:
            self._platform_accounts(sheet)

    def _upsert_org(self, name: str, role: str, row: dict[str, str]) -> str:
        if not name:
            return ""
        org_id = make_id("org", name)
        current = self.organizations.setdefault(
            org_id,
            {
                "id": org_id,
                "name": name,
                "entity_type": "enterprise",
                "roles": [],
                "contact": "",
                "phone": "",
                "address": "",
                "invoice_info": "",
                "payment_account": "",
                "source_files": [],
                "raw_samples": [],
            },
        )
        if role not in current["roles"]:
            current["roles"].append(role)
        current["contact"] = current["contact"] or first_value(row, "联系人", "联系", "联系人姓名")
        current["phone"] = current["phone"] or first_value(row, "联系电话", "电话", "联系人电话", "手机号")
        current["address"] = current["address"] or first_value(row, "地址", "收货信息")
        current["invoice_info"] = current["invoice_info"] or first_value(row, "开票信息", "发票信息")
        current["payment_account"] = current["payment_account"] or first_value(row, "收款信息", "收款账号")
        if row.get("_source_file") and row["_source_file"] not in current["source_files"]:
            current["source_files"].append(row["_source_file"])
        if len(current["raw_samples"]) < 3:
            current["raw_samples"].append(row)
        return org_id

    def _organizations(self, sheet: SheetRows, role: str) -> None:
        for row in sheet.rows:
            row = {**row, "_source_file": sheet.workbook, "_source_sheet": sheet.sheet}
            name = first_value(row, "公司名称", "单位全称", "客户名称", "企业名称")
            self._upsert_org(name, role, row)

    def _products_and_prices(self, sheet: SheetRows) -> None:
        for row in sheet.rows:
            row = {**row, "_source_file": sheet.workbook, "_source_sheet": sheet.sheet}
            product_name = first_value(row, "商品名称", "产品名称", "商品")
            model = first_value(row, "型号", "规格型号", "规格")
            if not product_name:
                continue
            product_key = f"{product_name}|{model}"
            product_id = make_id("prd", product_key)
            self.products.setdefault(
                product_id,
                {
                    "id": product_id,
                    "name": product_name,
                    "model": model,
                    "category": first_value(row, "商品类别", "商品类型", "分类"),
                    "kind": "physical",
                    "raw_samples": [],
                },
            )
            if len(self.products[product_id]["raw_samples"]) < 3:
                self.products[product_id]["raw_samples"].append(row)

            supplier_name = first_value(row, "渠道", "供应商", "公司名称", "渠道名称")
            supplier_id = self._upsert_org(supplier_name, "supplier", row) if supplier_name else ""
            purchase_price = first_value(row, "成本单价", "进货价", "采购价", "成本", "价格")
            sale_price = first_value(row, "售价", "公司报价", "报价")
            if supplier_id or purchase_price or sale_price:
                self.channel_prices.append(
                    {
                        "product_id": product_id,
                        "supplier_org_id": supplier_id,
                        "purchase_price": purchase_price,
                        "sale_price": sale_price,
                        "effective_date": first_value(row, "生效日期", "日期", "创建时间"),
                        "raw": row,
                    }
                )

    def _projects_and_sales_orders(self, sheet: SheetRows) -> None:
        for index, row in enumerate(sheet.rows, start=1):
            row = {**row, "_source_file": sheet.workbook, "_source_sheet": sheet.sheet}
            customer_id = self._upsert_org(
                first_value(row, "客户信息/渠道信息", "客户信息", "客户名称", "公司名称"),
                "customer",
                row,
            )
            usage_unit_id = self._upsert_org(first_value(row, "使用单位", "单位全称"), "usage_unit", row)
            product_name = first_value(row, "商品名称", "商品")
            project_id = make_id("proj", first_value(row, "自动编号", "订单编号") or f"{sheet.workbook}-{index}")
            self.projects.append(
                {
                    "id": project_id,
                    "type": "product_order",
                    "customer_org_id": customer_id,
                    "usage_unit_org_id": usage_unit_id,
                    "status": first_value(row, "状态"),
                    "amount": first_value(row, "金额", "实际到账", "售价"),
                    "contract_status": first_value(row, "合同"),
                    "invoice_status": first_value(row, "发票"),
                    "platform": first_value(row, "订单来源平台", "平台"),
                    "platform_order_no": first_value(row, "政采订单", "平台订单号"),
                    "raw": row,
                }
            )
            self.orders.append(
                {
                    "project_id": project_id,
                    "order_type": "sales",
                    "product_name": product_name,
                    "amount": first_value(row, "金额", "售价"),
                    "platform": first_value(row, "订单来源平台", "平台"),
                    "platform_order_no": first_value(row, "政采订单", "平台订单号"),
                    "raw": row,
                }
            )

    def _purchase_orders(self, sheet: SheetRows) -> None:
        for index, row in enumerate(sheet.rows, start=1):
            row = {**row, "_source_file": sheet.workbook, "_source_sheet": sheet.sheet}
            supplier_id = self._upsert_org(first_value(row, "采购渠道", "渠道", "供应商"), "supplier", row)
            usage_unit_id = self._upsert_org(first_value(row, "使用单位"), "usage_unit", row)
            self.orders.append(
                {
                    "id": make_id("po", f"{sheet.workbook}-{sheet.sheet}-{index}"),
                    "order_type": "purchase",
                    "supplier_org_id": supplier_id,
                    "usage_unit_org_id": usage_unit_id,
                    "product_name": first_value(row, "商品名称", "商品"),
                    "quantity": first_value(row, "数量"),
                    "purchase_price": first_value(row, "进货单价", "采购价", "单价"),
                    "amount": first_value(row, "进货总价", "总价", "金额"),
                    "invoice_status": first_value(row, "发票"),
                    "raw": row,
                }
            )

    def _platform_accounts(self, sheet: SheetRows) -> None:
        for index, row in enumerate(sheet.rows, start=1):
            row = {**row, "_source_file": sheet.workbook, "_source_sheet": sheet.sheet}
            customer_name = first_value(row, "公司名称", "客户名称", "客户")
            if not customer_name:
                continue
            customer_id = self._upsert_org(customer_name, "customer", row)
            self.platform_accounts.append(
                {
                    "id": make_id("acct", f"{sheet.workbook}-{sheet.sheet}-{index}"),
                    "customer_org_id": customer_id,
                    "platform": first_value(row, "平台", "地区", "服务平台"),
                    "account": first_value(row, "账号", "鲁采账号", "平台账号", "用户"),
                    "password": first_value(row, "密码", "鲁采密码", "平台密码"),
                    "supplier_account": first_value(row, "供应商账号", "供应商账号密码"),
                    "cloud_account": first_value(row, "云账号", "政务云账号密码"),
                    "domain": first_value(row, "域名"),
                    "icp": first_value(row, "ICP备案", "备案"),
                    "ca_status": first_value(row, "CA办理", "CA"),
                    "status": first_value(row, "客户状态", "目前客户状态", "服务状态"),
                    "raw": row,
                }
            )

    def build(self) -> dict[str, Any]:
        payload = {
            "organizations": sorted(self.organizations.values(), key=lambda item: item["id"]),
            "products": sorted(self.products.values(), key=lambda item: item["id"]),
            "channel_prices": self.channel_prices,
            "projects": self.projects,
            "orders": self.orders,
            "platform_accounts": self.platform_accounts,
            "import_report": self.report,
        }
        self.report["counts"] = {
            key: len(value)
            for key, value in payload.items()
            if isinstance(value, list)
        }
        return payload


def load_directory(input_dir: Path) -> dict[str, Any]:
    builder = ImportBuilder()
    files = sorted(input_dir.glob("*.xlsx"))
    if not files:
        builder.report["warnings"].append(f"No .xlsx files found in {input_dir}")
    for path in files:
        try:
            sheets = XlsxReader(path).read()
        except Exception as exc:  # noqa: BLE001 - report and continue for legacy files.
            builder.report["warnings"].append(f"{path.name}: failed to read workbook: {exc}")
            continue
        builder.add_file(path, sheets)
    return builder.build()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import legacy Excel data into normalized JSON.")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", action="store_true", help="Print import counts to stdout.")
    args = parser.parse_args(argv)

    payload = load_directory(args.input_dir)
    write_json(args.output, payload)

    if args.summary:
        print(json.dumps(payload["import_report"]["counts"], ensure_ascii=False, indent=2))
        for warning in payload["import_report"]["warnings"]:
            print(f"WARNING: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

