import subprocess
import sys
import importlib.util

# Function to check and install required packages
def install_package(package_name):
    """Check if a package is installed, if not, install it"""
    spec = importlib.util.find_spec(package_name)
    if spec is None:
        print(f"{package_name} not found. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
            print(f"{package_name} installed successfully!")
            return True
        except Exception as e:
            print(f"Failed to install {package_name}: {e}")
            return False
    else:
        print(f"{package_name} is already installed.")
        return True

# Try to install Pillow if needed
if not install_package("PIL"):
    print("ERROR: Could not install Pillow. Please install it manually using: pip install pillow")
    input("Press Enter to exit...")
    sys.exit(1)

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageOps
import os
import json
import traceback
import math

# ------------------------------------------------------------
# Simple Image to Mach3 G-code Engraving App
# ------------------------------------------------------------

CONFIG_FILE = "image_engrave_settings.json"


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception:
        pass


# Default parameters
default_params = {
    "input_image": "",
    "width_mm": 100.0,
    "height_mm": 80.0,
    "line_spacing_mm": 0.5,
    "pixel_spacing_mm": 0.5,
    "safe_z": 5.0,
    "surface_z": 0.0,
    "max_depth": 1.0,
    "feed_rate": 800,
    "plunge_rate": 300,
    "spindle_speed": 12000,
    "invert_image": False,
    "crop_to_subject": False,
    "background_threshold": 240,
}


class EngraveApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Engrave G-code Generator - Pet Portrait Edition")

        self.params = default_params.copy()
        self.tk_img = None
        self.orig_img_size = None
        self.cropped_img = None  # Store cropped version separately

        self.config = load_config()
        default_output_dir = os.path.expanduser("~/Desktop/CNC_Gcode")
        self.output_dir = self.config.get("output_dir", default_output_dir)
        
        # Create output directory if it doesn't exist
        try:
            os.makedirs(self.output_dir, exist_ok=True)
        except Exception as e:
            print(f"Could not create output directory: {e}")
            self.output_dir = os.path.expanduser("~/Desktop")
        
        self.output_path = ""

        self.create_widgets()
        self.update_output_path()

    def create_widgets(self):
        self.status_var = tk.StringVar(value="Ready.")
        self.img_info_var = tk.StringVar(value="")
        self.output_path_var = tk.StringVar(value="")

        # Tk variables for editable settings
        self.width_var = tk.DoubleVar(value=self.params["width_mm"])
        self.height_var = tk.DoubleVar(value=self.params["height_mm"])
        self.line_spacing_var = tk.DoubleVar(value=self.params["line_spacing_mm"])
        self.pixel_spacing_var = tk.DoubleVar(value=self.params["pixel_spacing_mm"])
        self.safe_z_var = tk.DoubleVar(value=self.params["safe_z"])
        self.surface_z_var = tk.DoubleVar(value=self.params["surface_z"])
        self.max_depth_var = tk.DoubleVar(value=self.params["max_depth"])
        self.feed_rate_var = tk.IntVar(value=self.params["feed_rate"])
        self.plunge_rate_var = tk.IntVar(value=self.params["plunge_rate"])
        self.spindle_speed_var = tk.IntVar(value=self.params["spindle_speed"])
        self.invert_image_var = tk.BooleanVar(value=self.params["invert_image"])
        self.crop_to_subject_var = tk.BooleanVar(value=self.params["crop_to_subject"])
        self.background_threshold_var = tk.IntVar(value=self.params["background_threshold"])

        # Guidance label
        help_text = "1. Select an image.  2. Choose output folder if needed.  3. Adjust settings.  4. Create G-code."
        tk.Label(self.root, text=help_text, fg="blue").pack(pady=(8, 2))

        main_frame = tk.Frame(self.root)
        main_frame.pack(padx=10, pady=10, fill="both", expand=True)

        left_frame = tk.Frame(main_frame)
        left_frame.pack(side="left", fill="y", padx=(0, 10), anchor="n")

        right_frame = tk.Frame(main_frame)
        right_frame.pack(side="left", fill="both", expand=True)

        # Input image controls
        tk.Label(left_frame, text="Input Image").pack(anchor="w")
        self.input_entry = tk.Entry(left_frame, width=42)
        self.input_entry.pack(anchor="w", pady=2)
        self.input_entry.insert(0, self.params["input_image"])

        tk.Button(left_frame, text="Browse / Load Image", command=self.browse_image).pack(anchor="w", pady=3)

        # Output controls
        tk.Label(left_frame, text="Output G-code File").pack(anchor="w", pady=(10, 0))
        self.output_label = tk.Label(
            left_frame,
            textvariable=self.output_path_var,
            fg="gray",
            wraplength=320,
            justify="left",
        )
        self.output_label.pack(anchor="w", pady=2)

        tk.Button(left_frame, text="Set Output Folder", command=self.browse_output_folder).pack(anchor="w", pady=3)

        # Separator
        tk.Frame(left_frame, height=2, bd=1, relief="sunken").pack(fill="x", pady=10)

        # Subject detection settings
        tk.Label(left_frame, text="Subject Detection (for pet portraits)", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 5))
        
        tk.Checkbutton(left_frame, text="Crop to subject only", 
                      variable=self.crop_to_subject_var,
                      command=self.on_crop_setting_changed).pack(anchor="w", pady=2)
        
        threshold_frame = tk.Frame(left_frame)
        threshold_frame.pack(anchor="w", pady=2, fill="x")
        tk.Label(threshold_frame, text="BG Brightness Threshold:", width=20, anchor="w").pack(side="left")
        threshold_scale = tk.Scale(threshold_frame, from_=200, to=255, 
                                   orient="horizontal", variable=self.background_threshold_var,
                                   length=120, command=self.on_threshold_changed)
        threshold_scale.pack(side="left")
        tk.Label(threshold_frame, text="(lower = more aggressive)", font=("Arial", 8)).pack(side="left", padx=5)
        
        tk.Label(left_frame, text="Tip: Use white/light backgrounds", 
                fg="gray", font=("Arial", 8)).pack(anchor="w", pady=(0, 10))

        # Separator
        tk.Frame(left_frame, height=2, bd=1, relief="sunken").pack(fill="x", pady=10)

        # Editable settings
        tk.Label(left_frame, text="Engraving Settings", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 5))
        
        settings = [
            ("Width mm", self.width_var),
            ("Height mm", self.height_var),
            ("Line spacing mm", self.line_spacing_var),
            ("Pixel spacing mm", self.pixel_spacing_var),
            ("Safe Z", self.safe_z_var),
            ("Surface Z", self.surface_z_var),
            ("Max depth (mm)", self.max_depth_var),
            ("Feed rate", self.feed_rate_var),
            ("Plunge rate", self.plunge_rate_var),
            ("Spindle speed", self.spindle_speed_var),
        ]

        for label_text, var in settings:
            row = tk.Frame(left_frame)
            row.pack(anchor="w", pady=2)
            tk.Label(row, text=label_text, width=18, anchor="w").pack(side="left")
            tk.Entry(row, textvariable=var, width=10).pack(side="left")

        tk.Checkbutton(left_frame, text="Invert image (engrave dark areas)", 
                      variable=self.invert_image_var).pack(anchor="w", pady=5)

        tk.Button(
            left_frame,
            text="Create G-code",
            command=self.save_gcode_button,
            width=20,
            height=2,
            bg="lightgreen",
        ).pack(anchor="w", pady=12)

        # Image preview on the right
        self.img_label = tk.Label(
            right_frame,
            text="No image loaded.\nClick 'Browse / Load Image' to start",
            width=90,
            height=32,
            relief="sunken",
            bg="white",
        )
        self.img_label.pack(padx=10, pady=5, fill="both", expand=True)

        tk.Label(right_frame, textvariable=self.img_info_var).pack(pady=2)
        tk.Label(right_frame, textvariable=self.status_var, anchor="w").pack(fill="x", pady=5)

    def on_crop_setting_changed(self):
        """Handle crop setting change"""
        if self.input_entry.get().strip() and os.path.exists(self.input_entry.get().strip()):
            self.load_image(self.input_entry.get().strip())

    def on_threshold_changed(self, value):
        """Handle threshold slider change"""
        if self.crop_to_subject_var.get() and self.input_entry.get().strip() and os.path.exists(self.input_entry.get().strip()):
            self.load_image(self.input_entry.get().strip())

    def find_subject_bounds(self, img_array, threshold=240):
        """Find the bounding box of the subject (non-background area)"""
        if img_array.mode != 'L':
            img_array = img_array.convert('L')
        
        pixels = img_array.load()
        width, height = img_array.size
        
        # Find min/max coordinates of non-background pixels
        min_x = width
        max_x = 0
        min_y = height
        max_y = 0
        found_pixels = False
        
        for y in range(height):
            for x in range(width):
                if pixels[x, y] < threshold:  # Non-background pixel
                    found_pixels = True
                    min_x = min(min_x, x)
                    max_x = max(max_x, x)
                    min_y = min(min_y, y)
                    max_y = max(max_y, y)
        
        if not found_pixels:
            return None
        
        # Add a small padding (5% on each side)
        padding_x = int((max_x - min_x) * 0.05)
        padding_y = int((max_y - min_y) * 0.05)
        
        min_x = max(0, min_x - padding_x)
        max_x = min(width - 1, max_x + padding_x)
        min_y = max(0, min_y - padding_y)
        max_y = min(height - 1, max_y + padding_y)
        
        return (min_x, min_y, max_x, max_y)

    def load_image(self, path):
        try:
            if not os.path.exists(path):
                self.status_var.set(f"Image not found: {path}")
                self.img_label.config(image="", text="No image loaded.")
                self.img_info_var.set("")
                return

            print(f"Opening image: {path}")
            original_img = Image.open(path)
            print(f"Original image size: {original_img.size}")
            
            # Apply subject detection if enabled
            if self.crop_to_subject_var.get():
                print("Detecting subject...")
                # Find subject bounds
                bounds = self.find_subject_bounds(original_img, self.background_threshold_var.get())
                
                if bounds:
                    min_x, min_y, max_x, max_y = bounds
                    print(f"Subject bounds: {bounds}")
                    
                    # Crop to subject
                    self.cropped_img = original_img.crop((min_x, min_y, max_x + 1, max_y + 1))
                    preview_img = self.cropped_img.copy()
                    self.orig_img_size = self.cropped_img.size
                    
                    # Calculate savings
                    original_area = original_img.size[0] * original_img.size[1]
                    cropped_area = self.cropped_img.size[0] * self.cropped_img.size[1]
                    savings = (1 - cropped_area / original_area) * 100
                    
                    self.status_var.set(f"Cropped to subject (saved {savings:.0f}% material)")
                else:
                    self.status_var.set("Warning: Could not detect subject, using full image")
                    preview_img = original_img.copy()
                    self.orig_img_size = original_img.size
                    self.cropped_img = None
                    messagebox.showwarning("Warning", "Could not detect subject with current threshold. Try adjusting the brightness threshold or disable 'Crop to subject'.")
            else:
                # Just use the original image
                preview_img = original_img.copy()
                self.orig_img_size = original_img.size
                self.cropped_img = None
            
            # Create preview (simple resize, no overlay)
            preview_width = 700
            preview_height = 520
            preview_img.thumbnail((preview_width, preview_height))
            preview_w, preview_h = preview_img.size

            self.tk_img = ImageTk.PhotoImage(preview_img)
            self.img_label.config(image=self.tk_img, text="")

            self.update_img_info(preview_w, preview_h)

        except Exception as e:
            error_msg = f"Error loading image: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.status_var.set(f"Error loading image: {str(e)}")
            self.img_label.config(image="", text=f"Error loading image:\n{str(e)}")
            self.img_info_var.set("")

    def update_output_path(self):
        try:
            input_path = self.input_entry.get().strip()

            if input_path and os.path.exists(input_path):
                base = os.path.splitext(os.path.basename(input_path))[0]
                if self.crop_to_subject_var.get():
                    base += "_cropped"
            else:
                base = "photo_engrave"

            self.output_path = os.path.join(self.output_dir, base + ".gc")
            self.output_path_var.set(self.output_path)
        except Exception as e:
            print(f"Error updating output path: {e}")
            self.output_path_var.set("Error generating path")

    def browse_image(self):
        """Browse for image file with error handling"""
        try:
            print("Browse button pressed - opening file dialog")
            
            filename = filedialog.askopenfilename(
                title="Select Image File",
                filetypes=[
                    ("Image Files", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.gif"),
                    ("All files", "*.*")
                ],
                parent=self.root
            )
            
            print(f"File dialog returned: {filename}")
            
            if filename and os.path.exists(filename):
                print(f"Loading image: {filename}")
                self.input_entry.delete(0, tk.END)
                self.input_entry.insert(0, filename)
                self.update_output_path()
                self.load_image(filename)
                self.status_var.set(f"Loaded: {os.path.basename(filename)}")
            elif filename:
                self.status_var.set(f"File not found: {filename}")
            else:
                print("No file selected")
                
        except Exception as e:
            error_msg = f"Error browsing for image: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.status_var.set(f"Error: {str(e)}")
            messagebox.showerror("Error", f"Failed to open file dialog:\n{str(e)}")

    def browse_output_folder(self):
        try:
            new_dir = filedialog.askdirectory(
                title="Select CNC Output Folder",
                initialdir=self.output_dir,
                parent=self.root
            )
            if new_dir and os.path.exists(new_dir):
                self.output_dir = new_dir
                self.config["output_dir"] = new_dir
                save_config(self.config)
                self.update_output_path()
                self.status_var.set(f"Output folder set to: {new_dir}")
            elif new_dir:
                self.status_var.set(f"Invalid folder: {new_dir}")
        except Exception as e:
            error_msg = f"Error selecting folder: {str(e)}"
            print(error_msg)
            self.status_var.set(error_msg)

    def update_img_info(self, preview_w=None, preview_h=None):
        if self.orig_img_size:
            w, h = self.orig_img_size
            info_text = f"Image size: {w} x {h} px"
            
            if self.crop_to_subject_var.get() and self.cropped_img:
                info_text += " (cropped to subject)"
            
            info_text += f" | Output: {self.width_var.get()} x {self.height_var.get()} mm"
            
            if preview_w and preview_h:
                info_text += f" | Preview: {preview_w} x {preview_h} px"
            
            self.img_info_var.set(info_text)
        else:
            self.img_info_var.set("")

    def save_gcode_button(self):
        self.update_output_path()

        self.params["input_image"] = self.input_entry.get()
        self.params["output_gcode"] = self.output_path
        self.params["width_mm"] = self.width_var.get()
        self.params["height_mm"] = self.height_var.get()
        self.params["line_spacing_mm"] = self.line_spacing_var.get()
        self.params["pixel_spacing_mm"] = self.pixel_spacing_var.get()
        self.params["safe_z"] = self.safe_z_var.get()
        self.params["surface_z"] = self.surface_z_var.get()
        self.params["max_depth"] = self.max_depth_var.get()
        self.params["feed_rate"] = self.feed_rate_var.get()
        self.params["plunge_rate"] = self.plunge_rate_var.get()
        self.params["spindle_speed"] = self.spindle_speed_var.get()
        self.params["invert_image"] = self.invert_image_var.get()
        self.params["crop_to_subject"] = self.crop_to_subject_var.get()
        self.params["background_threshold"] = self.background_threshold_var.get()

        try:
            self.generate_gcode()
            self.status_var.set(f"G-code saved as: {self.output_path}")
            messagebox.showinfo("Success", f"G-code saved as:\n{self.output_path}")
        except Exception as e:
            error_msg = f"Error generating G-code: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.status_var.set(f"Error: {str(e)}")
            messagebox.showerror("Error", f"Failed to generate G-code:\n{str(e)}")

    def generate_gcode(self):
        input_image = self.params["input_image"]
        output_gcode = self.params["output_gcode"]
        width_mm = self.params["width_mm"]
        height_mm = self.params["height_mm"]
        line_spacing_mm = self.params["line_spacing_mm"]
        pixel_spacing_mm = self.params["pixel_spacing_mm"]
        safe_z = self.params["safe_z"]
        surface_z = self.params["surface_z"]
        max_depth = abs(self.params["max_depth"])
        feed_rate = self.params["feed_rate"]
        plunge_rate = self.params["plunge_rate"]
        spindle_speed = self.params["spindle_speed"]
        invert_image = self.params["invert_image"]
        crop_to_subject = self.params["crop_to_subject"]
        background_threshold = self.params["background_threshold"]

        if not input_image or not os.path.exists(input_image):
            raise FileNotFoundError(f"Please select an image file first")

        if line_spacing_mm <= 0 or pixel_spacing_mm <= 0:
            raise ValueError("Line spacing and pixel spacing must be greater than zero.")

        # Load and process image
        if crop_to_subject and self.cropped_img:
            # Use the already cropped image
            img = self.cropped_img.copy()
            print(f"Using cropped image: {img.size}")
        else:
            img = Image.open(input_image).convert("L")
            
            # Crop to subject if enabled (but wasn't done in preview)
            if crop_to_subject:
                print("Cropping to subject for G-code generation...")
                bounds = self.find_subject_bounds(img, background_threshold)
                if bounds:
                    min_x, min_y, max_x, max_y = bounds
                    img = img.crop((min_x, min_y, max_x + 1, max_y + 1))
                    print(f"Cropped to: {img.size}")
        
        # Convert to grayscale if not already
        if img.mode != 'L':
            img = img.convert('L')
        
        # Calculate grid dimensions
        cols = max(1, int(width_mm / pixel_spacing_mm))
        rows = max(1, int(height_mm / line_spacing_mm))

        print(f"Generating G-code: {cols} x {rows} points")
        
        # Resize image to match grid
        img = img.resize((cols, rows))
        pixels = img.load()

        gcode = []
        gcode.append("(Photo engraving generated by Python)")
        gcode.append(f"(Input image: {os.path.basename(input_image)})")
        if crop_to_subject:
            gcode.append("(Mode: Cropped to subject only)")
        gcode.append(f"(Output size: {width_mm} x {height_mm} mm)")
        gcode.append(f"(Raster grid: {cols} columns x {rows} rows)")
        gcode.append(f"(Max depth: {max_depth} mm)")
        gcode.append("G21  (mm)")
        gcode.append("G90  (absolute positioning)")
        gcode.append("G17")
        gcode.append("G94")
        gcode.append(f"S{spindle_speed} M3")
        gcode.append(f"G0 Z{safe_z:.3f}")
        gcode.append("G0 X0 Y0")

        engraved_points = 0
        skipped_points = 0

        for row in range(rows):
            y = row * line_spacing_mm

            if row % 2 == 0:
                x_range = range(cols)
            else:
                x_range = range(cols - 1, -1, -1)

            first_point = True

            for col in x_range:
                x = col * pixel_spacing_mm
                brightness = pixels[col, rows - 1 - row]
                
                # If cropping is enabled, skip background pixels
                if crop_to_subject:
                    if brightness >= background_threshold:  # Background pixel
                        skipped_points += 1
                        first_point = True  # Reset first point for next valid pixel
                        continue

                if invert_image:
                    brightness = 255 - brightness

                darkness = 1.0 - (brightness / 255.0)
                z = surface_z - (darkness * max_depth)

                if first_point:
                    gcode.append(f"G0 Z{safe_z:.3f}")
                    gcode.append(f"G0 X{x:.3f} Y{y:.3f}")
                    gcode.append(f"G1 Z{z:.3f} F{plunge_rate}")
                    first_point = False
                    engraved_points += 1
                else:
                    gcode.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{feed_rate}")
                    engraved_points += 1

        gcode.append(f"G0 Z{safe_z:.3f}")
        gcode.append("M5")
        gcode.append("G0 X0 Y0")
        gcode.append("M30")

        output_folder = os.path.dirname(output_gcode)
        if output_folder:
            os.makedirs(output_folder, exist_ok=True)

        with open(output_gcode, "w") as f:
            f.write("\n".join(gcode))
        
        # Show statistics
        total_points = cols * rows
        if crop_to_subject:
            percent_engraved = (engraved_points / total_points) * 100
            self.status_var.set(f"G-code saved! Engraved {engraved_points}/{total_points} points ({percent_engraved:.1f}% of image)")
            print(f"Engraved: {engraved_points}, Skipped: {skipped_points} (background)")
        else:
            self.status_var.set(f"G-code saved to: {output_gcode}")
        
        print(f"G-code saved to: {output_gcode}")


def main():
    # Show a console window for installation messages
    print("=" * 50)
    print("Photo Engraving G-code Generator - Pet Portrait Edition")
    print("=" * 50)
    print("Checking dependencies...")
    
    try:
        root = tk.Tk()
        app = EngraveApp(root)
        root.mainloop()
    except Exception as e:
        print(f"Fatal error: {e}")
        print(traceback.format_exc())
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
