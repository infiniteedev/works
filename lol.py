import os
import requests
import zipfile
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from pathlib import Path
from time import sleep
from concurrent.futures import ThreadPoolExecutor, as_completed
import mimetypes
from tqdm import tqdm

# Constants
MAX_THREADS = 100  # Adjust number of concurrent downloads as needed
MAX_RETRIES = 5    # Number of retries for failed downloads
RETRY_DELAY = 2    # Delay between retries (in seconds)

# Function to create directories if they don't exist
def create_directories(path):
    if not os.path.exists(path):
        os.makedirs(path)

# Function to download a page (HTML)
def download_page(url):
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Raise error for bad status codes
            return response.text
        except requests.exceptions.RequestException as e:
            attempt += 1
            print(f"Error downloading page {url} (Attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                sleep(RETRY_DELAY)
            else:
                print(f"Failed to download page: {url}")
                return None

# Function to download any file (CSS, JS, Images, Fonts, PDFs, etc.)
def download_file(url, base_url, download_folder, progress_bar):
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            file_url = urljoin(base_url, url)
            response = requests.get(file_url, timeout=10, stream=True)
            response.raise_for_status()

            # Get the file name and prepare the path for saving
            parsed_url = urlparse(file_url)
            file_path = os.path.join(download_folder, parsed_url.netloc, parsed_url.path.lstrip("/"))

            # Ensure the directory exists
            create_directories(os.path.dirname(file_path))

            # Handle special cases for files without extensions (directories)
            if file_path.endswith('/'):
                file_path += 'index.html'

            # Download the file in chunks and save it
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        file.write(chunk)
            
            progress_bar.update(1)  # Update the progress bar for each file downloaded
            print(f"Downloaded: {file_url}")
            return True
        except requests.exceptions.RequestException as e:
            attempt += 1
            print(f"Error downloading file {url} (Attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                sleep(RETRY_DELAY)
            else:
                print(f"Failed to download file: {url}")
                return False

# Function to fix links in HTML pages (internal links to local paths)
def fix_html_links(html, base_url, download_folder):
    soup = BeautifulSoup(html, "lxml")

    # Fix internal links in <a href="...">
    for link in soup.find_all("a", href=True):
        link_url = link['href']
        if link_url.startswith('/'):  # Handle relative links
            link['href'] = os.path.join(download_folder, link_url.lstrip('/'))
        elif base_url in link_url:  # Handle full internal URLs
            link['href'] = os.path.join(download_folder, urlparse(link_url).path.lstrip('/'))

    # Fix resources (CSS, JS, Images, Fonts, etc.)
    for tag in soup.find_all(['img', 'link', 'script'], src=True):
        resource_url = tag.get('src') or tag.get('href')
        if resource_url.startswith('/'):  # Handle relative links
            tag['src'] = os.path.join(download_folder, resource_url.lstrip('/'))
        elif base_url in resource_url:  # Handle full internal URLs
            tag['src'] = os.path.join(download_folder, urlparse(resource_url).path.lstrip('/'))

    return str(soup)

# Function to crawl and download all pages and resources
def crawl_and_download(url, base_url, download_folder, visited, executor, progress_bar):
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

    # Queue links to be crawled concurrently
    for link in soup.find_all("a", href=True):
        link_url = link['href']
        if link_url.startswith('/'):  # Relative link
            link_url = urljoin(base_url, link_url)
        if link_url not in visited and base_url in link_url:
            visited.add(link_url)
            links_to_crawl.append(link_url)

    # Download resources (CSS, JS, Images, Fonts) concurrently
    futures = []
    for resource_tag in soup.find_all(['img', 'link', 'script'], src=True):
        resource_url = resource_tag.get('src') or resource_tag.get('href')
        futures.append(executor.submit(download_file, resource_url, base_url, download_folder, progress_bar))

    # Add internal links to the executor for crawling
    for link in links_to_crawl:
        futures.append(executor.submit(crawl_and_download, link, base_url, download_folder, visited, executor, progress_bar))

    # Wait for all downloads to finish
    for future in as_completed(futures):
        future.result()

# Function to start the crawl and download process
def download_website(url, download_folder):
    base_url = urlparse(url).scheme + "://" + urlparse(url).hostname  # For base URL

    # Create the folder where we will save the site
    create_directories(download_folder)

    # Set of visited URLs
    visited = set()
    visited.add(url)

    # ThreadPoolExecutor for concurrent downloads
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        # Set a rough estimate of the number of files to download for the progress bar
        total_files = 1000
        progress_bar = tqdm(total=total_files, desc="Downloading Website", unit="file")

        # Start the download process with the root URL
        executor.submit(crawl_and_download, url, base_url, download_folder, visited, executor, progress_bar)

        progress_bar.close()

    print("Download completed!")

# Function to zip the downloaded files
def zip_website_folder(download_folder, output_zip_file):
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
            
