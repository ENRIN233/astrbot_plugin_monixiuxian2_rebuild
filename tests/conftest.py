import sys
import json
import types
from pathlib import Path
import pytest
import pytest_asyncio
import aiosqlite

# ============== 在导入任何插件代码之前 mock astrbot.* ==============
# 插件依赖 astrbot.api.logger / astrbot.api.event 等，运行时由 AstrBot 提供。
# 测试环境用 stub 替代，避免 ImportError。
def _make_stub(name: str) -> types.ModuleType:
    m = types.ModuleType(name)
    return m

if "astrbot" not in sys.modules:
    astrbot = _make_stub("astrbot")
    astrbot_api = _make_stub("astrbot.api")
    astrbot_api_event = _make_stub("astrbot.api.event")
    astrbot_api_star = _make_stub("astrbot.api.star")
    astrbot_api_message_components = _make_stub("astrbot.api.message_components")

    # logger
    import logging as _logging
    astrbot_api.logger = _logging.getLogger("astrbot_stub")
    astrbot_api.AstrBotConfig = dict  # 简单替代

    # event stubs
    class _AstrMessageEvent: pass
    class _MessageChain:
        def message(self, *a, **k): return self
    class _Filter:
        def command(self, *a, **k):
            def deco(f): return f
            return deco
    astrbot_api_event.AstrMessageEvent = _AstrMessageEvent
    astrbot_api_event.MessageChain = _MessageChain
    astrbot_api_event.filter = _Filter()

    # star stubs
    class _Star: pass
    class _Context: pass
    class _StarTools:
        @staticmethod
        def get_data_dir(name): return Path("/tmp")
    astrbot_api_star.Star = _Star
    astrbot_api_star.Context = _Context
    astrbot_api_star.StarTools = _StarTools

    # message components stubs
    class _At: pass
    class _Plain:
        def __init__(self, text=""): self.text = text
    astrbot_api_message_components.At = _At
    astrbot_api_message_components.Plain = _Plain

    sys.modules["astrbot"] = astrbot
    sys.modules["astrbot.api"] = astrbot_api
    sys.modules["astrbot.api.event"] = astrbot_api_event
    sys.modules["astrbot.api.star"] = astrbot_api_star
    sys.modules["astrbot.api.message_components"] = astrbot_api_message_components

# ============== 把插件目录注册为 astrbot_plugin_monixiuxian2 包 ==============
_PLUGIN_DIR = Path(__file__).resolve().parent.parent
_PLUGIN_NAME = "astrbot_plugin_monixiuxian2"

if _PLUGIN_NAME not in sys.modules:
    pkg = types.ModuleType(_PLUGIN_NAME)
    pkg.__path__ = [str(_PLUGIN_DIR)]  # 作为命名空间包
    sys.modules[_PLUGIN_NAME] = pkg

# scripts 目录直接作为顶层包（无相对导入问题）
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))


@pytest.fixture
def tmp_config_dir(tmp_path):
    """生成一个临时 config 目录"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest_asyncio.fixture
async def memory_db():
    """生成内存 SQLite 连接"""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    yield conn
    await conn.close()


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
