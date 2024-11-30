from PIL import Image
from colorama import Fore, Back, Style, init

# Initialize colorama
init(autoreset=True)

# ASCII characters used for the conversion (darkest to lightest)
ASCII_CHARS = ['@', '#', 'S', '%', '?', '*', '+', ';', ':', ',', '.']

# Function to map pixel brightness to ASCII characters
def pixel_to_ascii(pixel):
    r, g, b = pixel
    brightness = (r + g + b) // 3
    ascii_index = int((brightness / 255) * (len(ASCII_CHARS) - 1))
    return ASCII_CHARS[ascii_index]

# Function to convert image to ASCII art with color codes using colorama
def image_to_colored_ascii(image_path, output_file='output.txt', new_width=100):
    # Open the image file
    img = Image.open(image_path)
    
    # Calculate the height ratio
    width, height = img.size
    ratio = height / width
    new_height = int(new_width * ratio)
    
    # Resize the image
    img = img.resize((new_width, new_height))
    
    # Convert the image to RGB mode if not already
    img = img.convert('RGB')
    
    # Open the output file to save the colorized ASCII
    with open(output_file, 'w') as file:
        for y in range(new_height):
            for x in range(new_width):
                pixel = img.getpixel((x, y))
                r, g, b = pixel
                ascii_char = pixel_to_ascii(pixel)
                
                # Using colorama to apply the color
                color_code = f"{Fore.rgb(r, g, b)}{ascii_char}"
                
                # Write the colorized ASCII character to the file
                file.write(f"{color_code}")
            file.write('\n')

    print(f"Colored ASCII art has been saved to {output_file}")

# Usage example:
image_path = 'vanilla.png'  # Replace with your image path
image_to_colored_ascii(image_path, 'vanilla.txt', 150)
                
