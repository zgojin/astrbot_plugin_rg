import asyncio
from astrbot.api.all import *
import random


@register("revolver_game", "长安某", "手枪", "1.0.0")
class RevolverGamePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.timer = None
        # 用于存储每个群的游戏状态，键为群 ID，值为该群的游戏状态字典
        self.group_states = {}
        # 用于存储每个群的走火开关状态，键为群 ID，值为布尔值表示开关状态
        self.group_misfire_switches = {}
        # 走火概率
        self.misfire_probability = 0.005

    @event_message_type(EventMessageType.ALL)
    async def on_all_messages(self, event: AstrMessageEvent):
        group_id = self._get_group_id(event)
        if not group_id:
            yield event.plain_result("该游戏仅限群聊中使用，请在群内游玩。")
            yield event
            return

        # 初始化群走火开关状态
        self._init_group_misfire_switch(group_id)

        message_str = event.message_str.strip()

        # 处理走火开关命令
        if message_str == "走火开":
            result = await self._handle_misfire_switch_on(event, group_id)
            yield result
            return
        elif message_str == "走火关":
            result = await self._handle_misfire_switch_off(event, group_id)
            yield result
            return

        # 如果走火开关关闭，不处理走火事件
        if not self.group_misfire_switches[group_id]:
            pass
        else:
            # 有概率触发走火事件
            if random.random() <= self.misfire_probability:
                async for result in self._handle_misfire(event, group_id):
                    yield result

        if message_str.startswith("装填"):
            num_bullets = self._parse_bullet_count(message_str)
            if num_bullets is None:
                yield event.plain_result("你输入的装填子弹数量不是有效的整数，请重新输入。")
                yield event
                return
            async for result in self.load_bullets(event, num_bullets):
                yield result
        elif message_str == "射爆":
            async for result in self.shoot(event):
                yield result

        yield event

    def _get_group_id(self, event: AstrMessageEvent):
        """获取消息所在的群 ID，如果不是群聊消息则返回 None"""
        return event.message_obj.group_id if hasattr(event.message_obj, "group_id") else None

    def _init_group_misfire_switch(self, group_id):
        """初始化群的走火开关状态，如果群 ID 不在开关字典中，默认开启"""
        if group_id not in self.group_misfire_switches:
            self.group_misfire_switches[group_id] = True

    async def _handle_misfire_switch_on(self, event: AstrMessageEvent, group_id):
        """处理开启走火功能的命令"""
        self.group_misfire_switches[group_id] = True
        return event.plain_result("本群左轮手枪走火功能已开启！")

    async def _handle_misfire_switch_off(self, event: AstrMessageEvent, group_id):
        """处理关闭走火功能的命令"""
        self.group_misfire_switches[group_id] = False
        return event.plain_result("本群左轮手枪走火功能已关闭！")

    async def _handle_misfire(self, event: AstrMessageEvent, group_id):
        """处理走火事件"""
        sender_nickname = event.get_sender_name()
        client = event.bot

        misfire_descriptions = [
            "突然，那把左轮手枪仿佛被一股神秘的力量操控，发出一声震耳欲聋的怒吼，像是对寂静的群聊发起了一场猝不及防的攻击！",
            "毫无征兆地，左轮手枪剧烈地颤抖起来，紧接着一声巨响如惊雷般炸裂，打破了群里原本的平静！",
            "在一片祥和的群聊氛围中，左轮手枪像是突然发疯了一样，“砰”的一声巨响，打破了宁静！",
            "静谧的群聊里，左轮手枪像是被恶魔附身，“轰”地一声，打破了这份寂静！",
            "群里正聊得火热，左轮手枪却意外走火，那声巨响如同末日警钟！"
        ]
        user_reactions = [
            f"{sender_nickname}原本谈笑风生的神情瞬间凝固，脸上满是惊愕与恐惧，身体像被重锤击中般猛地一颤，随后直挺挺地倒了下去。",
            f"{sender_nickname}双眼瞬间瞪得滚圆，眼神中满是绝望，双腿一软，整个人像断了线的风筝般瘫倒在地。",
            f"{sender_nickname}听到枪响的刹那，脸色变得惨白如纸，身体不受控制地颤抖起来，接着缓缓地屈膝跪地。",
            f"{sender_nickname}的笑容戛然而止，身体如同被定格，紧接着惊恐地摇晃了几下，一头栽倒。",
            f"{sender_nickname}身体猛地一震，眼神中充满了不可置信，缓缓地闭上双眼，瘫倒在虚拟的地上。"
        ]

        misfire_desc = random.choice(misfire_descriptions)
        user_reaction = random.choice(user_reactions)

        message = f"{misfire_desc} {user_reaction} 不幸被击中！"
        yield event.plain_result(message)
        await self._ban_user(event, client, int(event.get_sender_id()))

    def _parse_bullet_count(self, message_str):
        """解析装填子弹的数量，如果输入无效则返回 None"""
        parts = message_str.split()
        if len(parts) > 1:
            try:
                return int(parts[1])
            except ValueError:
                return None
        return 1

    async def load_bullets(self, event: AstrMessageEvent, x: int = 1):
        """处理装填子弹的逻辑"""
        sender_nickname = event.get_sender_name()
        group_id = event.message_obj.group_id
        group_state = self.group_states.get(group_id, {})

        if 'chambers' in group_state and sum(group_state['chambers']) > 0:
            yield event.plain_result(f"{sender_nickname}，游戏还未结束，不能重新装填，请继续射击！")
            return

        if x < 1 or x > 6:
            yield event.plain_result(f"{sender_nickname}，装填的实弹数量必须在 1 到 6 之间，请重新输入。")
            return

        chambers = [False] * 6
        positions = random.sample(range(6), x)
        for pos in positions:
            chambers[pos] = True

        group_state['chambers'] = chambers
        group_state['current_chamber_index'] = 0
        self.group_states[group_id] = group_state

        yield event.plain_result(f"{sender_nickname} 装填了 {x} 发实弹到 6 弹匣的左轮手枪，游戏开始！")

        if self.timer:
            self.timer.cancel()
        self.timer = asyncio.create_task(self.start_timeout(group_id))

    async def start_timeout(self, group_id):
        """处理游戏超时逻辑"""
        try:
            await asyncio.sleep(60)
            group_state = self.group_states.get(group_id)
            if group_state and 'chambers' in group_state and sum(group_state['chambers']) > 0:
                pistol_silence_descriptions = [
                    "左轮手枪静静地躺在那里，不再发出咆哮，仿佛被时间凝固，它的使命在这漫长的寂静中被搁置。",
                    "那把曾经充满火药味的左轮手枪，此刻陷入了深沉的沉默，像是在哀悼这场未完成的游戏。",
                    "手枪无声地伫立着，它的枪膛还残留着硝烟的气息，却再也等不到下一次的扣动扳机。",
                    "左轮手枪在寂静中失去了活力，它的轰鸣声仿佛还在群聊的记忆里回荡，但已不再响起。",
                    "那把枪安静地待着，像是一位疲惫的战士，在漫长的等待中耗尽了最后一丝力量。"
                ]
                description = random.choice(pistol_silence_descriptions)
                del self.group_states[group_id]
                client = self.context.bot
                event = AstrMessageEvent(None, None, None, None, None, None)  # 模拟一个事件
                event.message_obj.group_id = group_id
                await client.send_group_msg(group_id=group_id, message=description)
        except asyncio.CancelledError:
            pass

    async def _ban_user(self, event: AstrMessageEvent, client, user_id):
        """禁言用户"""
        try:
            await client.set_group_ban(
                group_id=int(event.get_group_id()),
                user_id=user_id,
                duration=60,
                self_id=int(event.get_self_id())
            )
        except Exception:
            pass

    async def shoot(self, event: AstrMessageEvent):
        """处理射击逻辑"""
        sender_nickname = event.get_sender_name()
        group_id = event.message_obj.group_id
        group_state = self.group_states.get(group_id)

        if not group_state or 'chambers' not in group_state:
            yield event.plain_result(f"{sender_nickname}，枪里好像没有子弹呢，请先装填。")
            return

        client = event.bot
        if self.timer:
            self.timer.cancel()
        self.timer = asyncio.create_task(self.start_timeout(group_id))

        chambers = group_state['chambers']
        current_index = group_state['current_chamber_index']

        if chambers[current_index]:
            async for result in self._handle_real_shot(event, group_state, chambers, current_index, sender_nickname, client):
                yield result
        else:
            async for result in self._handle_empty_shot(event, group_state, chambers, current_index, sender_nickname):
                yield result

        remaining_bullets = sum(group_state['chambers'])
        if remaining_bullets == 0:
            if self.timer:
                self.timer.cancel()
            del self.group_states[group_id]
            yield event.plain_result(f"{sender_nickname}，弹匣内的所有实弹都已射出，游戏结束。若想继续，可再次装填。")

    async def _handle_real_shot(self, event: AstrMessageEvent, group_state, chambers, current_index, sender_nickname, client):
        """处理实弹射击逻辑"""
        chambers[current_index] = False
        group_state['current_chamber_index'] = (current_index + 1) % 6

        trigger_descriptions = [
            "随着扳机一响",
            "扳机被扣动，“砰”的一声",
            "扳机轻轻一动，枪声响起"
        ]
        user_reactions = [
            f"{sender_nickname}身体猛地一震，眼神中充满了不可置信，缓缓地闭上双眼，瘫倒在虚拟的地上。",
            f"{sender_nickname}原本自信的笑容瞬间凝固，脸色变得煞白，双腿一软，直接跪了下去。",
            f"{sender_nickname}眼神瞬间惊恐，身体不受控制地颤抖，随后直直地倒了下去。"
        ]

        trigger_desc = random.choice(trigger_descriptions)
        user_reaction = random.choice(user_reactions)

        message = f"{trigger_desc}，{user_reaction}"
        yield event.plain_result(message)
        await self._ban_user(event, client, int(event.get_sender_id()))

    async def _handle_empty_shot(self, event: AstrMessageEvent, group_state, chambers, current_index, sender_nickname):
        """处理空弹射击逻辑"""
        group_state['current_chamber_index'] = (current_index + 1) % 6
        remaining_bullets = sum(chambers)

        miss_messages = [
            f"{sender_nickname} 扣下扳机，“咔哒”一声，却是空枪！虚惊一场，冷汗瞬间湿透了后背！",
            f"扳机被扣动，只传来一声清脆的“咔哒”，{sender_nickname} 躲过一劫，心脏仍在剧烈跳动！",
            f"随着“咔哒”一响，{sender_nickname} 发现是空枪，长舒了一口气，但紧张的情绪仍未消散！",
            f"{sender_nickname}扣动扳机，“咔哒”声在寂静中响起，暗自庆幸子弹没射出。",
            f"{sender_nickname}手一抖扣下扳机，听到“咔哒”声，瞬间心跳漏了一拍，还好是虚惊。"
        ]
        yield event.plain_result(random.choice(miss_messages))
