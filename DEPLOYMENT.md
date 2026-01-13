# Telegram User Bot 完整部署指南

本文档提供从零开始部署 Telegram User Bot 到 Linux 服务器的完整操作流程。

## 📋 目录

- [前置要求](#前置要求)
- [快速开始](#快速开始)
- [详细部署步骤](#详细部署步骤)
- [服务管理](#服务管理)
- [故障排查](#故障排查)
- [常见问题](#常见问题)

---

## 前置要求

### 系统要求

- **操作系统**: Ubuntu 22.04 LTS / Debian 12 / Rocky Linux 9（推荐 Ubuntu）
- **内存**: 至少 512MB（推荐 1GB）
- **Python**: 3.9 或更高版本
- **网络**: 能够访问 Telegram 服务器

### 需要准备的信息

- Telegram API ID 和 API Hash（从 https://my.telegram.org/apps 获取）
- 目标机器人用户名（不带 @）
- 服务器 SSH 访问权限

---

## 快速开始

### 一键部署命令（适用于已配置好环境的服务器）

```bash
# 1. 克隆或上传项目
cd /home/your_username
# 上传项目文件到此目录

# 2. 进入项目目录
cd tgUserBot

# 3. 创建虚拟环境并安装依赖
python3 -m venv tg_env
source tg_env/bin/activate
pip install --upgrade pip
pip install telethon

# 4. 配置项目
cp config.json.example config.json
nano config.json  # 编辑配置文件

# 5. 首次登录（如果需要）
python main.py  # 登录后 Ctrl+C 退出

# 6. 安装服务
chmod +x install_service.sh
./install_service.sh

# 7. 启动服务
sudo systemctl start tguserbot
sudo systemctl status tguserbot
```

---

## 详细部署步骤

### 步骤 1: 准备服务器环境

#### 1.1 连接到服务器

```bash
ssh username@your_server_ip
```

#### 1.2 更新系统（可选但推荐）

```bash
# Ubuntu/Debian
sudo apt update
sudo apt upgrade -y

# CentOS/Rocky Linux
sudo yum update -y
# 或
sudo dnf update -y
```

#### 1.3 安装 Python 3.9+

```bash
# Ubuntu/Debian
sudo apt install python3 python3-pip python3-venv -y

# CentOS/Rocky Linux
sudo yum install python3 python3-pip -y
# 或
sudo dnf install python3 python3-pip -y

# 验证 Python 版本
python3 --version
# 应该显示 Python 3.9.x 或更高版本
```

---

### 步骤 2: 上传项目文件

#### 方法一：使用 SCP（从本地 Mac/Windows）

```bash
# 在本地终端执行
scp -r tgUserBot username@server_ip:/home/username/
```

#### 方法二：使用 Git（如果项目在 Git 仓库）

```bash
# 在服务器上执行
cd /home/username
git clone your_repository_url tgUserBot
cd tgUserBot
```

#### 方法三：手动上传

使用 FTP/SFTP 工具（如 FileZilla、WinSCP）上传项目文件夹到服务器。

#### 验证文件

```bash
cd /home/username/tgUserBot
ls -la
# 应该看到以下文件：
# - main.py
# - config.json.example
# - install_service.sh
# - tguserbot.service
# - README_SYSTEMD.md
# - .gitignore
```

---

### 步骤 3: 创建虚拟环境

```bash
# 进入项目目录
cd /home/username/tgUserBot

# 创建虚拟环境
python3 -m venv tg_env

# 激活虚拟环境
source tg_env/bin/activate

# 验证虚拟环境
which python
# 应该显示: /home/username/tgUserBot/tg_env/bin/python
```

---

### 步骤 4: 安装 Python 依赖

```bash
# 确保虚拟环境已激活（提示符前应该有 (tg_env)）

# 升级 pip
pip install --upgrade pip

# 安装 Telethon
pip install telethon

# 验证安装
pip list | grep telethon
# 应该显示 telethon 及其版本号
```

**可选：创建 requirements.txt**

```bash
# 生成依赖列表
pip freeze > requirements.txt

# 以后可以使用以下命令安装所有依赖
pip install -r requirements.txt
```

---

### 步骤 5: 配置项目

#### 5.1 创建配置文件

```bash
# 复制配置模板
cp config.json.example config.json

# 编辑配置文件
nano config.json
# 或使用其他编辑器：vim, vi, code 等
```

#### 5.2 填写配置信息

编辑 `config.json`，填入以下信息：

```json
{
    "api_id": 12345678,
    "api_hash": "your_api_hash_here",
    "target_bot_username": "your_bot_username",
    "log_dir": "logs"
}
```

**获取 API 信息：**

1. 访问 https://my.telegram.org/apps
2. 使用你的 Telegram 账号登录
3. 创建新应用或使用现有应用
4. 复制 `api_id` 和 `api_hash`

**配置说明：**

- `api_id`: Telegram API ID（数字）
- `api_hash`: Telegram API Hash（字符串）
- `target_bot_username`: 要监听的机器人用户名（不带 @）
- `log_dir`: 日志目录（相对路径或绝对路径，默认 "logs"）

#### 5.3 验证配置文件

```bash
# 检查配置文件格式
python3 -m json.tool config.json
# 如果格式正确，会输出格式化的 JSON
# 如果有错误，会显示错误信息
```

---

### 步骤 6: 首次登录（重要）

首次运行需要完成 Telegram 登录验证。

```bash
# 确保虚拟环境已激活
source tg_env/bin/activate

# 运行脚本
python main.py
```

**登录过程：**

1. 脚本会提示输入手机号码（带国家代码，如：+8613800138000）
2. 输入验证码（Telegram 会发送到你的手机）
3. 如果启用了两步验证，输入密码
4. 登录成功后，会看到 "已开始监听所有群的指定机器人消息..."
5. 按 `Ctrl+C` 退出

**验证登录：**

```bash
# 检查是否生成了会话文件
ls -la *.session
# 应该看到 anon.session 文件
```

---

### 步骤 7: 安装 Systemd 服务

#### 7.1 使用自动安装脚本（推荐）

```bash
# 给安装脚本执行权限
chmod +x install_service.sh

# 运行安装脚本
./install_service.sh
```

脚本会自动：
- 检测当前用户名
- 检测项目路径
- 替换服务文件中的占位符
- 复制服务文件到 `/etc/systemd/system/`
- 重新加载 systemd 配置
- 启用服务（开机自启）

#### 7.2 手动安装（如果自动安装失败）

```bash
# 1. 编辑服务文件
nano tguserbot.service

# 2. 替换以下内容：
#    YOUR_USERNAME → 你的用户名（如：ubuntu）
#    /path/to/tgUserBot → 实际项目路径（如：/home/ubuntu/tgUserBot）

# 3. 复制服务文件
sudo cp tguserbot.service /etc/systemd/system/

# 4. 重新加载 systemd
sudo systemctl daemon-reload

# 5. 启用服务
sudo systemctl enable tguserbot.service
```

---

### 步骤 8: 启动和管理服务

#### 8.1 启动服务

```bash
sudo systemctl start tguserbot
```

#### 8.2 检查服务状态

```bash
sudo systemctl status tguserbot
```

**正常状态应该显示：**
- `Active: active (running)`
- 没有错误信息

#### 8.3 查看实时日志

```bash
# 查看 systemd 日志
sudo journalctl -u tguserbot -f

# 查看应用日志文件
tail -f /home/username/tgUserBot/logs/tguserbot_*.log
```

#### 8.4 验证服务运行

```bash
# 检查进程
ps aux | grep python | grep main.py

# 检查日志中是否有 "Telegram 客户端已启动"
sudo journalctl -u tguserbot | grep "已启动"
```

---

## 服务管理

### 基本命令

```bash
# 启动服务
sudo systemctl start tguserbot

# 停止服务
sudo systemctl stop tguserbot

# 重启服务
sudo systemctl restart tguserbot

# 查看状态
sudo systemctl status tguserbot

# 启用开机自启
sudo systemctl enable tguserbot

# 禁用开机自启
sudo systemctl disable tguserbot

# 重新加载配置（修改服务文件后）
sudo systemctl daemon-reload
sudo systemctl restart tguserbot
```

### 查看日志

```bash
# 查看最近的日志（最后 50 行）
sudo journalctl -u tguserbot -n 50

# 查看今天的日志
sudo journalctl -u tguserbot --since today

# 实时跟踪日志
sudo journalctl -u tguserbot -f

# 查看应用日志文件
tail -f /path/to/tgUserBot/logs/tguserbot_YYYYMMDD.log

# 查看所有日志文件
ls -lh /path/to/tgUserBot/logs/
```

---

## 故障排查

### 问题 1: 服务无法启动

**检查步骤：**

```bash
# 1. 查看服务状态
sudo systemctl status tguserbot

# 2. 查看详细错误信息
sudo journalctl -u tguserbot -n 100

# 3. 检查常见问题：
#    - 虚拟环境路径是否正确
#    - Python 解释器是否存在
#    - 配置文件是否存在且格式正确
#    - 会话文件权限是否正确
```

**常见错误及解决方案：**

- **错误**: `No such file or directory: /path/to/tgUserBot/tg_env/bin/python`
  - **解决**: 检查虚拟环境是否存在，重新创建虚拟环境

- **错误**: `配置文件不存在`
  - **解决**: 确保 `config.json` 文件存在

- **错误**: `配置文件格式错误`
  - **解决**: 检查 JSON 格式，使用 `python3 -m json.tool config.json` 验证

- **错误**: `Permission denied`
  - **解决**: 检查文件权限，确保服务用户有读取权限

### 问题 2: 服务启动后立即停止

**检查步骤：**

```bash
# 查看详细日志
sudo journalctl -u tguserbot -n 100 --no-pager

# 手动运行测试
cd /path/to/tgUserBot
source tg_env/bin/activate
python main.py
```

**可能原因：**

1. 配置文件错误
2. 会话文件损坏
3. 网络连接问题
4. API 信息错误

### 问题 3: 无法连接到 Telegram

**检查步骤：**

```bash
# 测试网络连接
ping api.telegram.org

# 检查防火墙
sudo ufw status  # Ubuntu
sudo firewall-cmd --list-all  # CentOS/Rocky Linux

# 检查代理设置（如果使用代理）
```

### 问题 4: 内存不足

**检查内存使用：**

```bash
# 查看内存使用情况
free -h

# 查看进程内存
ps aux --sort=-%mem | head

# 如果内存不足，考虑：
# 1. 增加 swap
# 2. 优化系统服务
# 3. 升级服务器内存
```

### 问题 5: 日志文件过大

**清理旧日志：**

```bash
# 查看日志文件大小
du -sh /path/to/tgUserBot/logs/

# 删除 7 天前的日志
find /path/to/tgUserBot/logs/ -name "*.log" -mtime +7 -delete

# 或配置日志轮转（推荐）
```

---

## 常见问题

### Q1: 如何更新代码？

```bash
# 1. 停止服务
sudo systemctl stop tguserbot

# 2. 更新代码（如果使用 Git）
cd /path/to/tgUserBot
git pull

# 或手动上传新文件

# 3. 检查配置文件是否需要更新
# 比较 config.json.example 和 config.json

# 4. 重启服务
sudo systemctl start tguserbot
```

### Q2: 如何更新依赖？

```bash
# 1. 停止服务
sudo systemctl stop tguserbot

# 2. 激活虚拟环境
cd /path/to/tgUserBot
source tg_env/bin/activate

# 3. 更新依赖
pip install --upgrade telethon

# 4. 重启服务
sudo systemctl start tguserbot
```

### Q3: 如何修改配置？

```bash
# 1. 编辑配置文件
nano /path/to/tgUserBot/config.json

# 2. 验证配置格式
python3 -m json.tool /path/to/tgUserBot/config.json

# 3. 重启服务使配置生效
sudo systemctl restart tguserbot
```

### Q4: 如何查看服务是否正常工作？

```bash
# 1. 检查服务状态
sudo systemctl status tguserbot

# 2. 查看日志
sudo journalctl -u tguserbot -f

# 3. 检查是否有消息处理记录
grep "已复制消息" /path/to/tgUserBot/logs/tguserbot_*.log
```

### Q5: 如何备份？

```bash
# 备份重要文件
tar -czf tguserbot_backup_$(date +%Y%m%d).tar.gz \
  /path/to/tgUserBot/config.json \
  /path/to/tgUserBot/*.session \
  /path/to/tgUserBot/main.py

# 恢复备份
tar -xzf tguserbot_backup_YYYYMMDD.tar.gz -C /path/to/tgUserBot/
```

### Q6: 如何卸载服务？

```bash
# 1. 停止服务
sudo systemctl stop tguserbot

# 2. 禁用服务
sudo systemctl disable tguserbot

# 3. 删除服务文件
sudo rm /etc/systemd/system/tguserbot.service

# 4. 重新加载 systemd
sudo systemctl daemon-reload

# 5. 删除项目文件（可选）
rm -rf /path/to/tgUserBot
```

---

## 安全建议

1. **保护配置文件**
   - 确保 `config.json` 权限为 600
   ```bash
   chmod 600 config.json
   ```

2. **保护会话文件**
   - 确保 `.session` 文件权限为 600
   ```bash
   chmod 600 *.session
   ```

3. **定期更新**
   - 定期更新 Python 依赖
   - 关注安全公告

4. **日志管理**
   - 定期清理旧日志
   - 日志可能包含敏感信息，注意保护

5. **防火墙配置**
   - 只开放必要的端口
   - 限制 SSH 访问

---

## 性能优化

### 对于 512MB 内存的服务器

1. **使用轻量级系统**
   - Alpine Linux
   - Debian 最小安装

2. **关闭不必要的服务**
   ```bash
   sudo systemctl disable snapd  # Ubuntu
   sudo systemctl disable bluetooth
   ```

3. **配置 Swap**
   ```bash
   sudo fallocate -l 512M /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

4. **定期清理日志**
   ```bash
   # 设置日志轮转，限制单个日志文件大小
   ```

---

## 联系与支持

如果遇到问题：

1. 查看本文档的故障排查部分
2. 检查日志文件
3. 查看 GitHub Issues（如果有）
4. 查阅 Telethon 官方文档

---

## 更新日志

- **2024-01-XX**: 初始版本
  - 添加完整部署流程
  - 添加故障排查指南
  - 添加服务管理说明

---

**祝部署顺利！** 🚀

