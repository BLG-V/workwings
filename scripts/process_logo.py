from PIL import Image, ImageDraw, ImageFilter
import os

src = r"c:\Users\wzt20\Desktop\agentflow\public\logo-mawp.png"
out_dir = r"c:\Users\wzt20\Desktop\agentflow\public"
img = Image.open(src).convert("RGBA")
w, h = img.size
pixels = img.load()

for y in range(h):
    for x in range(w):
        r, g, b, a = pixels[x, y]
        if r > 240 and g > 240 and b > 240:
            pixels[x, y] = (0, 0, 0, 0)

xs, ys = [], []
for y in range(h):
    for x in range(w):
        r, g, b, a = pixels[x, y]
        if a > 10 and (r + g + b) < 720:
            xs.append(x)
            ys.append(y)

minx, maxx = min(xs), max(xs)
miny, maxy = min(ys), max(ys)
content_h = maxy - miny + 1
pad = 10
icon_right = minx + int(content_h * 1.06) + pad
raw = img.crop((max(0, minx - pad), max(0, miny - pad), min(w, icon_right), min(h, maxy + pad)))

side = min(raw.size)
raw = raw.resize((side, side), Image.Resampling.LANCZOS)

# white filled circle + original dark strokes
mask = Image.new("L", (side, side), 0)
ImageDraw.Draw(mask).ellipse((2, 2, side - 3, side - 3), fill=255)

base = Image.new("RGBA", (side, side), (0, 0, 0, 0))
white = Image.new("RGBA", (side, side), (255, 255, 255, 255))
base.paste(white, mask=mask)

# paste dark ink from raw onto base where ink exists
rp = raw.load()
bp = base.load()
for y in range(side):
    for x in range(side):
        if mask.getpixel((x, y)) < 200:
            continue
        r, g, b, a = rp[x, y]
        if a > 20 and (r + g + b) < 680:
            bp[x, y] = (18, 22, 30, 255)

# soft shadow layer behind for depth on light bg
shadow = Image.new("RGBA", (side + 24, side + 24), (0, 0, 0, 0))
sh_mask = Image.new("L", (side + 24, side + 24), 0)
ImageDraw.Draw(sh_mask).ellipse((10, 12, side + 10, side + 14), fill=90)
shadow.putalpha(sh_mask.filter(ImageFilter.GaussianBlur(6)))
canvas = Image.new("RGBA", (side + 24, side + 24), (0, 0, 0, 0))
canvas.alpha_composite(shadow)
canvas.alpha_composite(base, (12, 10))

big = canvas.resize((canvas.width * 3, canvas.height * 3), Image.Resampling.LANCZOS)
icon_path = os.path.join(out_dir, "logo-icon.png")
big.save(icon_path)
print("icon", big.size)

# transparent full wordmark
full = img.crop((minx, miny, maxx + 1, maxy + 1))
full_big = full.resize((full.width * 3, full.height * 3), Image.Resampling.LANCZOS)
full_big.save(os.path.join(out_dir, "logo-mawp-transparent.png"))
print("full ok")
