# data/__init__.py

from .data_manager import DataBase

__all__ = ["DataBase", "MigrationManager"]


def __getattr__(name: str):
    # 延迟导出 MigrationManager：migration 依赖 config_manager，而 config_manager
    # 顶部 import data.default_configs 会触发本包初始化——包阶段直接导入会形成
    # config_manager -> data/__init__ -> migration -> config_manager 循环导入。
    # 首次属性访问时 config_manager 已加载完毕，再导入 migration 即安全。
    if name == "MigrationManager":
        from .migration import MigrationManager
        return MigrationManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
