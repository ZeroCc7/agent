"""LLM-based parameter advisor for manual adjustments.

Translates natural language instructions into concrete slider values
without any image generation. Uses a fast text model (qwen-plus).

Understands relative instructions:
  "再亮一点" → increases brightness from current value
  "磨皮" → enables smooth_skin
"""

import json
import os
import re

import dashscope
from dashscope import Generation

dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

_SYSTEM = """\
你是一位专业修图助手，将自然语言描述转换为图片调整参数，包含滑块值和色彩曲线控制点。

━━ 滑块参数（当前值已在消息中给出）━━
  brightness    亮度，-60~60，0=原图，正数更亮
  contrast      对比度，-60~60，正数更强
  saturation    饱和度，-60~60，正数更鲜艳，负数去色
  sharpness     锐度，-60~60，正数更锐利
  color_temp    色温，-100~100，负数偏冷蓝，正数偏暖黄
  smooth_skin   磨皮开关，true/false
  smooth_level  磨皮程度，0~100（整数）
  brighten_skin 提亮肤色开关，true/false
  background_action 背景处理，"none"/"blur"/"remove"

━━ 色彩曲线（curve_params）━━
曲线控制点为 [输入值, 输出值] 的数组，取值范围 0-255（整数）。
必须包含 [0,Y0] 和 [255,Y255] 两个端点，中间可添加 1-4 个控制点。
  rgb  主曲线，影响整体明暗和对比
  r    红色通道（增大=偏红/暖，减小=偏青）
  g    绿色通道
  b    蓝色通道（增大=偏蓝/冷，减小=偏黄）

常用曲线模式参考：
  自然S型对比度：[[0,0],[64,45],[192,210],[255,255]]
  提亮暗部/日系淡：[[0,25],[128,148],[255,245]]
  胶片感（压高光+提暗部）：[[0,20],[200,220],[255,235]]
  暖色调（主曲线微调+R上移+B下移）：
    rgb=[[0,0],[255,255]], r=[[0,5],[255,255]], b=[[0,0],[255,248]]
  冷蓝色调：rgb=[[0,0],[255,255]], r=[[0,0],[255,248]], b=[[0,8],[255,255]]
  增加对比+去灰（黑位下移）：[[0,0],[64,42],[192,213],[255,255]]

━━ 规则 ━━
1. 只修改用户指令涉及的参数，其余保持当前值原样输出
2. 理解相对指令："再亮一点"→ 在当前值基础上+15左右，"稍微"表示幅度小
3. 效果自然，滑块幅度建议 10~25；曲线控制点偏移建议不超过 30
4. 如果指令涉及色调/风格（如日系、胶片、暖调、冷调、高对比等），必须同时输出 curve_params
5. 纯亮度/磨皮/背景等简单指令可以省略 curve_params（保持不变）
6. 只返回 JSON，不含任何其他内容，格式如下：
{
  "brightness": 整数,
  "contrast": 整数,
  "saturation": 整数,
  "sharpness": 整数,
  "color_temp": 整数,
  "smooth_skin": bool,
  "smooth_level": 整数,
  "brighten_skin": bool,
  "background_action": "none"|"blur"|"remove",
  "curve_params": {
    "rgb": [[整数,整数], ...],
    "r":   [[整数,整数], ...],
    "g":   [[整数,整数], ...],
    "b":   [[整数,整数], ...]
  },
  "explanation": "一句话中文说明做了哪些调整"
}
curve_params 可以省略（表示曲线不变）。\
"""


def _parse_json(text: str) -> dict:
    text = re.sub(r"```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```\s*", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(match.group() if match else text)


def suggest_params(instruction: str, current: dict) -> dict:
    """
    Return updated parameter dict based on a natural language instruction.

    Args:
        instruction: User's description, e.g. "让照片更通透，色温偏暖"
        current: Current slider values (int, -60..60 for basic params)

    Returns:
        Dict with all parameter keys + "explanation" string.
    """
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("未配置 DASHSCOPE_API_KEY")

    model = os.getenv("SUGGEST_MODEL", "qwen-plus")
    user_msg = (
        f"当前参数：{json.dumps(current, ensure_ascii=False)}\n\n"
        f"用户指令：{instruction}"
    )

    rsp = Generation.call(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        result_format="message",
        api_key=api_key,
    )

    if rsp.status_code != 200:
        raise RuntimeError(f"LLM 调用失败 [{rsp.code}]: {rsp.message}")

    return _parse_json(rsp.output.choices[0].message.content)
