import logging
import sys
import os
import json
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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
logger.info(f"日志文件路径: {log_file}")

# 创建 Telegram 客户端
client = TelegramClient('anon', api_id, api_hash)

# 记录启动时间，用于过滤历史消息
start_time = None

@client.on(events.NewMessage())
async def handler(event):
    try:
        # 只处理启动后收到的新消息，忽略历史消息
        if start_time is None:
            return
        
        # 检查消息时间，只处理启动后的消息
        message_time = event.message.date
        # 确保时间对象都有时区信息，统一转换为 UTC 进行比较
        if message_time.tzinfo is None:
            # 如果没有时区信息，假设是 UTC
            from datetime import timezone
            message_time = message_time.replace(tzinfo=timezone.utc)
        
        if message_time < start_time:
            # 这是历史消息，忽略
            logger.debug(f"忽略历史消息 ID {event.message.id} (消息时间: {message_time}, 启动时间: {start_time})")
            return
        
        sender = await event.get_sender()
        # 判断是否为目标机器人
        if sender and sender.username == target_bot_username:
            # 获取消息所在的群组ID
            chat_id = event.chat_id
            msg_text = event.message.message or ''
            
            # 检查消息是否包含媒体（图片、视频等）
            if event.message.media:
                # 如果有媒体，发送消息和媒体到对应群组
                await client.send_message(chat_id, msg_text, file=event.message.media)
                logger.info(f"已复制消息（含媒体）到群组 {chat_id}: {msg_text[:100]}...")
            else:
                # 如果只有文本，只发送文本到对应群组
                await client.send_message(chat_id, msg_text)
                logger.info(f"已复制消息到群组 {chat_id}: {msg_text[:100]}...")
    except Exception as e:
        logger.error(f"处理消息时发生错误: {str(e)}", exc_info=True)

async def main():
    global start_time
    try:
        await client.start()
        # 记录启动时间，用于过滤历史消息
        from datetime import timezone
        start_time = datetime.now(timezone.utc)
        logger.info("Telegram 客户端已启动")
        logger.info(f"启动时间: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        logger.info("已开始监听所有群的指定机器人消息（仅处理启动后的新消息）...")
        await client.run_until_disconnected()
    except SessionPasswordNeededError:
        logger.error("需要两步验证密码，请在交互式环境中运行一次以完成登录")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"运行时发生错误: {str(e)}", exc_info=True)
        raise
    finally:
        await client.disconnect()
        logger.info("Telegram 客户端已断开连接")

if __name__ == '__main__':
    try:
        import asyncio
        asyncio.run(main())
    except Exception as e:
        logger.error(f"程序启动失败: {str(e)}", exc_info=True)
        sys.exit(1)
