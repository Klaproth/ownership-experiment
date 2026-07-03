import streamlit as st
import random
import math
import io
import zipfile
import csv
from PIL import Image, ImageDraw, ImageFilter

class VisualSearchGenerator:
    def __init__(self, width=1000, height=800):
        self.width = width
        self.height = height

    def _generate_background_and_patches(self, patch_count=4, patch_radius=150, grain_intensity=30):
        bg_img = Image.new('L', (self.width, self.height), 220)
        draw = ImageDraw.Draw(bg_img)
        
        patch_locations = []
        for _ in range(patch_count):
            px = random.randint(patch_radius, self.width - patch_radius)
            py = random.randint(patch_radius, self.height - patch_radius)
            patch_locations.append((px, py, patch_radius))
            draw.ellipse([px - patch_radius, py - patch_radius, px + patch_radius, py + patch_radius], fill=100)
            
        bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=60)).convert('RGBA')
        
        grain_img = Image.new('RGBA', (self.width, self.height))
        grain_pixels = grain_img.load()
        for x in range(self.width):
            for y in range(self.height):
                noise = random.randint(-grain_intensity, grain_intensity)
                grain_pixels[x, y] = (noise, noise, noise, 50)
                
        return Image.alpha_composite(bg_img, grain_img), patch_locations

    def _draw_shape(self, shape_type, size, color, stroke_width):
        canvas_size = int(size * 1.5)
        img = Image.new('RGBA', (canvas_size, canvas_size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        offset = (canvas_size - size) // 2
        
        if shape_type == 'T':
            draw.line([(offset, offset), (offset + size, offset)], fill=color, width=stroke_width)
            draw.line([(offset + size//2, offset), (offset + size//2, offset + size)], fill=color, width=stroke_width)
        elif shape_type == 'L':
            draw.line([(offset, offset), (offset, offset + size)], fill=color, width=stroke_width)
            short_leg = int(size * 0.6)
            draw.line([(offset, offset + size), (offset + short_leg, offset + size)], fill=color, width=stroke_width)
        elif shape_type == 'O':
            draw.ellipse([(offset, offset), (offset + size, offset + size)], outline=color, width=stroke_width)
        elif shape_type == 'Q':
            draw.ellipse([(offset, offset), (offset + size, offset + size)], outline=color, width=stroke_width)
            center = offset + size / 2.0
            radius = size / 2.0
            start_offset = radius * 0.707
            start_x, start_y = int(center + start_offset), int(center + start_offset)
            tail_length = size * 0.4
            end_x, end_y = int(start_x + tail_length * 0.707), int(start_y + tail_length * 0.707)
            draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=stroke_width)

        return img

    def _get_distribution(self, total, perc_feature, val1, val2):
        """Helper to return a strictly proportioned, shuffled list of features."""
        count1 = int(round(total * perc_feature))
        count2 = total - count1
        arr = [val1] * count1 + [val2] * count2
        random.shuffle(arr)
        return arr

    def generate_stimulus(self, 
                          total_TL, perc_L, total_QO, perc_O, 
                          size_small, size_large, stroke_width, min_distance, target_on_patch_prob,
                          opts_O, opts_Q, opts_T, opts_L,
                          rotations=[0, 90, 180, 270]):
        
        img, patches = self._generate_background_and_patches(patch_count=5, patch_radius=180)

        # 1. Calculate Base Item Counts
        num_L = int(round(total_TL * perc_L))
        num_T = total_TL - num_L
        num_O = int(round(total_QO * perc_O))
        num_Q = total_QO - num_O

        items_to_draw = []

        # 2. Build items with exact distributions for size and color
        shapes_info = [
            ('O', num_O, True, opts_O),
            ('Q', num_Q, False, opts_Q),
            ('T', num_T, False, opts_T),
            ('L', num_L, True, opts_L)
        ]

        for shape, count, is_target, opts in shapes_info:
            if count == 0:
                continue
                
            sizes = self._get_distribution(count, opts['perc_small'], size_small, size_large)
            colors = self._get_distribution(count, opts['perc_color1'], opts['color1'], opts['color2'])
            
            for s, c in zip(sizes, colors):
                items_to_draw.append((shape, c, s, is_target))

        random.shuffle(items_to_draw)

        # 3. Placement Logic
        locations = []
        max_attempts = 1000
        
        for shape, color, size, is_target in items_to_draw:
            placed = False
            attempts = 0
            while not placed and attempts < max_attempts:
                if is_target and random.random() < target_on_patch_prob and patches:
                    px, py, pr = random.choice(patches)
                    angle = random.uniform(0, 2 * math.pi)
                    r = random.uniform(0, pr * 0.8)
                    x, y = int(px + r * math.cos(angle)), int(py + r * math.sin(angle))
                else:
                    x = random.randint(min_distance, self.width - min_distance)
                    y = random.randint(min_distance, self.height - min_distance)
                
                if x < min_distance or x > self.width - min_distance or y < min_distance or y > self.height - min_distance:
                    attempts += 1
                    continue
                
                if all(math.hypot(x - lx, y - ly) > min_distance for lx, ly in locations):
                    locations.append((x, y))
                    placed = True
                attempts += 1

        # 4. Rendering & Metadata Collection
        metadata = []
        for (shape, color, size, _), (x, y) in zip(items_to_draw, locations):
            angle = random.choice(rotations)
            
            r, g, b, a = img.getpixel((x, y))
            bg_luminance = int(0.299 * r + 0.587 * g + 0.114 * b)
            
            metadata.append({
                "shape": shape,
                "center_x": x,
                "center_y": y,
                "color_hex": color,
                "size_px": size,
                "is_small": (size == size_small),
                "rotation_deg": angle,
                "bg_luminance": bg_luminance
            })
            
            shape_img = self._draw_shape(shape, size, color, stroke_width)
            rotated_shape = shape_img.rotate(angle, expand=1, resample=Image.Resampling.BICUBIC)
            
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

# Sidebar - Global Settings
st.sidebar.header("1. Output Settings")
num_images = st.sidebar.number_input("Images to Generate", min_value=1, max_value=100, value=1)
img_width = st.sidebar.number_input("Width (px)", min_value=500, max_value=3000, value=1000, step=100)
img_height = st.sidebar.number_input("Height (px)", min_value=500, max_value=3000, value=800, step=100)

st.sidebar.header("2. Layout & Base Sizes")
size_small = st.sidebar.slider("Fixed Small Size", 10, 40, 20)
size_large = st.sidebar.slider("Fixed Large Size", 20, 80, 40)
stroke_width = st.sidebar.slider("Stroke Width", 1, 10, 4)
min_distance = st.sidebar.slider("Min Distance Between Shapes", 10, 150, 50)
target_on_patch_prob = st.sidebar.slider("Target on Dark Patch Prob.", 0.0, 1.0, 0.85)

st.sidebar.header("3. Item Counts")
total_TL = st.sidebar.slider("Total T's and L's", 0, 100, 40)
perc_L = st.sidebar.slider("Percentage of L's (Targets)", 0.0, 1.0, 0.25)
total_QO = st.sidebar.slider("Total Q's and O's", 0, 100, 40)
perc_O = st.sidebar.slider("Percentage of O's (Targets)", 0.0, 1.0, 0.25)

st.sidebar.header("4. Shape Specific Properties")

with st.sidebar.expander("O Settings (Target)"):
    o_perc_small = st.slider("% Small O's", 0.0, 1.0, 0.5)
    o_c1 = st.color_picker("O Primary Color", "#FF8C00") # Default Orange
    o_c2 = st.color_picker("O Secondary Color", "#0064FF")
    o_perc_c1 = st.slider("% O's in Primary Color", 0.0, 1.0, 1.0)
    opts_O = {'perc_small': o_perc_small, 'color1': o_c1, 'color2': o_c2, 'perc_color1': o_perc_c1}

with st.sidebar.expander("Q Settings (Distractor)"):
    q_perc_small = st.slider("% Small Q's", 0.0, 1.0, 0.5)
    q_c1 = st.color_picker("Q Primary Color", "#FF8C00") # Default Orange
    q_c2 = st.color_picker("Q Secondary Color", "#0064FF")
    q_perc_c1 = st.slider("% Q's in Primary Color", 0.0, 1.0, 1.0)
    opts_Q = {'perc_small': q_perc_small, 'color1': q_c1, 'color2': q_c2, 'perc_color1': q_perc_c1}

with st.sidebar.expander("L Settings (Target)"):
    l_perc_small = st.slider("% Small L's", 0.0, 1.0, 0.5)
    l_c1 = st.color_picker("L Primary Color", "#0064FF") # Default Blue
    l_c2 = st.color_picker("L Secondary Color", "#FF8C00")
    l_perc_c1 = st.slider("% L's in Primary Color", 0.0, 1.0, 1.0)
    opts_L = {'perc_small': l_perc_small, 'color1': l_c1, 'color2': l_c2, 'perc_color1': l_perc_c1}

with st.sidebar.expander("T Settings (Distractor)"):
    t_perc_small = st.slider("% Small T's", 0.0, 1.0, 0.5)
    t_c1 = st.color_picker("T Primary Color", "#0064FF") # Default Blue
    t_c2 = st.color_picker("T Secondary Color", "#FF8C00")
    t_perc_c1 = st.slider("% T's in Primary Color", 0.0, 1.0, 1.0)
    opts_T = {'perc_small': t_perc_small, 'color1': t_c1, 'color2': t_c2, 'perc_color1': t_perc_c1}


# Generation button logic
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
                    opts_O=opts_O, opts_Q=opts_Q, opts_T=opts_T, opts_L=opts_L
                )
                
                # Write Image to ZIP
                img_buffer = io.BytesIO()
                img.save(img_buffer, format="JPEG")
                img_filename = f"stimulus_{i+1:03d}.jpg"
                zip_file.writestr(img_filename, img_buffer.getvalue())
                
                # Write CSV to ZIP
                csv_str = create_csv_string(metadata)
                csv_filename = f"stimulus_{i+1:03d}.csv"
                zip_file.writestr(csv_filename, csv_str)
        
        # Show preview
        st.image(img, caption=f"Preview (Image {num_images} of {num_images})", use_container_width=True)
        st.success("Successfully generated archive!")
        
        st.download_button(
            label="Download .ZIP Data Package",
            data=zip_buffer.getvalue(),
            file_name="visual_search_data.zip",
            mime="application/zip",
            use_container_width=True
        )