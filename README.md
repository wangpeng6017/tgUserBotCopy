# Telegram User Bot

一个基于 Telethon 的 Telegram 用户机器人，用于监听指定机器人的消息并自动复制到对应群组。

## ✨ 功能特性

- 🔍 监听所有群组中的指定机器人消息
- 📋 自动复制消息到对应群组
- 🖼️ 支持文本和媒体（图片、视频等）消息
- ⏰ **智能过滤历史消息**：只处理启动后的新消息，避免处理历史消息导致重复发送
- 📝 完整的日志记录功能
- 🔄 支持 systemd 服务管理
- ⚙️ 配置文件化管理

## 📚 文档

- **[完整部署指南](DEPLOYMENT.md)** - 从零开始的详细部署流程（**推荐新用户阅读**）
- [Systemd 服务安装指南](README_SYSTEMD.md) - 服务安装和管理的详细说明

## 🚀 快速开始

### 前置要求

- Python 3.9+
- Telegram API ID 和 API Hash
- Linux 服务器（推荐 Ubuntu 22.04）

### 安装步骤

1. **克隆或上传项目**
   ```bash
   cd /home/your_username
   # 上传项目文件
   ```

2. **安装 Python 和虚拟环境支持**
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install python3 python3-pip python3-venv -y
   
   # 如果遇到 "ensurepip is not available" 错误，安装对应版本：
   sudo apt install python3.12-venv -y  # 根据你的 Python 版本调整
   ```

3. **创建虚拟环境**
   ```bash
   cd tgUserBot
   python3 -m venv tg_env
   source tg_env/bin/activate
   pip install --upgrade pip
   pip install telethon
   ```

4. **配置项目**
   ```bash
   cp config.json.example config.json
   nano config.json  # 编辑配置文件
   ```

5. **首次登录**
   ```bash
   python main.py  # 登录后 Ctrl+C 退出
   ```

6. **安装服务**
   ```bash
   chmod +x install_service.sh
   ./install_service.sh
   sudo systemctl start tguserbot
   ```

**详细步骤请查看 [完整部署指南](DEPLOYMENT.md)**

## ⚙️ 配置说明

配置文件：`config.json`

```json
{
    "api_id": 12345678,
    "api_hash": "your_api_hash_here",
    "target_bot_username": "your_bot_username",
    "log_dir": "logs",
    "send_interval": 2
}
```

### 配置项说明

- `api_id`: Telegram API ID（从 https://my.telegram.org/apps 获取）
- `api_hash`: Telegram API Hash
- `target_bot_username`: 要监听的机器人用户名（不带 @）
- `log_dir`: 日志目录（相对路径或绝对路径，默认 "logs"）
- `send_interval`: 消息发送间隔（秒），用于控制发送频率避免被风控（默认 2 秒，建议 1-5 秒）

## 📖 使用方法

### 服务管理

```bash
# 启动服务
sudo systemctl start tguserbot

# 停止服务
sudo systemctl stop tguserbot

# 重启服务
sudo systemctl restart tguserbot

# 查看状态
sudo systemctl status tguserbot

# 查看日志
sudo journalctl -u tguserbot -f
```

### 查看日志

```bash
# Systemd 日志
sudo journalctl -u tguserbot -f

# 应用日志文件
tail -f logs/tguserbot_*.log
```

## 📁 项目结构

```
tgUserBot/
├── main.py                 # 主程序
├── config.json             # 配置文件（需要创建）
├── config.json.example     # 配置模板
├── tguserbot.service       # Systemd 服务文件
├── install_service.sh      # 自动安装脚本
├── README.md              # 本文件
├── DEPLOYMENT.md          # 完整部署指南
├── README_SYSTEMD.md      # 服务管理文档
├── .gitignore            # Git 忽略规则
└── logs/                  # 日志目录（自动创建）
```

## 🔧 故障排查

遇到问题？请查看：

1. [完整部署指南 - 故障排查部分](DEPLOYMENT.md#故障排查)
2. [Systemd 服务安装指南 - 故障排查部分](README_SYSTEMD.md#故障排查)

常见问题：
- 服务无法启动 → 检查虚拟环境、配置文件、权限
- 无法连接 Telegram → 检查网络、防火墙
- 内存不足 → 查看优化建议

## 🔒 安全建议

1. **保护敏感文件**
   ```bash
   chmod 600 config.json
   chmod 600 *.session
   ```

2. **不要提交敏感信息**
   - `config.json` 已添加到 `.gitignore`
   - `*.session` 文件已添加到 `.gitignore`

3. **定期更新依赖**
   ```bash
   source tg_env/bin/activate
   pip install --upgrade telethon
   ```

## 📝 更新日志

查看 [DEPLOYMENT.md](DEPLOYMENT.md#更新日志) 了解更新历史。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目仅供学习和个人使用。

## 🔗 相关链接

- [Telethon 文档](https://docs.telethon.dev/)
- [Telegram API](https://core.telegram.org/api)
- [获取 API 凭证](https://my.telegram.org/apps)

---

**需要帮助？** 请查看 [完整部署指南](DEPLOYMENT.md) 或提交 Issue。

