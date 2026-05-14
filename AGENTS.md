# AI 照片美化 — Agent 导航地图

## 项目概述
基于 FastAPI + Claude Vision 的照片美化 Web 应用。
用户上传日常照片，通过手动滑块或 AI 自然语言指令进行美化处理。

## 快速启动
```bash
cp .env.example .env       # 填写 ANTHROPIC_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# 浏览器打开 http://localhost:8000
```

## 代码导航

### 1. 入口点
| 文件 | 职责 |
|------|------|
| `app/main.py` | FastAPI 实例，挂载路由和静态文件 |
| `app/api/routes.py` | 全部 HTTP 端点（upload / edit/manual / edit/ai） |

### 2. 核心处理层（`app/core/`）
| 文件 | 职责 |
|------|------|
| `image_gen.py` | **主要** — DashScope wan2.7-image 生图编辑（AI 编辑路由使用） |
| `image_processor.py` | 亮度/对比度/饱和度/锐度/色温（Pillow，手动调整使用） |
| `portrait.py` | 磨皮（OpenCV 双边滤波）+ 提亮肤色（手动调整使用） |
| `background.py` | 背景虚化/去除（rembg，可选，手动调整使用） |

### 3. 数据模型（`app/types/models.py`）
- `EditParams` — 基础调整参数（Pillow enhancer 值域 0.1–3.0）
- `PortraitParams` — 人像美化参数
- `BackgroundParams` — 背景处理参数
- `ManualEditRequest / AIEditRequest / EditResponse` — API 请求/响应

### 4. 前端（`app/static/`）
| 文件 | 职责 |
|------|------|
| `index.html` | 单页应用，拖拽上传 + 手动/AI 编辑面板 |
| `app.js` | 上传、手动编辑、AI 编辑流程，滑块值映射 |
| `style.css` | Indigo 主题，响应式网格布局 |

## 关键不变量
- **无损处理**：`uploads/` 只读，输出写入 `outputs/`
- **默认无操作**：所有 core 模块参数为默认值时直接返回原图，零开销
- **rembg 可选**：background.py 有完整降级路径（无 rembg → 简单模糊）
- **AI 参数边界**：Claude 响应总被解析为带范围限制的 Pydantic 模型

## 编辑管道

**AI 生图路径（主要）：**
```
POST /api/edit/ai
  → image_gen.edit_image(src_path, instruction)
  → DashScope wan2.7-image (图片 + 自然语言 → 新图)
  → outputs/ai_{hex}.jpg
```

**手动调整路径（辅助）：**
```
POST /api/edit/manual
  → apply_basic_edits(EditParams)  → apply_portrait(PortraitParams)
  → apply_background(BackgroundParams)
  → outputs/edited_{hex}.jpg
```

## 滑块值映射（前端 → 后端）
前端滑块 `-60..60` 映射到 Pillow enhancer 值：
`enhancer = 1.0 + slider / 100.0`
（0 → 1.0 原图, 60 → 1.6 增强, -60 → 0.4 减弱）

## 环境变量
| 变量 | 必须 | 说明 |
|------|------|------|
| `DASHSCOPE_API_KEY` | 是（AI 生图编辑） | 阿里云 DashScope API Key |
| `PUBLIC_BASE_URL` | 仅云部署时 | 图片公网 URL 前缀，DashScope 需要能访问图片 |
| `HOST` | 否 | 默认 0.0.0.0 |
| `PORT` | 否 | 默认 8000 |

## 架构层级（依赖方向）
```
types/   ←  无内部依赖
core/    ←  仅依赖 types/
api/     ←  依赖 core/ + types/
main.py  ←  依赖 api/
```

## 详细文档
- `docs/ARCHITECTURE.md` — Mermaid 架构图、层级约束
- `docs/DEVELOPMENT.md` — 安装、运行、调试指南
