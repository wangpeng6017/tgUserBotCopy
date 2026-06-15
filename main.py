import logging
import sys
import os
import json
import asyncio
import random
import io
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Dict, Set, Tuple, Optional
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.utils import get_peer_id

# 加载配置文件
def load_config():
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    
    if not os.path.exists(config_path):
        print(f"错误: 配置文件不存在: {config_path}")
        print("请复制 config.json.example 为 config.json 并填写配置信息")
        sys.exit(1)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if 'accounts' not in config:
            if 'api_id' in config and 'api_hash' in config:
                config['accounts'] = [{
                    'api_id': config['api_id'],
                    'api_hash': config['api_hash'],
                    'name': f"account_{config['api_id']}"
                }]
            else:
                print("错误: 配置文件缺少必需的配置项: accounts 或 api_id/api_hash")
                sys.exit(1)
        
        if 'target_bot_username' not in config:
            print("错误: 配置文件缺少必需的配置项: target_bot_username")
            sys.exit(1)
        
        for i, account in enumerate(config['accounts']):
            if 'api_id' not in account or 'api_hash' not in account:
                print(f"错误: 账户 {i+1} 缺少 api_id 或 api_hash")
                sys.exit(1)
            if 'name' not in account:
                account['name'] = f"account_{account['api_id']}"
        
        return config
    except json.JSONDecodeError as e:
        print(f"错误: 配置文件格式错误: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: 加载配置文件失败: {str(e)}")
        sys.exit(1)

# 加载配置
config = load_config()
accounts = config['accounts']
target_bot_username = config['target_bot_username']
distribution_strategy = config.get('distribution_strategy', 'round_robin')
if distribution_strategy == 'round':
    distribution_strategy = 'round_robin'

# 消息发送配置（防止风控）
send_interval = config.get('send_interval', 2.0)
send_jitter = config.get('send_jitter', 1.0)

# 配置日志路径（支持相对路径和绝对路径）
log_dir_config = config.get('log_dir', 'logs')
if os.path.isabs(log_dir_config):
    log_dir = log_dir_config
else:
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), log_dir_config)

os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'tguserbot_{datetime.now().strftime("%Y%m%d")}.log')

log_level = config.get('log_level', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
logger.info(f"日志文件路径: {log_file}")
logger.info(f"配置了 {len(accounts)} 个账户")
logger.info(f"分配策略: {distribution_strategy}")

# 运行时由 main() 填充：仅包含成功启动的账户
clients: List[TelegramClient] = []
active_accounts: List[dict] = []
workdir = os.path.dirname(os.path.abspath(__file__))

start_time = None
message_queue: asyncio.Queue = None
message_dedup_lock: asyncio.Lock = None
seen_by_id: Set[Tuple] = set()
claimed_messages: Set[Tuple] = set()
sent_messages: Set[Tuple] = set()
our_user_ids: Set[int] = set()

chat_client_index: Dict[int, int] = defaultdict(int)
chat_client_usage: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))

class MessageTask:
    def __init__(self, chat_id, msg_text, media=None, user_type="", client_index=None, dedup_keys=None):
        self.chat_id = chat_id
        self.msg_text = msg_text
        self.media = media
        self.user_type = user_type
        self.client_index = client_index
        self.dedup_keys = dedup_keys or []

def make_id_key(event) -> Tuple:
    """按 message.id 快速去重（同 session 内）"""
    chat_id = get_peer_id(event.peer_id)
    return (chat_id, event.message.sender_id or 0, event.message.id)

def make_dedup_keys(event) -> List[Tuple]:
    """生成多条去重键，兼容不同账号收到同一消息时 message.id 不一致的情况"""
    chat_id = get_peer_id(event.peer_id)
    message = event.message
    sender_id = message.sender_id or 0
    keys = []
    
    if getattr(message, 'grouped_id', None):
        keys.append((chat_id, sender_id, 'album', message.grouped_id))
    
    keys.append((chat_id, sender_id, message.id))
    
    msg_date = int(message.date.timestamp()) if message.date else 0
    content = message.message or ''
    if not content and message.media:
        content = type(message.media).__name__
    keys.append((chat_id, sender_id, msg_date, content))
    
    return keys

def is_duplicate(keys: List[Tuple], store: Set[Tuple]) -> bool:
    return any(k in store for k in keys)

def mark_keys(keys: List[Tuple], store: Set[Tuple]) -> None:
    for k in keys:
        store.add(k)

