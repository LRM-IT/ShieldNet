from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any
from uuid import UUID

import qrcode
from PIL import Image, ImageColor, ImageDraw, ImageFont

from app.models.media_assets import MediaAsset
from app.models.template_bank import MediaTemplate, TemplateBankSettings


def _color(value: str | None, fallback: str = "#ffffff") -> tuple[int, int, int, int]:
    try:
        rgb = ImageColor.getcolor(value or fallback, "RGBA")
        return rgb
    except Exception:
        return ImageColor.getcolor(fallback, "RGBA")


def _font(size: int, weight: str | None = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    bold = str(weight or "400") in {"600", "700", "800", "900", "bold", "black"}
    candidates = [
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, max(8, int(size)))
        except Exception:
            pass
    return ImageFont.load_default()


def _resolve(value: str | None, data: dict[str, Any]) -> str:
    if not value:
        return ""
    result = str(value)
    for key, replacement in data.items():
        token = "{{" + str(key).upper() + "}}"
        result = result.replace(token, "" if replacement is None else str(replacement))
    return result


def _fit_text(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int],
              font_size: int, weight: str | None, min_size: int = 10):
    x1, y1, x2, y2 = box
    size = max(min_size, int(font_size))
    while size >= min_size:
        font = _font(size, weight)
        bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=max(2, size // 6))
        if bbox[2] - bbox[0] <= (x2 - x1) and bbox[3] - bbox[1] <= (y2 - y1):
            return font
        size -= 2
    return _font(min_size, weight)


class TemplateRenderer:
    def __init__(self, session):
        self.session = session

    async def render(self, template: MediaTemplate, data: dict[str, Any]) -> io.BytesIO:
        manifest = template.manifest or {}
        canvas = manifest.get("canvas") or {}
        width = int(canvas.get("width") or template.canvas_width or 1536)
        height = int(canvas.get("height") or template.canvas_height or 2048)

        image = Image.new("RGBA", (width, height), (6, 14, 22, 255))

        background_path = Path(template.background_path)
        if background_path.is_file():
            with Image.open(background_path) as background:
                background = background.convert("RGBA")
                background = self._cover(background, width, height)
                image.alpha_composite(background)

        draw = ImageDraw.Draw(image)
        layers = sorted(
            [layer for layer in manifest.get("layers", []) if layer.get("visible", True)],
            key=lambda layer: int(layer.get("zIndex", 0)),
        )

        for layer in layers:
            await self._draw_layer(image, draw, layer, data)

        output = io.BytesIO()
        image.convert("RGB").save(output, format="PNG", optimize=True)
        output.seek(0)
        return output

    async def _draw_layer(self, image: Image.Image, draw: ImageDraw.ImageDraw,
                          layer: dict[str, Any], data: dict[str, Any]) -> None:
        layer_type = layer.get("type")
        x = int(layer.get("x", 0))
        y = int(layer.get("y", 0))
        width = max(1, int(layer.get("width", 100)))
        height = max(1, int(layer.get("height", 100)))
        opacity = max(0.0, min(1.0, float(layer.get("opacity", 1))))
        rotation = float(layer.get("rotation", 0))

        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        if layer_type == "text":
            variable = layer.get("variable")
            text = _resolve(variable or layer.get("text") or "", data)
            font = _fit_text(
                overlay_draw, text, (0, 0, width, height),
                int(layer.get("fontSize", 48)), layer.get("fontWeight"),
            )
            align = layer.get("align", "left")
            anchor_x = 0 if align == "left" else width // 2 if align == "center" else width
            overlay_draw.multiline_text(
                (anchor_x, 0), text, font=font, fill=_color(layer.get("color")),
                align=align, anchor="la" if align == "left" else "ma" if align == "center" else "ra",
                spacing=max(2, int(layer.get("fontSize", 48)) // 6),
            )

        elif layer_type == "rectangle":
            fill = _color(layer.get("background"), "#15313c")
            border = _color(layer.get("borderColor"), "#35e2b2")
            border_width = max(0, int(layer.get("borderWidth", 0)))
            radius = max(0, int(layer.get("borderRadius", 0)))
            overlay_draw.rounded_rectangle(
                (0, 0, width - 1, height - 1),
                radius=radius, fill=fill,
                outline=border if border_width else None,
                width=border_width,
            )

        elif layer_type == "progress":
            raw = data.get("OPTION_PERCENTAGE", data.get("PROGRESS", 0))
            try:
                pct = max(0.0, min(100.0, float(str(raw).replace("%", ""))))
            except Exception:
                pct = 0.0
            radius = max(1, height // 2)
            overlay_draw.rounded_rectangle(
                (0, 0, width - 1, height - 1),
                radius=radius, fill=_color(layer.get("background"), "#17323c"),
            )
            filled = int(width * pct / 100)
            if filled > 0:
                overlay_draw.rounded_rectangle(
                    (0, 0, max(1, filled), height - 1),
                    radius=radius, fill=_color(layer.get("color"), "#35e2b2"),
                )

        elif layer_type == "qr":
            settings = await self.session.get(TemplateBankSettings, 1)
            default_url = settings.default_qr_url if settings else "https://discord.lrm-it.com"
            qr_value = _resolve(layer.get("variable") or "{{QR_URL}}", data) or default_url
            qr = qrcode.QRCode(version=None, box_size=8, border=1)
            qr.add_data(qr_value)
            qr.make(fit=True)
            qr_image = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
            qr_image = qr_image.resize((width, height), Image.Resampling.LANCZOS)
            overlay.alpha_composite(qr_image)

        elif layer_type == "image":
            asset_id = layer.get("assetId")
            if asset_id:
                try:
                    asset = await self.session.get(MediaAsset, UUID(str(asset_id)))
                except Exception:
                    asset = None
                if asset and Path(asset.file_path).is_file():
                    with Image.open(asset.file_path) as asset_image:
                        asset_image = asset_image.convert("RGBA")
                        asset_image = self._contain(asset_image, width, height)
                        overlay.alpha_composite(asset_image)

        if opacity < 1:
            alpha = overlay.getchannel("A").point(lambda value: int(value * opacity))
            overlay.putalpha(alpha)

        if rotation:
            overlay = overlay.rotate(-rotation, expand=True, resample=Image.Resampling.BICUBIC)
            x -= (overlay.width - width) // 2
            y -= (overlay.height - height) // 2

        image.alpha_composite(overlay, (x, y))

    @staticmethod
    def _cover(image: Image.Image, width: int, height: int) -> Image.Image:
        scale = max(width / image.width, height / image.height)
        resized = image.resize(
            (math.ceil(image.width * scale), math.ceil(image.height * scale)),
            Image.Resampling.LANCZOS,
        )
        left = max(0, (resized.width - width) // 2)
        top = max(0, (resized.height - height) // 2)
        return resized.crop((left, top, left + width, top + height))

    @staticmethod
    def _contain(image: Image.Image, width: int, height: int) -> Image.Image:
        scale = min(width / image.width, height / image.height)
        new_width = max(1, int(image.width * scale))
        new_height = max(1, int(image.height * scale))
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        canvas.alpha_composite(
            resized,
            ((width - new_width) // 2, (height - new_height) // 2),
        )
        return canvas
