# 参考图风格提取 + 参数预设库 设计文档

**日期**：2026-05-15  
**状态**：待实现

---

## 背景与目标

用户希望上传一张参考图，让 AI 分析其视觉风格并提取出可复用的编辑参数，同时支持一键保存为命名预设（类似滤镜）。功能分两条并行线路：

1. **编辑器内**：上传参考图 → AI 提取参数 / 生成风格图 → 保存为预设
2. **预设库**：独立管理所有参数预设，支持从参考图创建、手动创建、应用、删除

---

## 架构

### 新增后端模块

| 模块 | 职责 |
|------|------|
| `app/core/reference_analyzer.py` | 用 DashScope Qwen-VL 分析参考图，输出完整参数 JSON |
| `app/core/preset_store.py` | 参数预设的 JSON CRUD，模式与现有 `prompt_store.py` 一致 |

### 新增 API 路由（挂在现有 `routes.py`）

```
POST   /api/analyze-reference     上传参考图 → 返回提取的参数
GET    /api/presets               列出所有参数预设（支持 search/category 过滤）
POST   /api/presets               创建预设
PUT    /api/presets/{id}          更新预设
DELETE /api/presets/{id}          删除预设
```

### 数据流

```
用户上传参考图 → POST /api/upload（复用现有）
              → POST /api/analyze-reference（Qwen-VL 分析）
              → 返回 params + curve_params + style_name + explanation
              → [应用参数] 填入当前编辑器滑块
              → [AI 风格生成] 将 explanation 传给现有 /api/edit/ai（wan2.7-image-pro）
              → [保存预设] POST /api/presets
```

### `app/main.py` 补充

```python
Path("data").mkdir(exist_ok=True)  # 预设存储目录
```

---

## 数据模型

### 扩展 `CurrentParams`（`app/types/models.py`）

在现有字段基础上新增：

```python
# 高光/阴影精细控制
highlights: int = Field(0, ge=-100, le=100)
shadows: int = Field(0, ge=-100, le=100)
whites: int = Field(0, ge=-100, le=100)
blacks: int = Field(0, ge=-100, le=100)

# 质感
vibrance: int = Field(0, ge=-60, le=60)    # 皮肤保护型饱和度
clarity: int = Field(0, ge=-60, le=60)     # 中间调对比度

# 风格化
vignette: int = Field(0, ge=-100, le=100)  # 暗角，负=压暗边缘
grain: int = Field(0, ge=0, le=100)        # 胶片颗粒感

# 色调分离（Split Toning）
shadow_tint: int = Field(0, ge=0, le=360)
shadow_tint_strength: int = Field(0, ge=0, le=100)
highlight_tint: int = Field(0, ge=0, le=360)
highlight_tint_strength: int = Field(0, ge=0, le=100)
```

### 新增 Pydantic 模型

```python
# 参考图分析
class ReferenceAnalyzeRequest(BaseModel):
    filename: str  # 已上传的参考图文件名

class ReferenceAnalyzeResponse(BaseModel):
    params: CurrentParams
    curve_params: CurveParams
    style_name: str      # 建议的预设名，如"日系清透"
    explanation: str     # 一句话描述参考图风格特征

# 参数预设
class Preset(BaseModel):
    id: str
    name: str
    category: str = ""
    tags: List[str] = []
    params: CurrentParams
    curve_params: CurveParams
    created_at: str
    updated_at: str

class PresetCreate(BaseModel):
    name: str
    params: CurrentParams
    curve_params: CurveParams
    category: str = ""
    tags: List[str] = []

class PresetUpdate(BaseModel):
    name: Optional[str] = None
    params: Optional[CurrentParams] = None
    curve_params: Optional[CurveParams] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
```

### 预设存储格式

文件：`data/presets.json`，结构与现有 `data/prompts.json` 一致，由 `preset_store.py` 管理，文件 I/O 加 `threading.Lock`。

---

## 后端核心逻辑

### `reference_analyzer.py`

**System Prompt：**

