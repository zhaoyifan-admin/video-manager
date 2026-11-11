"""常驻回归测试（零额外依赖，标准库 unittest + Flask test client）

运行：
    cd backend
    ./venv/bin/python -m unittest discover -s tests -v

测试账号与视频使用 __test_ 前缀，结束后由外键级联清理，不污染真实数据。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402
from app import app  # noqa: E402
from auth import hash_password  # noqa: E402

PREFIX = "__test_"


class CoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ids = {}
        for key, role in (("admin", "admin"), ("user", "user"), ("reviewer", "reviewer")):
            name = PREFIX + key
            db.execute("DELETE FROM users WHERE username = %s", (name,))
            result = db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                (name, hash_password("test123456"), role),
            )
            cls.ids[key] = result["lastrowid"]
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        for key in cls.ids:
            db.execute("DELETE FROM users WHERE username = %s", (PREFIX + key,))

    # ---------- helpers ----------
    def login_as(self, key):
        with self.client.session_transaction() as sess:
            sess.clear()
            sess["user_id"] = self.ids[key]
            sess.permanent = True

    def call(self, method, path, key="user", expect=200, **kwargs):
        self.login_as(key)
        resp = getattr(self.client, method)(path, **kwargs)
        self.assertEqual(resp.status_code, expect, f"{method.upper()} {path} -> HTTP {resp.status_code}: {resp.get_json()}")
        return resp.get_json()

    def ok(self, body):
        self.assertEqual(body.get("code"), 0, body)
        return body.get("data")

    def make_video(self, key="admin", title="测试片", path="uploads/__test.mp4", **extra):
        payload = {"title": title, "filePath": path, "tags": [], "description": "", **extra}
        return self.ok(self.call("post", "/api/videos", key, json=payload))["id"]

    def audit(self, vid, status, reason="", key="admin"):
        return self.call("post", f"/api/videos/{vid}/audit", key, json={"status": status, "reason": reason})

    # ---------- 配置与路径安全 ----------
    def test_01_public_config(self):
        data = self.ok(self.call("get", "/api/auth/config", "user"))
        self.assertIn("registrationEnabled", data)
        self.assertIn("maxVideosPerUser", data)

    def test_02_path_whitelist_rejects_arbitrary_files(self):
        for bad in ("/etc/passwd", "/Users/shared/.ssh/id_rsa", "uploads/../../etc/passwd"):
            body = self.call("post", "/api/videos", "user", expect=400, json={
                "title": "越界路径", "filePath": bad, "tags": [],
            })
            self.assertNotEqual(body["code"], 0, f"应拒绝：{bad}")
        vid = self.make_video("user", "合法路径")
        self.assertIsInstance(vid, int)
        # 白名单外的路径不能被当做本地文件读取；文件不存在时同样返回 404
        self.assertEqual(self.call("get", f"/api/videos/{vid}/file", "user", expect=404)["code"], 1)

    def test_03_delete_does_not_remove_file_outside_whitelist(self):
        outside = "/tmp/__test_video_manager_outside.mp4"
        with open(outside, "wb") as f:
            f.write(b"keep me")
        try:
            vid = db.execute(
                "INSERT INTO videos (user_id, title, file_path, audit_status) VALUES (%s, %s, %s, 1)",
                (self.ids["user"], "白名单外文件", outside),
            )["lastrowid"]
            data = self.ok(self.call("delete", f"/api/videos/{vid}", "user"))
            self.assertFalse(data["fileDeleted"])
            self.assertTrue(os.path.isfile(outside), "不应删除白名单外的真实文件")
        finally:
            if os.path.isfile(outside):
                os.remove(outside)

    # ---------- 审核绕过修复 ----------
    def test_04_changing_file_reopens_audit(self):
        vid = self.make_video("admin", "先过审的片")
        row = db.query("SELECT audit_status FROM videos WHERE id = %s", (vid,), one=True)
        self.assertEqual(row["audit_status"], 1)  # 管理员上传免审通过
        self.ok(self.call("post", f"/api/videos/{vid}/public", "admin"))
        self.assertEqual(db.query("SELECT is_public FROM videos WHERE id = %s", (vid,), one=True)["is_public"], 1)

        self.ok(self.call("put", f"/api/videos/{vid}", "admin", json={
            "title": "换片后", "filePath": "uploads/__test_replaced.mp4", "tags": [], "description": "",
        }))
        row = db.query("SELECT audit_status, is_public FROM videos WHERE id = %s", (vid,), one=True)
        self.assertEqual(row["audit_status"], 0, "换片必须回到待审核")
        self.assertEqual(row["is_public"], 0, "换片必须收回公开")
        actions = [r["action"] for r in db.query(
            "SELECT action FROM video_audit_logs WHERE video_id = %s ORDER BY id", (vid,)
        )]
        self.assertIn("resubmit", actions)

    def test_05_editing_title_keeps_approved_state(self):
        vid = self.make_video("admin", "只改标题")
        self.ok(self.call("put", f"/api/videos/{vid}", "admin", json={
            "title": "改了标题", "filePath": "uploads/__test.mp4", "tags": [], "description": "",
        }))
        self.assertEqual(
            db.query("SELECT audit_status FROM videos WHERE id = %s", (vid,), one=True)["audit_status"], 1
        )

    # ---------- 热度去重 / 续播 / 通知 ----------
    def test_06_view_count_deduplicated_per_user_day(self):
        vid = self.make_video("user", "播放去重")
        before = db.query("SELECT view_count FROM videos WHERE id = %s", (vid,), one=True)["view_count"]
        first = self.ok(self.call("post", f"/api/videos/{vid}/view", "user"))
        second = self.ok(self.call("post", f"/api/videos/{vid}/view", "user"))
        self.assertTrue(first["counted"])
        self.assertFalse(second["counted"], "同一用户同一天重复刷新不应加热度")
        self.ok(self.call("post", f"/api/videos/{vid}/view", "reviewer"))
        after = db.query("SELECT view_count FROM videos WHERE id = %s", (vid,), one=True)["view_count"]
        self.assertEqual(after, before + 2)

    def test_07_progress_save_and_reset_when_finished(self):
        vid = self.make_video("user", "续播")
        self.ok(self.call("post", f"/api/videos/{vid}/progress", "user",
                          json={"position": 42, "duration": 100}))
        data = self.ok(self.call("get", f"/api/videos/{vid}/progress", "user"))
        self.assertEqual(data["position"], 42)
        self.ok(self.call("post", f"/api/videos/{vid}/progress", "user",
                          json={"position": 96, "duration": 100}))
        self.assertEqual(self.ok(self.call("get", f"/api/videos/{vid}/progress", "user"))["position"], 0)

    def test_08_reject_notification_unread_and_read(self):
        vid = self.make_video("user", "待驳回")
        # 驳回缺理由应被拒绝（HTTP 400）
        self.login_as("admin")
        no_reason = self.client.post(f"/api/videos/{vid}/audit", json={"status": 2, "reason": ""})
        self.assertEqual(no_reason.status_code, 400)
        self.assertNotEqual(no_reason.get_json()["code"], 0)
        self.ok(self.audit(vid, 2, "画面不清晰，请重新上传"))
        self.assertEqual(self.ok(self.call("get", "/api/notifications/unread-count", "user"))["count"], 1)
        items = self.ok(self.call("get", "/api/notifications", "user"))["items"]
        self.assertTrue(any(x["reason"] == "画面不清晰，请重新上传" for x in items))
        self.ok(self.call("post", "/api/notifications/read", "user", json={"ids": None}))
        self.assertEqual(self.ok(self.call("get", "/api/notifications/unread-count", "user"))["count"], 0)

    # ---------- 权限 ----------
    def test_09_reviewer_can_audit_but_not_manage(self):
        vid = self.make_video("user", "审核员测试")
        self.ok(self.audit(vid, 1, key="reviewer"))
        body = self.call("delete", f"/api/videos/{vid}", "reviewer", expect=404)
        self.assertNotEqual(body["code"], 0, "审核员不应能删除他人视频")
        scope = self.call("get", "/api/videos?scope=audit", "user", expect=403)
        self.assertNotEqual(scope["code"], 0, "普通用户不应访问审核范围")
        self.assertEqual(self.ok(self.call("get", "/api/videos?scope=audit&pageSize=1", "reviewer"))["page"], 1)

    def test_10_admin_overview_is_admin_only(self):
        self.assertEqual(self.call("get", "/api/admin/overview", "user", expect=403)["code"], 1)
        data = self.ok(self.call("get", "/api/admin/overview", "admin"))
        self.assertIn("videos", data)
        self.assertIn("hot", data)

    # ---------- 排序 / 合集 / 存储 ----------
    def test_11_sort_and_collection(self):
        cid = self.ok(self.call("post", "/api/collections", "admin",
                                json={"name": PREFIX + "合集"}))["id"]
        vid = self.make_video("admin", "合集内的片", collectionId=cid)
        data = self.ok(self.call("get", f"/api/videos?sort=hot&collectionId={cid}", "admin"))
        self.assertIn(vid, [x["id"] for x in data["items"]])
        listed = self.ok(self.call("get", "/api/collections", "admin"))["items"]
        self.assertTrue(any(x["id"] == cid and x["videoCount"] >= 1 for x in listed))
        self.ok(self.call("delete", f"/api/collections/{cid}", "admin"))

    def test_12_integrity_and_relocate_dry_run(self):
        vid = self.make_video("user", "路径重定位")
        report = self.ok(self.call("get", "/api/videos/integrity", "user"))
        self.assertIn("roots", report)
        old = "uploads/__test.mp4"
        result = self.ok(self.call("post", "/api/videos/relocate", "user", json={
            "oldPrefix": old, "newPrefix": "uploads/__test2.mp4", "dryRun": True,
        }))
        self.assertTrue(result["dryRun"])
        self.assertGreaterEqual(result["updated"], 1)
        self.assertEqual(
            db.query("SELECT file_path FROM videos WHERE id = %s", (vid,), one=True)["file_path"], old,
            "预览不应修改数据",
        )

    def test_13_batch_import_validates_paths(self):
        body = self.ok(self.call("post", "/api/videos/batch", "user", json={"items": [
            {"title": "合法", "filePath": "uploads/__test_batch.mp4"},
            {"title": "越界", "filePath": "/etc/passwd"},
        ]}))
        self.assertEqual(body["success"], 1)
        self.assertEqual(len(body["failed"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
