# 修图 Agent + 审查 Agent 设计文档

日期：2026-05-20

## 背景

现有 `ai_editor.py` 是单次 Claude 调用：分析图片 → 返回参数 → 执行。效果无法自我迭代优化。
目标是引入 EditingAgent + ReviewAgent 的协作循环，使修图结果能自动迭代至满意。

---

## 整体架构

```
用户请求 (图片 + 指令 + [参考图])
    │
    ▼
EditingAgent  ←──────────────────────────────┐
  分析图片 + 指令 + [参考图] + [上轮反馈]       │
  → 输出编辑参数                               │
    │                                         │
    ▼                                         │
执行图像处理 (Pillow/OpenCV)                   │
    │                                         │
    ▼                                    feedback
ReviewAgent                                   │
  对比原图 vs 结果图 + 指令 + [参考图]          │
  → 评分 + 反馈 + 是否满意？                   │
    │                                         │
    ├─ 满意 (score >= 8) 或已达上限 (5轮) ──→ 返回最佳结果
    │
    └─ 不满意 ────────────────────────────────┘
```

---

## 新增文件

| 文件 | 职责 |
|------|------|
| `app/core/editing_agent.py` | 修图 agent，含反馈注入逻辑 |
| `app/core/review_agent.py` | 审查 agent，三维评分 |
| `app/core/agent_loop.py` | 循环编排，追踪最高分，保存版本 |
| `app/api/routes_agent.py` | 新增 API 端点 `/agent/edit` |

现有 `ai_editor.py` 保留，作为无 agent 模式的快速通道。

---

## ReviewAgent 评分设计

### 输出格式

```json
{
  "scores": {
    "visual_quality": 7.5,
    "instruction_match": 6.0,
    "reference_match": 8.0
  },
  "overall": 7.1,
  "is_satisfied": false,
  "suggestions": {
    "visual_quality": "高光略过曝，建议 brightness 降至 1.1",
    "instruction_match": "用户要求暖色调，color_temp 应提升至 40+",
    "reference_match": "参考图饱和度更高，saturation 建议从 1.1 升至 1.3"
  }
}
```

### 评分维度与权重

| 场景 | visual_quality | instruction_match | reference_match |
|------|---------------|-------------------|-----------------|
| 无参考图 | 35% | 65% | — |
| 有参考图 | 25% | 40% | 35% |

### 终止条件

- `overall >= 8.0` → 标记 `is_satisfied: true`，停止循环
- 已满 5 轮 → 强制停止，返回历史最高分对应的版本

---

## EditingAgent 反馈注入设计

**第 1 轮**：原始图片 + 用户指令 → 输出参数（同现有逻辑）

**第 2 轮起**，在 system prompt 中额外注入：

```
上一轮参数：{ brightness: 1.3, color_temp: 20, ... }
审查反馈：
  - 视觉质量(6.5): 高光略过曝，brightness 降至 1.1
  - 指令匹配(5.0): 用户要求暖色调，color_temp 应提升至 40+
请在上一轮基础上针对以上问题调整参数，不要大幅改动已经合格的维度。
```

约束：只改有问题的维度，避免"修好了 A 又破坏了 B"的抖动。

---

## 版本保存结构

```
uploads/
  sessions/
    {session_id}/
      original.jpg
      ref.jpg               # 参考图（如有）
      v1_score6.2.jpg
      v2_score7.8.jpg
      v3_score8.4.jpg       # 最终最佳
      history.json
```

### history.json 格式

```json
{
  "session_id": "abc123",
  "instruction": "让照片更暖更通透",
  "created_at": "2026-05-20T10:00:00",
  "iterations": [
    {
      "round": 1,
      "image": "v1_score6.2.jpg",
      "params": { "brightness": 1.3, "color_temp": 20 },
      "scores": { "visual_quality": 6.5, "instruction_match": 5.8, "overall": 6.2 },
      "suggestions": { "visual_quality": "...", "instruction_match": "..." }
    }
  ],
  "best_round": 3
}
```

---

## 前端历史查看功能

- 时间轴展示所有历史 session
- 点击 session → 展开各轮缩略图 + 评分条
- 任意两版本左右对比视图
- 一键"应用此版本"

---

## API 设计

### POST `/agent/edit`

**Request:**
```json
{
  "instruction": "让照片更暖更通透",
  "image": "<base64>",
  "reference_image": "<base64 | null>"
}
```

**Response (streaming SSE):**
```
data: {"type": "progress", "round": 1, "status": "editing"}
data: {"type": "progress", "round": 1, "status": "reviewing", "score": 6.2}
data: {"type": "progress", "round": 2, "status": "editing"}
data: {"type": "progress", "round": 2, "status": "reviewing", "score": 7.8}
data: {"type": "done", "session_id": "abc123", "best_round": 3, "final_score": 8.4, "image": "<base64>"}
```

### GET `/agent/sessions`

返回所有 session 列表（用于历史查看）

### GET `/agent/sessions/{session_id}`

返回指定 session 的 history.json 完整数据
