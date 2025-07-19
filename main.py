import asyncio
from astrbot.api.all import *
from astrbot.api.event import MessageChain, filter
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import datetime
import yaml
import random
import os
import logging

# 插件目录
PLUGIN_DIR = os.path.join('data', 'plugins', 'astrbot_plugin_rg')
# 确保插件目录存在
if not os.path.exists(PLUGIN_DIR):
    os.makedirs(PLUGIN_DIR)

# 配置路径
TEXTS_FILE = os.path.join(PLUGIN_DIR, 'revolver_game_texts.yml')

@register("revolver_game", "长安某", "手枪", "1.3.1")
class RevolverGamePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 从 context 中获取配置
        self.config = context.get_config()
        # 群游戏状态
        self.group_states = {}
        # 加载走火开关
        self.group_misfire_switches = self._load_misfire_switches()
        # 走火概率
        self.misfire_probability = 0.005
        # 群定时器开始时间
        self.group_timer_start_time = {}
        # 加载游戏文本
        self.texts = self._load_texts()
        # 初始化定时器调度器
        if not hasattr(context, 'scheduler'):
            context.scheduler = AsyncIOScheduler()
            context.scheduler.start()
        self.scheduler = context.scheduler
        # 群消息来源映射
        self.group_umo_mapping = {}

    def _load_texts(self):
        """加载游戏文本，多编码尝试"""
        if not hasattr(self, '_cached_texts'):
            encodings = ['utf-8', 'gbk', 'gb2312']
            for encoding in encodings:
                try:
                    with open(TEXTS_FILE, 'r', encoding=encoding) as file:
                        self._cached_texts = yaml.safe_load(file)
                        break
                except UnicodeDecodeError:
                    continue
            else:
                self._cached_texts = {}
        return self._cached_texts

    def _load_misfire_switches(self):
        """从配置文件加载走火开关信息"""
        texts = self._load_texts()
        return texts.get('misfire_switches', {})

    def _save_misfire_switches(self):
        """保存走火开关信息到配置文件"""
        texts = self._load_texts()
        if 'misfire_switches' not in texts:
            texts['misfire_switches'] = {}
        texts['misfire_switches'].update(self.group_misfire_switches)
        with open(TEXTS_FILE, 'w', encoding='utf-8') as file:
            yaml.dump(texts, file, allow_unicode=True)

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """处理群消息"""
        group_id = event.message_obj.group_id
        message_str = event.message_str.strip()
        
        self._init_group_misfire_switch(group_id)

        if message_str == "走火开":
            result = await self._handle_misfire_switch_on(event, group_id)
            yield result
        elif message_str == "走火关":
            result = await self._handle_misfire_switch_off(event, group_id)
            yield result
        elif not self.group_misfire_switches[group_id]:
            pass
        else:
            if random.random() <= self.misfire_probability:
                async for result in self._handle_misfire(event, group_id):
                    yield result

        if message_str.startswith("装填"):
            num_bullets = self._parse_bullet_count(message_str)
            if num_bullets is None:
                yield event.plain_result("你输入的装填子弹数量不是有效的整数，请重新输入。")
            else:
                async for result in self.load_bullets(event, num_bullets):
                    yield result
        elif message_str == "射爆":
            async for result in self.shoot(event):
                yield result

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def on_private_message(self, event: AstrMessageEvent):
        """处理私聊消息"""
        message_str = event.message_str.strip()
        valid_commands = ["走火开", "走火关", "装填", "射爆"]
        if any(message_str.startswith(cmd) for cmd in valid_commands):
            yield event.plain_result("该游戏仅限群聊中使用，请在群内游玩。")

    def _get_group_id(self, event: AstrMessageEvent):
        """获取群id"""
        return event.message_obj.group_id if hasattr(event.message_obj, "group_id") else None

    def _init_group_misfire_switch(self, group_id):
        """初始化群走火开关"""
        if group_id not in self.group_misfire_switches:
            self.group_misfire_switches[group_id] = False

    async def _handle_misfire_switch_on(self, event: AstrMessageEvent, group_id):
        """开启群走火开关并保存信息"""
        self.group_misfire_switches[group_id] = True
        self._save_misfire_switches()
        return event.plain_result("本群左轮手枪走火功能已开启！")

    async def _handle_misfire_switch_off(self, event: AstrMessageEvent, group_id):
        """关闭群走火开关并保存信息"""
        self.group_misfire_switches[group_id] = False
        self._save_misfire_switches()
        return event.plain_result("本群左轮手枪走火功能已关闭！")

    async def _handle_misfire(self, event: AstrMessageEvent, group_id):
        """处理走火事件，禁言用户"""
        sender_nickname = event.get_sender_name()
        client = event.bot

        misfire_desc = random.choice(self.texts.get('misfire_descriptions', []))
        user_reaction = random.choice(self.texts.get('user_reactions', [])).format(sender_nickname=sender_nickname)
        message = f"{misfire_desc} {user_reaction} 不幸被击中！"
        try:
            yield event.plain_result(message)
        except Exception as e:
            logging.error(f"Failed to handle misfire: {e}")
        await self._ban_user(event, client, int(event.get_sender_id()))

    def _parse_bullet_count(self, message_str):
        """解析装填子弹数量"""
        parts = message_str.split()
        if len(parts) > 1:
            try:
                return int(parts[1])
            except ValueError:
                return None
        return 1

    async def load_bullets(self, event: AstrMessageEvent, x: int = 1):
        """装填子弹，检查并启动定时器"""
        sender_nickname = event.get_sender_name()
        group_id = event.message_obj.group_id
        group_state = self.group_states.get(group_id)

        job_id = f"timeout_{group_id}"
        self._remove_timer_job(job_id)

        if group_state and 'chambers' in group_state and any(group_state['chambers']):
            yield event.plain_result(f"{sender_nickname}，游戏还未结束，不能重新装填，请继续射击！")
            return

        if x < 1 or x > 6:
            yield event.plain_result(f"{sender_nickname}，装填的实弹数量必须在 1 到 6 之间，请重新输入。")
            return

        chambers = [False] * 6
        positions = random.sample(range(6), x)
        for pos in positions:
            chambers[pos] = True

        group_state = {
            'chambers': chambers,
            'current_chamber_index': 0
        }
        self.group_states[group_id] = group_state

        yield event.plain_result(f"{sender_nickname} 装填了 {x} 发实弹到 6 弹匣的左轮手枪，游戏开始！")
        self.start_timer(event, group_id, 180)

    async def shoot(self, event: AstrMessageEvent):
        """射击操作，处理结果"""
        sender_nickname = event.get_sender_name()
        group_id = event.message_obj.group_id
        group_state = self.group_states.get(group_id)

        job_id = f"timeout_{group_id}"
        self._remove_timer_job(job_id)

        if not group_state or 'chambers' not in group_state:
            yield event.plain_result(f"{sender_nickname}，枪里好像没有子弹呢，请先装填。")
            return

        client = event.bot
        self.start_timer(event, group_id, 180)

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
            self._remove_timer_job(job_id)
            del self.group_states[group_id]
            yield event.plain_result(f"{sender_nickname}，弹匣内的所有实弹都已射出，游戏结束。若想继续，可再次装填。")

    async def _handle_real_shot(self, event: AstrMessageEvent, group_state, chambers, current_index, sender_nickname, client):
        """处理击中目标，更新状态并禁言用户"""
        chambers[current_index] = False
        group_state['current_chamber_index'] = (current_index + 1) % 6
        trigger_desc = random.choice(self.texts.get('trigger_descriptions', []))
        user_reaction = random.choice(self.texts.get('user_reactions', [])).format(sender_nickname=sender_nickname)
        message = f"{trigger_desc}，{user_reaction}"
        try:
            yield event.plain_result(message)
        except Exception as e:
            logging.error(f"Failed to handle real shot: {e}")
        await self._ban_user(event, client, int(event.get_sender_id()))

    async def _handle_empty_shot(self, event: AstrMessageEvent, group_state, chambers, current_index, sender_nickname):
        """处理未击中目标，更新状态"""
        group_state['current_chamber_index'] = (current_index + 1) % 6
        miss_message = random.choice(self.texts.get('miss_messages', [])).format(sender_nickname=sender_nickname)
        try:
            yield event.plain_result(miss_message)
        except Exception as e:
            logging.error(f"Failed to handle empty shot: {e}")

    def start_timer(self, event: AstrMessageEvent, group_id, seconds):
        """启动群定时器"""
        umo = event.unified_msg_origin
        self.group_umo_mapping[group_id] = umo

        run_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        job_id = f"timeout_{group_id}"
        self.scheduler.add_job(
            self.timeout_callback,
            'date',
            run_date=run_time,
            args=[group_id],
            id=job_id
        )

    async def timeout_callback(self, group_id):
        """定时器超时，移除群游戏状态"""
        if group_id in self.group_states:
            del self.group_states[group_id]

    async def _ban_user(self, event: AstrMessageEvent, client, user_id):
        """禁言用户"""
        try:
            await client.set_group_ban(
                group_id=int(event.get_group_id()),
                user_id=user_id,
                duration=60,
                self_id=int(event.get_self_id())
            )
        except Exception as e:
            logging.error(f"Failed to ban user: {e}")

    def _remove_timer_job(self, job_id):
        """移除定时器任务"""
        try:
            self.scheduler.remove_job(job_id)
        except Exception as e:
            logging.error(f"Failed to remove timer job: {e}")
