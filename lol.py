import os
import requests
import zipfile
import threading
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from pathlib import Path
import mimetypes
from tqdm import tqdm
from queue import Queue
from time import sleep

# Number of concurrent threads for downloading
MAX_THREADS = 10

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

        # Ensure the directory exists
        create_directories(os.path.dirname(file_path))

        # Handle special cases for files without extensions (directories)
        if file_path.endswith('/'):
            file_path += 'index.html'

        # Save the file
        with open(file_path, 'wb') as file:
            file.write(response.content)
        print(f"Downloaded: {file_url}")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading file {url}: {e}")

# Function to fix links in the HTML page (internal links to local paths)
def fix_html_links(html, base_url, download_folder):
    soup = BeautifulSoup(html, "lxml")

    # Fix internal links in <a href="...">
    for link in soup.find_all("a", href=True):
        link_url = link['href']
        if link_url.startswith('/'):  # Handle relative links
            link['href'] = os.path.join(download_folder, link_url.lstrip('/'))
        elif base_url in link_url:  # Handle full internal URLs
            link['href'] = os.path.join(download_folder, urlparse(link_url).path.lstrip('/'))

    # Fix resources (CSS, JS, Images)
    for tag in soup.find_all(['img', 'link', 'script'], src=True):
        resource_url = tag.get('src') or tag.get('href')
        if resource_url.startswith('/'):  # Handle relative links
            tag['src'] = os.path.join(download_folder, resource_url.lstrip('/'))
        elif base_url in resource_url:  # Handle full internal URLs
            tag['src'] = os.path.join(download_folder, urlparse(resource_url).path.lstrip('/'))
    
    return str(soup)

# Function to handle downloading files and crawling pages with threading
def crawl_and_download(url, base_url, download_folder, visited, q, lock):
    page_content = download_page(url)
    if not page_content:
        return
    
    # Format and fix the HTML page links and resources
    formatted_html = fix_html_links(page_content, base_url, download_folder)

    # Save the HTML page
    parsed_url = urlparse(url)
    page_path = os.path.join(download_folder, parsed_url.netloc, parsed_url.path.lstrip("/"))
    create_directories(os.path.dirname(page_path))

    if not page_path.endswith('.html'):
        page_path += '/index.html'

    with open(page_path, 'w', encoding='utf-8') as f:
        f.write(formatted_html)
    print(f"Downloaded and saved page: {url}")

    # Parse the page content to find internal links
    soup = BeautifulSoup(page_content, "lxml")
    links_to_crawl = []

    for link in soup.find_all("a", href=True):
        link_url = link['href']
        if link_url.startswith('/'):  # Relative link
            link_url = urljoin(base_url, link_url)
        if link_url not in visited and base_url in link_url:
            visited.add(link_url)
            links_to_crawl.append(link_url)
            q.put(link_url)

    # Find and download resources (CSS, JS, Images)
    for resource_tag in soup.find_all(['img', 'link', 'script'], src=True):
        resource_url = resource_tag.get('src') or resource_tag.get('href')
        download_file(resource_url, base_url, download_folder)
    
    # Handle all internal links for crawling in a queue
    with lock:
        for link in links_to_crawl:
            q.put(link)

# Worker thread to handle the crawl queue
def worker(q, base_url, download_folder, visited, lock):
    while not q.empty():
        url = q.get()
        crawl_and_download(url, base_url, download_folder, visited, q, lock)
        q.task_done()

# Function to start the crawl and download process
def download_website(url, download_folder):
    base_url = urlparse(url).scheme + "://" + urlparse(url).hostname  # For base URL

    # Create the folder where we will save the site
    create_directories(download_folder)

    # Queue to manage threads
    q = Queue()
    visited = set()
    visited.add(url)
    lock = threading.Lock()

    # Start crawling and downloading resources
    q.put(url)

    # Thread pool to handle concurrent downloading
    threads = []
    for _ in range(MAX_THREADS):
        thread = threading.Thread(target=worker, args=(q, base_url, download_folder, visited, lock))
        thread.daemon = True
        thread.start()
        threads.append(thread)

    # Wait for the queue to be processed
    q.join()

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

    print("Download completed!")

# Function to zip the downloaded files
def zip_website_folder(download_folder, output_zip_file):
    # Zip the directory into a .zip file
    print("Compressing the website folder into a zip file...")
    with zipfile.ZipFile(output_zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for foldername, subfolders, filenames in os.walk(download_folder):
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                zipf.write(file_path, os.path.relpath(file_path, download_folder))

    print(f"Website has been compressed into {output_zip_file}")

# Main function to download and zip the website
def main():
    website_url = "https://docs.frac.gg/introduction"  # Replace with your website URL
    download_folder = "frac_website"  # Folder to save the website files
    output_zip_file = "frac.zip"  # Output zip file

    # Start the download process
    download_website(website_url, download_folder)

    # Compress the website folder into a zip file
    zip_website_folder(download_folder, output_zip_file)

if __name__ == "__main__":
    main()
              
