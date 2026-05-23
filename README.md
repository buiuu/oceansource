# OceanSource 资源查询网站

## 项目概述
一个清新主义风格的资源查询落地网站，具有动态海浪背景，实现从 yunso.net 搜索资源并自动转存到夸克网盘的功能。

## 项目结构
```
good/
├── frontend/              # 前端文件
│   └── index.html        # 清新风格单页应用（带海浪动画）
├── backend/              # 后端服务
│   ├── server.py         # Flask 后端（代理搜索+自动转存）
│   └── requirements.txt  # Python 依赖
├── start.bat            # 启动本地服务 ⭐
├── publish.bat          # 发布到公网 ⭐⭐
├── test.bat             # 快速测试网络
├── README.md            # 使用说明
└── PUBLISH_GUIDE.md     # 公网发布详细指南
```

## 功能特点
1. **清新海洋风格**：蓝白配色，动态海浪背景动画
2. **无登录注册**：直接搜索使用
3. **完整流程**：搜索 → 转存 → 分享
4. **双模式**：
   - **模拟模式**：默认演示，生成模拟夸克分享链接
   - **真实模式**：配置 Cookie 后真实转存到夸克网盘

## 快速启动

### 方法一：一键启动（推荐）
1. 双击 `start.bat`
2. 等待依赖安装完成
3. 服务启动后，打开浏览器访问：
   - 前端页面：`file:///C:/Users/你的用户名/Desktop/good/frontend/index.html`
   - 后端接口：`http://localhost:5001`

### 方法二：手动启动
```bash
# 进入后端目录
cd good/backend

# 安装依赖
pip install -r requirements.txt

# 启动服务
python server.py
```

## 配置说明

### 1. 启用真实夸克网盘转存
编辑 `backend/server.py`，修改以下配置：
```python
QUARK_COOKIE = "你的夸克网盘登录Cookie"
QUARK_SHARE_PWD = "1234"  # 可选分享密码
```

**获取 Cookie 方法**：
1. 浏览器登录夸克网盘
2. 按 F12 打开开发者工具
3. 进入 Network → 刷新页面 → 找到任意请求 → 复制 Cookie 值

### 2. 自定义搜索源
修改 `YUNSO_URL` 变量指向其他资源网站。

## 使用流程
1. **打开前端页面**：双击 `frontend/index.html`
2. **搜索资源**：输入关键词（如"设计素材"）
3. **查看结果**：显示从 yunso.net 获取的资源列表
4. **转存到网盘**：点击"保存到夸克网盘"
5. **获取分享链接**：系统自动生成夸克网盘分享链接
6. **复制链接**：点击"复制"按钮分享给他人

## 技术栈
- **前端**：纯 HTML/CSS/JavaScript + Canvas 海浪动画
- **后端**：Python Flask + BeautifulSoup 解析
- **通信**：RESTful API + CORS 跨域
- **部署**：本地运行，无需服务器

## 注意事项
1. **首次运行**：需要 Python 3.9+ 环境，Windows 系统自带
2. **网络要求**：需要能访问 yunso.net
3. **夸克网盘**：如需真实转存，需配置有效 Cookie
4. **安全提示**：Cookie 请妥善保管，不要分享

## 扩展建议
1. **添加数据库**：存储历史记录和用户偏好
2. **多网盘支持**：增加阿里云盘、百度网盘等
3. **资源预览**：显示文件大小、格式、提取码
4. **批量操作**：支持批量转存和分享
5. **移动端适配**：优化手机端体验

## 故障排除
- **无法搜索**：检查后端是否启动（端口 5001）
- **转存失败**：检查网络连接和 Cookie 配置
- **页面空白**：检查浏览器控制台错误
- **依赖安装失败**：使用 `pip install --upgrade pip`

---

**启动后访问地址**：
- 前端: `file:///C:/Users/你的用户名/Desktop/good/frontend/index.html`
- 后端健康检查: `http://localhost:5001/api/health`

**默认模拟模式已可用，无需配置即可体验完整流程！**