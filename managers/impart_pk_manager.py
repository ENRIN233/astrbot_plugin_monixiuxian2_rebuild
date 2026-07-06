# managers/impart_pk_manager.py
"""传承PK系统管理器"""
import random
from typing import Tuple
from ..data import DataBase
from ..models import Player
from .combat_manager import CombatManager

__all__ = ["ImpartPkManager"]


class ImpartPkManager:
    """传承PK管理器 - 玩家间争夺传承的战斗"""

    def __init__(self, db: DataBase, combat_mgr: CombatManager, config_manager=None):
        self.db = db
        self.combat_mgr = combat_mgr
        self.config_manager = config_manager

    async def challenge_impart(self, attacker: Player, defender: Player) -> Tuple[bool, str, dict]:
        """发起传承挑战

        Args:
            attacker: 挑战者
            defender: 被挑战者

        Returns:
            (attacker_wins, battle_log, rewards)
        """
        # 获取双方传承信息
        attacker_impart = await self.db.ext.get_impart_info(attacker.user_id)
        defender_impart = await self.db.ext.get_impart_info(defender.user_id)

        # 使用统一的 CombatStats 构建方法
        atk_stats = await CombatManager.build_player_combat_stats(attacker, attacker_impart, self.config_manager)
        def_stats = await CombatManager.build_player_combat_stats(defender, defender_impart, self.config_manager)

        # 使用统一的 PvP 战斗机制（切磋模式，不消耗HP/MP）
        result = self.combat_mgr.player_vs_player(atk_stats, def_stats, combat_type=1)

        attacker_wins = result["winner"] == attacker.user_id

        rewards = {}
        if attacker_wins:
            # 胜利奖励：获得传承加成
            impart_gain = random.uniform(0.01, 0.05)  # 1%-5%
            if attacker_impart:
                new_atk_per = min(1.0, attacker_impart.impart_atk_per + impart_gain)
                attacker_impart.impart_atk_per = new_atk_per
                await self.db.ext.update_impart_info(attacker_impart)
                rewards["impart_atk_gain"] = impart_gain

            # 失败惩罚
            if defender_impart and defender_impart.impart_atk_per > 0:
                loss = min(impart_gain / 2, defender_impart.impart_atk_per)
                defender_impart.impart_atk_per -= loss
                await self.db.ext.update_impart_info(defender_impart)
                rewards["defender_loss"] = loss
        else:
            # 失败惩罚：损失修为
            exp_loss = int(attacker.experience * 0.01)  # 1%
            attacker.experience = max(0, attacker.experience - exp_loss)
            await self.db.update_player(attacker)
            rewards["exp_loss"] = exp_loss

        # 只返回最后6条战斗日志
        log_lines = result["combat_log"][-6:]
        return attacker_wins, "\n".join(log_lines), rewards
    
    async def get_impart_ranking(self, limit: int = 10) -> list:
        """获取传承排行榜"""
        # 查询所有传承数据，按攻击加成排序
        async with self.db.conn.execute(
            """
            SELECT user_id, impart_hp_per, impart_mp_per, impart_atk_per, 
                   impart_know_per, impart_burst_per
            FROM impart_info 
            ORDER BY impart_atk_per DESC 
            LIMIT ?
            """,
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                user_id = row[0]
                player = await self.db.get_player_by_id(user_id)
                if player:
                    total_per = row[1] + row[2] + row[3] + row[4] + row[5]
                    results.append({
                        "user_id": user_id,
                        "user_name": player.user_name or user_id[:8],
                        "atk_per": row[3],
                        "total_per": total_per
                    })
            return results
