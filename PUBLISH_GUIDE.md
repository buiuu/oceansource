# OceanSource 公网发布指南

## 方法一：使用 ngrok（推荐，最简单）

### 步骤1：启动本地服务
双击运行 `start.bat`，确保后端在 `localhost:5001` 正常运行

### 步骤2：发布到公网
双击运行 `publish.bat`，选择：
- **已登录 ngrok**：输入 `y` 使用已登录账号（地址固定）
- **临时隧道**：输入 `n` 使用临时隧道（无需登录）

### 步骤3：获取公网地址
程序会显示类似这样的地址：
```
Forwarding https://abc123.ngrok-free.app -> http://localhost:5001
```

### 步骤4：分享给他人
将 `https://abc123.ngrok-free.app` 发送给朋友，他们就能：
- 直接访问网站
- 搜索资源
- 转存到夸克网盘
- 获取分享链接

## 方法二：使用 Cloudflare Tunnel（更稳定）

### 安装 Cloudflare Tunnel
```bash
# 下载 cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe -o cloudflared.exe

# 登录 Cloudflare
cloudflared.exe tunnel login

# 创建隧道
cloudflared.exe tunnel create oceansource

# 配置隧道
cloudflared.exe tunnel route dns oceansource oceansource.yourdomain.com

# 启动隧道
cloudflared.exe tunnel run oceansource
```

## 方法三：部署到云服务器（永久可用）

### 推荐平台
1. **Vercel**（免费）：适合前端
2. **Railway**（免费额度）：全栈部署
3. **PythonAnywhere**（免费）：Python后端
4. **Render**（免费）：全栈部署

### Vercel 部署步骤
```bash
# 安装 Vercel CLI
npm i -g vercel

# 登录
vercel login

# 部署
vercel --prod
```

## 方法四：使用本地网络共享（局域网内）

### Windows 网络共享
1. 打开 Windows 防火墙，允许端口 5001
2. 获取本机 IP 地址：`ipconfig`
3. 分享地址：`http://192.168.x.x:5001`

### 手机访问测试
在手机浏览器输入：`http://电脑IP:5001`

## 安全注意事项

### 1. 访问控制
- 临时隧道建议添加基础认证
- 生产环境建议设置访问密码
- 限制访问频率

### 2. API 保护
- 夸克网盘 Cookie 不要硬编码
- 使用环境变量存储敏感信息
- 添加请求频率限制

### 3. 数据安全
- 搜索结果缓存清理
- 用户数据定期清理
- 日志文件不包含敏感信息

## 性能优化建议

### 1. 前端优化
- 压缩静态资源
- 启用浏览器缓存
- 使用 CDN 加速

### 2. 后端优化
- 添加请求缓存
- 优化网络请求超时
- 使用异步处理

## 故障排除

### 常见问题
1. **无法连接**：检查防火墙，允许端口 5001
2. **地址失效**：ngrok 免费版隧道 2 小时重置
3. **速度慢**：使用 Cloudflare Tunnel 或部署到云服务器
4. **搜索失败**：检查 yunso.net 是否可访问

### 日志查看
```bash
# 查看后端日志
cd backend
python server.py

# 查看 ngrok 日志
ngrok http 5001 --log stdout
```

## 生产环境建议

### 1. 域名配置
- 购买自定义域名
- 配置 SSL 证书
- 设置 DNS 解析

### 2. 监控告警
- 服务健康检查
- 访问日志分析
- 异常告警通知

### 3. 备份策略
- 代码版本控制
- 数据库定期备份
- 配置文件备份

## 快速测试
1. 本地访问：`http://localhost:5001` ✅
2. 手机同 WiFi：`http://电脑IP:5001` ✅  
3. 公网访问：`https://xxx.ngrok-free.app` ✅

## 维护说明
- 每天首次使用需启动 `start.bat`
- 分享地址前先运行 `publish.bat`
- 长期运行建议部署到云服务器

---

**最简单方案**：双击 `publish.bat`，分享生成的 ngrok 地址即可！