# 智流 AgentFlow — 上线流程（不用域名）

适用：阿里云 ECS **Ubuntu 22.04**，2 核 8G。  
和同机已占用 **80** 的项目共存：AgentFlow 使用 **8080**。

最终访问地址（把 IP 换成你的）：

```text
http://47.94.238.221:8080/
```

下午那个项目继续用：`http://47.94.238.221/`（80，不动）。

---

## 总览（做完这 5 步就上线）

1. 安全组放行 **8080**
2. 本机打包上传代码到服务器 `/opt/agentflow`
3. 填写 `backend/.env`（DeepSeek、邮箱 SMTP 等）
4. 执行 `sudo bash deploy/setup-ubuntu.sh`
5. 浏览器打开 `http://公网IP:8080/` 自检

---

## 第 1 步：安全组放行 8080

1. 阿里云控制台 → **云服务器 ECS** → 点开你的实例
2. 上面点 **「安全组」** 或左侧「网络与安全组」
3. 点进安全组 → **配置规则** → **入方向** → **手动添加**

| 协议 | 端口 | 授权对象 | 说明 |
|------|------|----------|------|
| TCP | **8080** | `0.0.0.0/0` | AgentFlow 网站 |
| TCP | 22 | 建议仅你的 IP | SSH（已有可跳过） |
| TCP | 80 | 已有可跳过 | 下午那个项目 |

保存。**不配域名，不必开 443。**

---

## 第 2 步：SSH 登录服务器

实例页点 **「远程连接」**，或本机 PowerShell：

```powershell
ssh root@47.94.238.221
```

（若用密钥：`ssh -i 你的密钥.pem root@47.94.238.221`）

---

## 第 3 步：把代码弄到服务器

在你 **自己的 Windows 电脑**、项目根目录 `agentflow` 里打开 PowerShell：

```powershell
cd C:\Users\wzt20\Desktop\agentflow

# 打包（排除大目录）
tar --exclude=node_modules --exclude=.venv --exclude=dist --exclude=.git -czf $env:TEMP\agentflow.tgz .

# 上传（会提示输入 root 密码）
scp $env:TEMP\agentflow.tgz root@47.94.238.221:/tmp/
```

若本机没有 `tar`/`scp`，可用：

- Win11 自带 OpenSSH（上面命令一般可用）
- 或用 **FinalShell / Xshell** 把整个项目文件夹拖到服务器 `/opt/agentflow`

然后在 **服务器** 上：

```bash
sudo mkdir -p /opt/agentflow
sudo tar -xzf /tmp/agentflow.tgz -C /opt/agentflow
cd /opt/agentflow
ls package.json deploy/setup-ubuntu.sh
```

能看到这两个文件就对了。

> 若仓库已推到 GitHub/Gitee，也可以在服务器：  
> `git clone <仓库地址> /opt/agentflow`

---

## 第 4 步：填写密钥（必做）

```bash
cd /opt/agentflow
sudo cp -n backend/.env.example backend/.env
sudo nano backend/.env
```

至少改这些（按你真实值填，不要留空关键项）：

```env
DEEPSEEK_API_KEY=sk-你的key
AUTH_DEV_MODE=0
AUTH_ADMIN_EMAILS=你的邮箱@qq.com
MAWP_HOST=127.0.0.1
MAWP_PORT=8787

SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=你的QQ邮箱@qq.com
SMTP_PASSWORD=QQ邮箱授权码
SMTP_FROM=你的QQ邮箱@qq.com
```

可选：`BOCHA_API_KEY`、`POLLINATIONS_API_KEY`。  
保存：`Ctrl+O` 回车，退出：`Ctrl+X`。

---

## 第 5 步：一键安装（约 5～15 分钟）

```bash
cd /opt/agentflow
sudo sed -i 's/\r$//' deploy/*.sh
sudo bash deploy/setup-ubuntu.sh
```

脚本会自动：

- 安装 Node 20、Nginx、Python 虚拟环境
- `npm install` + `npm run build`（生成前端 `dist/`）
- 启动 `agentflow-api`（本机 8787）
- 配置 Nginx 监听 **8080**（不抢 80）
- 防火墙放行 8080

成功时终端会打印类似：

```text
访问：http://47.94.238.221:8080/
```

---

## 第 6 步：验证

**服务器上：**

```bash
systemctl status agentflow-api --no-pager
systemctl status nginx --no-pager
curl -sI http://127.0.0.1:8080/ | head -5
curl -s http://127.0.0.1:8787/api/health
```

**你自己电脑浏览器：**

打开 → [http://47.94.238.221:8080/](http://47.94.238.221:8080/)

自检清单：

1. 能打开登录页  
2. 邮箱收验证码并登录  
3. 能发一条对话（依赖 DeepSeek Key）

---

## 以后改代码怎么更新

本机改完再打包上传，或服务器上 `git pull`，然后：

```bash
cd /opt/agentflow
sudo sed -i 's/\r$//' deploy/update.sh
sudo bash deploy/update.sh
```

只改了 `.env`：

```bash
sudo systemctl restart agentflow-api
# 若改了 DEEPSEEK / BOCHA / POLLINATIONS 的 Key，再跑一遍 update.sh 刷新 Nginx 密钥
```

看日志：

```bash
journalctl -u agentflow-api -f
```

---

## 常见问题

| 现象 | 处理 |
|------|------|
| 浏览器打不开 :8080 | 安全组是否放行 8080；`sudo ss -lntp \| grep 8080` 是否在听 |
| 打开是别的项目 | 你访问的是 80；AgentFlow 必须带 **:8080** |
| 页面空白 | `ls /opt/agentflow/dist/index.html`；没有则构建失败，重跑 setup/update |
| 对话失败 / 502 | `journalctl -u agentflow-api -n 80`；检查 `DEEPSEEK_API_KEY` |
| 收不到验证码 | `AUTH_DEV_MODE=0`；SMTP 用 QQ **授权码**；`systemctl restart agentflow-api` |
| 安装报端口被占 | `HTTP_PORT=8888 sudo bash deploy/setup-ubuntu.sh`，安全组同步开 8888 |

---

## 架构（不用记，排错用）

```text
浏览器
  → http://公网IP:8080
      Nginx
        /              → /opt/agentflow/dist
        /api/mawp/     → 127.0.0.1:8787
        /api/deepseek/ → DeepSeek（密钥在 nginx snippet）
        /api/bocha/    → 博查
        /api/pollinations/ → 文生图
```

8787 **不要**在安全组对公网开放。

---

## 文件清单

| 路径 | 作用 |
|------|------|
| `deploy/setup-ubuntu.sh` | 首次安装 |
| `deploy/update.sh` | 更新 |
| `deploy/nginx.conf` | 监听 8080 |
| `deploy/agentflow-api.service` | API 开机自启 |
| `backend/.env` | 密钥（勿提交 Git） |
