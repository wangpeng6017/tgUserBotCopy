import logging
import sys
import os
import json
import asyncio
import random
from datetime import datetime
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError

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
        
        # 验证必需的配置项
        required_keys = ['api_id', 'api_hash', 'target_bot_username']
        for key in required_keys:
            if key not in config:
                print(f"错误: 配置文件缺少必需的配置项: {key}")
                sys.exit(1)
        
        return config
    except json.JSONDecodeError as e:
        print(f"错误: 配置文件格式错误: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: 加载配置文件失败: {str(e)}")
        sys.exit(1)

# 加载配置
config = load_config()
api_id = config['api_id']
api_hash = config['api_hash']
target_bot_username = config['target_bot_username']

# 消息发送配置（防止风控）
send_interval = config.get('send_interval', 2.0)  # 发送间隔（秒），默认2秒
send_jitter = config.get('send_jitter', 1.0)  # 抖动时间（秒），默认1秒，会在0到send_jitter之间随机

# 配置日志路径（支持相对路径和绝对路径）
log_dir_config = config.get('log_dir', 'logs')
if os.path.isabs(log_dir_config):
    # 绝对路径
    log_dir = log_dir_config
else:
    # 相对路径，相对于脚本目录
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), log_dir_config)

os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'tguserbot_{datetime.now().strftime("%Y%m%d")}.log')

# 配置日志格式
# 从环境变量或配置中读取日志级别，默认为 INFO
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

# 创建 Telegram 客户端，使用 api_id 作为 session 文件名
session_name = f'session_{api_id}'
client = TelegramClient(session_name, api_id, api_hash)

# 记录启动时间，用于过滤历史消息
start_time = None

# 消息队列，用于排队发送
message_queue = asyncio.Queue()

# 消息数据结构
class MessageTask:
    def __init__(self, chat_id, msg_text, media=None, user_type=""):
        self.chat_id = chat_id
        self.msg_text = msg_text
        self.media = media
        self.user_type = user_type

async def message_sender():
    """消息发送任务，从队列中取出消息并按间隔发送"""
    logger.info("消息发送任务已启动，等待队列中的消息...")
    while True:
        try:
            # 从队列中获取消息（会阻塞直到有消息）
            task = await message_queue.get()
            logger.info(f"从队列获取到消息，准备发送到群组 {task.chat_id}...")
            
            # 计算延迟时间（基础间隔 + 随机抖动）
            jitter = random.uniform(0, send_jitter)
            delay = send_interval + jitter
            logger.info(f"等待 {delay:.2f} 秒后发送（间隔: {send_interval}秒，抖动: {jitter:.2f}秒）...")
            
            # 等待延迟时间
            await asyncio.sleep(delay)
            
            # 发送消息
            try:
                logger.info(f"开始发送消息到群组 {task.chat_id}...")
                if task.media:
                    await client.send_message(task.chat_id, task.msg_text, file=task.media)
                    logger.info(f"✓ 已复制{task.user_type}消息（含媒体）到群组 {task.chat_id}: {task.msg_text[:100]}...")
                else:
                    await client.send_message(task.chat_id, task.msg_text)
                    logger.info(f"✓ 已复制{task.user_type}消息到群组 {task.chat_id}: {task.msg_text[:100]}...")
            except Exception as e:
                logger.error(f"✗ 发送消息到群组 {task.chat_id} 时发生错误: {str(e)}", exc_info=True)
            
            # 标记任务完成
            message_queue.task_done()
            logger.info(f"消息发送完成，当前队列剩余: {message_queue.qsize()} 条")
            
        except asyncio.CancelledError:
            logger.info("消息发送任务已取消")
            break
        except Exception as e:
            logger.error(f"消息发送任务发生错误: {str(e)}", exc_info=True)
            await asyncio.sleep(1)  # 出错后等待1秒再继续

# 添加一个测试事件处理器，验证事件系统是否工作
@client.on(events.NewMessage())
async def test_handler(event):
    """测试事件处理器，验证事件系统是否正常工作"""
    logger.info(f"🧪 [测试] 事件系统工作正常！收到消息 ID: {event.message.id}")

