import os
import requests
from bs4 import BeautifulSoup
import urllib.parse
import aiohttp
import asyncio
from tqdm import tqdm
import re
import cssbeautifier
import jsbeautifier
import json
import xml.dom.minidom
import black
import markdown_it
import phpbeautifier


# Function to get all links from the website
def get_all_links(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        links = []

        # Find all anchor tags with href and all script and link tags with src
        for tag in soup.find_all(['a', 'img', 'link', 'script']):
            href = tag.get('href') or tag.get('src')
            if href:
                absolute_url = urllib.parse.urljoin(url, href)
                links.append(absolute_url)

        return set(links)
    except Exception as e:
        print(f"Error getting links from {url}: {e}")
        return set()


# Function to create directories
def create_directories(file_path):
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)


# Formatting Functions

def format_html(content):
    soup = BeautifulSoup(content, 'html.parser')
    return soup.prettify()


def format_css(content):
    return cssbeautifier.beautify(content)


def format_js(content):
    return jsbeautifier.beautify(content)


def format_python(content):
    return black.format_str(content, mode=black.Mode())


def format_markdown(content):
    md = markdown_it.MarkdownIt()
    return md.render(content)


def format_php(content):
    return phpbeautifier.beautify(content)


def format_json(content):
    parsed_json = json.loads(content)
    return json.dumps(parsed_json, indent=4)


def format_xml(content):
    dom = xml.dom.minidom.parseString(content)
    return dom.toprettyxml()


def format_ejs(content):
    # Split content into HTML and JavaScript parts (i.e., <% %> blocks)
    formatted_html = content
    ejs_code_blocks = re.findall(r"<%.*?%>", content, re.DOTALL)

    for block in ejs_code_blocks:
        # Format the JavaScript inside <% %>
        js_code = block[2:-2].strip()  # Remove the <% %> markers
        formatted_js_code = format_js(js_code)
        content = content.replace(block, f"<% {formatted_js_code} %>")

    return format_html(content)


# Function to determine file type and format it
def format_file(content, url):
    if url.endswith('.html') or 'text/html' in content[:100].lower():
        return format_html(content)
    elif url.endswith('.css') or 'text/css' in content[:100].lower():
        return format_css(content)
    elif url.endswith('.js') or 'application/javascript' in content[:100].lower():
        return format_js(content)
    elif url.endswith('.py') or 'application/python' in content[:100].lower():
        return format_python(content)
    elif url.endswith('.md') or 'text/markdown' in content[:100].lower():
        return format_markdown(content)
    elif url.endswith('.php') or 'application/php' in content[:100].lower():
        return format_php(content)
    elif url.endswith('.json') or 'application/json' in content[:100].lower():
        return format_json(content)
    elif url.endswith('.xml') or 'application/xml' in content[:100].lower():
        return format_xml(content)
    elif url.endswith('.ejs') or 'text/ejs' in content[:100].lower():
        return format_ejs(content)
    else:
        return content  # Return the content as is if no formatting is found


# Function to download a single file
async def download_file(session, url, backup_folder, progress_bar):
    try:
        parsed_url = urllib.parse.urlparse(url)
        file_path = os.path.join(backup_folder, parsed_url.netloc, parsed_url.path.lstrip('/'))

        # Skip if the file already exists
        if not os.path.exists(file_path):
            create_directories(file_path)
            
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.text()  # Read content as text
                    formatted_content = format_file(content, url)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(formatted_content)
                    progress_bar.update(1)
                else:
                    print(f"Failed to download {url}, status code: {response.status}")
    except Exception as e:
        print(f"Error downloading {url}: {e}")


# Main function to crawl the website and download files
async def crawl_and_download(url, backup_folder):
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)

    print(f"Starting to crawl {url}")
    links = get_all_links(url)

    total_files = len(links)
    print(f"Total files to download: {total_files}")
    progress_bar = tqdm(total=total_files, desc="Downloading", unit="file")

    async with aiohttp.ClientSession() as session:
        tasks = [download_file(session, link, backup_folder, progress_bar) for link in links]
        await asyncio.gather(*tasks)

    print("\nDownload complete!")


# Function to start the crawling and downloading process
def start_crawl(url, backup_folder="fractal"):
    asyncio.run(crawl_and_download(url, backup_folder))


# Main script
if __name__ == "__main__":
    website_url = input("Enter the website URL (e.g., https://frac.gg): ")
    start_crawl(website_url)