def pick_sender_index(chat_id: int) -> int:
    """为一条消息选定唯一发送账号（与 clientTgUserBot 相同的分配逻辑）"""
    if len(clients) == 0:
        raise ValueError("没有可用的客户端")
    
    if distribution_strategy == 'round_robin':
        index = chat_client_index[chat_id] % len(clients)
        chat_client_index[chat_id] += 1
        logger.info(f"轮询分配：群组 {chat_id} → {active_accounts[index]['name']} (索引: {index})")
    elif distribution_strategy == 'random':
        usage = chat_client_usage[chat_id]
        usage_counts = [usage.get(i, 0) for i in range(len(clients))]
        min_usage = min(usage_counts) if usage_counts else 0
        least_used_indices = [i for i, count in enumerate(usage_counts) if count == min_usage]
        if len(least_used_indices) > 1:
            index = random.choice(least_used_indices)
        else:
            index = least_used_indices[0]
        chat_client_usage[chat_id][index] += 1
        logger.info(f"随机分配（加权）：群组 {chat_id} → {active_accounts[index]['name']} (索引: {index}, 使用次数: {chat_client_usage[chat_id][index]})")
    else:
        logger.warning(f"未知的分配策略: {distribution_strategy}，使用第一个客户端")
        index = 0
    
    return index

async def download_message_media(event) -> Optional[bytes]:
    """用监听账号下载媒体为 bytes，避免跨账号发送时 MediaEmptyError"""
    if not event.message.media:
        return None
    try:
        data = await event.client.download_media(event.message, bytes)
        if data:
            logger.info(f"已下载媒体文件 ({len(data)} 字节)")
            return data
        logger.warning("媒体下载结果为空")
    except Exception as e:
        logger.warning(f"媒体下载失败，将尝试仅发送文本: {str(e)}")
    return None

async def send_task_message(client: TelegramClient, task: MessageTask) -> None:
    """发送单条任务消息"""
    if task.media:
        media_file = io.BytesIO(task.media)
        await client.send_message(task.chat_id, task.msg_text, file=media_file)
    else:
        await client.send_message(task.chat_id, task.msg_text)

async def enqueue_target_message(event, listener_name: str, chat_id: int, msg_text: str, media_data: Optional[bytes], user_type: str, dedup_keys: List[Tuple], client_index: int) -> bool:
    """将已认领的消息入队（去重在 handler 中完成）"""
    sender_name = active_accounts[client_index]['name']
    task = MessageTask(
        chat_id=chat_id,
        msg_text=msg_text,
        media=media_data,
        user_type=user_type,
        client_index=client_index,
        dedup_keys=dedup_keys
    )
    await message_queue.put(task)
    media_hint = f"，含媒体 {len(media_data)} 字节" if media_data else ""
    logger.info(f"📥 [{listener_name}] 消息已入队 → 指定由 [{sender_name}] 发送{media_hint}（去重键: {dedup_keys}，队列: {message_queue.qsize()}）")
    return True

async def message_sender():
    """消息发送任务，从队列中取出消息并按间隔发送"""
    logger.info("消息发送任务已启动，等待队列中的消息...")
    while True:
        try:
            task = await message_queue.get()
            
            if task.client_index is None:
                logger.error("任务未指定发送账号，跳过")
                message_queue.task_done()
                continue
            
            async with message_dedup_lock:
                if task.dedup_keys and is_duplicate(task.dedup_keys, sent_messages):
                    logger.info(f"⏭️ 跳过重复发送: {task.dedup_keys}")
                    message_queue.task_done()
                    continue
            
            jitter = random.uniform(0, send_jitter)
            delay = send_interval + jitter
            logger.info(f"等待 {delay:.2f} 秒后发送（间隔: {send_interval}秒，抖动: {jitter:.2f}秒）...")
            await asyncio.sleep(delay)
            
            indices_to_try = [task.client_index] + [
                i for i in range(len(clients)) if i != task.client_index
            ]
            sent = False
            last_error = None
            
            for idx in indices_to_try:
                send_client = clients[idx]
                send_client_name = active_accounts[idx]['name']
                try:
                    logger.info(f"开始使用客户端 {send_client_name} 发送消息到群组 {task.chat_id}...")
                    await send_task_message(send_client, task)
                    if task.media:
                        logger.info(f"✓ [{send_client_name}] 已复制{task.user_type}消息（含媒体）到群组 {task.chat_id}: {task.msg_text[:100]}...")
                    else:
                        logger.info(f"✓ [{send_client_name}] 已复制{task.user_type}消息到群组 {task.chat_id}: {task.msg_text[:100]}...")
                    sent = True
                    break
                except Exception as e:
                    last_error = e
                    logger.error(f"✗ [{send_client_name}] 发送失败: {str(e)}")
            
            if not sent and last_error:
                logger.error(f"✗ 所有账号均发送失败，最后错误: {str(last_error)}")
            elif sent and task.dedup_keys:
                async with message_dedup_lock:
                    mark_keys(task.dedup_keys, sent_messages)
            
            message_queue.task_done()
            logger.info(f"消息发送完成，当前队列剩余: {message_queue.qsize()} 条")
            
        except asyncio.CancelledError:
            logger.info("消息发送任务已取消")
            break
        except Exception as e:
            logger.error(f"消息发送任务发生错误: {str(e)}", exc_info=True)
            await asyncio.sleep(1)

