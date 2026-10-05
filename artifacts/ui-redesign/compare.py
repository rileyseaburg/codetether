"""Compose unaltered live-data screenshots for a direct layout comparison."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[2]
before = Image.open(root / 'artifacts/ui-live/verified-task-result.png').convert('RGB')
after = Image.open(root / 'artifacts/ui-redesign/task-result-desktop.png').convert('RGB')
canvas = Image.new('RGB', (before.width + after.width, max(before.height, after.height) + 64), '#f8fafc')
canvas.paste(before, (0, 64))
canvas.paste(after, (before.width, 64))
draw = ImageDraw.Draw(canvas)
try:
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 23)
except OSError:
    font = ImageFont.load_default()
draw.text((24, 18), 'BEFORE · previous local UI', fill='#0f172a', font=font)
draw.text((before.width + 24, 18), 'AFTER · redesigned preview (not deployed)', fill='#0f172a', font=font)
canvas.save(Path(__file__).parent / 'tasks-before-after.png')
print('Saved tasks-before-after.png; source screenshots retained unchanged.')
