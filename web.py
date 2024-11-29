import requests
from PIL import Image
import sys
from colorama import Fore, init
from io import BytesIO

# Initialize colorama
init(autoreset=True)

# List of ASCII characters from light to dark
ASCII_CHARS = ["@", "#", "8", "&", "%", "$", "?", "*", "+", ";", ":", ",", "."]

# Function to resize image while maintaining aspect ratio
def resize_image(image, new_width=100):
    width, height = image.size
    aspect_ratio = height / width
    new_height = int(new_width * aspect_ratio)
    resized_image = image.resize((new_width, new_height))
    return resized_image

# Function to convert each pixel to grayscale and then to a corresponding ASCII character
def pixel_to_ascii(pixel):
    r, g, b = pixel
    brightness = (r + g + b) // 3
    ascii_char = ASCII_CHARS[brightness * len(ASCII_CHARS) // 256]
    return ascii_char

# Function to get the closest color in the terminal (for colorama)
def get_terminal_color(r, g, b):
    if r > g and r > b:
        return Fore.RED
    elif g > r and g > b:
        return Fore.GREEN
    elif b > r and b > g:
        return Fore.BLUE
    else:
        return Fore.WHITE

# Function to download and process the image from the URL
def download_image(image_url):
    response = requests.get(image_url)
    if response.status_code == 200:
        image = Image.open(BytesIO(response.content))
        return image
    else:
        raise Exception(f"Failed to download image, status code: {response.status_code}")

# Function to convert image to ASCII art
def image_to_ascii(image, new_width=100):
    image = resize_image(image, new_width)
    
    ascii_image = []
    ascii_image_plain = []  # For saving plain ASCII art without colors
    
    for y in range(image.height):
        row = ""
        row_plain = ""
        for x in range(image.width):
            pixel = image.getpixel((x, y))
            ascii_char = pixel_to_ascii(pixel)
            color = get_terminal_color(*pixel)
            row += color + ascii_char
            row_plain += ascii_char
        ascii_image.append(row)
        ascii_image_plain.append(row_plain)
    
    return "\n".join(ascii_image), "\n".join(ascii_image_plain)

# Function to save ASCII art to a text file
def save_ascii_to_file(ascii_art, filename="ascii_image.txt"):
    with open(filename, "w") as file:
        file.write(ascii_art)
    print(f"ASCII art saved to {filename}")

# Main function to run the program
def main(image_url, output_file="ascii_image.txt"):
    try:
        image = download_image(image_url)
        ascii_image_colored, ascii_image_plain = image_to_ascii(image)
        
        # Print colored ASCII art in the terminal
        print(ascii_image_colored)
        
        # Save plain ASCII art (without color) to a file
        save_ascii_to_file(ascii_image_plain, output_file)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ascii_image.py <image_url> [output_file]")
    else:
        image_url = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else "ascii_image.txt"
        main(image_url, output_file)
        
