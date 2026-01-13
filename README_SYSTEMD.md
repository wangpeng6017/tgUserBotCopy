# Telegram User Bot Systemd 服务安装指南

## 前置要求

1. Python 3.9+ 已安装
2. 虚拟环境已创建并安装了依赖（telethon）
3. 已配置好 API 信息和登录（首次运行需要交互式登录）

## 安装步骤

### 1. 修改服务文件

编辑 `tguserbot.service` 文件，替换以下路径：

- `YOUR_USERNAME`: 替换为运行服务的 Linux 用户名
- `/path/to/tgUserBot`: 替换为项目的实际路径（例如：`/home/username/tgUserBot`）

示例：
```ini
User=ubuntu
WorkingDirectory=/home/ubuntu/tgUserBot
Environment="PATH=/home/ubuntu/tgUserBot/tg_env/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/ubuntu/tgUserBot/tg_env/bin/python /home/ubuntu/tgUserBot/main.py
```

### 2. 复制服务文件到 systemd 目录

```bash
sudo cp tguserbot.service /etc/systemd/system/
```

### 3. 重新加载 systemd 配置

```bash
sudo systemctl daemon-reload
```

### 4. 启用服务（开机自启）

```bash
sudo systemctl enable tguserbot.service
```

### 5. 启动服务

```bash
sudo systemctl start tguserbot.service
```

### 6. 检查服务状态

```bash
sudo systemctl status tguserbot.service
```

## 常用命令

### 查看服务状态
```bash
sudo systemctl status tguserbot.service
```

### 启动服务
```bash
sudo systemctl start tguserbot.service
```

### 停止服务
```bash
sudo systemctl stop tguserbot.service
```

### 重启服务
```bash
sudo systemctl restart tguserbot.service
```

### 查看日志
```bash
# 查看 systemd 日志
sudo journalctl -u tguserbot.service -f

# 查看最近的日志
sudo journalctl -u tguserbot.service -n 100

# 查看今天的日志
sudo journalctl -u tguserbot.service --since today

# 查看应用日志文件（在 logs 目录下）
tail -f /path/to/tgUserBot/logs/tguserbot_*.log
```

### 禁用开机自启
```bash
sudo systemctl disable tguserbot.service
```

## 日志位置

- **Systemd 日志**: 通过 `journalctl` 命令查看
- **应用日志**: 项目目录下的 `logs/` 文件夹，按日期命名（例如：`tguserbot_20240101.log`）

## 故障排查

### 1. 服务无法启动

检查服务状态和错误信息：
```bash
sudo systemctl status tguserbot.service
sudo journalctl -u tguserbot.service -n 50
```

### 2. 权限问题

确保：
- 服务文件中的 `User` 有权限访问项目目录
- 项目目录和文件有正确的权限：
```bash
sudo chown -R YOUR_USERNAME:YOUR_USERNAME /path/to/tgUserBot
chmod +x /path/to/tgUserBot/main.py
```

### 3. Python 路径问题

确保虚拟环境的 Python 路径正确：
```bash
# 检查虚拟环境 Python 路径
/path/to/tgUserBot/tg_env/bin/python --version
```

### 4. 首次登录问题

如果首次运行需要交互式登录（输入验证码等），可以：
1. 先手动运行一次脚本完成登录：
```bash
/path/to/tgUserBot/tg_env/bin/python /path/to/tgUserBot/main.py
```
2. 登录成功后按 Ctrl+C 退出
3. 然后再启动 systemd 服务

## 注意事项

1. 确保 `.session` 文件有正确的权限，服务用户能够读写
2. 如果修改了代码，需要重启服务才能生效
3. 日志文件会自动按日期创建，建议定期清理旧日志

