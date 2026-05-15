# AI 照片美化

> 上传一张照片，几秒钟内呈现专业级修图效果。

用 AI 驱动的视觉模型分析照片风格、提取调色参数、生成效果图——同时保留完整的手动控制权，让你在 AI 建议和精细调整之间自由切换。

**技术栈：FastAPI · DashScope Qwen-VL · Pillow · OpenCV · 原生 JS**

---

## 能做什么

### 手动精调
- **基础调整** — 亮度、对比度、饱和度、锐度、色温，所见即所得
- **高级调整** — 高光 / 阴影 / 白点 / 黑点、自然饱和度、清晰度、暗角、胶片颗粒
- **色彩曲线** — 交互式 RGB / R / G / B 四通道 PCHIP 样条曲线编辑器，精准到每个像素

### AI 辅助
- **AI 解读参数** — 用一句话描述想要的效果（"再亮一点，色调偏暖"），AI 自动调整所有滑块和曲线
- **AI 风格建议** — 上传照片，Qwen-VL 分析内容，生成 4 种风格方案供选择
- **AI 图像生成** — 输入文字描述，万象 2.7 直接重绘照片

### 参考图工作流
- **风格提取** — 上传任意参考图，AI 提取其色调、对比度、分色风格，转化为可复现的参数集
- **AI 比对调整** — 应用参考参数后，再把效果图和参考图同时发给 AI，让它找出差距、二次修正，**迭代逼近目标风格**
- **预设库** — 将满意的风格参数一键保存，随时覆盖或叠加应用到新照片

### 人像 & 背景
- **磨皮** — 双边滤波皮肤平滑，可调节强度
- **提亮肤色** — HSV 色域精准提亮，不影响背景
- **背景处理** — 高斯虚化或一键去除背景（需安装 `rembg`）

---

## 快速开始

```bash
# 1. 克隆项目
git clone <repo-url>
cd agent

# 2. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

# 3. 安装依赖
pip install -r requirements.txt

# 可选：背景去除
pip install rembg

# 4. 配置环境变量
copy .env.example .env        # Windows
cp .env.example .env          # macOS / Linux
# 填入 DASHSCOPE_API_KEY

# 5. 启动
uvicorn app.main:app --reload --port 8001
# 访问 http://localhost:8001
```

---

## 环境变量

```ini
DASHSCOPE_API_KEY=your_key_here   # 必填，DashScope API Key

USE_BASE64=true                   # 可选：以 base64 而非 file:// 发送图片
ANALYZE_MODEL=qwen3.6-plus        # 视觉模型，用于照片分析 / 参考图提取 / AI 比对
SUGGEST_MODEL=qwen-plus           # 文本模型，用于自然语言解读参数
```

---

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/upload` | 上传图片 |
| `POST` | `/api/analyze` | 视觉模型分析 → 4 种风格建议 |
| `POST` | `/api/edit/manual` | 应用滑块 + 曲线参数 → 输出图片 |
| `POST` | `/api/edit/suggest` | 自然语言 → 参数值 + 曲线控制点 |
| `POST` | `/api/edit/ai` | 文字描述 → AI 重绘图片 |
| `POST` | `/api/analyze-reference` | 参考图 → 风格参数提取 |
| `POST` | `/api/compare-style` | 效果图 + 参考图 → AI 差距比对 + 修正参数 |
| `GET/POST/PUT/DELETE` | `/api/presets` | 预设库 CRUD |
| `GET/POST/PUT/DELETE` | `/api/prompts` | 提示词库 CRUD |

---

## 项目结构

```
app/
├── main.py                   FastAPI 应用入口，静态文件挂载
├── api/routes.py             全部 HTTP 端点
├── core/
│   ├── image_processor.py    Pillow 基础 + 高级调整（色调范围、暗角、颗粒等）
│   ├── portrait.py           OpenCV 磨皮与肤色提亮
│   ├── background.py         背景虚化 / rembg 去除
│   ├── curve_processor.py    PCHIP Fritsch-Carlson → 256 级 LUT
│   ├── image_gen.py          DashScope 万象图像生成
│   ├── image_analyzer.py     DashScope Qwen-VL 照片风格分析
│   ├── param_advisor.py      自然语言 → 参数建议
│   ├── reference_analyzer.py 参考图风格提取 + 双图 AI 比对
│   ├── preset_store.py       预设库（JSON 文件存储）
│   └── prompt_store.py       提示词库（JSON 文件存储）
├── types/models.py           Pydantic 数据模型
└── static/
    ├── index.html
    ├── style.css             Anti-polish 设计系统（手写体 + 牛皮纸色）
    ├── app.js                前端逻辑
    └── curve_editor.js       Canvas PCHIP 曲线编辑器
data/
├── presets.json              预设库（自动创建）
└── prompts.json              提示词库（自动创建）
uploads/                      原始上传图片
outputs/                      处理结果图片
```

---

## 注意事项

- **Windows 下 DashScope file URI**：SDK 要求 `file://E:/path`（双斜杠），Python `Path.as_uri()` 会生成三斜杠导致报错，`_file_uri()` 函数处理了这个差异。
- **Python 版本**：使用 `Optional[X]` 类型注解，兼容 Python 3.8 / 3.9。
- **曲线一致性**：后端 `curve_processor.py` 与前端 `curve_editor.js` 实现了相同的 Fritsch-Carlson PCHIP 单调三次样条算法，保证编辑器预览与实际渲染结果一致。
- **rembg 可选**：未安装时背景去除端点会返回友好错误，不影响其他功能。
