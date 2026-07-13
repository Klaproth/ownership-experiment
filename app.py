import streamlit as st
import random
import math
import io
import zipfile
import csv
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

class VisualSearchGenerator:
    def __init__(self, width=1000, height=800):
        self.width = width
        self.height = height

    def _generate_background(self, grain_intensity=35, dark_patch_prob=0.3):
        w_base = max(1, self.width // 120)
        h_base = max(1, self.height // 120)
        
        # Octave 1
        grid1 = Image.new('L', (w_base, h_base))
        pixels1 = grid1.load()
        for x in range(w_base):
            for y in range(h_base):
                if random.random() < dark_patch_prob:
                    pixels1[x, y] = random.randint(30, 90)
                else:
                    pixels1[x, y] = random.randint(150, 240)
                
        # Octave 2
        grid2 = Image.new('L', (w_base * 2, h_base * 2))
        pixels2 = grid2.load()
        for x in range(w_base * 2):
            for y in range(h_base * 2):
                if random.random() < dark_patch_prob:
                    pixels2[x, y] = random.randint(30, 100)
                else:
                    pixels2[x, y] = random.randint(140, 230)
                
        img1 = grid1.resize((self.width, self.height), Image.Resampling.BICUBIC)
        img2 = grid2.resize((self.width, self.height), Image.Resampling.BICUBIC)
        
        smooth_bg = Image.blend(img1, img2, alpha=0.4)
        smooth_bg = smooth_bg.filter(ImageFilter.GaussianBlur(radius=40))
        
        contrast_enhancer = ImageEnhance.Contrast(smooth_bg)
        smooth_bg = contrast_enhancer.enhance(1.8) 
        
        brightness_enhancer = ImageEnhance.Brightness(smooth_bg)
        smooth_bg = brightness_enhancer.enhance(1.25)
        
        bg_rgba = smooth_bg.convert('RGBA')
        
        grain_img = Image.new('RGBA', (self.width, self.height))
        grain_pixels = grain_img.load()
        for x in range(self.width):
            for y in range(self.height):
                noise = random.randint(-grain_intensity, grain_intensity)
                grain_pixels[x, y] = (noise, noise, noise, 60) 
                
        final_bg = Image.alpha_composite(bg_rgba, grain_img)
        
        return final_bg, smooth_bg

    def _draw_shape(self, shape_type, size, color, stroke_width):
        canvas_size = int(size * 2.0)
        img = Image.new('RGBA', (canvas_size, canvas_size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        
        cx = canvas_size / 2.0
        cy = canvas_size / 2.0
        
        if shape_type == 'T':
            draw.line([(cx - size/2, cy - size/2), (cx + size/2, cy - size/2)], fill=color, width=stroke_width)
            draw.line([(cx, cy - size/2), (cx, cy + size/2)], fill=color, width=stroke_width)
            
        elif shape_type == 'L':
            short_leg = size * 0.6
            draw.line([(cx - short_leg/2, cy - size/2), (cx - short_leg/2, cy + size/2)], fill=color, width=stroke_width)
            draw.line([(cx - short_leg/2, cy + size/2), (cx + short_leg/2, cy + size/2)], fill=color, width=stroke_width)
            
        elif shape_type == 'O':
            draw.ellipse([(cx - size/2, cy - size/2), (cx + size/2, cy + size/2)], outline=color, width=stroke_width)
            
        elif shape_type == 'Q':
            draw.ellipse([(cx - size/2, cy - size/2), (cx + size/2, cy + size/2)], outline=color, width=stroke_width)
            start_offset = (size / 2.0) * 0.707
            start_x, start_y = cx + start_offset, cy + start_offset
            tail_length = size * 0.4
            end_x, end_y = start_x + tail_length * 0.707, start_y + tail_length * 0.707
            draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=stroke_width)

        return img

    def _get_distribution(self, total, perc_feature, val1, val2):
        count1 = int(round(total * perc_feature))
        count2 = total - count1
        arr = [val1] * count1 + [val2] * count2
        random.shuffle(arr)
        return arr

    def generate_stimulus(self, 
                          total_TL, perc_L, total_QO, perc_O, 
                          size_small, size_large, stroke_width, min_distance, target_on_patch_prob,
                          opts_O, opts_Q, opts_T, opts_L, dark_threshold=120, dark_patch_prob=0.3,
                          rotations=[0, 90, 180, 270]):
        
        img, smooth_bg = self._generate_background(dark_patch_prob=dark_patch_prob)

        num_L = int(round(total_TL * perc_L))
        num_T = total_TL - num_L
        num_O = int(round(total_QO * perc_O))
        num_Q = total_QO - num_O

        items_to_draw = []

        shapes_info = [
            ('O', num_O, True, opts_O),
            ('Q', num_Q, False, opts_Q),
            ('T', num_T, False, opts_T),
            ('L', num_L, True, opts_L)
        ]

        for shape, count, is_target, opts in shapes_info:
            if count == 0: continue
            sizes = self._get_distribution(count, opts['perc_small'], size_small, size_large)
            colors = self._get_distribution(count, opts['perc_color1'], opts['color1'], opts['color2'])
            for s, c in zip(sizes, colors):
                items_to_draw.append((shape, c, s, is_target))

        random.shuffle(items_to_draw)

        locations = []
        max_attempts = 1500
        
        for shape, color, size, is_target in items_to_draw:
            placed = False
            attempts = 0
            
            needs_dark_patch = is_target and (random.random() < target_on_patch_prob)

            while not placed and attempts < max_attempts:
                x = random.randint(min_distance, self.width - min_distance)
                y = random.randint(min_distance, self.height - min_distance)
                
                if any(math.hypot(x - lx, y - ly) < min_distance for lx, ly in locations):
                    attempts += 1
                    continue
                
                if needs_dark_patch:
                    bg_lum = smooth_bg.getpixel((x, y))
                    if bg_lum > dark_threshold:
                        attempts += 1
                        continue 
                
                locations.append((x, y))
                placed = True
                
            if not placed:
                locations.append((x, y))

        metadata = []
        for (shape, color, size, _), (x, y) in zip(items_to_draw, locations):
            angle = random.choice(rotations)
            
            r, g, b, a = img.getpixel((x, y))
            bg_luminance = int(0.299 * r + 0.587 * g + 0.114 * b)
            
            # Record the metadata
            metadata.append({
                "shape": shape,
                "center_x": x,
                "center_y": y,
                "color_hex": color,
                "size_px": size,
                "is_small": (size == size_small),
                "rotation": angle, # Extracted as the exact degree
                "bg_luminance": bg_luminance,
                "bg_dark": bool(bg_luminance <= dark_threshold) # Boolean based on exact threshold logic
            })
            
            shape_img = self._draw_shape(shape, size, color, stroke_width)
            # Use negative angle so it rotates clockwise visually, matching the CSV value
            rotated_shape = shape_img.rotate(-angle, expand=1, resample=Image.Resampling.BICUBIC)
            
            paste_x, paste_y = int(x - rotated_shape.width / 2), int(y - rotated_shape.height / 2)
            img.paste(rotated_shape, (paste_x, paste_y), rotated_shape)

        return img.convert('RGB'), metadata

def create_csv_string(metadata):
    output = io.StringIO()
    if len(metadata) > 0:
        writer = csv.DictWriter(output, fieldnames=metadata[0].keys())
        writer.writeheader()
        writer.writerows(metadata)
    return output.getvalue()

# --- Streamlit UI ---
st.set_page_config(page_title="Visual Search Stimulus Generator", layout="wide")
st.title("Visual Search Stimulus Generator")

st.sidebar.header("1. Output Settings")
num_images = st.sidebar.number_input("Images to Generate", min_value=1, max_value=100, value=1)
img_width = st.sidebar.number_input("Width (px)", min_value=500, max_value=3000, value=1000, step=100)
img_height = st.sidebar.number_input("Height (px)", min_value=500, max_value=3000, value=800, step=100)

st.sidebar.header("2. Layout & Base Sizes")
size_small = st.sidebar.slider("Fixed Small Size", 10, 40, 20)
size_large = st.sidebar.slider("Fixed Large Size", 20, 80, 40)
stroke_width = st.sidebar.slider("Stroke Width", 1, 10, 4)
min_distance = st.sidebar.slider("Min Distance Between Shapes", 10, 150, 50)

st.sidebar.header("3. Background Dynamics")
dark_patch_prob = st.sidebar.slider("Frequency of Dark Patches", 0.05, 0.95, 0.25, 
                                    help="Controls how many dark clouds form. Lower values mean fewer, more isolated patches.")
target_on_patch_prob = st.sidebar.slider("Target on Dark Patch Prob.", 0.0, 1.0, 0.85)
dark_threshold = st.sidebar.slider("Dark Patch Threshold (Luminance)", 50, 220, 120, 
                                   help="Lower values mean targets will only spawn in the darkest black spots. Higher values allow targets in grayer areas.")

st.sidebar.header("4. Item Counts")
total_TL = st.sidebar.slider("Total T's and L's", 0, 100, 40)
perc_L = st.sidebar.slider("Percentage of L's (Targets)", 0.0, 1.0, 0.25)
total_QO = st.sidebar.slider("Total Q's and O's", 0, 100, 40)
perc_O = st.sidebar.slider("Percentage of O's (Targets)", 0.0, 1.0, 0.25)

st.sidebar.header("5. Shape Specific Properties")

with st.sidebar.expander("O Settings (Target)"):
    o_perc_small = st.slider("% Small O's", 0.0, 1.0, 0.5)
    o_c1 = st.color_picker("O Primary Color", "#FF8C00") 
    o_c2 = st.color_picker("O Secondary Color", "#0064FF")
    o_perc_c1 = st.slider("% O's in Primary Color", 0.0, 1.0, 1.0)
    opts_O = {'perc_small': o_perc_small, 'color1': o_c1, 'color2': o_c2, 'perc_color1': o_perc_c1}

with st.sidebar.expander("Q Settings (Distractor)"):
    q_perc_small = st.slider("% Small Q's", 0.0, 1.0, 0.5)
    q_c1 = st.color_picker("Q Primary Color", "#FF8C00") 
    q_c2 = st.color_picker("Q Secondary Color", "#0064FF")
    q_perc_c1 = st.slider("% Q's in Primary Color", 0.0, 1.0, 1.0)
    opts_Q = {'perc_small': q_perc_small, 'color1': q_c1, 'color2': q_c2, 'perc_color1': q_perc_c1}

with st.sidebar.expander("L Settings (Target)"):
    l_perc_small = st.slider("% Small L's", 0.0, 1.0, 0.5)
    l_c1 = st.color_picker("L Primary Color", "#0064FF") 
    l_c2 = st.color_picker("L Secondary Color", "#FF8C00")
    l_perc_c1 = st.slider("% L's in Primary Color", 0.0, 1.0, 1.0)
    opts_L = {'perc_small': l_perc_small, 'color1': l_c1, 'color2': l_c2, 'perc_color1': l_perc_c1}

with st.sidebar.expander("T Settings (Distractor)"):
    t_perc_small = st.slider("% Small T's", 0.0, 1.0, 0.5)
    t_c1 = st.color_picker("T Primary Color", "#0064FF") 
    t_c2 = st.color_picker("T Secondary Color", "#FF8C00")
    t_perc_c1 = st.slider("% T's in Primary Color", 0.0, 1.0, 1.0)
    opts_T = {'perc_small': t_perc_small, 'color1': t_c1, 'color2': t_c2, 'perc_color1': t_perc_c1}

if st.sidebar.button("Generate Downloadable Archive", type="primary"):
    generator = VisualSearchGenerator(width=img_width, height=img_height)
    
    with st.spinner(f"Generating data archive (Images & CSVs)..."):
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            for i in range(num_images):
                img, metadata = generator.generate_stimulus(
                    total_TL=total_TL, perc_L=perc_L, total_QO=total_QO, perc_O=perc_O,
                    size_small=size_small, size_large=size_large, stroke_width=stroke_width,
                    min_distance=min_distance, target_on_patch_prob=target_on_patch_prob,
                    opts_O=opts_O, opts_Q=opts_Q, opts_T=opts_T, opts_L=opts_L, 
                    dark_threshold=dark_threshold, dark_patch_prob=dark_patch_prob
                )
                
                img_buffer = io.BytesIO()
                img.save(img_buffer, format="JPEG")
                img_filename = f"stimulus_{i+1:03d}.jpg"
                zip_file.writestr(img_filename, img_buffer.getvalue())
                
                csv_str = create_csv_string(metadata)
                csv_filename = f"stimulus_{i+1:03d}.csv"
                zip_file.writestr(csv_filename, csv_str)
        
        st.image(img, caption=f"Preview (Image {num_images} of {num_images})", use_container_width=True)
        st.success("Successfully generated archive!")
        
        st.download_button(
            label="Download .ZIP Data Package",
            data=zip_buffer.getvalue(),
            file_name="visual_search_data.zip",
            mime="application/zip",
            use_container_width=True
        )