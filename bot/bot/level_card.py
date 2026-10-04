"""Local, deterministic level-up cards; no AI calls or member data uploads."""
from io import BytesIO
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont, ImageOps

ASSETS = Path(__file__).parent / "assets"


def font(size):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def fit(draw, value, width, size):
    while size > 14 and draw.textlength(value, font=font(size)) > width:
        size -= 1
    return font(size)


def render_level_card(avatar_bytes: bytes | None, display_name: str, level: int, role_names: list[str]) -> bytes:
    image = Image.open(ASSETS / "level-background.png").convert("RGBA").resize((1200, 400), Image.Resampling.LANCZOS)
    shade = Image.new("RGBA", image.size, (12, 8, 30, 75))
    image = Image.alpha_composite(image, shade)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((2, 2, 1197, 397), radius=28, outline="#7866cb", width=2)
    try:
        avatar = ImageOps.fit(Image.open(BytesIO(avatar_bytes)).convert("RGB"), (286, 286), method=Image.Resampling.LANCZOS)
    except Exception:
        avatar = Image.new("RGB", (286, 286), "#382262")
        a = ImageDraw.Draw(avatar)
        a.text((143, 143), (display_name or "?")[:1].upper(), font=font(120), fill="white", anchor="mm")
    mask = Image.new("L", (286, 286))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 285, 285), radius=20, fill=255)
    image.paste(avatar, (32, 35), mask)
    draw.rounded_rectangle((30, 33, 320, 323), radius=22, outline="#74e6ef", width=3)
    name = display_name[:45]
    draw.text((175, 354), name, font=fit(draw, name, 290, 22), fill="white", anchor="mm")
    center = 535 if role_names else 750
    draw.text((center, 102), "LEVEL UP!", font=font(47 if role_names else 60), fill="white", anchor="mm", stroke_width=1)
    draw.text((center, 236), str(level), font=fit(draw, str(level), 320 if role_names else 620, 170), fill="white", anchor="mm")
    if role_names:
        draw.line((745, 50, 745, 340), fill="#68dce5", width=2)
        cx, cy = 960, 96
        draw.ellipse((cx-42, cy-42, cx+42, cy+42), fill="#e9b747", outline="#ffeab0", width=4)
        points = [(cx+math.cos(-math.pi/2+i*math.pi/5)*(26 if i%2==0 else 12), cy+math.sin(-math.pi/2+i*math.pi/5)*(26 if i%2==0 else 12)) for i in range(10)]
        draw.polygon(points, fill="#6e4013")
        draw.text((960, 167), "YOUR NEW ROLE" if len(role_names)==1 else "YOUR NEW ROLES", font=font(24), fill="#eee3ff", anchor="mm")
        draw.rounded_rectangle((775, 200, 1148, 320), radius=18, fill="#301052", outline="#c7a6ff", width=3)
        # Fit long names and multiple rewards without overflowing the badge.
        text = " · ".join(role_names)
        lines = [text]
        if draw.textlength(text, font=font(30)) > 335:
            words = text.split()
            lines = [""]
            for word in words:
                candidate = (lines[-1]+" "+word).strip()
                if lines[-1] and draw.textlength(candidate,font=font(25))>335:
                    lines.append(word)
                else:
                    lines[-1]=candidate
            if len(lines)>3:
                lines=lines[:2]+[lines[2][:24]+"…"]
        for i,line in enumerate(lines):
            draw.text((960,260+(i-(len(lines)-1)/2)*30),line,font=fit(draw,line,335,34 if len(lines)==1 else 25),fill="white",anchor="mm")
    draw.text((1155, 375), "GUILDCONSOLE", font=font(12), fill="#bdb4d1", anchor="rm")
    output=BytesIO()
    image.convert("RGB").save(output,format="PNG",optimize=True)
    return output.getvalue()
