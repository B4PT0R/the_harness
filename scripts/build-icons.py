"""Generate platform icons from one small, editable vector geometry."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
# Two rails joined by a blue bridge: a harness, without a character or mascot.
SHAPES = [
    ('#eef2f8', [(132,128),(188,128),(188,384),(132,384)]),
    ('#eef2f8', [(324,128),(380,128),(380,384),(324,384)]),
    ('#397bff', [(176,228),(336,228),(336,284),(176,284)]),
    ('#70a3ff', [(256,204),(308,256),(256,308),(204,256)]),
]

def svg(symbolic=False):
    background = '' if symbolic else '<rect x="16" y="16" width="480" height="480" rx="112" fill="#202226"/>'
    shapes = ''.join(f'<polygon fill="{"#dce8ff" if symbolic else color}" points="' + ' '.join(f'{x},{y}' for x,y in points) + '"/>' for color,points in SHAPES)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">{background}{shapes}</svg>\n'

def png(path, size, symbolic=False):
    image = Image.new('RGBA', (1024,1024))
    draw = ImageDraw.Draw(image)
    if not symbolic: draw.rounded_rectangle((32,32,992,992),radius=224,fill='#202226')
    for color,points in SHAPES:
        draw.polygon([(x*2,y*2) for x,y in points],fill='#dce8ff' if symbolic else color)
    image.resize((size,size),Image.Resampling.LANCZOS).save(path)

assets=ROOT/'assets'
assets.mkdir(exist_ok=True)
(assets/'assistant.svg').write_text(svg())
(assets/'assistant-symbolic.svg').write_text(svg(True))
png(assets/'assistant.png',512)
png(assets/'assistant-tray.png',64,True)
for name in ('assistant.svg','assistant.png'):
    (ROOT/'desktop/public'/name).write_bytes((assets/name).read_bytes())