```
你是一位有十年经验的专业摄影师和调色师，精通 Lightroom、Photoshop 等修图工具。
你的任务是：分析一张参考图的视觉风格，将其转化为可复现该风格的具体参数值。
这些参数将被应用到另一张照片上，目标是让那张照片呈现出与参考图相近的视觉氛围。
你必须做到：参数值具体、精准，能真正体现参考图的色调特征，不说套话，不给无意义的中性默认值。
```

**User Prompt：**

```
仔细观察这张参考图，从以下维度进行量化分析：

【曝光与亮度】
- 整体曝光水平：偏亮（日系清透）、偏暗（电影感）还是正常曝光？
- 暗部处理：阴影是否被提亮（灰雾/胶片感），还是压暗（强对比/黑位下沉）？
- 高光处理：高光是否有压制（保留细节）或轻微溢出倾向？

【对比度】
- 整体对比强弱：高对比（明暗分明）、中等，还是低对比（柔和/平淡）？
- 是否存在局部拉伸（暗部/亮部分别处理）？

【色彩】
- 饱和度：鲜艳（高饱和）、自然，还是偏灰/褪色（低饱和）？
- 色温：偏暖（金黄/琥珀）还是偏冷（蓝调/青冷）？
- 色偏：是否有明显色偏（偏绿、偏品红、偏青等）？
- 颜色分离：高光和阴影是否有不同色彩倾向（如高光暖+阴影冷的电影分色）？

【锐度与质感】
- 画面是锐利清晰，还是柔和/胶片颗粒感的朦胧？

基于以上分析，输出下面的 JSON（只输出 JSON，不含任何其他文字）：

━━ 参数说明 ━━
  brightness    整体亮度，-60~60，0=原图，正=更亮，负=更暗
  contrast      对比度，-60~60，正=更强，负=更柔
  highlights    高光控制，-100~100，负=压制高光，正=拉亮高光
  shadows       阴影控制，-100~100，正=提亮暗部，负=压暗
  whites        白点，-100~100，控制极亮区域
  blacks        黑点，-100~100，控制极暗区域
  saturation    饱和度，-60~60，正=鲜艳，负=去色/褪色
  vibrance      自然饱和度，-60~60，优先提升低饱和区域，保护肤色
  clarity       清晰度，-60~60，正=通透质感，负=柔焦奶油感
  sharpness     锐度，-60~60，正=更锐，负=更柔
  color_temp    色温，-100~100，负=冷蓝，正=暖黄
  vignette      暗角，-100~100，负=边缘压暗（电影感），正=边缘提亮
  grain         颗粒感，0~100，模拟胶片颗粒
  shadow_tint           阴影色相，0~360
  shadow_tint_strength  阴影色调强度，0~100
  highlight_tint        高光色相，0~360
  highlight_tint_strength 高光色调强度，0~100
  smooth_skin   磨皮开关，true/false（参考图有人像且皮肤明显柔化时开启）
  smooth_level  磨皮程度，0~100
  brighten_skin 提亮肤色，true/false

━━ 色彩曲线（curve_params）━━
控制点格式：[输入值, 输出值]，范围 0-255（整数）
必须包含 [0,Y0] 和 [255,Y255] 两个端点，中间可加 1-4 个控制点
  rgb   主曲线，控制整体明暗与对比
  r     红色通道（增大=偏红/暖，减小=偏青）
  g     绿色通道（增大=偏绿，减小=偏品红）
  b     蓝色通道（增大=偏蓝/冷，减小=偏黄）

━━ 规则 ━━
1. 参数必须真实反映图片，不要给无意义的中性值（如全部填 0）
2. 曲线是风格的核心，必须认真分析并给出有差异的控制点
3. brightness/highlights/shadows 等滑块和曲线可以同时使用，共同实现效果
4. style_name 要简洁有识别度（2-5字），explanation 要说清"为什么这么调"（30-60字）
5. 若图片色彩风格不明显，曲线可用直线，但滑块仍需如实填写

输出格式：
{
  "brightness": 整数,
  "contrast": 整数,
  "highlights": 整数,
  "shadows": 整数,
  "whites": 整数,
  "blacks": 整数,
  "saturation": 整数,
  "vibrance": 整数,
  "clarity": 整数,
  "sharpness": 整数,
  "color_temp": 整数,
  "vignette": 整数,
  "grain": 整数,
  "shadow_tint": 整数,
  "shadow_tint_strength": 整数,
  "highlight_tint": 整数,
  "highlight_tint_strength": 整数,
  "smooth_skin": bool,
  "smooth_level": 整数,
  "brighten_skin": bool,
  "curve_params": {
    "rgb": [[整数,整数], ...],
    "r":   [[整数,整数], ...],
    "g":   [[整数,整数], ...],
    "b":   [[整数,整数], ...]
  },
  "style_name": "字符串",
  "explanation": "字符串"
}
```