@client.on(events.NewMessage())
async def handler(event):
    global start_time
    try:
        # 记录启动时间（首次收到消息时）
        if start_time is None:
            from datetime import timezone
            start_time = datetime.now(timezone.utc)
            logger.info(f"首次收到消息，启动时间: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        # 记录所有收到的消息（用于调试）
        logger.info(f"🔔 收到新消息 - 消息ID: {event.message.id}, 群组ID: {event.chat_id}, 是否群组: {event.is_group}")
        
        # 检查消息时间，只处理启动后的消息
        message_time = event.message.date
        # 确保时间对象都有时区信息，统一转换为 UTC 进行比较
        if message_time.tzinfo is None:
            # 如果没有时区信息，假设是 UTC
            from datetime import timezone
            message_time = message_time.replace(tzinfo=timezone.utc)
        
        if message_time < start_time:
            # 这是历史消息，忽略
            logger.info(f"⏮️ 忽略历史消息 ID {event.message.id} (消息时间: {message_time}, 启动时间: {start_time})")
            return
        
        logger.info(f"✅ 消息时间检查通过，继续处理...")
        
        sender = await event.get_sender()
        # 记录所有收到的消息
        if sender:
            sender_info = f"用户名: {sender.username or '无用户名'}, ID: {sender.id}, 是否机器人: {sender.bot}"
            logger.info(f"👤 发送者信息 - {sender_info}, 群组: {event.chat_id}, 消息ID: {event.message.id}")
        else:
            logger.warning("⚠️ 无法获取发送者信息，sender 为 None")
            return
        
        # 判断是否为目标用户（可以是机器人或普通用户）
        logger.info(f"🔍 检查用户名匹配 - 目标: '{target_bot_username}', 实际: '{sender.username if sender else None}'")
        
        if sender and sender.username == target_bot_username:
            logger.info(f"✅ 匹配到目标用户: {sender.username} (ID: {sender.id})")
            # 获取消息所在的群组ID
            chat_id = event.chat_id
            msg_text = event.message.message or ''
            
            # 获取用户类型信息（用于日志）
            user_type = "机器人" if sender.bot else "普通用户"
            
            # 将消息加入队列，而不是直接发送
            task = MessageTask(
                chat_id=chat_id,
                msg_text=msg_text,
                media=event.message.media if event.message.media else None,
                user_type=user_type
            )
            await message_queue.put(task)
            queue_size = message_queue.qsize()
            logger.info(f"消息已加入队列（队列长度: {queue_size}），等待发送...")
            
        else:
            logger.info(f"❌ 用户名不匹配，跳过处理")
            
    except Exception as e:
        logger.error(f"❌ 处理消息时发生错误: {str(e)}", exc_info=True)

# 启动消息发送任务的辅助函数
async def start_sender():
    """启动消息发送任务"""
    await message_sender()

if __name__ == '__main__':
    try:
        import asyncio
        
        # 使用同步方式启动（与 test_login.py 相同），避免异步环境中的问题
        logger.info("正在启动 Telegram 客户端（同步方式）...")
        session_file = f'{session_name}.session'
        logger.info(f"检查 session 文件: {session_file} (存在: {os.path.exists(session_file)})")
        logger.info(f"发送间隔: {send_interval}秒，抖动时间: 0-{send_jitter}秒")
        logger.info(f"目标用户名: {target_bot_username}")
        
        # 使用同步方式启动客户端（与 test_login.py 完全相同）
        client.start()
        logger.info("Telegram 客户端已启动")
        logger.info("已开始监听所有群的指定用户消息...")
        
        # 在后台启动消息发送任务
        loop = asyncio.get_event_loop()
        sender_task = loop.create_task(start_sender())
        logger.info("消息队列发送任务已启动，等待消息...")
        
        logger.info("程序运行中，等待消息...")
        logger.info("=" * 60)
        logger.info("📢 提示：请在 Telegram 中发送一条测试消息")
        logger.info("📢 如果看到 '🧪 [测试] 事件系统工作正常' 说明事件监听正常")
        logger.info("=" * 60)
        
        try:
            # 运行直到断开（同步方式）
            client.run_until_disconnected()
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭...")
        finally:
            # 取消消息发送任务
            sender_task.cancel()
            try:
                loop.run_until_complete(sender_task)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning(f"取消发送任务时出错: {str(e)}")
            
            # 等待队列中的消息发送完成（最多等待30秒）
            if not message_queue.empty():
                logger.info(f"等待队列中的 {message_queue.qsize()} 条消息发送完成...")
                try:
                    loop.run_until_complete(asyncio.wait_for(message_queue.join(), timeout=30.0))
                except asyncio.TimeoutError:
                    logger.warning("等待消息发送超时，强制关闭")
            
            client.disconnect()
            logger.info("Telegram 客户端已断开连接")
            
    except SessionPasswordNeededError:
        logger.error("需要两步验证密码，请在交互式环境中运行一次以完成登录")
        sys.exit(1)
    except Exception as e:
        logger.error(f"程序启动失败: {str(e)}", exc_info=True)
        sys.exit(1)