async def handler(event):
    global start_time
    try:
        if event.message.out:
            return
        
        id_key = make_id_key(event)
        async with message_dedup_lock:
            if id_key in seen_by_id:
                return
            seen_by_id.add(id_key)
        
        dedup_keys = make_dedup_keys(event)
        
        try:
            listener_index = clients.index(event.client)
            listener_name = active_accounts[listener_index]['name']
        except ValueError:
            listener_name = 'unknown'
        
        logger.info(f"🔔 [{listener_name}] 收到新消息 - 消息ID: {event.message.id}, 群组ID: {event.chat_id}, 去重键: {dedup_keys}")
        
        message_time = event.message.date
        if message_time.tzinfo is None:
            message_time = message_time.replace(tzinfo=timezone.utc)
        
        if start_time and message_time < start_time:
            logger.info(f"⏮️ 忽略历史消息 ID {event.message.id} (消息时间: {message_time}, 启动时间: {start_time})")
            return
        
        sender = await event.get_sender()
        if sender:
            if sender.id in our_user_ids:
                return
            sender_info = f"用户名: {sender.username or '无用户名'}, ID: {sender.id}, 是否机器人: {sender.bot}"
            logger.info(f"👤 发送者信息 - {sender_info}, 群组: {event.chat_id}, 消息ID: {event.message.id}")
        else:
            logger.warning("⚠️ 无法获取发送者信息，sender 为 None")
            return
        
        logger.info(f"🔍 检查用户名匹配 - 目标: '{target_bot_username}', 实际: '{sender.username if sender else None}'")
        
        if sender and sender.username == target_bot_username:
            async with message_dedup_lock:
                if is_duplicate(dedup_keys, claimed_messages) or is_duplicate(dedup_keys, sent_messages):
                    logger.info(f"⏭️ [{listener_name}] 目标消息已认领/已发送，跳过重复: {dedup_keys}")
                    return
                mark_keys(dedup_keys, claimed_messages)
                client_index = pick_sender_index(event.chat_id)
            
            logger.info(f"✅ [{listener_name}] 匹配到目标用户: {sender.username} (ID: {sender.id})")
            media_data = await download_message_media(event)
            await enqueue_target_message(
                event=event,
                listener_name=listener_name,
                chat_id=event.chat_id,
                msg_text=event.message.message or '',
                media_data=media_data,
                user_type="机器人" if sender.bot else "普通用户",
                dedup_keys=dedup_keys,
                client_index=client_index
            )
        else:
            logger.info("❌ 用户名不匹配，跳过处理")
            
    except Exception as e:
        logger.error(f"❌ 处理消息时发生错误: {str(e)}", exc_info=True)

def prompt_input(message: str) -> str:
    """在日志输出后仍能可见的交互输入"""
    print(message, end='', flush=True)
    return input()

async def start_client(client: TelegramClient, account: dict) -> None:
    """连接并登录单个客户端，带明确的交互提示"""
    name = account['name']
    logger.info(f"[{name}] 正在连接 Telegram 服务器...")

    await client.connect()
    logger.info(f"[{name}] 连接成功，正在验证登录状态...")

    if await client.is_user_authorized():
        me = await client.get_me()
        username = me.username or '无用户名'
        logger.info(f"✓ [{name}] 已登录: {me.first_name} (@{username}, ID: {me.id})")
        return

    logger.info(f"[{name}] session 未登录或已失效，需要重新验证")
    print(f"\n{'=' * 60}", flush=True)
    print(f"📱 账户 [{name}] 需要登录 Telegram", flush=True)
    print(f"{'=' * 60}", flush=True)

    phone = prompt_input(f"[{name}] 请输入手机号（格式 +86 13800138000）: ")
    await client.send_code_request(phone)
    code = prompt_input(f"[{name}] 请输入 Telegram 发送的验证码: ")

    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        password = prompt_input(f"[{name}] 请输入两步验证密码: ")
        await client.sign_in(password=password)

    me = await client.get_me()
    username = me.username or '无用户名'
    logger.info(f"✓ [{name}] 登录成功: {me.first_name} (@{username}, ID: {me.id})")

def create_client(account: dict) -> TelegramClient:
    """在事件循环内创建 Telegram 客户端"""
    api_id = account['api_id']
    api_hash = account['api_hash']
    name = account['name']
    session_name = f'session_{name}_{api_id}'
    session_path = os.path.join(workdir, session_name)
    client = TelegramClient(session_path, api_id, api_hash)
    logger.info(f"创建客户端: {name} (api_id: {api_id}, session: {session_name})")
    return client

