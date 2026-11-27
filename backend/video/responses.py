"""统一响应格式：{code, msg, data}，code === 0 表示成功"""
from flask import jsonify


def ok(data=None):
    return jsonify({"code": 0, "msg": "ok", "data": data})


def fail(msg, status=400):
    return jsonify({"code": 1, "msg": msg}), status
