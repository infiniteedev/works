import os
import requests
import zipfile
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from pathlib import Path
import mimetypes
import time

# Function to create directories if they do not exist
def create_directories(path):
    if not os.path.exists(path):
        os.makedirs(path)

# Function to download a page (HTML)
def download_page(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise error for bad status codes
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return None

# Function to download any file (CSS, JS, Images, etc.)
def download_file(url, base_url, download_folder):
    try:
        file_url = urljoin(base_url, url)
        response = requests.get(file_url)
        response.raise_for_status()

        # Get the file name and prepare the path for saving
        parsed_url = urlparse(file_url)
        file_path = os.path.join(download_folder, parsed_url.netloc, parsed_url.path.lstrip("/"))

        # Ensure that directories exist for the file
        create_directories(os.path.dirname(file_path))

        with open(file_path, 'wb') as file:
            file.write(response.content)
        print(f"Downloaded: {file_url}")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading file {url}: {e}")

# Function to download all files associated with a page
def crawl_and_download(url, download_folder, visited=set()):
    # Skip if URL is already visited
    if url in visited:
        return
    visited.add(url)

    print(f"Crawling: {url}")
    
    # Download the page's HTML
    html_content = download_page(url)
    if html_content:
        # Save the HTML page with the correct structure
        parsed_url = urlparse(url)
        local_path = os.path.join(download_folder, parsed_url.netloc, parsed_url.path.lstrip('/'))
        if local_path.endswith('/'):
            local_path += 'index.html'
        create_directories(os.path.dirname(local_path))
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Parse HTML to find all links for assets and other pages
        soup = BeautifulSoup(html_content, 'lxml')
        base_url = urlparse(url)._replace(path='').geturl()  # Get base URL without path
        
        # Find all anchor links, images, CSS, JS, and other resources
        for tag in soup.find_all(['a', 'img', 'link', 'script']):
            href = tag.get('href') or tag.get('src')
            if href:
                # Only handle valid links (absolute or relative)
                if href.startswith('http') or href.startswith('/'):
                    if href.startswith('/'):
                        href = base_url + href
                    
                    # Recursively crawl and download resources like images, CSS, JS, etc.
                    if href.endswith(('.html', '.htm')):
                        crawl_and_download(href, download_folder, visited)
                    else:
                        download_file(href, base_url, download_folder)

# Function to zip all downloaded files
def zip_downloaded_files(zip_filename, download_folder):
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(download_folder):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, download_folder))

# Main function to start the crawling and zipping process
def main(url, download_folder, zip_filename):
    # Ensure the download folder exists
    create_directories(download_folder)
    
    # Start crawling from the root URL
    crawl_and_download(url, download_folder)
    
    # Create the zip archive from the downloaded content
    zip_downloaded_files(zip_filename, download_folder)
    print(f"Website content zipped into {zip_filename}")

# Example Usage
if __name__ == "__main__":
    website_url = "https://docs.frac.gg/introduction"  # Replace with the target website URL
    download_folder = "downloaded_site"  # Folder to store the files
    zip_filename = "frac.zip"  # Output zip file
    
    # Run the script
    main(website_url, download_folder, zip_filename)
