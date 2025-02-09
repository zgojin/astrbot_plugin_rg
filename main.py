import asyncio
from astrbot.api.all import *
import random


@register("revolver_game", "长安某", "俄罗斯轮盘赌", "1.0.0")
class RevolverGamePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.timer = None
        # 用于存储每个群的游戏状态，键为群 ID，值为该群的游戏状态字典
        self.group_states = {}

    @event_message_type(EventMessageType.ALL)
    async def on_all_messages(self, event: AstrMessageEvent):
        group_id = event.message_obj.group_id if hasattr(event.message_obj, "group_id") else None
        if not group_id:
            yield event.plain_result("该游戏仅限群聊中使用，请在群内游玩。")
            yield event
            return

        message_str = event.message_str.strip()

        if random.random() <= 0.01:
            try:
                client = event.bot
                group_members = await client.get_group_member_list(group_id=group_id, self_id=int(event.get_self_id()))
                group_members = [member for member in group_members if member['user_id'] != int(event.get_self_id())]

                if group_members:
                    random_member = random.choice(group_members)
                    random_member_id = random_member['user_id']
                    random_member_nickname = random_member.get('card', random_member.get('nickname', '未知群友'))

                    misfire_descriptions = [
                        "突然，那把左轮手枪仿佛被一股神秘的力量操控，发出一声震耳欲聋的怒吼，像是对寂静的群聊发起了一场猝不及防的攻击！",
                        "毫无征兆地，左轮手枪剧烈地颤抖起来，紧接着一声巨响如惊雷般炸裂，打破了群里原本的平静，走火的子弹如夺命幽灵般射出！",
                        "在一片祥和的群聊氛围中，左轮手枪像是突然发疯了一样，“砰”的一声巨响，一股刺鼻的硝烟瞬间弥漫开来，子弹呼啸而出！",
                        "静谧的群聊里，左轮手枪像是被恶魔附身，“轰”地一声，走火的子弹带着死亡气息横冲直撞！",
                        "群里正聊得火热，左轮手枪却意外走火，那声巨响如同末日警钟，子弹如离弦之箭射出！"
                    ]
                    bullet_descriptions = [
                        "那枚被火药灼烧得滚烫的子弹，拖着一缕刺鼻的硝烟，以破竹之势瞬间冲出枪膛。",
                        "一颗带着金属寒光的子弹，在火药的咆哮中如流星般疾驰而出，空气都为之炸裂。",
                        "这颗沉甸甸的子弹，裹挟着强大的冲击力和高温，“嗖”地一声冲破了寂静。",
                        "子弹像是一道炽热的闪电，在火药的推力下，瞬间穿透了空气的束缚。",
                        "那子弹好似愤怒的精灵，带着滚烫的温度和尖锐的呼啸，飞射出枪膛。"
                    ]
                    user_reactions = [
                        f"{random_member_nickname}原本谈笑风生的神情瞬间凝固，脸上满是惊愕与恐惧，身体像被重锤击中般猛地一颤，随后直挺挺地倒了下去。",
                        f"{random_member_nickname}双眼瞬间瞪得滚圆，眼神中满是绝望，双腿一软，整个人像断了线的风筝般瘫倒在地。",
                        f"{random_member_nickname}听到枪响的刹那，脸色变得惨白如纸，身体不受控制地颤抖起来，接着缓缓地屈膝跪地。",
                        f"{random_member_nickname}的笑容戛然而止，身体如同被定格，紧接着惊恐地摇晃了几下，一头栽倒。",
                        f"{random_member_nickname}身体猛地一震，眼神中充满了不可置信，缓缓地闭上双眼，瘫倒在虚拟的地上。"
                    ]
                    misfire_desc = random.choice(misfire_descriptions)
                    bullet_desc = random.choice(bullet_descriptions)
                    user_reaction = random.choice(user_reactions)

                    message = f"{misfire_desc} {bullet_desc} {user_reaction} 不幸被击中！"
                    yield event.plain_result(message)
                    await self._ban_user(event, client, random_member_id)
            except Exception:
                pass

        if message_str.startswith("装填"):
            parts = message_str.split()
            if len(parts) > 1:
                try:
                    num_bullets = int(parts[1])
                except ValueError:
                    yield event.plain_result("你输入的装填子弹数量不是有效的整数，请重新输入。")
                    yield event
                    return
            else:
                num_bullets = 1

            async for result in self.load_bullets(event, num_bullets):
                yield result
        elif message_str == "射爆":
            async for result in self.shoot(event):
                yield result

        yield event

    async def load_bullets(self, event: AstrMessageEvent, x: int = 1):
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
            chambers[current_index] = False
            remaining_bullets = sum(chambers)
            group_state['current_chamber_index'] = (current_index + 1) % 6

            bullet_descriptions = [
                "那枚被火药灼烧得滚烫的子弹，拖着一缕刺鼻的硝烟，以破竹之势瞬间冲出枪膛。",
                "一颗带着金属寒光的子弹，在火药的咆哮中如流星般疾驰而出，空气都为之炸裂。",
                "这颗沉甸甸的子弹，裹挟着强大的冲击力和高温，“嗖”地一声冲破了寂静。",
                "子弹像是一道炽热的闪电，在火药的推力下，瞬间穿透了空气的束缚。",
                "那子弹好似愤怒的精灵，带着滚烫的温度和尖锐的呼啸，飞射出枪膛。"
            ]
            user_reactions = [
                "原本紧咬的牙关瞬间松开，脸上满是惊愕与恐惧，身体像被重锤击中般猛地一颤，随后直挺挺地倒了下去。",
                "双眼瞬间瞪得滚圆，眼神中满是绝望，双腿一软，整个人像断了线的风筝般瘫倒在地。",
                "听到枪响的刹那，脸色变得惨白如纸，身体不受控制地颤抖起来，接着缓缓地屈膝跪地。",
                "身体猛地一震，仿佛被电流击中，脸上的表情瞬间扭曲，随后无力地倒下。",
                "整个人像被抽走了灵魂，眼神空洞，身体摇晃几下后，重重地摔倒在地。"
            ]
            pistol_descriptions = [
                "左轮手枪微微震颤，似乎还未释放完所有的力量。",
                "手枪发出低沉的余响，仿佛在诉说着还有未尽的使命。",
                "这把左轮手枪轻颤着，感觉还没满足，仍渴望再次怒吼。",
                "左轮手枪抖动了一下，好像在积蓄下一次爆发的能量。",
                "手枪嗡嗡作响，似乎对这一枪还意犹未尽。"
            ]

            bullet_desc = random.choice(bullet_descriptions)
            user_reaction = random.choice(user_reactions)

            # 判断是否是最后一发子弹
            if remaining_bullets > 0:
                pistol_desc = random.choice(pistol_descriptions)
                message = f"{sender_nickname} {bullet_desc} {user_reaction} {pistol_desc}"
            else:
                message = f"{sender_nickname} {bullet_desc} {user_reaction}"

            yield event.plain_result(message)
            await self._ban_user(event, client, int(event.get_sender_id()))
        else:
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

        if remaining_bullets == 0:
            if self.timer:
                self.timer.cancel()
            del self.group_states[group_id]
            yield event.plain_result(f"{sender_nickname}，弹匣内的所有实弹都已射出，游戏结束。若想继续，可再次装填。")
