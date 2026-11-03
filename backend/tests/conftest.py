"""测试引导：在任何 backend 模块导入之前，把数据目录指到临时副本。

storage.DATA_DIR 在导入期读取 THE_ORIGIN_DATA_DIR，所以这段必须最先执行
（pytest 会先收集并导入 conftest，再导入测试模块，时序刚好）。
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

_TMP_DATA = Path(tempfile.mkdtemp(prefix="the_origin_test_data_"))
shutil.copytree(BACKEND_DIR / "data", _TMP_DATA, dirs_exist_ok=True)
# 剔除可能随仓库携带的运行时存档，保证从零开始
for sub in ("saves", "moments"):
    folder = _TMP_DATA / sub
    if folder.is_dir():
        for f in folder.glob("*.json"):
            f.unlink()

os.environ["THE_ORIGIN_DATA_DIR"] = str(_TMP_DATA)
sys.path.insert(0, str(BACKEND_DIR))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def clean_runtime_saves():
    """每个用例前后都清空运行时存档，用例之间互不污染。"""
    import storage

    storage.reset_all_saves()
    yield
    storage.reset_all_saves()


@pytest.fixture()
def client(monkeypatch):
    """注入假模型（固定流式回复）的 TestClient，不依赖任何真实 LLM API。"""
    import llm
    import main
    from fastapi.testclient import TestClient

    reply = (
        "（她抬起头，把手机扣在桌面上）你好，请问有什么事？"
        '<state>{"trust": 62, "suspicion": 8, "tactic": "礼貌寒暄", '
        '"gossip": "前台来了个自称咨询顾问的人", '
        '"claims": ["访客自称来自睿析咨询"]}</state>'
    )

    def fake_chat_stream(messages, temperature=0.85, max_tokens=800):
        for i in range(0, len(reply), 16):
            yield reply[i : i + 16]

    def fake_chat(messages, temperature=0.7, max_tokens=800):
        return "（压缩后的前情摘要）访客自称睿析咨询顾问，问过标定进度。"

    monkeypatch.setattr(llm, "chat_stream", fake_chat_stream)
    monkeypatch.setattr(llm, "chat", fake_chat)
    with TestClient(main.app) as c:
        yield c