**解析与降级策略：**

- 复用 `image_analyzer.py` 的 `_parse_json()` + `_extract_text()` 模式
- 数值字段缺失 → 填 0（中性值）
- `curve_params` 缺失 → 填直线 `[[0,0],[255,255]]`
- 数值 clamp：超出范围截断而非报错
- 若模型输出无法解析为 JSON → 返回全中性参数，`explanation` 填原始文本

### `preset_store.py`

```python
def list_presets(search: str = "", category: str = "") -> List[dict]
    # 按 name/tags 模糊匹配 + category 过滤，按 updated_at 倒序

def create_preset(name, params, curve_params, category, tags) -> dict
    # 生成 uuid id + ISO 时间戳

def update_preset(id, **kwargs) -> Optional[dict]
    # 只更新传入字段，更新 updated_at

def delete_preset(id) -> bool

def get_preset(id) -> Optional[dict]
```

文件 I/O 加 `threading.Lock`，与 `prompt_store.py` 一致。

### 路由层

| 路由 | 入参 | 成功响应 | 错误 |
|------|------|----------|------|
| `POST /api/analyze-reference` | `ReferenceAnalyzeRequest` | `ReferenceAnalyzeResponse` | 404 文件不存在 / 500 分析失败 |
| `GET /api/presets` | query: `search`, `category` | `{presets, categories}` | — |
| `POST /api/presets` | `PresetCreate` | `Preset` | 400 名称为空 |
| `PUT /api/presets/{id}` | `PresetUpdate` | `Preset` | 404 |
| `DELETE /api/presets/{id}` | — | `{"ok": true}` | 404 |

---

## 前端（暂缓）

- 编辑器内"参考图"折叠面板
- 独立"预设库"标签页
- 应用预设时弹窗选择覆盖（直接替换所有参数）或叠加（数值取平均，曲线直接替换，布尔值取 preset OR current）

---

## 图像处理扩展（`image_processor.py`）

新参数需新增对应 PIL 实现：

| 参数 | 实现方式 |
|------|----------|
| highlights / shadows | 分区曲线映射（亮部/暗部单独调整） |
| whites / blacks | 白点/黑点偏移 |
| vibrance | HSV 空间对低饱和像素优先提升 |
| clarity | 非锐化掩模（USM）作用于中间调 |
| vignette | 径向渐变蒙版叠加 |
| grain | 高斯噪点层叠加 |
| shadow_tint / highlight_tint | HSV 空间按亮度分区着色 |

---

## 文件变更清单

| 文件 | 变更类型 |
|------|----------|
| `app/types/models.py` | 扩展 `CurrentParams`，新增 `ReferenceAnalyzeRequest/Response`、`Preset`、`PresetCreate`、`PresetUpdate` |
| `app/core/reference_analyzer.py` | 新建 |
| `app/core/preset_store.py` | 新建（复用 `prompt_store.py` 结构） |
| `app/core/image_processor.py` | 新增 highlights/shadows/vibrance/clarity/vignette/grain/split toning 实现 |
| `app/api/routes.py` | 新增 `/analyze-reference` 和 `/presets` 路由组 |
| `app/main.py` | 新增 `Path("data").mkdir(exist_ok=True)` |
| `app/static/app.js` | 新增参考图面板 + 预设库 UI（前端阶段实现） |
| `app/static/style.css` | 配套样式（前端阶段实现） |