async def main():
    global clients, active_accounts, message_queue, message_dedup_lock, start_time
    global seen_by_id, claimed_messages, sent_messages, our_user_ids
    global chat_client_index, chat_client_usage
    clients = []
    active_accounts = []
    message_queue = asyncio.Queue()
    message_dedup_lock = asyncio.Lock()
    seen_by_id = set()
    claimed_messages = set()
    sent_messages = set()
    our_user_ids = set()
    chat_client_index = defaultdict(int)
    chat_client_usage = defaultdict(lambda: defaultdict(int))
    sender_task = None
    start_time = None
    
    try:
        logger.info(f"进程 PID: {os.getpid()}")
        logger.info("正在启动 Telegram 客户端...")
        logger.info(f"共配置 {len(accounts)} 个账户")
        logger.info(f"发送间隔: {send_interval}秒，抖动时间: 0-{send_jitter}秒")
        logger.info(f"目标用户名: {target_bot_username}")
        logger.info(f"分配策略: {distribution_strategy}")
        
        for account in accounts:
            name = account['name']
            if account.get('enabled', True) is False:
                logger.info(f"[{name}] 已禁用（enabled=false），跳过")
                continue
            
            client = create_client(account)
            session_file = os.path.join(workdir, f'session_{name}_{account["api_id"]}.session')
            logger.info(f"[{name}] 检查 session 文件: {session_file} (存在: {os.path.exists(session_file)})")
            
            try:
                await start_client(client, account)
                me = await client.get_me()
                our_user_ids.add(me.id)
            except Exception as e:
                logger.error(f"✗ [{name}] 启动失败，跳过该账户: {str(e)}", exc_info=True)
                try:
                    await client.disconnect()
                except Exception:
                    pass
                continue
            
            client.add_event_handler(handler, events.NewMessage(incoming=True))
            clients.append(client)
            active_accounts.append(account)
            logger.info(f"✓ [{name}] 客户端已就绪，消息监听已注册")
        
        if not clients:
            logger.error("没有可用的客户端，请检查账户配置或登录状态")
            return
        
        start_time = datetime.now(timezone.utc)
        logger.info(f"监听基准时间: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}（此时间之前的消息视为历史消息）")
        
        logger.info("=" * 60)
        logger.info(f"✓ 已启动 {len(clients)} 个客户端: {', '.join(a['name'] for a in active_accounts)}")
        logger.info("所有在线账户均监听；同一消息只处理一次；发送按 distribution_strategy 分配唯一账号")
        logger.info("=" * 60)
        
        sender_task = asyncio.create_task(message_sender())
        logger.info("消息队列发送任务已启动，等待消息...")
        
        logger.info("程序运行中，等待消息...")
        logger.info("=" * 60)
        logger.info("📢 提示：请在 Telegram 中发送一条测试消息")
        logger.info("=" * 60)
        
        await asyncio.gather(*[client.run_until_disconnected() for client in clients])
        
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    finally:
        if sender_task:
            sender_task.cancel()
            try:
                await sender_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning(f"取消发送任务时出错: {str(e)}")
        
        if message_queue and not message_queue.empty():
            logger.info(f"等待队列中的 {message_queue.qsize()} 条消息发送完成...")
            try:
                await asyncio.wait_for(message_queue.join(), timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning("等待消息发送超时，强制关闭")
        
        for i, client in enumerate(clients):
            try:
                await client.disconnect()
                logger.info(f"✓ [{active_accounts[i]['name']}] Telegram 客户端已断开连接")
            except Exception as e:
                logger.warning(f"断开客户端 {active_accounts[i]['name']} 时出错: {str(e)}")

if __name__ == '__main__':
    try:
        logger.info("检查 session 文件状态...")
        for account in accounts:
            session_file = os.path.join(workdir, f'session_{account["name"]}_{account["api_id"]}.session')
            if os.path.exists(session_file):
                logger.info(f"✓ [{account['name']}] 找到已保存的 session 文件: {session_file}")
            else:
                old_session_file = os.path.join(workdir, f'session_{account["api_id"]}.session')
                if os.path.exists(old_session_file):
                    logger.info(f"⚠ [{account['name']}] 发现旧格式 session 文件: {old_session_file}，建议重命名为 {session_file}")
                else:
                    logger.info(f"✗ [{account['name']}] 未找到 session 文件: {session_file}")
                    logger.info("将进入首次登录流程，需要输入电话号码和验证码")
        
        asyncio.run(main())
    except SessionPasswordNeededError:
        logger.error("需要两步验证密码，请在交互式环境中运行一次以完成登录")
        sys.exit(1)
    except Exception as e:
        logger.error(f"程序启动失败: {str(e)}", exc_info=True)
        sys.exit(1)
