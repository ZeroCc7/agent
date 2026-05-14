import base64
import io
import json
import os

import anthropic
from PIL import Image

from app.types.models import BackgroundParams, EditParams, PortraitParams

_SYSTEM = """You are an expert photo retouching assistant for everyday life photos.
Analyze the image and the user's instruction, then return ONLY a valid JSON object.
Keep edits subtle and natural — never exaggerated.

Return this exact JSON (all fields required):
{
  "brightness": <float 0.5-2.0, 1.0=unchanged>,
  "contrast": <float 0.5-2.0, 1.0=unchanged>,
  "saturation": <float 0.5-2.0, 1.0=unchanged>,
  "sharpness": <float 0.5-2.0, 1.0=unchanged>,
  "color_temp": <int -100 to 100, 0=neutral, positive=warm, negative=cool>,
  "smooth_skin": <bool>,
  "smooth_level": <float 0.0-1.0>,
  "brighten_skin": <bool>,
  "brighten_level": <float 0.0-1.0>,
  "background_action": <"none"|"blur"|"remove">,
  "blur_radius": <int 5-30>,
  "explanation": "<one sentence in Chinese explaining what you changed>"
}"""


def analyze_and_plan(
    img: Image.Image, instruction: str
) -> tuple[EditParams, PortraitParams, BackgroundParams, str]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("请在 .env 文件中设置 ANTHROPIC_API_KEY")

    client = anthropic.Anthropic(api_key=api_key)

    buf = io.BytesIO()
    thumb = img.convert("RGB")
    thumb.thumbnail((1024, 1024), Image.LANCZOS)
    thumb.save(buf, format="JPEG", quality=85)
    image_b64 = base64.standard_b64encode(buf.getvalue()).decode()

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": instruction},
                ],
            }
        ],
    )

    text = response.content[0].text.strip()
    # Strip markdown code fences if present
    if "```" in text:
        parts = text.split("```")
        text = parts[1].lstrip("json").strip() if len(parts) > 1 else text

    data = json.loads(text)

    edit_params = EditParams(
        brightness=data.get("brightness", 1.0),
        contrast=data.get("contrast", 1.0),
        saturation=data.get("saturation", 1.0),
        sharpness=data.get("sharpness", 1.0),
        color_temp=data.get("color_temp", 0),
    )
    portrait_params = PortraitParams(
        smooth_skin=data.get("smooth_skin", False),
        smooth_level=data.get("smooth_level", 0.3),
        brighten_skin=data.get("brighten_skin", False),
        brighten_level=data.get("brighten_level", 0.2),
    )
    background_params = BackgroundParams(
        action=data.get("background_action", "none"),
        blur_radius=data.get("blur_radius", 15),
    )
    explanation = data.get("explanation", "")

    return edit_params, portrait_params, background_params, explanation
