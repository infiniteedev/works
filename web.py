import os
import requests
from bs4 import BeautifulSoup
import urllib.parse
import aiohttp
import asyncio
from tqdm import tqdm
import re

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

# Function to download a single file
async def download_file(session, url, backup_folder, progress_bar):
    try:
        # Parse the URL to get the correct file path
        parsed_url = urllib.parse.urlparse(url)
        file_path = os.path.join(backup_folder, parsed_url.netloc, parsed_url.path.lstrip('/'))

        if not os.path.exists(file_path):
            # Create directories if they don't exist
            create_directories(file_path)
            
            async with session.get(url) as response:
                if response.status == 200:
                    # Write the content to the backup folder
                    with open(file_path, 'wb') as f:
                        f.write(await response.read())
                    progress_bar.update(1)
                else:
                    print(f"Failed to download {url}, status code: {response.status}")
    except Exception as e:
        print(f"Error downloading {url}: {e}")

# Main function to crawl the website and download files
async def crawl_and_download(url, backup_folder):
    # Create the backup folder
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)

    # Get all links from the website
    print(f"Starting to crawl {url}")
    links = get_all_links(url)
    
    # Prepare for downloading
    total_files = len(links)
    print(f"Total files to download: {total_files}")
    progress_bar = tqdm(total=total_files, desc="Downloading", unit="file")

    # Use aiohttp to download files asynchronously
    async with aiohttp.ClientSession() as session:
        tasks = [download_file(session, link, backup_folder, progress_bar) for link in links]
        await asyncio.gather(*tasks)

    print("\nDownload complete!")

# Function to start the crawling and downloading process
def start_crawl(url, backup_folder="fractal"):
    asyncio.run(crawl_and_download(url, backup_folder))

# Main script
if __name__ == "__main__":
    website_url = input("https://frac.gg")
    start_crawl(website_url)
