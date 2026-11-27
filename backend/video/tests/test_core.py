"""常驻回归测试（零额外依赖，标准库 unittest + Flask test client）

运行：
    cd backend/video
    ./venv/bin/python tests/test_core.py

测试账号与视频使用 __test_ 前缀，结束后由外键级联清理，不污染真实数据。
"""
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

SUBSYSTEM_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_BACKEND_DIR = os.path.dirname(SUBSYSTEM_BACKEND_DIR)
sys.path.insert(0, SUBSYSTEM_BACKEND_DIR)
sys.path.insert(1, MAIN_BACKEND_DIR)

import db  # noqa: E402
from app import app  # noqa: E402
from auth import hash_password  # noqa: E402
from core.modules.video import bp as video_admin_bp  # noqa: E402

# 审核 / 站点管理 / 分类管理已移至主系统（/api/video-admin/*）。
# 测试客户端挂上同一蓝图，让原回归用例继续覆盖这些业务逻辑的真实实现。
app.register_blueprint(video_admin_bp, url_prefix="/api/video-admin")

PREFIX = "__test_"

# 旧视频侧管理接口 → 主系统新接口的路径映射
_ADMIN_STATIC = {
    "/api/admin/overview": "/api/video-admin/admin/overview",
    "/api/admin-logs": "/api/video-admin/admin/logs",
    "/api/videos/integrity": "/api/video-admin/admin/integrity",
    "/api/videos/relocate": "/api/video-admin/admin/relocate",
    "/api/audit-logs": "/api/video-admin/audit/logs",
}
_TAXONOMY = {"tags": "tag", "types": "type", "collections": "collection"}


def _map_admin_route(method, path):
    """把已搬移的管理接口映射到主系统新地址；视频侧日常接口保持不变。"""
    base, sep, query = path.partition("?")
    suffix = ("?" + query) if sep else ""
    if base in _ADMIN_STATIC:
        return _ADMIN_STATIC[base] + suffix
    m = re.match(r"^/api/videos/(\d+)/audit$", base)
    if m:
        return f"/api/video-admin/audit/videos/{m.group(1)}/review" + suffix
    m = re.match(r"^/api/(tags|types|collections)(?:/(\d+)(?:/(review|resubmit|logs))?)?$", base)
    if m:
        plural, row_id, action = m.group(1), m.group(2), m.group(3)
        if not row_id and not action:
            # 合集提交已移至主系统；标签 / 类型的用户提交仍留在视频侧
            if method == "post" and plural == "collections":
                return "/api/video-admin/taxonomy/collection" + suffix
            return path
        new = f"/api/video-admin/taxonomy/{_TAXONOMY[plural]}/{row_id}"
        return (f"{new}/{action}" if action else new) + suffix
    return path


def _map_payload(path, body):
    """主系统审核接口沿用 status(1/2) 请求体，与原视频侧一致，无需转换。"""
    return body


class CoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ids = {}
        for key, role in (("admin", "admin"), ("manager", "manager"), ("user", "user"), ("reviewer", "reviewer")):
            name = PREFIX + key
            db.execute("DELETE FROM users WHERE username = %s", (name,))
            result = db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                (name, hash_password("test123456"), role),
            )
            cls.ids[key] = result["lastrowid"]
            # 主系统权限码来自 sys_user_role，测试账号需显式关联 RBAC 角色
            db.execute(
                "INSERT INTO sys_user_role (user_id, role_id) "
                "SELECT %s, id FROM sys_role WHERE role_code = %s",
                (cls.ids[key], role),
            )
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
        mapped = _map_admin_route(method, path)
        if "json" in kwargs:
            kwargs["json"] = _map_payload(path, kwargs["json"])
        resp = getattr(self.client, method)(mapped, **kwargs)
        self.assertEqual(
            resp.status_code, expect,
            f"{method.upper()} {path} -> {mapped} -> HTTP {resp.status_code}: {resp.get_json()}",
        )
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

    def test_03_delete_source_file_three_states(self):
        # 跨平台：把白名单收窄到 uploads，验证白名单外的真实文件不被物理删除
        # （Windows 下所有盘符都在白名单内，必须收窄才能构造「白名单外」场景）
        import storage
        outside = os.path.join(tempfile.gettempdir(), "__test_video_manager_outside.mp4")
        with open(outside, "wb") as f:
            f.write(b"keep me")
        try:
            vid = db.execute(
                "INSERT INTO videos (user_id, title, file_path, audit_status) VALUES (%s, %s, %s, 1)",
                (self.ids["user"], "白名单外文件", outside),
            )["lastrowid"]
            narrow = [os.path.realpath(storage.UPLOAD_DIR)]
            with mock.patch.object(storage, "media_roots", return_value=narrow):
                data = self.ok(self.call("delete", f"/api/videos/{vid}", "user"))
            # 白名单外：文件存在但删不掉 → fileDeleted/fileMissing 均为 False（前端提示手动处理）
            self.assertFalse(data["fileDeleted"])
            self.assertFalse(data.get("fileMissing"))
            self.assertTrue(os.path.isfile(outside), "不应删除白名单外的真实文件")
        finally:
            if os.path.isfile(outside):
                os.remove(outside)

        # 白名单内：删除记录时应连源文件一起物理删除
        inside_name = "__test_inside_delete.mp4"
        inside = os.path.join(storage.UPLOAD_DIR, inside_name)
        with open(inside, "wb") as f:
            f.write(b"inside")
        vid2 = db.execute(
            "INSERT INTO videos (user_id, title, file_path, audit_status) VALUES (%s, %s, %s, 1)",
            (self.ids["user"], "白名单内文件", f"uploads/{inside_name}"),
        )["lastrowid"]
        data2 = self.ok(self.call("delete", f"/api/videos/{vid2}", "user"))
        self.assertTrue(data2["fileDeleted"])
        self.assertFalse(os.path.isfile(inside), "白名单内源文件应被一并删除")

        # 源文件本就不存在：仅清理记录，标记 fileMissing
        vid3 = db.execute(
            "INSERT INTO videos (user_id, title, file_path, audit_status) VALUES (%s, %s, %s, 1)",
            (self.ids["user"], "源文件丢失", "uploads/__test_never_existed.mp4"),
        )["lastrowid"]
        data3 = self.ok(self.call("delete", f"/api/videos/{vid3}", "user"))
        self.assertFalse(data3["fileDeleted"])
        self.assertTrue(data3["fileMissing"])

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
        no_reason = self.client.post(f"/api/video-admin/audit/videos/{vid}/review",
                                     json={"status": 2, "reason": ""})
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
        report = self.ok(self.call("get", "/api/videos/integrity", "admin"))
        self.assertIn("roots", report)
        old = "uploads/__test.mp4"
        result = self.ok(self.call("post", "/api/videos/relocate", "admin", json={
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

    # ---------- 标签：普通用户可提交待审，审核员审核发布，权限边界 ----------
    def test_14_tag_review_and_visibility(self):
        # 普通用户可提交新标签（进入待审核，不再 403）
        name = PREFIX + "标签A"
        data = self.ok(self.call("post", "/api/tags", "user", json={"name": name}))
        tid = data["id"]
        self.assertEqual(data["auditStatus"], 0)
        # 创建者本人能在列表看到（无论是否发布），且带 isMine / 发布状态供前端判断操作权限
        mine = next(t for t in self.ok(self.call("get", "/api/tags", "user")) if t["id"] == tid)
        self.assertTrue(mine["isMine"])
        self.assertFalse(mine["isPublished"])
        self.assertIsNotNone(mine["createdBy"])
        # 审核角色能看到待审核标签
        self.assertIn(name, [t["name"] for t in self.ok(self.call("get", "/api/tags", "admin"))])
        # 管理员创建未发布的标签：非创建者的普通用户不可见
        hidden = self.ok(self.call("post", "/api/tags", "admin", json={"name": PREFIX + "隐藏标", "isPublished": False}))
        self.assertNotIn(PREFIX + "隐藏标", [t["name"] for t in self.ok(self.call("get", "/api/tags", "user"))])
        # 管理员审核通过用户提交的标签 → 发布
        self.ok(self.call("post", f"/api/tags/{tid}/review", "admin", json={"action": "approve"}))
        row = db.query("SELECT is_published, audit_status FROM tags WHERE id = %s", (tid,), one=True)
        self.assertEqual(row["is_published"], 1)
        self.assertEqual(row["audit_status"], 1)
        # 驳回必须填理由
        rname = PREFIX + "标签驳回"
        rdata = self.ok(self.call("post", "/api/tags", "user", json={"name": rname}))
        rid = rdata["id"]
        self.assertEqual(self.call("post", f"/api/tags/{rid}/review", "admin", json={"action": "reject"}, expect=400)["code"], 1)
        self.ok(self.call("post", f"/api/tags/{rid}/review", "admin", json={"action": "reject", "reason": "不符合规范"}))
        rrow = db.query("SELECT audit_status, is_published, audit_reason FROM tags WHERE id = %s", (rid,), one=True)
        self.assertEqual(rrow["audit_status"], 2)
        self.assertEqual(rrow["is_published"], 0)
        self.assertEqual(rrow["audit_reason"], "不符合规范")
        # 重新提交被驳回标签（管理动作已归主系统，由管理员执行）
        self.ok(self.call("post", f"/api/tags/{rid}/resubmit", "admin"))
        self.assertEqual(db.query("SELECT audit_status FROM tags WHERE id = %s", (rid,), one=True)["audit_status"], 0)
        # 普通用户无分类管理权限 → 403
        self.assertEqual(self.call("delete", f"/api/tags/{tid}", "user", expect=403)["code"], 1)
        # 管理员可删任意标签
        self.ok(self.call("delete", f"/api/tags/{rid}", "admin"))
        self.ok(self.call("delete", f"/api/tags/{tid}", "admin"))
        self.ok(self.call("delete", f"/api/tags/{hidden['id']}", "admin"))
        self.assertIsNone(db.query("SELECT id FROM tags WHERE id = %s", (tid,), one=True))
        self.assertIsNone(db.query("SELECT id FROM tags WHERE id = %s", (rid,), one=True))

    # ---------- 视频标签挂接：普通用户静默忽略未知标签，管理员自动建并发布 ----------
    def test_14b_video_tag_filter(self):
        # 普通用户保存视频：未知标签静默忽略，不自动创建
        vid = self.make_video("user", "标签过滤", tags=[PREFIX + "未知标"])
        rows = db.query(
            "SELECT t.name FROM video_tags vt JOIN tags t ON t.id = vt.tag_id WHERE vt.video_id = %s",
            (vid,),
        )
        self.assertEqual([r["name"] for r in rows], [])
        self.assertIsNone(db.query("SELECT id FROM tags WHERE name = %s", (PREFIX + "未知标",), one=True))
        # 管理员保存视频：未知标签自动创建并发布
        vid2 = self.make_video("admin", "管理员建标", tags=[PREFIX + "管理员新标"])
        rows = db.query(
            "SELECT t.is_published FROM video_tags vt JOIN tags t ON t.id = vt.tag_id WHERE vt.video_id = %s",
            (vid2,),
        )
        self.assertEqual(rows[0]["is_published"], 1)
        row = db.query("SELECT id FROM tags WHERE name = %s", (PREFIX + "管理员新标",), one=True)
        if row:
            db.execute("DELETE FROM tags WHERE id = %s", (row["id"],))

    # ---------- 标签栏展示视图：可见性由后端按角色裁定，前端不参与判断 ----------
    def test_14c_tag_visible_scope(self):
        stem = PREFIX + "可见性"
        published, hidden, pending, rejected = (
            stem + "已发布", stem + "未发布", stem + "待审", stem + "已驳回",
        )
        db.execute("DELETE FROM tags WHERE name LIKE %s", (stem + "%",))
        p = self.ok(self.call("post", "/api/tags", "admin", json={"name": published, "isPublished": True}))
        # 超管直接建「未发布」写的是待审核态；要得到「已通过但未发布」需先发布再取消发布
        h = self.ok(self.call("post", "/api/tags", "admin", json={"name": hidden, "isPublished": True}))
        self.ok(self.call("put", f"/api/tags/{h['id']}", "admin", json={"isPublished": False}))
        pend = self.ok(self.call("post", "/api/tags", "user", json={"name": pending}))
        rj = self.ok(self.call("post", "/api/tags", "user", json={"name": rejected}))
        self.ok(self.call("post", f"/api/tags/{rj['id']}/review", "admin",
                          json={"action": "reject", "reason": "测试驳回"}))
        try:
            # 超管：全部标签，四种状态角标齐全
            admin_rows = {t["name"]: t for t in self.ok(self.call("get", "/api/tags/visible", "admin"))}
            self.assertEqual(admin_rows[published]["badge"], "")
            self.assertEqual(admin_rows[hidden]["badge"], "未发布")
            self.assertFalse(admin_rows[hidden]["isPublished"])
            self.assertEqual(admin_rows[pending]["badge"], "待审核")
            self.assertEqual(admin_rows[rejected]["badge"], "已驳回")
            # 展示视图只给最小字段，不携带驳回理由 / 创建者等管理信息
            self.assertNotIn("auditReason", admin_rows[hidden])
            self.assertNotIn("createdByName", admin_rows[hidden])
            # 其他等级：严格只有已发布，连自己提交的待审 / 驳回标签也不返回
            for key in ("manager", "reviewer", "user"):
                rows = self.ok(self.call("get", "/api/tags/visible", key))
                names = [t["name"] for t in rows]
                self.assertIn(published, names)
                for private in (hidden, pending, rejected):
                    self.assertNotIn(private, names)
                self.assertTrue(all(t["isPublished"] is True and t["badge"] == ""
                                    for t in rows if t["name"].startswith(stem)))
            # 管理视图不受影响：审核角色仍看待审，普通用户仍看自己提交项
            self.assertIn(pending, [t["name"] for t in self.ok(self.call("get", "/api/tags", "reviewer"))])
            self.assertIn(pending, [t["name"] for t in self.ok(self.call("get", "/api/tags", "user"))])
        finally:
            for tid in (p["id"], h["id"], pend["id"], rj["id"]):
                self.ok(self.call("delete", f"/api/tags/{tid}", "admin"))

    # ---------- 角色层级：管理员平级及以下可见/可审 ----------
    def test_15_role_hierarchy_visibility(self):
        vid_user = self.make_video("user", "用户待审片")     # 普通用户上传（待审核）
        vid_admin = self.make_video("admin", "超管的片")     # 超管上传（免审通过）
        vid_mgr = self.make_video("manager", "管理员待审片")  # 管理员上传（待审核）

        # 管理员：平级及以下用户的视频全部可见（含待审核），超管的不可见
        self.assertEqual(self.call("get", f"/api/videos/{vid_user}", "manager")["code"], 0)
        self.assertEqual(self.call("get", f"/api/videos/{vid_mgr}", "manager")["code"], 0)
        body = self.call("get", f"/api/videos/{vid_admin}", "manager", expect=404)
        self.assertNotEqual(body["code"], 0)
        # 审核范围：能看到用户/管理员的待审片，看不到超管的
        audit_ids = [x["id"] for x in self.ok(self.call("get", "/api/videos?scope=audit&pageSize=100", "manager"))["items"]]
        self.assertIn(vid_user, audit_ids)
        self.assertIn(vid_mgr, audit_ids)
        self.assertNotIn(vid_admin, audit_ids)
        # 管理员有审核权：可审平级及以下，不可审超管的
        self.ok(self.audit(vid_user, 1, key="manager"))
        body = self.call("post", f"/api/videos/{vid_admin}/audit", "manager", expect=403,
                         json={"status": 1, "reason": ""})
        self.assertNotEqual(body["code"], 0)
        # 管理员无管理权：不能编辑/删除他人视频
        body = self.call("delete", f"/api/videos/{vid_user}", "manager", expect=404)
        self.assertNotEqual(body["code"], 0)
        # 普通用户：看不到管理员上传的待审片
        body = self.call("get", f"/api/videos/{vid_mgr}", "user", expect=404)
        self.assertNotEqual(body["code"], 0)
        # 审核员保持现状：全部可见
        self.assertEqual(self.call("get", f"/api/videos/{vid_admin}", "reviewer")["code"], 0)
        # 超管：全部可见
        self.assertEqual(self.call("get", f"/api/videos/{vid_mgr}", "admin")["code"], 0)

    # ---------- 影视类型：普通用户可提交待审，审核员审核发布，权限边界 ----------
    def test_16_type_review_and_visibility(self):
        # 清理历史残留，避免名称被占用导致重复提交被拦
        db.execute("DELETE FROM types WHERE name LIKE %s", (PREFIX + "%",))
        # 普通用户可提交新类型（进入待审核，不再直接发布）
        name = PREFIX + "类型A"
        data = self.ok(self.call("post", "/api/types", "user", json={"name": name}))
        tid = data["id"]
        self.assertEqual(data["auditStatus"], 0)
        # 创建者本人能在列表看到（无论是否发布），且带 isMine / 发布状态供前端判断操作权限
        mine = next(t for t in self.ok(self.call("get", "/api/types", "user")) if t["id"] == tid)
        self.assertTrue(mine["isMine"])
        self.assertFalse(mine["isPublished"])
        self.assertIsNotNone(mine["createdBy"])
        # 审核角色能看到待审核类型
        self.assertIn(name, [t["name"] for t in self.ok(self.call("get", "/api/types", "admin"))])
        # 管理员创建未发布的类型：非创建者的普通用户不可见
        hidden = self.ok(self.call("post", "/api/types", "admin",
                                   json={"name": PREFIX + "隐藏类", "isPublished": False}))
        self.assertNotIn(PREFIX + "隐藏类", [t["name"] for t in self.ok(self.call("get", "/api/types", "user"))])
        # 管理员审核通过用户提交的类型 → 发布
        self.ok(self.call("post", f"/api/types/{tid}/review", "admin", json={"action": "approve"}))
        row = db.query("SELECT is_published, audit_status FROM types WHERE id = %s", (tid,), one=True)
        self.assertEqual(row["is_published"], 1)
        self.assertEqual(row["audit_status"], 1)
        # 驳回必须填理由
        rname = PREFIX + "类型驳回"
        rdata = self.ok(self.call("post", "/api/types", "user", json={"name": rname}))
        rid = rdata["id"]
        self.assertEqual(self.call("post", f"/api/types/{rid}/review", "admin", json={"action": "reject"}, expect=400)["code"], 1)
        self.ok(self.call("post", f"/api/types/{rid}/review", "admin", json={"action": "reject", "reason": "不符合规范"}))
        rrow = db.query("SELECT audit_status, is_published, audit_reason FROM types WHERE id = %s", (rid,), one=True)
        self.assertEqual(rrow["audit_status"], 2)
        self.assertEqual(rrow["is_published"], 0)
        self.assertEqual(rrow["audit_reason"], "不符合规范")
        # 重新提交被驳回类型（管理动作已归主系统，由管理员执行）
        self.ok(self.call("post", f"/api/types/{rid}/resubmit", "admin"))
        self.assertEqual(db.query("SELECT audit_status FROM types WHERE id = %s", (rid,), one=True)["audit_status"], 0)
        # 普通用户无分类管理权限 → 403
        self.assertEqual(self.call("delete", f"/api/types/{tid}", "user", expect=403)["code"], 1)
        # 管理员可删任意类型
        self.ok(self.call("delete", f"/api/types/{rid}", "admin"))
        self.ok(self.call("delete", f"/api/types/{tid}", "admin"))
        self.ok(self.call("delete", f"/api/types/{hidden['id']}", "admin"))
        self.assertIsNone(db.query("SELECT id FROM types WHERE id = %s", (tid,), one=True))
        self.assertIsNone(db.query("SELECT id FROM types WHERE id = %s", (rid,), one=True))

    # ---------- 频道页多行筛选（year / letter / region / language） ----------
    def test_17_channel_filters(self):
        base = {"scope": "gallery", "page": 1, "pageSize": 100}
        def ids(**kw):
            data = self.ok(self.call("get", "/api/videos", "admin", query_string={**base, **kw}))
            return [x["id"] for x in data["items"]]

        vid = self.make_video("admin", title=PREFIX + "日本频道筛选片", description="日语原声 纪录片")
        year = db.query("SELECT YEAR(created_at) AS y FROM videos WHERE id = %s", (vid,), one=True)["y"]
        alpha = self.make_video("admin", title="Alpha_" + PREFIX + "首字母")
        digit = self.make_video("admin", title="2024_" + PREFIX + "数字开头")

        # 地区 / 语言：分别命中标题与备注
        self.assertIn(vid, ids(region="日本"))
        self.assertIn(vid, ids(language="日语"))
        self.assertEqual(ids(region="不存在的地区XYZ"), [])
        # 年份：按入库年份，错年不命中
        self.assertIn(vid, ids(year=year))
        self.assertNotIn(vid, ids(year=year - 1))
        # 首字母：A-Z 与 0-9
        self.assertIn(alpha, ids(letter="A"))
        self.assertNotIn(vid, ids(letter="A"))
        self.assertIn(digit, ids(letter="0-9"))
        # 多条件按 AND 叠加
        self.assertIn(vid, ids(region="日本", language="日语", year=year))
        self.assertNotIn(vid, ids(region="日本", language="英语"))
        # 非法 letter 不生效（不报错、不误筛）
        self.assertIn(vid, ids(letter="%%"))

        for x in (vid, alpha, digit):
            self.ok(self.call("delete", f"/api/videos/{x}", "admin"))

    # ---------- 发布 / 取消发布：PUT /:id 的 isPublished，仅超管可执行 ----------
    def test_18_publish_toggle(self):
        # 清理历史残留，避免名称被占用
        db.execute("DELETE FROM tags WHERE name LIKE %s", (PREFIX + "%",))
        db.execute("DELETE FROM types WHERE name LIKE %s", (PREFIX + "%",))

        tag_name = PREFIX + "发布标签"
        tag = self.ok(self.call("post", "/api/tags", "admin",
                                json={"name": tag_name, "isPublished": True}))
        tid = tag["id"]
        self.assertTrue(tag["isPublished"])
        self.assertIn(tag_name, [t["name"] for t in self.ok(self.call("get", "/api/tags", "user"))])
        # 普通用户无分类管理权限，不能改发布状态
        self.assertEqual(self.call("put", f"/api/tags/{tid}", "user",
                                   json={"isPublished": False}, expect=403)["code"], 1)
        # 超管取消发布：审核状态保持「已通过」，普通用户列表不再出现
        data = self.ok(self.call("put", f"/api/tags/{tid}", "admin", json={"isPublished": False}))
        self.assertFalse(data["isPublished"])
        self.assertEqual(data["auditStatus"], 1)
        self.assertNotIn(tag_name, [t["name"] for t in self.ok(self.call("get", "/api/tags", "user"))])
        # 重新发布
        data = self.ok(self.call("put", f"/api/tags/{tid}", "admin", json={"isPublished": True}))
        self.assertTrue(data["isPublished"])
        self.assertIn(tag_name, [t["name"] for t in self.ok(self.call("get", "/api/tags", "user"))])
        # 待审核条目被管理员直接发布 → 同步免审通过
        pending = self.ok(self.call("post", "/api/tags", "user", json={"name": PREFIX + "待审发布"}))
        self.assertEqual(pending["auditStatus"], 0)
        data = self.ok(self.call("put", f"/api/tags/{pending['id']}", "admin",
                                 json={"isPublished": True}))
        self.assertEqual(data["auditStatus"], 1)
        self.assertTrue(data["isPublished"])
        # 影视类型走同一套发布开关
        type_name = PREFIX + "发布类型"
        tp = self.ok(self.call("post", "/api/types", "admin",
                               json={"name": type_name, "isPublished": True}))
        self.ok(self.call("put", f"/api/types/{tp['id']}", "admin", json={"isPublished": False}))
        self.assertNotIn(type_name, [t["name"] for t in self.ok(self.call("get", "/api/types", "user"))])
        self.ok(self.call("put", f"/api/types/{tp['id']}", "admin", json={"isPublished": True}))
        self.assertIn(type_name, [t["name"] for t in self.ok(self.call("get", "/api/types", "user"))])
        # 清理
        for path in (f"/api/tags/{tid}", f"/api/tags/{pending['id']}", f"/api/types/{tp['id']}"):
            self.ok(self.call("delete", path, "admin"))


    # ---------- 运营管理：合集审核模型 ----------
    def test_19_collection_audit_flow(self):
        db.execute("DELETE FROM collections WHERE name LIKE %s", (PREFIX + "合集%",))
        name_a = PREFIX + "合集A"
        created = self.ok(self.call("post", "/api/collections", "admin",
                                    json={"name": name_a, "description": "审核链路测试"}))
        cid = created["id"]
        self.assertEqual(created["auditStatus"], 0)
        self.assertFalse(created["isPublished"])
        self.assertTrue(created["isMine"])
        # 待审合集：创建者（管理员）与审核角色可见，普通用户不可见
        self.assertIn(cid, [c["id"] for c in self.ok(self.call("get", "/api/collections", "admin"))["items"]])
        self.assertIn(cid, [c["id"] for c in self.ok(self.call("get", "/api/collections", "reviewer"))["items"]])
        # 普通用户无审核权
        self.assertEqual(self.call("post", f"/api/collections/{cid}/review", "user",
                                   json={"action": "approve"}, expect=403)["code"], 1)
        # 审核员通过 → 已发布
        approved = self.ok(self.call("post", f"/api/collections/{cid}/review", "reviewer",
                                     json={"action": "approve"}))["item"]
        self.assertEqual(approved["auditStatus"], 1)
        self.assertTrue(approved["isPublished"])
        pub = [c for c in self.ok(self.call("get", "/api/collections", "user"))["items"] if c["id"] == cid]
        self.assertTrue(pub and pub[0]["isPublished"])

        # 驳回必填理由 + 创建者重新提交 + 审核轨迹
        name_b = PREFIX + "合集B"
        c2 = self.ok(self.call("post", "/api/collections", "admin", json={"name": name_b}))["id"]
        self.assertEqual(self.call("post", f"/api/collections/{c2}/review", "reviewer",
                                   json={"action": "reject"}, expect=400)["code"], 1)
        rejected = self.ok(self.call("post", f"/api/collections/{c2}/review", "reviewer",
                                     json={"action": "reject", "reason": "名称不规范"}))["item"]
        self.assertEqual(rejected["auditStatus"], 2)
        self.assertEqual(rejected["auditReason"], "名称不规范")
        self.assertEqual(self.ok(self.call("post", f"/api/collections/{c2}/resubmit", "admin"))["auditStatus"], 0)
        logs = self.ok(self.call("get", f"/api/collections/{c2}/logs", "admin"))["items"]
        self.assertEqual([l["action"] for l in logs], ["submit", "reject", "resubmit"])
        # 无分类管理权限不能删除合集
        self.assertEqual(self.call("delete", f"/api/collections/{c2}", "reviewer", expect=403)["code"], 1)

        for x in (cid, c2):
            self.ok(self.call("delete", f"/api/collections/{x}", "admin"))

    # ---------- 运营管理：管理员操作审计 ----------
    def test_20_admin_audit_logs(self):
        # 账号与角色已统一到平台 P1 用户管理，视频侧不再产生 change_role 审计；
        # 这里改用视频管理专属的 delete_video 动作验证审计流水。
        vid = self.make_video("admin", title=PREFIX + "auditvid")
        self.ok(self.call("delete", f"/api/videos/{vid}", "admin"))

        data = self.ok(self.call("get", "/api/admin-logs?pageSize=50", "admin"))
        actions = [i["action"] for i in data["items"]]
        self.assertIn("delete_video", actions)
        self.assertTrue(data["actionOptions"])
        # 仅超管可查
        for key in ("user", "reviewer", "manager"):
            self.assertEqual(self.call("get", "/api/admin-logs", key, expect=403)["code"], 1)
        # 关键词 / 动作筛选
        kw = self.ok(self.call("get", "/api/admin-logs?keyword=" + PREFIX + "auditvid", "admin"))
        self.assertTrue(any(i["action"] == "delete_video" for i in kw["items"]))
        act = self.ok(self.call("get", "/api/admin-logs?action=delete_video", "admin"))
        self.assertTrue(all(i["action"] == "delete_video" for i in act["items"]))

        db.execute(
            "DELETE FROM admin_audit_logs WHERE operator_name IN (%s,%s,%s,%s)",
            tuple(PREFIX + k for k in ("admin", "manager", "user", "reviewer")),
        )

    # ---------- 运营管理：数据看板增强 ----------
    def test_21_admin_overview_trends(self):
        data = self.ok(self.call("get", "/api/admin/overview", "admin"))
        self.assertEqual(len(data["viewTrend"]), 14)
        self.assertTrue(all({"date", "fullDate", "views"} <= set(p) for p in data["viewTrend"]))
        self.assertIsInstance(data["hotTags"], list)
        self.assertTrue(all({"name", "videoCount", "totalViews"} <= set(t) for t in data["hotTags"]))
        growth = data["storageGrowth"]
        self.assertEqual(len(growth["points"]), 30)
        self.assertEqual(growth["totalVideos"], data["videos"]["total"])
        self.assertGreaterEqual(growth["totalBytes"], 0)
        self.assertGreaterEqual(growth["unmeasured"], 0)


    # ---------- 第四档：评分 / 想看清单 / 相关推荐 ----------
    def test_22_engagement_rating_watchlist_recommendation(self):
        admin_id = self.ids["admin"]

        def add_video(title, public=True):
            return db.execute(
                "INSERT INTO videos (user_id, title, file_path, audit_status, is_public) "
                "VALUES (%s, %s, %s, 1, %s)",
                (admin_id, PREFIX + title, "uploads/__test_engagement.mp4", 1 if public else 0),
            )["lastrowid"]

        a, b, hidden = add_video("engage_a"), add_video("engage_b"), add_video("engage_hidden", False)
        tag_id = db.execute(
            "INSERT INTO tags (name, is_published, audit_status) VALUES (%s, 1, 1)",
            (PREFIX + "engage_tag",),
        )["lastrowid"]
        for vid in (a, b):
            db.execute("INSERT INTO video_tags (video_id, tag_id) VALUES (%s, %s)", (vid, tag_id))
        try:
            # 评分范围校验：越界与非整数都不接受
            self.assertEqual(self.call("put", f"/api/videos/{a}/rating", "user", expect=400, json={"score": 6})["code"], 1)
            self.assertEqual(self.call("put", f"/api/videos/{a}/rating", "user", expect=400, json={"score": "5"})["code"], 1)
            d = self.ok(self.call("put", f"/api/videos/{a}/rating", "user", json={"score": 5}))
            self.assertEqual((d["myScore"], d["avgScore"], d["ratingCount"]), (5, 5.0, 1))
            # 多用户评分聚合；reviewer 可见全部影片，适合做第二位评价人
            d = self.ok(self.call("put", f"/api/videos/{a}/rating", "reviewer", json={"score": 3}))
            self.assertEqual((d["avgScore"], d["ratingCount"]), (4.0, 2))
            d = self.ok(self.call("get", f"/api/videos/{a}/engagement", "user"))
            self.assertEqual(d["myScore"], 5)
            self.assertFalse(d["isWantToWatch"])
            d = self.ok(self.call("put", f"/api/videos/{a}/rating", "user", json={"score": 0}))
            self.assertEqual((d["myScore"], d["ratingCount"]), (0, 1))

            # 想看清单：切换 + 按用户隔离 + 列表随带互动字段
            self.assertTrue(self.ok(self.call("post", f"/api/videos/{a}/watchlist", "user"))["isWantToWatch"])
            self.assertFalse(self.ok(self.call("post", f"/api/videos/{a}/watchlist", "user"))["isWantToWatch"])
            self.assertTrue(self.ok(self.call("post", f"/api/videos/{a}/watchlist", "user"))["isWantToWatch"])
            lst = self.ok(self.call("get", "/api/videos?wantlist=1", "user"))
            self.assertIn(a, [x["id"] for x in lst["items"]])
            self.assertTrue(all({"avgScore", "myScore", "isWantToWatch"} <= set(x) for x in lst["items"]))
            other = self.ok(self.call("get", "/api/videos?wantlist=1", "reviewer"))
            self.assertNotIn(a, [x["id"] for x in other["items"]])

            # 推荐：排除自身与不可见影片，同标签影片优先，附带推荐理由
            rec = self.ok(self.call("get", f"/api/videos/{a}/recommendations?limit=5", "user"))
            ids = [x["id"] for x in rec["items"]]
            self.assertNotIn(a, ids)
            self.assertNotIn(hidden, ids)
            self.assertIn(b, ids)
            self.assertEqual(rec["items"][0]["id"], b)
            self.assertTrue(all("recommendReason" in x for x in rec["items"]))
            self.assertEqual(self.call("get", f"/api/videos/{hidden}/engagement", "user", expect=404)["code"], 1)
        finally:
            for vid in (a, b, hidden):
                db.execute("DELETE FROM videos WHERE id = %s", (vid,))
            db.execute("DELETE FROM tags WHERE id = %s", (tag_id,))


if __name__ == "__main__":
    unittest.main(verbosity=2)
