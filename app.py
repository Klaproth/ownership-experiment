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

    def generate_stimulus(self, total_TL, perc_L, color_T, color_L, total_QO, perc_O, color_Q, color_O, 
                          size_min, size_max, stroke_width, target_on_patch_prob, 
                          rotations=[0, 90, 180, 270], min_distance=50):
        
        img, patches = self._generate_background_and_patches(patch_count=5, patch_radius=180)

        num_L = int(total_TL * perc_L)
        num_T = total_TL - num_L
        num_O = int(total_QO * perc_O)
        num_Q = total_QO - num_O

        items_to_draw = []
        items_to_draw.extend([('L', color_L, True)] * num_L)
        items_to_draw.extend([('O', color_O, True)] * num_O)
        items_to_draw.extend([('T', color_T, False)] * num_T)
        items_to_draw.extend([('Q', color_Q, False)] * num_Q)
        random.shuffle(items_to_draw)

        locations = []
        max_attempts = 1000
        
        # Calculate Valid Coordinates
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

        # Render items and collect ground-truth metadata
        metadata = []
        for (shape, color, _), (x, y) in zip(items_to_draw, locations):
            size = random.randint(size_min, size_max)
            angle = random.choice(rotations)
            
            # 1. Sample Background Luminance (0 = black, 255 = white) at the exact center (x, y)
            r, g, b, a = img.getpixel((x, y))
            bg_luminance = int(0.299 * r + 0.587 * g + 0.114 * b)
            
            # 2. Save metadata for the CSV
            metadata.append({
                "shape": shape,
                "center_x": x,
                "center_y": y,
                "color_hex": color,
                "size_px": size,
                "rotation_deg": angle,
                "bg_luminance": bg_luminance
            })
            
            # 3. Draw and rotate
            shape_img = self._draw_shape(shape, size, color, stroke_width)
            rotated_shape = shape_img.rotate(angle, expand=1, resample=Image.Resampling.BICUBIC)
            
            # 4. Paste centered on (x,y)
            paste_x, paste_y = int(x - rotated_shape.width / 2), int(y - rotated_shape.height / 2)
            img.paste(rotated_shape, (paste_x, paste_y), rotated_shape)

        return img.convert('RGB'), metadata

def create_csv_string(metadata):
    """Helper function to convert metadata list of dicts to a CSV string."""
    output = io.StringIO()
    if len(metadata) > 0:
        writer = csv.DictWriter(output, fieldnames=metadata[0].keys())
        writer.writeheader()
        writer.writerows(metadata)
    return output.getvalue()


# --- Streamlit UI ---
st.set_page_config(page_title="Visual Search Stimulus Generator", layout="wide")
st.title("Visual Search Stimulus Generator")
st.write("Adjust the parameters and click **Generate** to create your stimuli and coordinate data.")

# Sidebar - Global Settings
st.sidebar.header("Global Output Settings")
num_images = st.sidebar.number_input("Number of Images to Generate", min_value=1, max_value=100, value=1)
img_width = st.sidebar.number_input("Image Width (px)", min_value=500, max_value=3000, value=1000, step=100)
img_height = st.sidebar.number_input("Image Height (px)", min_value=500, max_value=3000, value=800, step=100)

# Sidebar - Item Parameters
st.sidebar.header("Item Parameters")
total_TL = st.sidebar.slider("Total T's and L's", 0, 100, 40)
perc_L = st.sidebar.slider("Percentage of L's (Targets)", 0.0, 1.0, 0.25)

total_QO = st.sidebar.slider("Total Q's and O's", 0, 100, 40)
perc_O = st.sidebar.slider("Percentage of O's (Targets)", 0.0, 1.0, 0.25)

# Sidebar - Colors
st.sidebar.header("Shape Colors")
color_O = st.sidebar.color_picker("Color of O's", "#FF8C00")
color_Q = st.sidebar.color_picker("Color of Q's", "#FF8C00")
color_L = st.sidebar.color_picker("Color of L's", "#0064FF")
color_T = st.sidebar.color_picker("Color of T's", "#0064FF")

# Sidebar - Appearance & Layout
st.sidebar.header("Appearance & Layout")
size_min = st.sidebar.slider("Minimum Size", 10, 50, 25)
size_max = st.sidebar.slider("Maximum Size", size_min, 80, 40)
stroke_width = st.sidebar.slider("Stroke Width", 1, 10, 4)
min_distance = st.sidebar.slider("Minimum Distance Between Shapes", 10, 150, 50)
target_on_patch_prob = st.sidebar.slider("Target on Dark Patch Prob.", 0.0, 1.0, 0.85)

# Generation button logic
if st.sidebar.button("Generate Stimuli", type="primary"):
    generator = VisualSearchGenerator(width=img_width, height=img_height)
    
    # Logic for a SINGLE image + csv
    if num_images == 1:
        with st.spinner("Generating image and coordinate data..."):
            img, metadata = generator.generate_stimulus(
                total_TL=total_TL, perc_L=perc_L, color_T=color_T, color_L=color_L,
                total_QO=total_QO, perc_O=perc_O, color_Q=color_Q, color_O=color_O,
                size_min=size_min, size_max=size_max, stroke_width=stroke_width,
                target_on_patch_prob=target_on_patch_prob, min_distance=min_distance
            )
            
            st.image(img, caption="Generated Stimulus", use_container_width=True)
            
            # Prepare Image Bytes
            img_buf = io.BytesIO()
            img.save(img_buf, format="JPEG")
            byte_im = img_buf.getvalue()
            
            # Prepare CSV Bytes
            csv_str = create_csv_string(metadata)
            
            # Create two side-by-side buttons
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="Download Image (.jpg)",
                    data=byte_im,
                    file_name="stimulus_001.jpg",
                    mime="image/jpeg",
                    use_container_width=True
                )
            with col2:
                st.download_button(
                    label="Download Coordinate Data (.csv)",
                    data=csv_str,
                    file_name="stimulus_001.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
    # Logic for BATCH generation (ZIP file containing JPGs and CSVs)
    else:
        with st.spinner(f"Generating batch of {num_images} images and data files..."):
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                for i in range(num_images):
                    # 1. Generate image and metadata
                    img, metadata = generator.generate_stimulus(
                        total_TL=total_TL, perc_L=perc_L, color_T=color_T, color_L=color_L,
                        total_QO=total_QO, perc_O=perc_O, color_Q=color_Q, color_O=color_O,
                        size_min=size_min, size_max=size_max, stroke_width=stroke_width,
                        target_on_patch_prob=target_on_patch_prob, min_distance=min_distance
                    )
                    
                    # 2. Write Image to ZIP
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format="JPEG")
                    img_filename = f"stimulus_{i+1:03d}.jpg"
                    zip_file.writestr(img_filename, img_buffer.getvalue())
                    
                    # 3. Write CSV to ZIP
                    csv_str = create_csv_string(metadata)
                    csv_filename = f"stimulus_{i+1:03d}.csv"
                    zip_file.writestr(csv_filename, csv_str)
            
            # Show the final image generated as a preview
            st.image(img, caption=f"Preview (Image {num_images} of {num_images})", use_container_width=True)
            st.success(f"Successfully generated {num_images} images and {num_images} CSV files!")
            
            st.download_button(
                label=f"Download Archive (.zip)",
                data=zip_buffer.getvalue(),
                file_name="visual_search_batch.zip",
                mime="application/zip",
                use_container_width=True
            )