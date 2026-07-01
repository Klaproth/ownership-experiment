import streamlit as st
import random
import math
import io
from PIL import Image, ImageDraw, ImageFilter

# --- The Generator Class (Same as before) ---
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

    def generate_stimulus(self, total_TL, perc_L, color_TL, total_QO, perc_O, color_QO, 
                          size_min, size_max, stroke_width, target_on_patch_prob, 
                          rotations=[0, 90, 180, 270], min_distance=50):
        
        img, patches = self._generate_background_and_patches(patch_count=5, patch_radius=180)

        num_L = int(total_TL * perc_L)
        num_T = total_TL - num_L
        num_O = int(total_QO * perc_O)
        num_Q = total_QO - num_O

        items_to_draw = []
        items_to_draw.extend([('L', color_TL, True)] * num_L)
        items_to_draw.extend([('O', color_QO, True)] * num_O)
        items_to_draw.extend([('T', color_TL, False)] * num_T)
        items_to_draw.extend([('Q', color_QO, False)] * num_Q)
        random.shuffle(items_to_draw)

        locations = []
        max_attempts = 1000
        
        for shape, color, is_target in items_to_draw:
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

        for (shape, color, _), (x, y) in zip(items_to_draw, locations):
            size = random.randint(size_min, size_max)
            angle = random.choice(rotations)
            shape_img = self._draw_shape(shape, size, color, stroke_width)
            rotated_shape = shape_img.rotate(angle, expand=1, resample=Image.Resampling.BICUBIC)
            
            paste_x, paste_y = int(x - rotated_shape.width / 2), int(y - rotated_shape.height / 2)
            img.paste(rotated_shape, (paste_x, paste_y), rotated_shape)

        return img.convert('RGB')

# --- Streamlit UI ---
st.set_page_config(page_title="Visual Search Stimulus Generator", layout="wide")
st.title("Visual Search Stimulus Generator")
st.write("Adjust the parameters in the sidebar and click **Generate** to create a new stimulus.")

# Sidebar Parameters
st.sidebar.header("Item Parameters")
total_TL = st.sidebar.slider("Total T's and L's", 0, 100, 40)
perc_L = st.sidebar.slider("Percentage of L's (Targets)", 0.0, 1.0, 0.25)
color_TL = st.sidebar.color_picker("Color of T's and L's", "#FF8C00")

total_QO = st.sidebar.slider("Total Q's and O's", 0, 100, 40)
perc_O = st.sidebar.slider("Percentage of O's (Targets)", 0.0, 1.0, 0.25)
color_QO = st.sidebar.color_picker("Color of Q's and O's", "#0064FF")

st.sidebar.header("Appearance")
size_min = st.sidebar.slider("Minimum Size", 10, 50, 25)
size_max = st.sidebar.slider("Maximum Size", size_min, 80, 40)
stroke_width = st.sidebar.slider("Stroke Width", 1, 10, 4)
target_on_patch_prob = st.sidebar.slider("Target on Dark Patch Prob.", 0.0, 1.0, 0.85)

# Generation button
if st.sidebar.button("Generate Stimulus", type="primary"):
    with st.spinner("Generating..."):
        generator = VisualSearchGenerator(width=1000, height=800)
        img = generator.generate_stimulus(
            total_TL=total_TL, perc_L=perc_L, color_TL=color_TL,
            total_QO=total_QO, perc_O=perc_O, color_QO=color_QO,
            size_min=size_min, size_max=size_max, stroke_width=stroke_width,
            target_on_patch_prob=target_on_patch_prob
        )
        
        # Display the image
        st.image(img, caption="Generated Stimulus", use_container_width=True)
        
        # Convert image to bytes for the download button
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        byte_im = buf.getvalue()
        
        st.download_button(
            label="Download Image",
            data=byte_im,
            file_name="visual_search_stimulus.jpg",
            mime="image/jpeg"
        )