from django.test import TestCase

from apps.data_store.management.commands.default_qhc_first_service import default_qinghuicai_service_projects
from apps.data_store.models import ProjectRecord
from apps.data_store.views import save_app_data


class QinghuicaiFirstServiceTests(TestCase):
    def test_sets_qinghuicai_service_projects_only(self):
        save_app_data(
            {
                "projects": [
                    {
                        "id": "pj-qhc-empty",
                        "projectNo": "FW-1",
                        "name": "青慧采未标记",
                        "type": "服务项目",
                        "customerOrgId": "c1",
                        "sourcePlatform": "青慧采",
                        "status": "入驻中",
                        "updatedAt": "2026-09-01T10:00:00",
                    },
                    {
                        "id": "pj-qhc-renew",
                        "projectNo": "FW-2",
                        "name": "青慧采续费",
                        "type": "服务项目",
                        "customerOrgId": "c1",
                        "sourcePlatform": "青慧采",
                        "serviceCustomerKind": "续费客户",
                        "status": "入驻中",
                        "updatedAt": "2026-09-01T10:00:00",
                    },
                    {
                        "id": "pj-qec",
                        "projectNo": "FW-3",
                        "name": "泉E采续费",
                        "type": "服务项目",
                        "customerOrgId": "c1",
                        "sourcePlatform": "泉E采",
                        "serviceCustomerKind": "续费客户",
                        "status": "入驻中",
                        "updatedAt": "2026-09-01T10:00:00",
                    },
                    {
                        "id": "pj-goods",
                        "projectNo": "SP-1",
                        "name": "商品项目",
                        "type": "商品项目",
                        "customerOrgId": "c1",
                        "sourcePlatform": "青慧采",
                        "status": "进行中",
                        "updatedAt": "2026-09-01T10:00:00",
                    },
                ]
            }
        )
        self.assertEqual(default_qinghuicai_service_projects(), 2)
        self.assertEqual(default_qinghuicai_service_projects(), 0)

        by_id = {record.id: record.data for record in ProjectRecord.objects.filter(is_deleted=False)}
        self.assertEqual(by_id["pj-qhc-empty"]["serviceCustomerKind"], "首次服务")
        self.assertEqual(by_id["pj-qhc-renew"]["serviceCustomerKind"], "首次服务")
        self.assertEqual(by_id["pj-qec"]["serviceCustomerKind"], "续费客户")
        self.assertNotIn("serviceCustomerKind", by_id["pj-goods"])
