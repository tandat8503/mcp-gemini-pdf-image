import base64
import io
import json
import os
import warnings
from typing import Any, Dict, List

import requests
from PIL import Image, ImageDraw

from google import genai
from google.genai import types
from fastmcp import FastMCP
from dotenv import load_dotenv
import concurrent.futures as futures

# -----------------------------
# Constants (hard-coded for simplicity)
# -----------------------------
TOOL_TIMEOUT_SECONDS = 6000.0
HTTP_TIMEOUT_SECONDS = 6000.0
MAX_IMAGE_EDGE = 1024
SEGMENT_OUTPUT_DIR = "segmentation_outputs"


# -----------------------------
# Utilities
# -----------------------------

def _ensure_client() -> genai.Client:
    """Create a Google GenAI client using GEMINI_API_KEY from .env file."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. Please set it in your .env file. "
            "Get key at: https://aistudio.google.com/app/apikey"
        )
    return genai.Client(api_key=api_key)


def _image_url_bytes(url: str) -> bytes:
    resp = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.content


def _json_from_markdown_fenced(text: str) -> str:
    # Extract JSON from ```json ... ``` blocks when present.
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "```json":
            inner = "\n".join(lines[i + 1 :])
            return inner.split("```", 1)[0]
    return text


def _json_from_markdown_fenced(text: str) -> str:
    # Extract JSON from ```json ... ``` blocks when present.
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "```json":
            inner = "\n".join(lines[i + 1 :])
            return inner.split("```", 1)[0]
    return text


def _maybe_resize_image_bytes(image_bytes: bytes, mime_type: str, max_edge: int) -> bytes:
    """Downscale image so the longest edge <= max_edge. Returns possibly re-encoded bytes.

    If decoding fails, returns original bytes.
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as im:
            im = im.convert("RGBA") if im.mode in ("P", "LA") else im  # normalize paletted
            width, height = im.size
            if max(width, height) <= max_edge:
                return image_bytes
            im.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            format_from_mime = "JPEG"
            if mime_type.lower() in ("image/png",):
                format_from_mime = "PNG"
            elif mime_type.lower() in ("image/webp",):
                format_from_mime = "WEBP"
            else:
                format_from_mime = "JPEG"
            save_kwargs: Dict[str, Any] = {}
            if format_from_mime == "JPEG":
                im = im.convert("RGB")
                save_kwargs["quality"] = 88
                save_kwargs["optimize"] = True
            im.save(buf, format=format_from_mime, **save_kwargs)
            return buf.getvalue()
    except Exception:
        return image_bytes


def _run_with_timeout(callable_fn, timeout_seconds: float):
    with futures.ThreadPoolExecutor(max_workers=1) as executor:
        fut = executor.submit(callable_fn)
        return fut.result(timeout=timeout_seconds)


# -----------------------------
# MCP App with tools
# -----------------------------

# Load environment variables
load_dotenv()

# Initialize MCP server
app = FastMCP("img-understanding-mcp")


@app.tool()
def caption_url(url: str, mime_type: str = "image/jpeg", prompt: str = "What is this image?") -> str:
    """Caption an image from a URL. Returns plain text caption.

    - url: public image URL
    - mime_type: expected image MIME type
    - prompt: prompt text
    """
    client = _ensure_client()
    image_bytes = _image_url_bytes(url)
    image_bytes = _maybe_resize_image_bytes(image_bytes, mime_type, MAX_IMAGE_EDGE)
    part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    def call():
        return client.models.generate_content(model="gemini-2.5-flash", contents=[prompt, part])
    response = _run_with_timeout(call, TOOL_TIMEOUT_SECONDS)
    return response.text or ""


@app.tool()
def multi_image_prompt_urls(urls: List[str], mimes: List[str] | None = None, prompt: str = "Describe these images.") -> str:
    """Send multiple image URLs with a single prompt in one request.

    - urls: list of public image URLs
    - mimes: optional list of MIME types matching urls (defaults to image/jpeg)
    - prompt: text prompt to append after images
    """
    client = _ensure_client()

    if mimes is None:
        mimes = ["image/jpeg"] * len(urls)
    if len(mimes) != len(urls):
        raise ValueError("Length of mimes must match length of urls")

    parts: List[types.Part] = []
    for url, mt in zip(urls, mimes):
        img_bytes = _maybe_resize_image_bytes(_image_url_bytes(url), mt, MAX_IMAGE_EDGE)
        parts.append(types.Part.from_bytes(data=img_bytes, mime_type=mt))

    contents: List[Any] = [*parts, prompt]

    def call():
        return client.models.generate_content(model="gemini-2.5-flash", contents=contents)

    response = _run_with_timeout(call, TOOL_TIMEOUT_SECONDS)
    return response.text or ""


