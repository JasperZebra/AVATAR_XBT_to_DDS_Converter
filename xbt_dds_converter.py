import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import struct
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from PIL import Image, ImageTk
import logging
import io
import tempfile
import shutil
import subprocess
import numpy as np
import webbrowser

class XBTDDSConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("XBT ↔ DDS Converter | Made By: Jasper_Zebra | Version 1.0")
        self.root.geometry("1600x1000")
        self.root.resizable(False, False)
        self.root.configure(bg='#2c2c2c')
        
        # Initialize variables
        self.conversion_mode = tk.StringVar(value="single")
        self.conversion_type = tk.StringVar(value="auto")
        self.file_path = tk.StringVar()
        self.include_subdirs = tk.BooleanVar(value=True)
        self.overwrite_existing = tk.BooleanVar(value=False)
        self.fix_dds_format = tk.BooleanVar(value=False)  # ADD THIS LINE
        self.background_image = None
        self.temp_files = []  # Track temporary files for cleanup
        self.window_icon = None  # Add this to store icon reference
        
        # Set up logging
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger('XBTDDSConverter')
        
        # Set up window icon
        self._setup_window_icon()

        # Setup the modern interface
        self._setup_background_image()
        self.setup_modern_ui()
        
        # Bind file path changes to preview updates
        self.file_path.trace('w', self.update_preview)       

    def _setup_window_icon(self):
        """Set up the window icon"""
        try:
            # Try different possible icon locations
            icon_paths = [
                os.path.join("assets", "converter_icon.png"),
                os.path.join("assets", "converter_icon.ico"),
                os.path.join("Background", "converter_background.png"),
                "converter_icon.png",
                "converter_icon.ico"
            ]
            
            icon_set = False
            
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    try:
                        if icon_path.lower().endswith('.ico'):
                            # Use ICO file directly
                            self.root.iconbitmap(icon_path)
                            self.logger.debug(f"Set ICO icon: {icon_path}")
                            icon_set = True
                            break
                        elif icon_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                            # Convert image to PhotoImage and use as icon
                            icon_image = Image.open(icon_path)
                            # Resize to appropriate icon size
                            icon_image = icon_image.resize((32, 32), Image.Resampling.LANCZOS)
                            icon_photo = ImageTk.PhotoImage(icon_image)
                            
                            # Set the icon
                            self.root.iconphoto(True, icon_photo)
                            
                            # Keep a reference to prevent garbage collection
                            self.window_icon = icon_photo
                            
                            self.logger.debug(f"Set PNG icon: {icon_path}")
                            icon_set = True
                            break
                            
                    except Exception as e:
                        self.logger.warning(f"Failed to load icon {icon_path}: {str(e)}")
                        continue
            
            if not icon_set:
                self.logger.info("No icon file found, using default system icon")
                
            return icon_set
            
        except Exception as e:
            self.logger.error(f"Error setting up window icon: {str(e)}")
            return False

    def _setup_background_image(self):
        """Load and set up the background image"""
        try:
            # You can use the same background or create a similar one
            bg_image_path = os.path.join("Background", "converter_background.png")
            
            if os.path.exists(bg_image_path):
                pil_image = Image.open(bg_image_path)
                pil_image = pil_image.resize((1600, 1000), Image.Resampling.LANCZOS)
                self.background_image = ImageTk.PhotoImage(pil_image)
                
                self.canvas = tk.Canvas(self.root, width=1400, height=900, highlightthickness=0)
                self.canvas.pack(fill=tk.BOTH, expand=True)
                self.canvas.create_image(0, 0, anchor=tk.NW, image=self.background_image)
                
                self.logger.debug(f"Background image loaded successfully")
                return True
            else:
                self.logger.warning(f"Background image not found, using solid background")
                self.canvas = tk.Canvas(self.root, width=1400, height=900, bg='#2c2c2c', highlightthickness=0)
                self.canvas.pack(fill=tk.BOTH, expand=True)
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to load background image: {str(e)}")
            self.canvas = tk.Canvas(self.root, width=1400, height=900, bg='#2c2c2c', highlightthickness=0)
            self.canvas.pack(fill=tk.BOTH, expand=True)
            return False

    def extract_dds_data(self, filepath):
        """Extract DDS data from XBT or DDS file"""
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            
            # Check if it's an XBT file
            if data[:4] == b'TBX\x00':
                # Find DDS signature in XBT file
                dds_start = data.find(b'DDS ')
                if dds_start == -1:
                    return None, "No DDS data found in XBT file"
                return data[dds_start:], None
            
            # Check if it's a DDS file
            elif data[:4] == b'DDS ':
                return data, None
            
            else:
                return None, "File is neither XBT nor DDS format"
                
        except Exception as e:
            return None, f"Error reading file: {str(e)}"

    def parse_dds_header(self, dds_data):
        """Parse DDS header to extract image information"""
        try:
            if len(dds_data) < 128:  # DDS header is 128 bytes minimum
                return None, "DDS data too small"
            
            # DDS header structure (simplified)
            magic = dds_data[:4]  # Should be b'DDS '
            if magic != b'DDS ':
                return None, "Invalid DDS magic signature"
            
            # Read basic header info
            size = struct.unpack('<I', dds_data[4:8])[0]  # Should be 124
            flags = struct.unpack('<I', dds_data[8:12])[0]
            height = struct.unpack('<I', dds_data[12:16])[0]
            width = struct.unpack('<I', dds_data[16:20])[0]
            pitch_or_linear_size = struct.unpack('<I', dds_data[20:24])[0]
            depth = struct.unpack('<I', dds_data[24:28])[0]
            mipmap_count = struct.unpack('<I', dds_data[28:32])[0]
            
            # Skip reserved fields and get pixel format
            pf_size = struct.unpack('<I', dds_data[76:80])[0]
            pf_flags = struct.unpack('<I', dds_data[80:84])[0]
            pf_fourcc = dds_data[84:88]
            
            # Determine format
            format_name = "Unknown"
            if pf_flags & 0x4:  # DDPF_FOURCC
                try:
                    format_name = pf_fourcc.decode('ascii').strip('\x00')
                except:
                    format_name = f"FourCC: {pf_fourcc.hex().upper()}"
            elif pf_flags & 0x40:  # DDPF_RGB
                rgb_bit_count = struct.unpack('<I', dds_data[88:92])[0]
                format_name = f"RGB {rgb_bit_count}-bit"
            
            info = {
                'width': width,
                'height': height,
                'format': format_name,
                'mipmap_count': mipmap_count,
                'size': len(dds_data)
            }
            
            return info, None
            
        except Exception as e:
            return None, f"Error parsing DDS header: {str(e)}"

    def create_preview_image(self, dds_data, max_size=360):
        """Create a preview image from DDS data"""
        try:
            # For now, we'll create a placeholder that shows the texture exists
            # and basic info. Full DDS decoding would require more complex logic
            # or external libraries like DirectXTex
            
            info, error = self.parse_dds_header(dds_data)
            if error:
                return None, error
            
            # Create a placeholder image with texture info
            preview_img = Image.new('RGB', (max_size, max_size), color='#404040')
            
            # Try to extract some pixel data for a simple preview
            # This is a very basic approach - real DDS decoding is much more complex
            try:
                # Skip DDS header (128 bytes) and try to interpret raw pixel data
                pixel_data_start = 128
                if len(dds_data) > pixel_data_start + 1024:  # Ensure we have some data
                    # Create a simple pattern from the raw data
                    raw_pixels = dds_data[pixel_data_start:pixel_data_start + min(max_size * max_size * 3, len(dds_data) - pixel_data_start)]
                    
                    # Create a simple visualization
                    if len(raw_pixels) > 0:
                        # Scale the raw data to create a pattern
                        pattern_size = min(64, int(len(raw_pixels) ** 0.5))
                        if pattern_size > 0:
                            pattern_img = Image.new('RGB', (pattern_size, pattern_size))
                            pixels = []
                            
                            for i in range(0, min(len(raw_pixels), pattern_size * pattern_size * 3), 3):
                                if i + 2 < len(raw_pixels):
                                    r = raw_pixels[i] if i < len(raw_pixels) else 0
                                    g = raw_pixels[i + 1] if i + 1 < len(raw_pixels) else 0
                                    b = raw_pixels[i + 2] if i + 2 < len(raw_pixels) else 0
                                    pixels.append((r, g, b))
                                else:
                                    pixels.append((100, 100, 100))
                            
                            # Fill remaining pixels if needed
                            while len(pixels) < pattern_size * pattern_size:
                                pixels.append((100, 100, 100))
                            
                            pattern_img.putdata(pixels[:pattern_size * pattern_size])
                            
                            # Scale up the pattern to preview size
                            preview_img = pattern_img.resize((max_size, max_size), Image.NEAREST)
            except:
                # If pixel extraction fails, create a info display
                pass
            
            return preview_img, None
            
        except Exception as e:
            return None, f"Error creating preview: {str(e)}"

    def update_preview(self, *args):
        """Update the preview window when a file is selected"""
        filepath = self.file_path.get()
        
        # Clean up previous temp files
        self.cleanup_temp_files()

        # Clear the conversion log when loading a new file
        self.log_text.delete(1.0, tk.END)


        self.fix_dds_format = tk.BooleanVar(value=False)
        
        # Clear previous preview
        self.preview_canvas.delete("all")
        
        if not filepath or not os.path.exists(filepath):
            # Show placeholder
            self.preview_canvas.create_text(
                175, 175,  # Updated center position
                text="🖼️\nSelect a file to preview", 
                font=('Segoe UI', 10), 
                fill='#666666', 
                justify=tk.CENTER
            )
            
            # Reset info labels
            self.preview_info['filename'].config(text="No file selected")
            self.preview_info['format'].config(text="Format: -")
            self.preview_info['dimensions'].config(text="Dimensions: -")
            self.preview_info['size'].config(text="File Size: -")
            self.preview_info['compression'].config(text="Compression: -")
            self.preview_info['header_size'].config(text="Header Size: -")
            return
        
        try:
            # Extract DDS data and create temp file
            temp_dds_path = self.create_temp_dds(filepath)
            if not temp_dds_path:
                self.preview_canvas.create_text(
                    175, 175, 
                    text="❌\nCannot extract DDS data", 
                    font=('Segoe UI', 10), 
                    fill='#ff6666', 
                    justify=tk.CENTER
                )
                return
            
            # Parse DDS header from temp file
            dds_info, error = self.parse_dds_header_from_file(temp_dds_path)
            if error:
                self.preview_canvas.create_text(
                    175, 175, 
                    text=f"❌\nError parsing DDS: {error}", 
                    font=('Segoe UI', 10), 
                    fill='#ff6666', 
                    justify=tk.CENTER
                )
                return
            
            # Update info labels
            filename = os.path.basename(filepath)
            file_size = os.path.getsize(filepath)
            
            self.preview_info['filename'].config(text=filename)
            self.preview_info['format'].config(text=f"Format: {dds_info['format']}")
            self.preview_info['dimensions'].config(text=f"Dimensions: {dds_info['width']} × {dds_info['height']}")
            self.preview_info['size'].config(text=f"File Size: {file_size:,} bytes")
            self.preview_info['compression'].config(text=f"Compression: {dds_info['format']}")
            
            # Determine header size
            if filepath.lower().endswith('.xbt'):
                with open(filepath, 'rb') as f:
                    data = f.read()
                    dds_start = data.find(b'DDS ')
                header_size = dds_start if dds_start != -1 else 0
                self.preview_info['header_size'].config(text=f"Header Size: {header_size} bytes (XBT)")
            else:
                self.preview_info['header_size'].config(text="Header Size: 128 bytes (DDS)")
            
            # Try to load the DDS file with PIL
            try:
                # PIL might not support DDS directly, so we'll show a pattern preview
                preview_img = self.create_preview_from_temp_dds(temp_dds_path, dds_info)
                
                if preview_img:
                    # Convert to PhotoImage and display
                    self.preview_photo = ImageTk.PhotoImage(preview_img)
                    
                    # Center the image in the canvas - UPDATED FOR LARGER CANVAS
                    canvas_width = 450
                    canvas_height = 450
                    img_x = (canvas_width - preview_img.width) // 4
                    img_y = (canvas_height - preview_img.height) // 4
                    
                    self.preview_canvas.create_image(
                        img_x, img_y, 
                        anchor=tk.NW, 
                        image=self.preview_photo
                    )
                    
                    # Add a border around the image
                    self.preview_canvas.create_rectangle(
                        img_x - 1, img_y - 1, 
                        img_x + preview_img.width + 1, img_y + preview_img.height + 1,
                        outline='#666666', 
                        width=1
                    )
                    
                    # Add info overlay at bottom
                    self.preview_canvas.create_text(
                        canvas_width // 2, canvas_height - 20,
                        text=f"{dds_info['width']} × {dds_info['height']} • {dds_info['format']}",
                        font=('Segoe UI', 9),
                        fill='#cccccc',
                        justify=tk.CENTER
                    )
                else:
                    # Show info without image
                    self.preview_canvas.create_text(
                        175, 175, 
                        text=f"📊\nDDS Info Preview\n{dds_info['width']} × {dds_info['height']}\n{dds_info['format']}", 
                        font=('Segoe UI', 10), 
                        fill='#cccccc', 
                        justify=tk.CENTER
                    )
            
            except Exception as e:
                # Show info without image preview
                self.preview_canvas.create_text(
                    175, 175, 
                    text=f"📊\nDDS Info Available\n{dds_info['width']} × {dds_info['height']}\n{dds_info['format']}", 
                    font=('Segoe UI', 10), 
                    fill='#cccccc', 
                    justify=tk.CENTER
                )
                
        except Exception as e:
            self.preview_canvas.create_text(
                175, 175, 
                text=f"❌\nPreview Error:\n{str(e)}", 
                font=('Segoe UI', 10), 
                fill='#ff6666', 
                justify=tk.CENTER
            )

    def create_temp_dds(self, filepath):
        """Create a temporary DDS file from XBT or DDS file"""
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            
            # Check if it's an XBT file
            if data[:4] == b'TBX\x00':
                # Find DDS signature in XBT file
                dds_start = data.find(b'DDS ')
                if dds_start == -1:
                    return None
                dds_data = data[dds_start:]
            elif data[:4] == b'DDS ':
                # Already a DDS file
                dds_data = data
            else:
                return None
            
            # Create temporary file
            temp_fd, temp_path = tempfile.mkstemp(suffix='.dds', prefix='preview_')
            self.temp_files.append(temp_path)
            
            # Write DDS data to temp file
            with os.fdopen(temp_fd, 'wb') as temp_file:
                temp_file.write(dds_data)
            
            return temp_path
            
        except Exception as e:
            self.log_message(f"❌ Error creating temp DDS: {str(e)}")
            return None

    def parse_dds_header_from_file(self, dds_path):
        """Parse DDS header from a file"""
        try:
            with open(dds_path, 'rb') as f:
                dds_data = f.read(128)  # Read header only
            
            return self.parse_dds_header(dds_data)
            
        except Exception as e:
            return None, f"Error reading DDS file: {str(e)}"

    def create_preview_from_temp_dds(self, temp_dds_path, dds_info, max_size=340):
        """Create a preview image from temporary DDS file"""
        try:
            # Try to use PIL to open the DDS file directly
            # Note: PIL may not support all DDS formats
            try:
                pil_image = Image.open(temp_dds_path)
                # Resize to fit preview area while maintaining aspect ratio
                pil_image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                return pil_image
            except:
                # PIL can't open DDS, create a pattern preview
                pass
            
            # Fallback: Create pattern from raw pixel data
            with open(temp_dds_path, 'rb') as f:
                f.seek(128)  # Skip DDS header
                pixel_data = f.read(min(max_size * max_size * 4, 65536))  # Read some pixel data
            
            if len(pixel_data) > 0:
                # Create a simple pattern visualization
                pattern_size = min(128, int(len(pixel_data) ** 0.5))  # Increased from 64 to 128
                if pattern_size > 8:
                    pattern_img = Image.new('RGB', (pattern_size, pattern_size))
                    pixels = []
                    
                    for i in range(0, min(len(pixel_data), pattern_size * pattern_size * 3), 3):
                        if i + 2 < len(pixel_data):
                            r = pixel_data[i] if i < len(pixel_data) else 128
                            g = pixel_data[i + 1] if i + 1 < len(pixel_data) else 128
                            b = pixel_data[i + 2] if i + 2 < len(pixel_data) else 128
                            pixels.append((r, g, b))
                    
                    # Fill remaining pixels
                    while len(pixels) < pattern_size * pattern_size:
                        pixels.append((128, 128, 128))
                    
                    pattern_img.putdata(pixels[:pattern_size * pattern_size])
                    
                    # Scale up to preview size maintaining aspect ratio
                    preview_img = pattern_img.resize((max_size, max_size), Image.NEAREST)
                    return preview_img
            
            return None
            
        except Exception as e:
            self.log_message(f"❌ Error creating preview: {str(e)}")
            return None

    def cleanup_temp_files(self):
        """Clean up temporary files"""
        for temp_path in self.temp_files:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception as e:
                self.log_message(f"⚠️ Could not delete temp file: {str(e)}")
        
        self.temp_files.clear()

    def on_closing(self):
        """Handle application closing"""
        self.cleanup_temp_files()
        self.root.destroy()

    def setup_modern_ui(self):
        """Create the modern UI layout"""
        self._create_header_section()
        self._create_mode_selection_cards()
        self._create_file_selection_section()
        self._create_conversion_options()
        self._create_action_section()
        self._create_progress_section()
        self._create_preview_section()
        self._create_log_section()
        self._create_footer_section()
        
    def _create_header_section(self):
        """Create the modern header section"""
        # Main title
        self.canvas.create_text(
            80, 20,
            text="🔄 XBT ↔ DDS Converter | Version 1.0",
            font=('Segoe UI', 32, 'bold'),
            fill='white',
            anchor=tk.NW
        )
        
        # Subtitle
        self.canvas.create_text(
            80, 90,
            text="Advanced Texture Converter - Complete Header Preservation",
            font=('Segoe UI', 14),
            fill='#dddddd',
            anchor=tk.NW
        )
        
        # Version info
        self.canvas.create_text(
            80, 115,
            text="Modern Edition | Perfect Round-trip Conversion",
            font=('Segoe UI', 10),
            fill='#bbbbbb',
            anchor=tk.NW
        )
        
    def _create_mode_selection_cards(self):
        """Create modern mode selection cards"""
        # Section title
        self.canvas.create_text(
            80, 160,
            text="Select Conversion Mode:",
            font=('Segoe UI', 16, 'bold'),
            fill='white',
            anchor=tk.NW
        )
        
        # Mode cards
        modes = [
            {
                "id": "single",
                "name": "Single File",
                "icon": "📄",
                "description": "Convert one file at a time",
                "details": "Perfect for individual textures",
                "x": 100
            },
            {
                "id": "batch",
                "name": "Batch Folder",
                "icon": "📁",
                "description": "Convert entire folders",
                "details": "Process multiple files at once",
                "x": 400
            }
        ]
        
        self.mode_cards = {}
        for mode in modes:
            self._create_mode_card(mode)
            
    def _create_mode_card(self, mode):
        """Create a mode selection card"""
        x = mode["x"]
        y = 200
        width = 250
        height = 120
        
        # Card background
        card_bg = self.canvas.create_rectangle(
            x, y, x + width, y + height,
            fill='#4B4B4B',
            outline='#404040',
            width=1,
            tags=f"mode_card_{mode['id']}"
        )
        
        # Icon
        self.canvas.create_text(
            x + 30, y + 30,
            text=mode["icon"],
            font=('Segoe UI Emoji', 24),
            fill='white',
            tags=f"mode_card_{mode['id']}"
        )
        
        # Name
        self.canvas.create_text(
            x + 70, y + 20,
            text=mode["name"],
            font=('Segoe UI', 14, 'bold'),
            fill='white',
            anchor=tk.NW,
            tags=f"mode_card_{mode['id']}"
        )
        
        # Description
        self.canvas.create_text(
            x + 70, y + 40,
            text=mode["description"],
            font=('Segoe UI', 10),
            fill='#dddddd',
            anchor=tk.NW,
            tags=f"mode_card_{mode['id']}"
        )
        
        # Details
        self.canvas.create_text(
            x + 70, y + 55,
            text=mode["details"],
            font=('Segoe UI', 9),
            fill='#bbbbbb',
            anchor=tk.NW,
            tags=f"mode_card_{mode['id']}"
        )
        
        # Selection indicator
        indicator = self.canvas.create_oval(
            x + width - 25, y + 15, x + width - 10, y + 30,
            fill='#404040',
            outline='#666666',
            tags=f"mode_indicator_{mode['id']}"
        )
        
        self.mode_cards[mode['id']] = {
            'card': card_bg,
            'indicator': indicator,
            'selected': mode['id'] == 'single'
        }
        
        # Update initial selection
        if mode['id'] == 'single':
            self._update_mode_selection('single')
        
        # Bind click events
        def on_click(event, mode_id=mode['id']):
            self.conversion_mode.set(mode_id)
            self._update_mode_selection(mode_id)
            self.on_mode_change()
        
        self.canvas.tag_bind(f"mode_card_{mode['id']}", "<Button-1>", on_click)
        
        # Add hover effects
        def on_enter(event, mode_id=mode['id']):
            if not self.mode_cards[mode_id]['selected']:
                self.canvas.itemconfig(self.mode_cards[mode_id]['card'], outline='#2a7fff', width=2)
        
        def on_leave(event, mode_id=mode['id']):
            if not self.mode_cards[mode_id]['selected']:
                self.canvas.itemconfig(self.mode_cards[mode_id]['card'], outline='#404040', width=1)
        
        self.canvas.tag_bind(f"mode_card_{mode['id']}", "<Enter>", on_enter)
        self.canvas.tag_bind(f"mode_card_{mode['id']}", "<Leave>", on_leave)
        
    def _update_mode_selection(self, selected_mode):
        """Update visual selection of mode cards"""
        for mode_id, card_data in self.mode_cards.items():
            if mode_id == selected_mode:
                # Selected style
                self.canvas.itemconfig(card_data['card'], fill='#3a5998', outline='#2a7fff', width=2)
                self.canvas.itemconfig(card_data['indicator'], fill='#2a7fff', outline='#2a7fff')
                card_data['selected'] = True
            else:
                # Unselected style
                self.canvas.itemconfig(card_data['card'], fill='#4B4B4B', outline='#404040', width=1)
                self.canvas.itemconfig(card_data['indicator'], fill='#404040', outline='#666666')
                card_data['selected'] = False
                
    def has_alpha(self, image):
        """Check if image has meaningful alpha data"""
        if image.mode != 'RGBA':
            return False
        alpha = np.array(image.split()[-1])
        return not np.all(alpha == 255)

    def has_mipmaps(self, filepath):
        """Check if DDS file has mipmaps"""
        try:
            with open(filepath, 'rb') as f:
                f.read(4)  # Skip magic
                header = f.read(28)  # Read partial header
                flags = struct.unpack('<I', header[4:8])[0]
                mip_count = struct.unpack('<I', header[24:28])[0]
                return bool(flags & 0x20000) and mip_count > 1
        except:
            return False

    def find_texconv(self):
        """Find texconv.exe tool"""
        # Check current directory first
        local_texconv = os.path.join(os.path.dirname(__file__), 'texconv.exe')
        if os.path.exists(local_texconv):
            return local_texconv
        
        # Check PATH
        try:
            subprocess.run(['texconv'], capture_output=True, check=False)
            return 'texconv'
        except FileNotFoundError:
            return None

    def fix_dds_format_with_texconv(self, input_path, texconv_path):
        """Fix DDS format using texconv tool"""
        try:
            # Test if the DDS file is readable
            try:
                with Image.open(input_path) as img:
                    img_rgba = img.convert('RGBA')
                use_alpha = self.has_alpha(img_rgba)
            except Exception as e:
                self.log_message(f"  ⚠️ Could not read with PIL ({e}), proceeding anyway...")
                use_alpha = False
            
            has_mips = self.has_mipmaps(input_path)
            
            self.log_message(f"🔧 Fixing DDS format: {os.path.basename(input_path)}")
            self.log_message(f"  Alpha: {'Yes' if use_alpha else 'No'}")
            self.log_message(f"  Mipmaps: {'Yes' if has_mips else 'No'}")
            
            # Create temp file for fixed DDS
            temp_fd, temp_fixed_path = tempfile.mkstemp(suffix='_fixed.dds', prefix='fixed_')
            self.temp_files.append(temp_fixed_path)
            os.close(temp_fd)  # Close the file descriptor, we just need the path
            
            # Build texconv command
            cmd = [texconv_path]
            
            # Set format based on alpha
            if use_alpha:
                cmd.extend(['-f', 'BC3_UNORM'])  # DXT5
            else:
                cmd.extend(['-f', 'BC1_UNORM'])  # DXT1
            
            # Set mipmap options
            if has_mips:
                cmd.extend(['-m', '0'])  # Generate full mip chain
            else:
                cmd.extend(['-m', '1'])  # Keep single mip level only
            
            # Force overwrite and output to temp file
            cmd.extend(['-y', '-o', os.path.dirname(temp_fixed_path)])
            cmd.append(input_path)
            
            # Run texconv
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Find the output file (texconv uses original filename)
                original_name = os.path.basename(input_path)
                texconv_output = os.path.join(os.path.dirname(temp_fixed_path), original_name)
                
                if os.path.exists(texconv_output):
                    # Move to our temp file location
                    os.replace(texconv_output, temp_fixed_path)
                    self.log_message(f"  ✅ DDS format fixed successfully")
                    return temp_fixed_path
                else:
                    self.log_message(f"  ❌ texconv output not found")
                    return None
            else:
                self.log_message(f"  ❌ texconv failed: {result.stderr.strip() if result.stderr else 'Unknown error'}")
                return None
                
        except Exception as e:
            self.log_message(f"❌ Error fixing DDS format: {str(e)}")
            return None

    def fix_dds_format_fallback(self, input_path):
        """Fallback DDS format fixing without external tools"""
        try:
            # Create temp file for fixed DDS
            temp_fd, temp_fixed_path = tempfile.mkstemp(suffix='_fixed.dds', prefix='fixed_')
            self.temp_files.append(temp_fixed_path)
            os.close(temp_fd)
            
            # Load and convert image
            with Image.open(input_path) as img:
                img_rgba = img.convert('RGBA')
            
            use_alpha = self.has_alpha(img_rgba)
            
            self.log_message(f"🔧 Fixing DDS format: {os.path.basename(input_path)} (fallback mode)")
            self.log_message(f"  Alpha: {'Yes' if use_alpha else 'No'}")
            self.log_message(f"  ⚠️ Using basic conversion (limited format support)")
            
            # Convert to RGB if no alpha
            if not use_alpha:
                rgb_img = Image.new('RGB', img_rgba.size, (255, 255, 255))
                rgb_img.paste(img_rgba, mask=img_rgba.split()[-1])
                img_rgba = rgb_img
            
            # Save as DDS
            img_rgba.save(temp_fixed_path, format='DDS')
            
            self.log_message(f"  ✅ DDS format fixed (basic)")
            return temp_fixed_path
            
        except Exception as e:
            self.log_message(f"❌ Error fixing DDS format: {str(e)}")
            return None

    def _create_file_selection_section(self):
        """Create modern file selection section"""
        # Create a frame for file selection widgets
        self.file_frame = tk.Frame(self.root, bg='#3a3a3a', relief='solid', bd=1)
        self.file_frame_window = self.canvas.create_window(80, 350, anchor=tk.NW, window=self.file_frame, width=600, height=80)
        
        # Title
        title_label = tk.Label(self.file_frame, text="📂 File Selection", 
                              font=('Segoe UI', 12, 'bold'), fg='white', bg='#3a3a3a')
        title_label.pack(anchor=tk.W, padx=15, pady=(10, 5))
        
        # File path section
        path_frame = tk.Frame(self.file_frame, bg='#3a3a3a')
        path_frame.pack(fill=tk.X, padx=15, pady=(0, 10))
        
        self.selection_label = tk.Label(path_frame, text="Input File:", 
                                       font=('Segoe UI', 10), fg='#dddddd', bg='#3a3a3a')
        self.selection_label.pack(side=tk.LEFT)
        
        self.file_entry = tk.Entry(path_frame, textvariable=self.file_path, 
                                  font=('Segoe UI', 10), bg='#2c2c2c', fg='white',
                                  insertbackground='white', relief='solid', bd=1)
        self.file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 10))
        
        self.browse_btn = tk.Button(path_frame, text="Browse File", 
                                   font=('Segoe UI', 10, 'bold'), bg='#2a7fff', fg='white',
                                   relief='flat', padx=20, command=self.browse_file)
        self.browse_btn.pack(side=tk.RIGHT)
        
    def _create_conversion_options(self):
        """Create modern conversion options section"""
        # Main options frame
        options_frame = tk.Frame(self.root, bg='#3a3a3a', relief='solid', bd=1)
        self.options_window = self.canvas.create_window(80, 450, anchor=tk.NW, window=options_frame, width=600, height=270)  # Increased height
        
        # Title
        title_label = tk.Label(options_frame, text="⚙️ Conversion Options", 
                            font=('Segoe UI', 12, 'bold'), fg='white', bg='#3a3a3a')
        title_label.pack(anchor=tk.W, padx=15, pady=(10, 5))
        
        # Conversion type section
        type_frame = tk.Frame(options_frame, bg='#3a3a3a')
        type_frame.pack(fill=tk.X, padx=15, pady=5)
        
        tk.Label(type_frame, text="Conversion Direction:", 
                font=('Segoe UI', 10, 'bold'), fg='#dddddd', bg='#3a3a3a').pack(anchor=tk.W)
        
        direction_frame = tk.Frame(type_frame, bg='#3a3a3a')
        direction_frame.pack(anchor=tk.W, pady=5)
        
        tk.Radiobutton(direction_frame, text="🔍 Auto-detect", variable=self.conversion_type, value="auto",
                    font=('Segoe UI', 9), fg='white', bg='#3a3a3a', selectcolor='#3a3a3a',
                    activebackground='#3a3a3a', activeforeground='white').pack(side=tk.LEFT)
        
        tk.Radiobutton(direction_frame, text="📤 XBT → DDS", variable=self.conversion_type, value="xbt_to_dds",
                    font=('Segoe UI', 9), fg='white', bg='#3a3a3a', selectcolor='#3a3a3a',
                    activebackground='#3a3a3a', activeforeground='white').pack(side=tk.LEFT, padx=(20, 0))
        
        tk.Radiobutton(direction_frame, text="📥 DDS → XBT", variable=self.conversion_type, value="dds_to_xbt",
                    font=('Segoe UI', 9), fg='white', bg='#3a3a3a', selectcolor='#3a3a3a',
                    activebackground='#3a3a3a', activeforeground='white').pack(side=tk.LEFT, padx=(20, 0))
        
        # DDS Format Fixing section - NEW
        dds_fix_frame = tk.Frame(options_frame, bg='#3a3a3a')
        dds_fix_frame.pack(fill=tk.X, padx=15, pady=(10, 5))
        
        tk.Label(dds_fix_frame, text="DDS Format Options:", 
                font=('Segoe UI', 10, 'bold'), fg='#dddddd', bg='#3a3a3a').pack(anchor=tk.W)
        
        dds_option_frame = tk.Frame(dds_fix_frame, bg='#3a3a3a')
        dds_option_frame.pack(anchor=tk.W, pady=5)
        
        tk.Checkbutton(dds_option_frame, text="🔧 Fix DDS format before DDS → XBT conversion (Recommended)", 
                    variable=self.fix_dds_format,
                    font=('Segoe UI', 9), fg='white', bg='#3a3a3a', selectcolor='#3a3a3a',
                    activebackground='#3a3a3a', activeforeground='white').pack(side=tk.LEFT)
        
        # Batch options (initially hidden)
        self.batch_frame = tk.Frame(options_frame, bg='#3a3a3a')
        
        tk.Label(self.batch_frame, text="Batch Options:", 
                font=('Segoe UI', 10, 'bold'), fg='#dddddd', bg='#3a3a3a').pack(anchor=tk.W, pady=(10, 5))
        
        batch_options_frame = tk.Frame(self.batch_frame, bg='#3a3a3a')
        batch_options_frame.pack(anchor=tk.W)
        
        tk.Checkbutton(batch_options_frame, text="📁 Include subdirectories", variable=self.include_subdirs,
                    font=('Segoe UI', 9), fg='white', bg='#3a3a3a', selectcolor='#3a3a3a',
                    activebackground='#3a3a3a', activeforeground='white').pack(side=tk.LEFT)
        
        tk.Checkbutton(batch_options_frame, text="🔄 Overwrite existing files", variable=self.overwrite_existing,
                    font=('Segoe UI', 9), fg='white', bg='#3a3a3a', selectcolor='#3a3a3a',
                    activebackground='#3a3a3a', activeforeground='white').pack(side=tk.LEFT, padx=(20, 0))
        
    def _create_action_section(self):
        """Create modern action section with convert button"""
        # Convert button
        self.convert_btn = tk.Button(self.root, text="🚀 Convert File", 
                                    font=('Segoe UI', 14, 'bold'), bg='#2a7fff', fg='white',
                                    relief='flat', padx=40, pady=15, command=self.convert_file,
                                    state='disabled')
        self.convert_btn_window = self.canvas.create_window(80, 730, anchor=tk.NW, window=self.convert_btn)
        
    def _create_progress_section(self):
        """Create modern progress section"""
        # Progress frame
        progress_frame = tk.Frame(self.root, bg='#3a3a3a', relief='solid', bd=1)
        self.progress_window = self.canvas.create_window(80, 810, anchor=tk.NW, window=progress_frame, width=600, height=60)
        
        # Progress bar
        self.progress = ttk.Progressbar(progress_frame, mode='indeterminate', length=550)
        self.progress.pack(padx=15, pady=(20, 5))
        
        # Progress label
        self.progress_label = tk.Label(progress_frame, text="", font=('Segoe UI', 9), 
                                      fg='#dddddd', bg='#3a3a3a')
        self.progress_label.pack(padx=15, pady=(0, 10))
        
    def _create_preview_section(self):
        """Create modern DDS/XBT preview section"""
        # Preview frame
        preview_frame = tk.Frame(self.root, bg='#3a3a3a', relief='solid', bd=1)
        self.preview_window = self.canvas.create_window(800, 100, anchor=tk.NW, window=preview_frame, width=700, height=550)
        
        # Title
        title_label = tk.Label(preview_frame, text="🖼️ Texture Preview",
                            font=('Segoe UI', 12, 'bold'), fg='white', bg='#3a3a3a')
        title_label.pack(anchor=tk.W, padx=15, pady=(10, 5))
        
        # Preview content frame
        preview_content_frame = tk.Frame(preview_frame, bg='#3a3a3a')
        preview_content_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        # Create preview canvas for image display - INCREASED SIZE
        self.preview_canvas = tk.Canvas(preview_content_frame, width=450, height=450, 
                                    bg='#2c2c2c', relief='solid', bd=1,
                                    highlightthickness=0)
        self.preview_canvas.pack(side=tk.LEFT, padx=(0, 15), pady=5)
        
        # Info frame on the right - REDUCED WIDTH
        info_frame = tk.Frame(preview_content_frame, bg='#3a3a3a', width=200)
        info_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 0), pady=5)
        info_frame.pack_propagate(False)  # Prevent frame from shrinking
        
        # Preview info labels
        self.preview_info = {
            'filename': tk.Label(info_frame, text="No file selected", 
                                font=('Segoe UI', 9, 'bold'), fg='white', bg='#3a3a3a', wraplength=180),
            'format': tk.Label(info_frame, text="Format: -", 
                            font=('Segoe UI', 8), fg='#dddddd', bg='#3a3a3a'),
            'dimensions': tk.Label(info_frame, text="Dimensions: -", 
                                font=('Segoe UI', 8), fg='#dddddd', bg='#3a3a3a'),
            'size': tk.Label(info_frame, text="File Size: -", 
                            font=('Segoe UI', 8), fg='#dddddd', bg='#3a3a3a'),
            'compression': tk.Label(info_frame, text="Compression: -", 
                                font=('Segoe UI', 8), fg='#dddddd', bg='#3a3a3a'),
            'header_size': tk.Label(info_frame, text="Header Size: -", 
                                font=('Segoe UI', 8), fg='#dddddd', bg='#3a3a3a')
        }
        
        # Pack info labels
        for i, (key, label) in enumerate(self.preview_info.items()):
            label.pack(anchor=tk.W, pady=3, padx=5)
        
        # Preview placeholder
        self.preview_image = None
        self.preview_canvas.create_text(230, 230, text="🖼️\nSelect a file to preview", 
                                    font=('Segoe UI', 20), fill='#666666', justify=tk.CENTER)
        
    def _create_log_section(self):
        """Create modern log section - smaller version"""
        # Log frame - reduced height from 440 to 200
        log_frame = tk.Frame(self.root, bg='#3a3a3a', relief='solid', bd=1)
        self.log_window = self.canvas.create_window(800, 660, anchor=tk.NW, window=log_frame, width=700, height=220)
        
        # Title
        title_label = tk.Label(log_frame, text="📋 Conversion Log", 
                              font=('Segoe UI', 12, 'bold'), fg='white', bg='#3a3a3a')
        title_label.pack(anchor=tk.W, padx=15, pady=(10, 5))
        
        # Log text area with scrollbar - reduced height
        log_content_frame = tk.Frame(log_frame, bg='#3a3a3a')
        log_content_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        self.log_text = tk.Text(log_content_frame, height=10, wrap=tk.WORD,
                               font=('Consolas', 9), bg='#2c2c2c', fg='#dddddd',
                               insertbackground='white', relief='solid', bd=1)
        
        scrollbar = tk.Scrollbar(log_content_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
    def _create_footer_section(self):
        """Create modern footer section"""
        # Separator line
        self.canvas.create_line(
            80, 890, 1520, 890,
            fill='#404040',
            width=1
        )
        
        # Tips
        self.canvas.create_text(
            80, 900,
            text="💡 XBT → DDS: Creates .dds + .xml (header) files | DDS → XBT: Requires both .dds and .xml files.",
            font=('Segoe UI', 10),
            fill='#bbbbbb',
            anchor=tk.NW
        )
        
        self.canvas.create_text(
            80, 930,
            text="💡 XML files contain original header data for perfect round-trip conversion, so don't delete it.",
            font=('Segoe UI', 10),
            fill='#bbbbbb',
            anchor=tk.NW
        )

        self.canvas.create_text(
        800, 900,
        text="💡 DDS files are GPU-optimized textures with built-in compression and mipmaps for gaming.",
        font=('Segoe UI', 10),
        fill='#bbbbbb',
        anchor=tk.NW
        )
        
        # Create the text with clickable link
        tip_text = self.canvas.create_text(
            800, 930,
            text="💡 Like this tool, check out my AVATAR: The Game Save Editor: ",
            font=('Segoe UI', 10),
            fill='#bbbbbb',
            anchor=tk.NW
        )
        
        # Create clickable link text
        link_text = self.canvas.create_text(
            1170, 930,  # Position after the tip text
            text="https://github.com/JasperZebra/AVATAR-Save-Editor/releases",
            font=('Segoe UI', 10, 'underline'),
            fill='#2a7fff',  # Blue color for link
            anchor=tk.NW,
            tags="avatar_link"
        )
        
        # Bind click event to open URL
        def open_avatar_link(event):
            webbrowser.open("https://github.com/JasperZebra/AVATAR-Save-Editor/releases")
        
        self.canvas.tag_bind("avatar_link", "<Button-1>", open_avatar_link)
        
        # Add hover effects for the link
        def on_link_enter(event):
            self.canvas.itemconfig(link_text, fill='#4d9fff')  # Lighter blue on hover
            self.root.config(cursor="hand2")  # Change cursor to hand
        
        def on_link_leave(event):
            self.canvas.itemconfig(link_text, fill='#2a7fff')  # Original blue
            self.root.config(cursor="")  # Reset cursor
        
        self.canvas.tag_bind("avatar_link", "<Enter>", on_link_enter)
        self.canvas.tag_bind("avatar_link", "<Leave>", on_link_leave)

        # Status
        self.status_var = tk.StringVar(value="Ready - Select a file to begin")
        self.canvas.create_text(
            80, 960,
            text="Status: ",
            font=('Segoe UI', 10, 'bold'),
            fill='#2a7fff',
            anchor=tk.NW
        )
        
        self.status_text = self.canvas.create_text(
            130, 960,
            text="Ready - Select a file to begin",
            font=('Segoe UI', 10),
            fill='#dddddd',
            anchor=tk.NW
        )

    def update_status(self, message):
        """Update the status text"""
        self.canvas.itemconfig(self.status_text, text=message)
        self.root.update_idletasks()
        
    def log_message(self, message):
        """Add a message to the log text area"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def on_mode_change(self):
        """Handle conversion mode change"""
        mode = self.conversion_mode.get()
        
        if mode == "single":
            self.selection_label.config(text="Input File:")
            self.browse_btn.config(text="Browse File", command=self.browse_file)
            self.convert_btn.config(text="🚀 Convert File")
            self.batch_frame.pack_forget()
        else:  # batch
            self.selection_label.config(text="Input Folder:")
            self.browse_btn.config(text="Browse Folder", command=self.browse_folder)
            self.convert_btn.config(text="🚀 Convert Folder")
            self.batch_frame.pack(fill=tk.X, padx=15, pady=5)
            
        # Reset selection and disable convert button
        self.file_path.set("")
        self.convert_btn.config(state='disabled')
        self.progress_label.config(text="")
        self.update_status("Ready - Select a file/folder to begin")
        
    def browse_file(self):
        """Open file dialog to select input file"""
        filetypes = [
            ("All supported", "*.xbt;*.dds"),
            ("XBT files", "*.xbt"),
            ("DDS files", "*.dds"),
            ("All files", "*.*")
        ]
        
        filename = filedialog.askopenfilename(
            title="Select XBT or DDS file",
            filetypes=filetypes
        )
        
        if filename:
            self.file_path.set(filename)
            self.convert_btn.config(state='normal')
            self.log_message(f"✅ Selected file: {os.path.basename(filename)}")
            self.update_status(f"File selected: {os.path.basename(filename)}")
            
    def browse_folder(self):
        """Open folder dialog to select input folder"""
        folder_path = filedialog.askdirectory(
            title="Select folder containing XBT or DDS files"
        )
        
        if folder_path:
            self.file_path.set(folder_path)
            self.convert_btn.config(state='normal')
            self.log_message(f"✅ Selected folder: {folder_path}")
            self.update_status(f"Folder selected: {os.path.basename(folder_path)}")
            
    # Include all the conversion methods from the original code
    def detect_file_type(self, filepath):
        """Detect if file is XBT or DDS based on header"""
        try:
            with open(filepath, 'rb') as f:
                header = f.read(4)
                if header == b'TBX\x00':
                    return 'xbt'
                elif header == b'DDS ':
                    return 'dds'
                else:
                    return 'unknown'
        except Exception as e:
            self.log_message(f"❌ Error detecting file type: {str(e)}")
            return 'unknown'
            
    def parse_xbt_header(self, data):
        """Parse XBT header and return header size, DDS start position, and header data"""
        try:
            if len(data) < 16:
                raise ValueError("File too small to be valid XBT")
                
            if data[:4] != b'TBX\x00':
                raise ValueError("Invalid XBT signature")
                
            # Read header size from offset 0x08
            header_size = struct.unpack('<I', data[8:12])[0]
            
            # Find DDS signature
            dds_start = data.find(b'DDS ')
            if dds_start == -1:
                raise ValueError("No DDS data found in XBT file")
                
            self.log_message(f"📊 XBT header size: {header_size} bytes")
            self.log_message(f"📊 DDS data starts at offset: {dds_start}")
            
            return header_size, dds_start, data[:dds_start]
            
        except Exception as e:
            raise ValueError(f"Error parsing XBT header: {str(e)}")
            
    def save_header_to_xml(self, header_data, xml_path):
        """Save XBT header data to XML file for later reconstruction"""
        try:
            # Create XML structure
            root = ET.Element("XBTHeader")
            
            # Add metadata
            metadata = ET.SubElement(root, "Metadata")
            ET.SubElement(metadata, "HeaderSize").text = str(len(header_data))
            ET.SubElement(metadata, "CreatedBy").text = "XBT-DDS Converter"
            
            # Parse and store header components
            if len(header_data) >= 16:
                # XBT signature (should be TBX\x00)
                signature = header_data[:4]
                ET.SubElement(metadata, "Signature").text = signature.hex()
                
                # Unknown bytes at 0x04
                unknown1 = struct.unpack('<I', header_data[4:8])[0]
                ET.SubElement(metadata, "Unknown1").text = str(unknown1)
                
                # Header size at 0x08
                stored_header_size = struct.unpack('<I', header_data[8:12])[0]
                ET.SubElement(metadata, "StoredHeaderSize").text = str(stored_header_size)
                
                # Unknown bytes at 0x0C
                unknown2 = struct.unpack('<I', header_data[12:16])[0]
                ET.SubElement(metadata, "Unknown2").text = str(unknown2)
                
                # Hash/checksum bytes at 0x10-0x1B (if present)
                if len(header_data) >= 28:
                    hash_bytes = header_data[16:28]
                    ET.SubElement(metadata, "HashBytes").text = hash_bytes.hex()
                
                # Check for embedded path (everything after the fixed header until null terminator)
                if len(header_data) > 28:
                    path_data = header_data[28:]
                    # Look for null terminator
                    null_pos = path_data.find(b'\x00')
                    if null_pos > 0:
                        try:
                            embedded_path = path_data[:null_pos].decode('ascii', errors='ignore')
                            if embedded_path.strip():  # Only add if not empty
                                ET.SubElement(metadata, "EmbeddedPath").text = embedded_path
                                self.log_message(f"📁 Found embedded path: {embedded_path}")
                        except:
                            pass  # Skip if decoding fails
            
            # Store raw header data as hex
            raw_data = ET.SubElement(root, "RawHeaderData")
            raw_data.text = header_data.hex()
            
            # Write formatted XML
            xml_str = ET.tostring(root, encoding='unicode')
            dom = minidom.parseString(xml_str)
            pretty_xml = dom.toprettyxml(indent="  ")
            
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write(pretty_xml)
                
            self.log_message(f"💾 Header saved to XML: {os.path.basename(xml_path)}")
            return True
            
        except Exception as e:
            self.log_message(f"❌ Error saving header to XML: {str(e)}")
            return False
            
    def load_header_from_xml(self, xml_path):
        """Load XBT header data from XML file"""
        try:
            if not os.path.exists(xml_path):
                raise ValueError(f"XML header file not found: {xml_path}")
                
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            if root.tag != "XBTHeader":
                raise ValueError("Invalid XML header file format")
                
            # Get raw header data
            raw_data_elem = root.find("RawHeaderData")
            if raw_data_elem is None or not raw_data_elem.text:
                raise ValueError("No raw header data found in XML")
                
            header_data = bytes.fromhex(raw_data_elem.text.strip())
            
            # Log some metadata for verification
            metadata = root.find("Metadata")
            if metadata is not None:
                header_size = metadata.find("HeaderSize")
                if header_size is not None:
                    self.log_message(f"📊 Loaded header size: {header_size.text} bytes")
                    
                embedded_path = metadata.find("EmbeddedPath")
                if embedded_path is not None and embedded_path.text:
                    self.log_message(f"📁 Embedded path: {embedded_path.text}")
            
            self.log_message(f"📂 Header loaded from XML: {os.path.basename(xml_path)}")
            return header_data
            
        except Exception as e:
            self.log_message(f"❌ Error loading header from XML: {str(e)}")
            return None

    def xbt_to_dds(self, input_path, output_path):
        """Convert XBT file to DDS by removing the header and saving it to XML"""
        try:
            with open(input_path, 'rb') as f:
                data = f.read()
                
            header_size, dds_start, header_data = self.parse_xbt_header(data)
            
            # Generate XML path for header
            base_name = os.path.splitext(output_path)[0]
            xml_path = base_name + ".xml"
            
            # Save header to XML file
            if not self.save_header_to_xml(header_data, xml_path):
                raise ValueError("Failed to save header to XML")
            
            # Extract DDS data (everything after DDS signature)
            dds_data = data[dds_start:]
            
            # Write DDS file
            with open(output_path, 'wb') as f:
                f.write(dds_data)
                
            self.log_message(f"✅ Successfully converted XBT to DDS")
            self.log_message(f"📊 Removed {dds_start} bytes of XBT header")
            self.log_message(f"📊 DDS file size: {len(dds_data)} bytes")
            self.log_message(f"💾 Header saved as: {os.path.basename(xml_path)}")
            
            return True
            
        except Exception as e:
            self.log_message(f"❌ Error converting XBT to DDS: {str(e)}")
            return False

    def dds_to_xbt(self, input_path, output_path):
        """Convert DDS file to XBT by adding the original header from XML"""
        try:
            actual_dds_path = input_path
            
            # Check if DDS format fixing is enabled
            if self.fix_dds_format.get():
                self.log_message(f"🔧 DDS format fixing enabled")
                
                # Find texconv tool
                texconv_path = self.find_texconv()
                if texconv_path:
                    self.log_message(f"📦 Using texconv: {texconv_path}")
                    fixed_dds_path = self.fix_dds_format_with_texconv(input_path, texconv_path)
                else:
                    self.log_message(f"📦 texconv not found, using fallback mode")
                    fixed_dds_path = self.fix_dds_format_fallback(input_path)
                
                if fixed_dds_path:
                    actual_dds_path = fixed_dds_path
                    self.log_message(f"✅ Using fixed DDS file for conversion")
                else:
                    self.log_message(f"⚠️ DDS fixing failed, using original file")
            
            # Read DDS file (original or fixed)
            with open(actual_dds_path, 'rb') as f:
                dds_data = f.read()
                
            if not dds_data.startswith(b'DDS '):
                raise ValueError("Invalid DDS file - missing DDS signature")
                
            # Look for corresponding XML header file
            base_name = os.path.splitext(input_path)[0]  # Use original path for XML lookup
            xml_path = base_name + ".xml"
            
            # Load header from XML
            header_data = self.load_header_from_xml(xml_path)
            if not header_data:
                raise ValueError(f"Failed to load header from XML file: {xml_path}")
                
            # Combine header and DDS data
            with open(output_path, 'wb') as f:
                f.write(header_data)
                f.write(dds_data)
                
            self.log_message(f"✅ Successfully converted DDS to XBT")
            self.log_message(f"📂 Used header from: {os.path.basename(xml_path)}")
            self.log_message(f"📊 Added {len(header_data)} bytes XBT header")
            self.log_message(f"📊 Total XBT file size: {len(header_data) + len(dds_data)} bytes")
            
            return True
            
        except Exception as e:
            self.log_message(f"❌ Error converting DDS to XBT: {str(e)}")
            return False
    
    def find_files_in_folder(self, folder_path, extensions):
        """Find all files with given extensions in folder"""
        files = []
        
        if self.include_subdirs.get():
            # Search recursively
            for root, dirs, filenames in os.walk(folder_path):
                for filename in filenames:
                    if any(filename.lower().endswith(ext.lower()) for ext in extensions):
                        files.append(os.path.join(root, filename))
        else:
            # Search only in root folder
            for filename in os.listdir(folder_path):
                filepath = os.path.join(folder_path, filename)
                if os.path.isfile(filepath) and any(filename.lower().endswith(ext.lower()) for ext in extensions):
                    files.append(filepath)
                    
        return sorted(files)
        
    def check_conversion_requirements(self, input_path, conversion_type):
        """Check if all required files exist for conversion"""
        if conversion_type == "dds_to_xbt":
            # For DDS to XBT, we need the corresponding XML file
            base_name = os.path.splitext(input_path)[0]
            xml_path = base_name + ".xml"
            if not os.path.exists(xml_path):
                return False, f"Required XML header file not found: {os.path.basename(xml_path)}"
        return True, ""

    def convert_batch(self, folder_path):
        """Convert all XBT/DDS files in a folder"""
        try:
            # Determine which files to process
            conversion_type = self.conversion_type.get()
            
            if conversion_type == "auto":
                # Find both XBT and DDS files
                extensions = ['.xbt', '.dds']
            elif conversion_type == "xbt_to_dds":
                extensions = ['.xbt']
            else:  # dds_to_xbt
                extensions = ['.dds']
                
            files = self.find_files_in_folder(folder_path, extensions)
            
            if not files:
                self.log_message(f"❌ No files found with extensions: {', '.join(extensions)}")
                return False
                
            self.log_message(f"📊 Found {len(files)} file(s) to convert")
            
            # Switch to determinate progress bar
            self.progress.config(mode='determinate', maximum=len(files), value=0)
            
            converted = 0
            skipped = 0
            errors = 0
            
            for i, input_path in enumerate(files):
                try:
                    # Update progress
                    self.progress_label.config(text=f"Processing {i+1}/{len(files)}: {os.path.basename(input_path)}")
                    self.progress.config(value=i)
                    self.root.update_idletasks()
                    
                    # Determine conversion for this file
                    if conversion_type == "auto":
                        file_type = self.detect_file_type(input_path)
                        if file_type == 'xbt':
                            current_conversion = "xbt_to_dds"
                        elif file_type == 'dds':
                            current_conversion = "dds_to_xbt"
                        else:
                            self.log_message(f"⚠️ Skipping unknown file type: {os.path.basename(input_path)}")
                            skipped += 1
                            continue
                    else:
                        current_conversion = conversion_type
                        
                    # Check conversion requirements
                    can_convert, error_msg = self.check_conversion_requirements(input_path, current_conversion)
                    if not can_convert:
                        self.log_message(f"⚠️ Skipping {os.path.basename(input_path)}: {error_msg}")
                        skipped += 1
                        continue

                    # Generate output path
                    base_name = os.path.splitext(input_path)[0]
                    if current_conversion == "xbt_to_dds":
                        output_path = base_name + ".dds"
                    else:
                        output_path = base_name + ".xbt"
                        
                    # Check if output already exists
                    if os.path.exists(output_path) and not self.overwrite_existing.get():
                        self.log_message(f"⚠️ Skipping existing file: {os.path.basename(output_path)}")
                        skipped += 1
                        continue
                        
                    # Perform conversion
                    self.log_message(f"🔄 Converting: {os.path.basename(input_path)} → {os.path.basename(output_path)}")
                    
                    if current_conversion == "xbt_to_dds":
                        success = self.xbt_to_dds(input_path, output_path)
                    else:
                        success = self.dds_to_xbt(input_path, output_path)
                        
                    if success:
                        converted += 1
                    else:
                        errors += 1
                        
                except Exception as e:
                    self.log_message(f"❌ Error processing {os.path.basename(input_path)}: {str(e)}")
                    errors += 1
                    
            # Final progress update
            self.progress.config(value=len(files))
            self.progress_label.config(text=f"Batch conversion complete: {converted} converted, {skipped} skipped, {errors} errors")
            
            # Summary
            self.log_message("="*60)
            self.log_message(f"📊 Batch conversion summary:")
            self.log_message(f"   Files processed: {len(files)}")
            self.log_message(f"   ✅ Successfully converted: {converted}")
            self.log_message(f"   ⚠️ Skipped: {skipped}")
            self.log_message(f"   ❌ Errors: {errors}")
            
            return errors == 0
            
        except Exception as e:
            self.log_message(f"❌ Batch conversion error: {str(e)}")
            return False

    def convert_file(self):
        """Main conversion function - handles both single file and batch conversion"""
        input_path = self.file_path.get()
        
        if not input_path:
            messagebox.showerror("Error", "Please select an input file or folder")
            return
            
        # Clear log
        self.log_text.delete(1.0, tk.END)
        
        # Start progress animation
        self.progress.start(10)
        self.convert_btn.config(state='disabled')
        self.progress_label.config(text="")
        self.update_status("Converting...")
        
        try:
            mode = self.conversion_mode.get()
            
            if mode == "single":
                # Single file conversion
                if not os.path.exists(input_path):
                    raise ValueError("Selected file does not exist")
                    
                success = self.convert_single_file(input_path)
                
            else:
                # Batch folder conversion
                if not os.path.isdir(input_path):
                    raise ValueError("Selected path is not a folder")
                    
                success = self.convert_batch(input_path)
                
            if success:
                self.update_status("✅ Conversion completed successfully!")
                if mode == "single":
                    messagebox.showinfo("Success", "File converted successfully!")
                else:
                    messagebox.showinfo("Success", "Batch conversion completed successfully!")
            else:
                self.update_status("❌ Conversion failed!")
                messagebox.showerror("Error", "Conversion failed. Check the log for details.")
                
        except Exception as e:
            self.log_message(f"❌ Conversion error: {str(e)}")
            self.update_status("❌ Conversion failed!")
            messagebox.showerror("Error", f"Conversion failed: {str(e)}")
            
        finally:
            # Stop progress animation and re-enable button
            self.progress.stop()
            self.progress.config(mode='indeterminate', value=0)
            self.convert_btn.config(state='normal')
            self.progress_label.config(text="")
            
    def convert_single_file(self, input_path):
        """Convert a single file"""
        try:
            # Determine conversion direction
            conversion_type = self.conversion_type.get()
            
            if conversion_type == "auto":
                file_type = self.detect_file_type(input_path)
                if file_type == 'xbt':
                    conversion_type = "xbt_to_dds"
                elif file_type == 'dds':
                    conversion_type = "dds_to_xbt"
                else:
                    raise ValueError("Unable to detect file type. Please specify conversion direction manually.")
                    
            self.log_message(f"🚀 Starting conversion: {conversion_type}")
            self.log_message(f"📂 Input file: {input_path}")
            
            # Generate output filename
            base_name = os.path.splitext(input_path)[0]
            
            if conversion_type == "xbt_to_dds":
                output_path = base_name + ".dds"
                success = self.xbt_to_dds(input_path, output_path)
            else:  # dds_to_xbt
                output_path = base_name + ".xbt"
                success = self.dds_to_xbt(input_path, output_path)
                
            if success:
                self.log_message(f"💾 Output file: {output_path}")
                
            return success
            
        except Exception as e:
            self.log_message(f"❌ Single file conversion error: {str(e)}")
            return False

def main():
    root = tk.Tk()
    app = XBTDDSConverter(root)
    
    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    root.mainloop()

if __name__ == "__main__":
    main()