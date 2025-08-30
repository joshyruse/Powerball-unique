from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Output path
OUT = Path("assets/icon.png")
OUT.parent.mkdir(parents=True, exist_ok=True)

# Canvas
SIZE = 1024  # square icon
BG = (0, 0, 0, 0)  # transparent
img = Image.new("RGBA", (SIZE, SIZE), BG)
draw = ImageDraw.Draw(img)

# Colors
WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
RED = (208, 2, 27, 255)  # Powerball red
OUTLINE = (0, 0, 0, 38)  # subtle outline for white balls

# Layout: 6 balls in a row: P O W E R | BALL
# Choose a diameter/gap that fits nicely within 1024px
D = 150   # diameter of each ball
GAP = 20  # gap between balls
N = 6
row_width = N * D + (N - 1) * GAP
start_x = (SIZE - row_width) // 2
center_y = SIZE // 2

# Try to load a bold, modern system font. Fall back gracefully.
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
]

def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    # Last resort: default bitmap font
    return ImageFont.load_default()

# Helper to center text in a circle bbox

def draw_centered_text(text: str, bbox: tuple[int, int, int, int], color, base_size: int, max_width_pad: int = 12):
    # Reduce font until it fits horizontally within the circle minus padding
    size = base_size
    while size > 8:
        font = load_font(size)
        tb = draw.textbbox((0, 0), text, font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        if tw <= (bbox[2] - bbox[0]) - max_width_pad:
            x = bbox[0] + (bbox[2] - bbox[0] - tw) // 2
            y = bbox[1] + (bbox[3] - bbox[1] - th) // 2
            draw.text((x, y), text, font=font, fill=color)
            return
        size -= 2
    # Fallback tiny
    font = load_font(10)
    tb = draw.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    x = bbox[0] + (bbox[2] - bbox[0] - tw) // 2
    y = bbox[1] + (bbox[3] - bbox[1] - th) // 2
    draw.text((x, y), text, font=font, fill=color)

# Draw the five white balls with P O W E R
letters = "POWER"
for i, ch in enumerate(letters):
    cx = start_x + i * (D + GAP)
    bbox = (cx, center_y - D // 2, cx + D, center_y + D // 2)
    draw.ellipse(bbox, fill=WHITE, outline=OUTLINE, width=8)
    draw_centered_text(ch, bbox, BLACK, base_size=int(D * 0.6))

# Draw the red BALL ball
ix = 5  # sixth index
cx = start_x + ix * (D + GAP)
red_bbox = (cx, center_y - D // 2, cx + D, center_y + D // 2)
draw.ellipse(red_bbox, fill=RED)
# Fit the word "BALL" into the red circle (smaller font to fit four letters)
draw_centered_text("BALL", red_bbox, WHITE, base_size=int(D * 0.38), max_width_pad=18)

# Save original large master
OUT = Path("assets/icon.png")
img.save(OUT)
print(f"wrote {OUT.resolve()}")

# Also save resized icons for PWA
icon_dir = Path("api/static/icons")
icon_dir.mkdir(parents=True, exist_ok=True)

for size in (192, 512):
    resized = img.resize((size, size), Image.LANCZOS)
    out_path = icon_dir / f"icon-{size}.png"
    resized.save(out_path)
    print(f"wrote {out_path.resolve()}")