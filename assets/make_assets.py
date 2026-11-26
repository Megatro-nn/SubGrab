"""Generates the logo files. Run: python assets/make_assets.py   (needs Pillow)

Design: a speech-bubble "subtitle card" whose tail is a download arrow -
subtitles being grabbed down into your folder. Bold blue-to-violet gradient,
white caption bars, readable at 16px.
"""
import base64
import io
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BLUE, VIOLET = (37, 99, 235), (124, 58, 237)
NAVY = (13, 20, 36)
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def bubble_mask(s=1024):
    """The logo silhouette: subtitle speech bubble whose tail is a download arrow."""
    m = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle((112, 140, 912, 690), 170, fill=255)             # bubble body
    d.rectangle((472, 640, 552, 790), fill=255)                          # arrow shaft (overlaps body)
    d.polygon([(392, 750), (632, 750), (512, 900)], fill=255)            # arrow head
    return m


def logo(size=1024):
    s = 1024
    grad = Image.new("RGB", (s, s))
    dg = ImageDraw.Draw(grad)
    for y in range(s):  # diagonal-ish gradient via rows tinted left-to-right
        for_band = y / s
        dg.line([(0, y), (s, y)], fill=(
            int(BLUE[0] + (VIOLET[0] - BLUE[0]) * for_band),
            int(BLUE[1] + (VIOLET[1] - BLUE[1]) * for_band),
            int(BLUE[2] + (VIOLET[2] - BLUE[2]) * for_band)))
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-200, -260, 620, 480), fill=(255, 255, 255, 56))
    grad = Image.alpha_composite(grad.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(150)))
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    im.paste(grad, (0, 0), bubble_mask(s))
    d = ImageDraw.Draw(im)
    # app name inside the bubble, two-tone
    f = ImageFont.truetype(FONT_B, 122)
    w_sub, w_grab = f.getlength("Sub"), f.getlength("Grab")
    x0 = 512 - (w_sub + w_grab) / 2
    d.text((x0, 208), "Sub", font=f, fill="white")
    d.text((x0 + w_sub, 208), "Grab", font=f, fill=(196, 181, 253))
    # three broken caption lines, exact pattern from the reference: long+short, short+long, long+short
    IX0, IW = 223, 583  # inner left edge and inner width of the bubble
    ROW_A = ((0.037, 0.610), (0.699, 0.971))
    ROW_B = ((0.037, 0.309), (0.397, 0.971))
    for row, y in ((ROW_A, 402), (ROW_B, 482), (ROW_A, 562)):
        fill = "white" if row is ROW_A else (219, 234, 254)
        for f0, f1 in row:
            d.rounded_rectangle((IX0 + f0 * IW, y, IX0 + f1 * IW, y + 52), 26, fill=fill)
    return im.resize((size, size), Image.LANCZOS) if size != s else im


def fit_font(text, font_path, start, max_w):
    size = start
    while size > 10:
        f = ImageFont.truetype(font_path, size)
        if f.getlength(text) <= max_w:
            return f
        size -= 2
    return f


def banner():
    W, H = 1280, 640
    im = Image.new("RGB", (W, H), NAVY)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-420, -260, 700, 860), fill=(37, 99, 235, 110))
    ImageDraw.Draw(glow).ellipse((980, 380, 1560, 900), fill=(124, 58, 237, 80))
    im = Image.alpha_composite(im.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(180))).convert("RGB")
    d = ImageDraw.Draw(im)
    lg = logo(360)
    im.paste(lg, (120, 140), lg)
    tx = 560
    f_title = ImageFont.truetype(FONT_B, 124)
    d.text((tx, 170), "Sub", font=f_title, fill="white")
    w_sub = f_title.getlength("Sub")
    d.text((tx + w_sub, 170), "Grab", font=f_title, fill=(165, 180, 252))
    tag = "Find, fix and save subtitles for every video in a folder"
    d.text((tx + 4, 340), tag, font=fit_font(tag, FONT_R, 40, W - tx - 60), fill=(203, 213, 225))
    src = "OpenSubtitles  ·  SubSource  ·  Podnapisi  ·  Subf2m"
    d.text((tx + 4, 490), src, font=fit_font(src, FONT_R, 30, W - tx - 60), fill=(100, 116, 139))
    im.save(os.path.join(HERE, "banner.png"))


def installer_images():
    w = Image.new("RGB", (164, 314), NAVY)
    d = ImageDraw.Draw(w)
    lg = logo(120)
    w.paste(lg, (22, 40), lg)
    d.text((18, 175), "SubGrab", font=ImageFont.truetype(FONT_B, 28), fill="white")
    d.text((18, 212), "Subtitles,\ndone for you.", font=ImageFont.truetype(FONT_R, 14), fill=(203, 213, 225))
    w.save(os.path.join(HERE, "installer_wizard.bmp"))
    sm = Image.new("RGB", (55, 55), (255, 255, 255))
    l2 = logo(50)
    sm.paste(l2, (2, 2), l2)
    sm.save(os.path.join(HERE, "installer_small.bmp"))


def main():
    big = logo(1024)
    big.save(os.path.join(HERE, "logo.png"))
    big.save(os.path.join(HERE, "subgrab.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    buf = io.BytesIO()
    logo(128).save(buf, "PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()
    with open(os.path.join(ROOT, "subgrab_assets.py"), "w") as f:
        f.write('"""Generated by assets/make_assets.py - the 128px logo used for the window icon."""\n')
        f.write("LOGO_PNG_B64 = (\n")
        for i in range(0, len(b64), 100):
            f.write(f'    "{b64[i:i + 100]}"\n')
        f.write(")\n")
    banner()
    installer_images()
    print("assets written")


if __name__ == "__main__":
    main()
