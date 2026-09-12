# zhiliu.cyou 上线 HTTPS（阿里云免费证书）

服务器：`47.94.238.221` · AgentFlow 已在 `/opt/agentflow`

---

## 第 1 步：DNS 解析（控制台）

域名列表 → `zhiliu.cyou` → **解析** → 添加两条 **A 记录**：

| 主机记录 | 类型 | 记录值 |
|---------|------|--------|
| `@` | A | `47.94.238.221` |
| `www` | A | `47.94.238.221` |

等 5～10 分钟，本机测试：

```powershell
ping zhiliu.cyou
```

应显示 `47.94.238.221`。

---

## 第 2 步：申请免费 SSL 证书

1. 阿里云控制台搜索 **「SSL 证书」**
2. **个人测试证书（免费）** 或 **DV 免费证书** → **创建证书**
3. 证书类型：**单域名**
4. 域名填：`zhiliu.cyou`（若还要 `www`，可再申请一张或选多域名套餐）
5. 验证方式：**DNS 自动验证**（域名在阿里云会自动加 TXT）
6. 等待 **已签发**
7. **下载** → 服务器类型选 **Nginx** → 得到 `.pem` + `.key`

---

## 第 3 步：证书上传到服务器

Windows PowerShell（改成本地解压后的实际路径）：

```powershell
scp zhiliu.cyou.pem zhiliu.cyou.key root@47.94.238.221:/tmp/
```

服务器上：

```bash
sudo mkdir -p /etc/nginx/ssl
sudo mv /tmp/zhiliu.cyou.pem /etc/nginx/ssl/
sudo mv /tmp/zhiliu.cyou.key /etc/nginx/ssl/
sudo chmod 600 /etc/nginx/ssl/zhiliu.cyou.key
```

若下载的文件名是 `xxxx.pem` / `xxxx.key`，可重命名或改 nginx 配置里的路径。

---

## 第 4 步：安全组

入方向放行：**443**（80 已有可保留，用于跳转 HTTPS）

---

## 第 5 步：安装 Nginx 站点

```bash
cd /opt/agentflow
# 若本机已更新仓库，先上传 deploy/nginx-zhiliu-cyou-https.conf

sudo cp deploy/nginx-zhiliu-cyou-https.conf /etc/nginx/sites-available/zhiliu-cyou
sudo ln -sfn /etc/nginx/sites-available/zhiliu-cyou /etc/nginx/sites-enabled/zhiliu-cyou

# 确认密钥片段存在（之前 setup 装过）
ls /etc/nginx/snippets/agentflow-secrets-deepseek.conf

sudo nginx -t
sudo systemctl reload nginx
sudo systemctl status agentflow-api --no-pager
```

---

## 第 6 步：访问

- **https://zhiliu.cyou**
- **https://www.zhiliu.cyou**（若解析了 www 且证书包含 www）

应显示小锁；**语音输入**在 HTTPS 下可用。

旧地址 `http://47.94.238.221:8888` 仍可作备用。

---

## 备案说明（课程演示）

域名指向国内 ECS 的 80/443 按规定需 **ICP 备案**（约 1～2 周）。未备案时部分地区可能打不开域名，但 IP:8888 仍可用。答辩若被拦，说明「备案进行中」并用 IP 演示。

---

## 续费

`zhiliu.cyou` 到期 **2027-08-26**；不续费域名会释放。可在域名列表开 **自动续费** 或到期前手动续费（约 10 元/年）。
