# -*- coding: utf-8 -*-
"""存档目录名解析（resolve_plugin_data_dirname）测试"""
import tempfile
from pathlib import Path

from astrbot_plugin_monixiuxian2.handlers.utils import resolve_plugin_data_dirname


def test_follows_metadata_name():
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "metadata.yaml").write_text(
            "name: astrbot_plugin_monixiuxian2_rebuild\nversion: v4.3.9\n", encoding="utf-8"
        )
        assert resolve_plugin_data_dirname(Path(td)) == "astrbot_plugin_monixiuxian2_rebuild"


def test_name_with_inline_comment():
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "metadata.yaml").write_text(
            "name: my_plugin # 插件唯一标识\nversion: v1.0.0\n", encoding="utf-8"
        )
        assert resolve_plugin_data_dirname(Path(td)) == "my_plugin"


def test_missing_metadata_falls_back():
    with tempfile.TemporaryDirectory() as td:
        assert resolve_plugin_data_dirname(Path(td)) == "astrbot_plugin_monixiuxian2"


def test_real_plugin_metadata():
    """真实插件目录：必须解析出带 _rebuild 后缀的新名（回归锁：防再次硬编码旧名）"""
    plugin_dir = Path(__file__).resolve().parent.parent
    name = resolve_plugin_data_dirname(plugin_dir)
    assert name == "astrbot_plugin_monixiuxian2_rebuild", f"实际解析到 {name}"
