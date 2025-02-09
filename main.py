import asyncio
from astrbot.api.all import *
import random
import re

# 注册左轮手枪装填射击游戏插件
@register("revolver_game", "长安某", "俄罗斯轮盘赌", "1.0.0")
class RevolverGamePlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        if config is None:
            config = {}
        self.config = config
        self.timer = None

    @event_message_type(EventMessageType.ALL)
    async def filter_messages(self, event: AstrMessageEvent):
        """
        全局事件过滤器，检查消息是否来自群聊，同时有 1% 概率触发手枪走火。
        """
        group_id = event.message_obj.group_id if hasattr(event.message_obj, "group_id") else None
        if not group_id:
            yield event.plain_result("该游戏仅限群聊中使用，请在群内游玩。")
            return

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
                        "在一片祥和的群聊氛围中，左轮手枪像是突然发疯了一样，“砰”的一声巨响，一股刺鼻的硝烟瞬间弥漫开来，子弹呼啸而出！"
                    ]
                    bullet_descriptions = [
                        "那枚被火药灼烧得滚烫的子弹，拖着一缕刺鼻的硝烟，以破竹之势瞬间冲出枪膛。",
                        "一颗带着金属寒光的子弹，在火药的咆哮中如流星般疾驰而出，空气都为之炸裂。",
                        "这颗沉甸甸的子弹，裹挟着强大的冲击力和高温，“嗖”地一声冲破了寂静。"
                    ]
                    user_reactions = [
                        f"{random_member_nickname}原本谈笑风生的神情瞬间凝固，脸上满是惊愕与恐惧，身体像被重锤击中般猛地一颤，随后直挺挺地倒了下去。",
                        f"{random_member_nickname}双眼瞬间瞪得滚圆，眼神中满是绝望，双腿一软，整个人像断了线的风筝般瘫倒在地。",
                        f"{random_member_nickname}听到枪响的刹那，脸色变得惨白如纸，身体不受控制地颤抖起来，接着缓缓地屈膝跪地。"
                    ]
                    misfire_desc = random.choice(misfire_descriptions)
                    bullet_desc = random.choice(bullet_descriptions)
                    user_reaction = random.choice(user_reactions)

                    message = f"{misfire_desc} {bullet_desc} {user_reaction} 不幸被击中！"
                    yield event.plain_result(message)
                    await self._ban_user(event, client, random_member_id)
            except Exception:
                pass

        return event

    @command("装填")
    async def load_bullets(self, event: AstrMessageEvent, x: int = 1):
        #装填
        sender_nickname = event.get_sender_name()
        if hasattr(event.message_obj, 'chambers'):
            remaining_bullets = sum(event.message_obj.chambers)
            if remaining_bullets > 0:
                yield event.plain_result(f"{sender_nickname}，游戏还未结束，不能重新装填，请继续射击！")
                return

        if x < 1 or x > 6:
            yield event.plain_result(f"{sender_nickname}，装填的实弹数量必须在 1 到 6 之间，请重新输入。")
            return

        chambers = [False] * 6
        positions = random.sample(range(6), x)
        for pos in positions:
            chambers[pos] = True

        event.message_obj.chambers = chambers
        event.message_obj.current_chamber_index = 0

        yield event.plain_result(f"{sender_nickname} 装填了 {x} 发实弹到 6 弹匣的左轮手枪，游戏开始！")

        if self.timer:
            self.timer.cancel()
        self.timer = asyncio.create_task(self.start_timeout(event))

    async def start_timeout(self, event):

        #一分钟后游戏无响应，结束游戏。
        try:
            await asyncio.sleep(60)
            if hasattr(event.message_obj, 'chambers'):
                remaining_bullets = sum(event.message_obj.chambers)
                if remaining_bullets > 0:
                    pistol_silence_descriptions = [
                        "左轮手枪静静地躺在那里，不再发出咆哮，仿佛被时间凝固，它的使命在这漫长的寂静中被搁置。",
                        "那把曾经充满火药味的左轮手枪，此刻陷入了深沉的沉默，像是在哀悼这场未完成的游戏。",
                        "手枪无声地伫立着，它的枪膛还残留着硝烟的气息，却再也等不到下一次的扣动扳机。"
                    ]
                    description = random.choice(pistol_silence_descriptions)
                    del event.message_obj.chambers
                    del event.message_obj.current_chamber_index
                    yield event.plain_result(description)
        except asyncio.CancelledError:
            pass

    async def _ban_user(self, event: AstrMessageEvent, client, user_id):
       
        #对指定用户禁言一分钟。
        
        try:
            await client.set_group_ban(
                group_id=int(event.get_group_id()),
                user_id=user_id,
                duration=60,
                self_id=int(event.get_self_id())
            )
        except Exception:
            pass

    @command("射爆")
    async def shoot(self, event: AstrMessageEvent):
        #射击
        sender_nickname = event.get_sender_name()
        if not hasattr(event.message_obj, 'chambers'):
            yield event.plain_result(f"{sender_nickname}，枪里好像没有子弹呢，请先装填。")
            return

        client = event.bot
        if self.timer:
            self.timer.cancel()
        self.timer = asyncio.create_task(self.start_timeout(event))

        chambers = event.message_obj.chambers
        current_index = event.message_obj.current_chamber_index

        if chambers[current_index]:
            chambers[current_index] = False
            remaining_bullets = sum(chambers)
            event.message_obj.current_chamber_index = (current_index + 1) % 6

            bullet_descriptions = [
                "那枚被火药灼烧得滚烫的子弹，拖着一缕刺鼻的硝烟，以破竹之势瞬间冲出枪膛。",
                "一颗带着金属寒光的子弹，在火药的咆哮中如流星般疾驰而出，空气都为之炸裂。",
                "这颗沉甸甸的子弹，裹挟着强大的冲击力和高温，“嗖”地一声冲破了寂静。"
            ]
            user_reactions = [
                "原本紧咬的牙关瞬间松开，脸上满是惊愕与恐惧，身体像被重锤击中般猛地一颤，随后直挺挺地倒了下去。",
                "双眼瞬间瞪得滚圆，眼神中满是绝望，双腿一软，整个人像断了线的风筝般瘫倒在地。",
                "听到枪响的刹那，脸色变得惨白如纸，身体不受控制地颤抖起来，接着缓缓地屈膝跪地。"
            ]
            pistol_descriptions = [
                "左轮手枪微微震颤，似乎还未释放完所有的力量。",
                "手枪发出低沉的余响，仿佛在诉说着还有未尽的使命。",
                "这把左轮手枪轻颤着，感觉还没满足，仍渴望再次怒吼。"
            ]

            bullet_desc = random.choice(bullet_descriptions)
            user_reaction = random.choice(user_reactions)
            pistol_desc = random.choice(pistol_descriptions)

            message = f"{sender_nickname} {bullet_desc} {user_reaction} {pistol_desc}"
            yield event.plain_result(message)
            await self._ban_user(event, client, int(event.get_sender_id()))
        else:
            event.message_obj.current_chamber_index = (current_index + 1) % 6
            remaining_bullets = sum(chambers)

            miss_messages = [
                f"{sender_nickname} 扣下扳机，“咔哒”一声，却是空枪！虚惊一场，冷汗瞬间湿透了后背！",
                f"扳机被扣动，只传来一声清脆的“咔哒”，{sender_nickname} 躲过一劫，心脏仍在剧烈跳动！",
                f"随着“咔哒”一响，{sender_nickname} 发现是空枪，长舒了一口气，但紧张的情绪仍未消散！"
            ]
            yield event.plain_result(random.choice(miss_messages))

        if remaining_bullets == 0:
            if self.timer:
                self.timer.cancel()
            del event.message_obj.chambers
            del event.message_obj.current_chamber_index
            yield event.plain_result(f"{sender_nickname}，弹匣内的所有实弹都已射出，游戏结束。若想继续，可再次装填。")
