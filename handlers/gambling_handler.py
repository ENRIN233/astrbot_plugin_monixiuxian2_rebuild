# handlers/gambling_handler.py
"""金银阁赌坊 - 押注灵石掷骰子定输赢

玩法（忠实复现 nonebot 原版赌坊）：
- 大：骰点 >= 4 胜，1:1 赔付
- 小：骰点 <= 3 胜，1:1 赔付
- 奇：骰点为单数(1/3/5) 胜，1:1 赔付
- 偶：骰点为双数(2/4/6) 胜，1:1 赔付
- 猜<N>：骰点 == N(1~6) 胜，5 倍赔付
数学期望均为 0（无庄家抽水）。赢则 gold += bet*倍数，输则 gold -= bet。
"""
import re
import time
import random

from astrbot.api.event import AstrMessageEvent
from ..data import DataBase
from ..models import Player
from .utils import player_required

__all__ = ["GamblingHandler", "resolve_bet"]

# 设计参数（可调）
MIN_BET = 100              # 单次最低下注
MAX_BET = 100_000_000      # 单次最高下注（1 亿，防止经济瞬间剧烈波动）
GAMBLING_CD = 5            # 每用户冷却秒数，防刷屏

# 下注模式解析正则：金额 + 模式 + 可选猜测点数
_BET_PATTERN = re.compile(r"^(\d+)\s*([大小奇偶猜])\s*(\d+)?$")
# 全角数字 -> 半角
_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")

OVERVIEW_TEXT = (
    "🎲【金银阁】小赌怡情，大赌伤身~\n"
    "━━━━━━━━━━━━━━━\n"
    "以六面灵骰定输赢：\n"
    "· 金银阁 <金额> 大   骰点≥4 → 猜中1:1\n"
    "· 金银阁 <金额> 小   骰点≤3 → 猜中1:1\n"
    "· 金银阁 <金额> 奇   单数   → 猜中1:1\n"
    "· 金银阁 <金额> 偶   双数   → 猜中1:1\n"
    "· 金银阁 <金额> 猜3  猜中点数 → 5倍奉还\n"
    "━━━━━━━━━━━━━━━\n"
    f"单次下注 {MIN_BET:,} ~ {MAX_BET:,} 灵石，每 {GAMBLING_CD} 秒一次\n"
    "例：金银阁 1000 大 | 金银阁 1000 猜3"
)


def resolve_bet(roll: int, mode: str, guess: int) -> tuple:
    """根据骰点与模式判定输赢（纯函数，便于单测）。

    Args:
        roll: 骰子点数 1~6
        mode: 大/小/奇/偶/猜
        guess: 当 mode 为「猜」时的猜测点数，其余模式忽略

    Returns:
        (是否赢, 赔率倍数)。赢时倍数为净赢倍数（大/小/奇/偶=1，猜=5），输时为 0。
    """
    if mode == "大":
        won = roll >= 4
    elif mode == "小":
        won = roll <= 3
    elif mode == "奇":
        won = roll % 2 == 1
    elif mode == "偶":
        won = roll % 2 == 0
    elif mode == "猜":
        won = roll == guess
    else:
        won = False

    if not won:
        return False, 0
    return True, (5 if mode == "猜" else 1)


class GamblingHandler:
    """金银阁赌坊处理器"""

    def __init__(self, db: DataBase):
        self.db = db
        # 内存级每用户冷却 {user_id: last_ts}，重启清空，作为轻量防刷
        self._cd = {}

    @player_required
    async def handle_gambling(self, player: Player, event: AstrMessageEvent):
        """金银阁主入口：无参显示总览，有参则下注"""
        # 取原始消息，归一化全角空格/数字，剥离指令前缀
        raw = event.get_message_str().strip()
        raw = raw.replace("　", " ").translate(_FULLWIDTH_DIGITS)
        if raw.startswith("/"):
            raw = raw[1:].strip()
        if raw.startswith("金银阁"):
            raw = raw[len("金银阁"):].strip()

        # 无参数 -> 玩法总览
        if not raw:
            yield event.plain_result(OVERVIEW_TEXT)
            return

        m = _BET_PATTERN.match(raw)
        if not m:
            yield event.plain_result(
                "指令格式有误~\n例：金银阁 1000 大 | 金银阁 1000 奇 | 金银阁 1000 猜3"
            )
            return

        bet = int(m.group(1))
        mode = m.group(2)
        guess = int(m.group(3)) if m.group(3) else 0

        # 校验：猜测点数
        if mode == "猜" and not (1 <= guess <= 6):
            yield event.plain_result("「猜」需指定 1~6 的点数，例：金银阁 1000 猜3")
            return

        # 校验：下注额范围
        if bet < MIN_BET:
            yield event.plain_result(f"下注至少 {MIN_BET:,} 灵石，莫要小家子气~")
            return
        if bet > MAX_BET:
            yield event.plain_result(f"单次下注上限 {MAX_BET:,} 灵石，赌坊也怕你赢光~")
            return
        if player.gold < bet:
            yield event.plain_result(f"灵石不足！你只有 {player.gold:,} 灵石，押不起 {bet:,}。")
            return

        # 校验：冷却
        now = time.time()
        last = self._cd.get(player.user_id, 0)
        if now - last < GAMBLING_CD:
            remaining = int(GAMBLING_CD - (now - last)) + 1
            yield event.plain_result(f"手气莫急~ 请 {remaining} 秒后再来。")
            return
        self._cd[player.user_id] = now

        # 掷骰子
        roll = random.randint(1, 6)
        won, mult = resolve_bet(roll, mode, guess)

        if won:
            winnings = bet * mult
            player.gold += winnings
            await self.db.update_player(player)
            if mode == "猜":
                outcome = f"猜中！{mult}倍奉还，赢得灵石 {winnings:,}"
            else:
                outcome = f"【{mode}】道友好运，赢得灵石 {winnings:,}"
        else:
            player.gold -= bet
            await self.db.update_player(player)
            if mode == "猜":
                outcome = f"差之毫厘，输掉灵石 {bet:,}"
            else:
                outcome = f"【{mode}】可惜，输掉灵石 {bet:,}"

        yield event.plain_result(
            f"🎲 骰子落定：{roll} 点！\n{outcome}\n当前灵石：{player.gold:,}"
        )