@app.tool()
def compare_urls(url1: str, url2: str, mime1: str = "image/jpeg", mime2: str = "image/jpeg") -> str:
    """Compare two image URLs and describe differences. Returns plain text description.

    - url1, url2: public image URLs
    - mime1, mime2: MIME types for the images
    """
    client = _ensure_client()
    img1 = _maybe_resize_image_bytes(_image_url_bytes(url1), mime1, MAX_IMAGE_EDGE)
    img2 = _maybe_resize_image_bytes(_image_url_bytes(url2), mime2, MAX_IMAGE_EDGE)

    def call():
        return client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                "What is different between these two images?",
                types.Part.from_bytes(data=img1, mime_type=mime1),
                types.Part.from_bytes(data=img2, mime_type=mime2),
            ],
        )
    response = _run_with_timeout(call, TOOL_TIMEOUT_SECONDS)
    return response.text or ""


@app.tool()
def detect_boxes_json_url(url: str, mime_type: str = "image/jpeg", prompt: str = (
    "Detect the all of the prominent items in the image. "
    "The box_2d should be [ymin, xmin, ymax, xmax] normalized to 0-1000."
)) -> dict:
    """Detect prominent items from a URL and return absolute pixel boxes.

    Returns: {"image_width": int, "image_height": int, "boxes": [[x1, y1, x2, y2], ...]}
    """
    client = _ensure_client()
    img_bytes = _maybe_resize_image_bytes(_image_url_bytes(url), mime_type, MAX_IMAGE_EDGE)
    with Image.open(io.BytesIO(img_bytes)) as im:
        width, height = im.size

        config = types.GenerateContentConfig(response_mime_type="application/json")
        def call():
            return client.models.generate_content(model="gemini-2.5-flash", contents=[im, prompt], config=config)
        response = _run_with_timeout(call, TOOL_TIMEOUT_SECONDS)

    raw = json.loads(response.text)
    absolute_boxes: List[List[int]] = []
    for bb in raw:
        y1 = int(bb["box_2d"][0] / 1000 * height)
        x1 = int(bb["box_2d"][1] / 1000 * width)
        y2 = int(bb["box_2d"][2] / 1000 * height)
        x2 = int(bb["box_2d"][3] / 1000 * width)
        absolute_boxes.append([x1, y1, x2, y2])

    return {"image_width": width, "image_height": height, "boxes": absolute_boxes}


@app.tool()
def segment_items_url(url: str, mime_type: str = "image/jpeg", prompt: str = (
    "Give the segmentation masks for the wooden and glass items.\n"
    "Output a JSON list of segmentation masks where each entry contains the 2D "
    "bounding box in the key \"box_2d\", the segmentation mask in key \"mask\", and "
    "the text label in the key \"label\". Use descriptive labels."
)) -> dict:
    """Run segmentation on an image URL; save masks and overlays.

    Returns: {"output_dir": str, "items": [{"label": str, "box": [x1,y1,x2,y2], "mask_file": str, "overlay_file": str}]}
    """
    client = _ensure_client()

    img_bytes = _maybe_resize_image_bytes(_image_url_bytes(url), mime_type, MAX_IMAGE_EDGE)
    im = Image.open(io.BytesIO(img_bytes))
    im.thumbnail([MAX_IMAGE_EDGE, MAX_IMAGE_EDGE], Image.Resampling.LANCZOS)

    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0)
    )

    def call():
        return client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, im],
            config=config,
        )
    response = _run_with_timeout(call, TOOL_TIMEOUT_SECONDS)

    items_json = _json_from_markdown_fenced(response.text)
    items = json.loads(items_json)

    output_dir = SEGMENT_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    results: List[Dict[str, Any]] = []

    for i, item in enumerate(items):
        box = item["box_2d"]
        y0 = int(box[0] / 1000 * im.size[1])
        x0 = int(box[1] / 1000 * im.size[0])
        y1 = int(box[2] / 1000 * im.size[1])
        x1 = int(box[3] / 1000 * im.size[0])

        if y0 >= y1 or x0 >= x1:
            continue

        png_str: str = item["mask"]
        if not png_str.startswith("data:image/png;base64,"):
            continue
        png_str = png_str.removeprefix("data:image/png;base64,")
        mask_data = base64.b64decode(png_str)
        mask_img = Image.open(io.BytesIO(mask_data))
        mask_img = mask_img.resize((x1 - x0, y1 - y0), Image.Resampling.BILINEAR)

        # Prepare overlay
        overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        mask_pixels = mask_img.convert("L")
        mask_px = mask_pixels.load()
        for y in range(y0, y1):
            for x in range(x0, x1):
                if mask_px[x - x0, y - y0] > 128:
                    overlay_draw.point((x, y), fill=(255, 255, 255, 200))

        mask_filename = f"{item['label']}_{i}_mask.png"
        overlay_filename = f"{item['label']}_{i}_overlay.png"

        mask_img.save(os.path.join(output_dir, mask_filename))
        composite = Image.alpha_composite(im.convert("RGBA"), overlay)
        composite.save(os.path.join(output_dir, overlay_filename))

        results.append(
            {
                "label": item.get("label", f"item_{i}"),
                "box": [x0, y0, x1, y1],
                "mask_file": os.path.join(output_dir, mask_filename),
                "overlay_file": os.path.join(output_dir, overlay_filename),
            }
        )

    return {"output_dir": output_dir, "items": results}


if __name__ == "__main__":
    app.run(transport="stdio")


