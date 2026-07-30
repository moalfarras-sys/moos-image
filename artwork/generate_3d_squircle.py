import os
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import cairosvg
import io

def generate_glass_squircle(symbol_svg_path, color_start, color_end, output_path):
    size = 1024
    squircle_box = [72, 72, 72+880, 72+880]
    radius = 232
    
    # 1. Base Gradient Squircle
    base = Image.new("RGBA", (size, size), (0,0,0,0))
    squircle_mask = Image.new("L", (size, size), 0)
    draw_mask = ImageDraw.Draw(squircle_mask)
    draw_mask.rounded_rectangle(squircle_box, radius=radius, fill=255)
    
    gradient = Image.new("RGBA", (size, size))
    draw_grad = ImageDraw.Draw(gradient)
    for y in range(size):
        r = int(color_start[0] + (color_end[0] - color_start[0]) * y / size)
        g = int(color_start[1] + (color_end[1] - color_start[1]) * y / size)
        b = int(color_start[2] + (color_end[2] - color_start[2]) * y / size)
        draw_grad.line([(0, y), (size, y)], fill=(r,g,b, 255))
        
    base.paste(gradient, (0,0), squircle_mask)
    
    # 2. Glass reflection (top half)
    reflection = Image.new("RGBA", (size, size), (0,0,0,0))
    refl_draw = ImageDraw.Draw(reflection)
    for y in range(size // 2 + 150):
        alpha = int(120 * (1 - y / (size // 2 + 150)))
        refl_draw.line([(0, y), (size, y)], fill=(255,255,255, alpha))
    
    base.alpha_composite(Image.composite(reflection, Image.new("RGBA", (size, size)), squircle_mask))
    
    # 3. Inner highlight (top-left)
    highlight_mask = Image.new("L", (size, size), 0)
    draw_hl = ImageDraw.Draw(highlight_mask)
    draw_hl.rounded_rectangle([72, 72, 72+880, 72+880], radius=radius, outline=255, width=15)
    highlight_mask = highlight_mask.filter(ImageFilter.GaussianBlur(3))
    
    hl_img = Image.new("RGBA", (size, size), (255,255,255, 230))
    offset_hl = Image.new("L", (size, size), 0)
    offset_hl.paste(highlight_mask, (8, 8))
    
    from PIL import ImageChops
    hl_final = ImageChops.darker(offset_hl, squircle_mask)
    base.paste(hl_img, (0,0), hl_final)
    
    # Inner shadow (bottom-right)
    shadow_mask = Image.new("L", (size, size), 0)
    draw_sh = ImageDraw.Draw(shadow_mask)
    draw_sh.rounded_rectangle([72, 72, 72+880, 72+880], radius=radius, outline=255, width=15)
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(4))
    
    sh_img = Image.new("RGBA", (size, size), (0,0,0, 150))
    offset_sh = Image.new("L", (size, size), 0)
    offset_sh.paste(shadow_mask, (-8, -8))
    
    sh_final = ImageChops.darker(offset_sh, squircle_mask)
    base.paste(sh_img, (0,0), sh_final)
    
    # 4. Symbolic Icon
    svg_data = open(symbol_svg_path, 'rb').read()
    png_data = cairosvg.svg2png(bytestring=svg_data, output_width=440, output_height=440)
    symbol_img = Image.open(io.BytesIO(png_data)).convert("RGBA")
    
    # Colorize symbol to white
    r,g,b,a = symbol_img.split()
    white = Image.new("L", symbol_img.size, 255)
    symbol_white = Image.merge("RGBA", (white, white, white, a))
    
    # Add drop shadow to symbol
    shadow = symbol_white.filter(ImageFilter.GaussianBlur(10))
    enhancer = ImageEnhance.Brightness(shadow)
    shadow = enhancer.enhance(0.1) # dark
    
    sym_x = (size - 440) // 2
    sym_y = (size - 440) // 2
    
    base.paste(shadow, (sym_x, sym_y + 15), shadow)
    base.paste(symbol_white, (sym_x, sym_y), symbol_white)
    
    base.save(output_path)
    print(f"Generated {output_path}")

apps = {
    "moos-control-center": ("moos-settings-symbolic.svg", (71, 85, 105), (30, 41, 59)),
    "moos-installer": ("moos-install-symbolic.svg", (56, 189, 248), (2, 132, 199)),
    "moos-moplayer": ("moos-video-symbolic.svg", (236, 72, 153), (190, 24, 93)),
    "moos-pc-remote": ("moos-phone-symbolic.svg", (52, 211, 153), (4, 120, 87)),
    "moos-recovery": ("moos-repair-symbolic.svg", (251, 146, 60), (194, 65, 12)),
    "moos-store": ("moos-boxes-symbolic.svg", (250, 204, 21), (217, 119, 6)),
    "moos-themes": ("moos-ui-symbolic.svg", (192, 132, 252), (126, 34, 206)),
    "moos-updater": ("moos-safe-update-symbolic.svg", (45, 212, 191), (15, 118, 110)),
    "moos-welcome": ("moos-spark-symbolic.svg", (251, 113, 133), (225, 29, 72)),
    "org.kde.dolphin": ("moos-document-symbolic.svg", (59, 130, 246), (29, 78, 216)),
    "firefox": ("moos-globe-symbolic.svg", (249, 115, 22), (153, 27, 27)),
    "org.kde.konsole": ("moos-code-symbolic.svg", (16, 185, 129), (17, 24, 39)),
    "org.kde.gwenview": ("moos-camera-symbolic.svg", (129, 140, 248), (67, 56, 202)),
}

base_svg_dir = "/var/home/moos/moos-image/system_files/usr/share/icons/MoOSUI2Daylight/moos/actions/scalable"

for name, (svg_name, c1, c2) in apps.items():
    svg_path = os.path.join(base_svg_dir, svg_name)
    out_path = f"/var/home/moos/moos-image/artwork/master_icons/{name}.png"
    generate_glass_squircle(svg_path, c1, c2, out_path)
