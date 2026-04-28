from PIL import Image
import os

def convert_to_rgb565(img_path, output_h, width=160, height=120):
    img = Image.open(img_path)
    # Resize and crop to fill
    img = img.resize((width, height), Image.Resampling.LANCZOS)
    img = img.convert('RGB')
    
    with open(output_h, 'w') as f:
        f.write('#include <Arduino.h>\n\n')
        f.write('const uint16_t epd_bitmap_Porsche[] PROGMEM = {\n')
        
        pixels = list(img.getdata())
        for i, (r, g, b) in enumerate(pixels):
            # RGB888 to RGB565
            # r: 5 bits, g: 6 bits, b: 5 bits
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            f.write(f'0x{rgb565:04X}')
            if i < len(pixels) - 1:
                f.write(', ')
            if (i + 1) % 12 == 0:
                f.write('\n')
                
        f.write('\n};\n')

if __name__ == "__main__":
    img_path = r"c:\Users\Minh\OneDrive\Mon_Chuyen_Nganh\Project1\IoT_Camera_System\Camera_Node\Porsche-Taycan8.jpg"
    output_h = r"c:\Users\Minh\OneDrive\Mon_Chuyen_Nganh\Project1\IoT_Camera_System\Camera_Node\temp_pio\src\image.h"
    convert_to_rgb565(img_path, output_h)
    print(f"Converted {img_path} to {output_h}")
