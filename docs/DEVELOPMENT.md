# 开发指南

## 环境要求
- Python 3.10+
- Windows / macOS / Linux

## 安装

```bash
# 1. 进入项目目录
cd agent

# 2. 创建虚拟环境（推荐）
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. 安装依赖
pip install -r requirements.txt

# 4. 可选：安装 AI 背景去除支持（会下载约 170MB 模型）
pip install rembg onnxruntime

# 5. 配置环境变量
cp .env.example .env
# 编辑 .env，填写 DASHSCOPE_API_KEY
```

## DashScope API Key 获取
1. 前往 https://dashscope.aliyun.com/ 注册登录
2. 控制台 → API-KEY 管理 → 创建新 API Key
3. 将 Key 填入 `.env` 中的 `DASHSCOPE_API_KEY`

## 图片访问说明（重要）

AI 生图时，DashScope 需要能访问你上传的图片。

**本地开发（推荐）：** SDK 默认使用 `file://` 本地路径，无需额外配置。

**云服务器部署：** DashScope 服务器在阿里云，无法访问你服务器上的 `file://` 路径，需在 `.env` 配置公网域名：
```
PUBLIC_BASE_URL=https://your-domain.com
```

## 运行

```bash
# 开发模式（热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或使用 Makefile
make run
```

浏览器访问 http://localhost:8000

## 项目结构

```
app/
├── main.py             # FastAPI 入口
├── types/models.py     # Pydantic 数据模型
├── core/
│   ├── image_processor.py  # 基础调整（Pillow）
│   ├── portrait.py         # 人像美化（OpenCV）
│   ├── background.py       # 背景处理（rembg）
│   └── ai_editor.py        # Claude AI 集成
├── api/routes.py       # HTTP 路由
└── static/             # 前端文件
    ├── index.html
    ├── style.css
    └── app.js
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload` | 上传图片，返回 `{filename, width, height}` |
| POST | `/api/edit/manual` | 手动参数编辑 |
| POST | `/api/edit/ai` | AI 自然语言编辑 |
| GET  | `/uploads/{filename}` | 访问原图 |
| GET  | `/outputs/{filename}` | 访问输出图 |

## 依赖检查

```bash
make lint
# 或
python scripts/lint-deps.py
```

## 常见问题

**Q: AI 编辑报错"未配置 DASHSCOPE_API_KEY"**
A: 在 `.env` 文件中添加 `DASHSCOPE_API_KEY=your_key`（阿里云控制台获取）。

**Q: AI 编辑报错图片无法访问/URL 错误**
A: DashScope 无法访问本地 `file://` 路径（仅云部署时出现）。在 `.env` 设置 `PUBLIC_BASE_URL=https://你的域名`。

**Q: 背景虚化/去除无效**
A: 需要安装 rembg：`pip install rembg onnxruntime`
   首次运行会下载约 170MB 的 ONNX 模型，请耐心等待。

**Q: OpenCV 安装失败**
A: 尝试 `pip install opencv-python-headless --no-cache-dir`

**Q: 图片上传成功但处理报 500 错误**
A: 查看 uvicorn 终端的详细错误信息。
