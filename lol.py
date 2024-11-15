import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import shutil
import time
from tqdm import tqdm

class WebCrawlerBackup:
    def __init__(self, base_url, backup_dir):
        self.base_url = base_url
        self.backup_dir = backup_dir
        self.visited_urls = set()
        self.files_to_download = set()
        self.sess = requests.Session()  # Using session for connection pooling

    def start_crawl(self):
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
        
        # Step 1: Crawl to collect all files without downloading them
        self._crawl_page(self.base_url)

        # Step 2: Show progress bar and download files
        self._download_files()

    def _crawl_page(self, url):
        """
        Crawls a webpage, extracts links, and finds files to download.
        """
        if url in self.visited_urls:
            return
        print(f"Crawling: {url}")
        self.visited_urls.add(url)

        try:
            response = self.sess.get(url)
            if response.status_code != 200:
                print(f"Skipping {url}, Status Code: {response.status_code}")
                return
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract page HTML and save it (but not yet)
            self._save_page_html(url, response.text)

            # Extract all internal links
            links = soup.find_all("a", href=True)
            for link in links:
                href = link["href"]
                full_url = urljoin(url, href)
                if self._is_internal_url(full_url):
                    self._crawl_page(full_url)

            # Extract all assets (e.g., images, CSS, JS)
            self._extract_assets(soup, url)

        except Exception as e:
            print(f"Error while crawling {url}: {str(e)}")

    def _save_page_html(self, url, html_content):
        """
        Save HTML content of a page into the backup directory (but don't actually download yet).
        """
        parsed_url = urlparse(url)
        path = parsed_url.path if parsed_url.path != '' else 'index.html'
        filename = path.strip('/').replace('/', '_') + '.html'
        save_path = os.path.join(self.backup_dir, filename)
        
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Discovered HTML page: {save_path}")

    def _is_internal_url(self, url):
        """
        Checks if the URL is an internal URL based on the base URL.
        """
        return urlparse(url).netloc == urlparse(self.base_url).netloc

    def _extract_assets(self, soup, base_url):
        """
        Extracts resources like images, CSS, and JS files and schedules them for download.
        """
        # Find all assets (images, CSS, JavaScript, and other files)
        for tag in soup.find_all(['img', 'link', 'script'], src=True):
            src = tag.get('src') or tag.get('href')
            full_url = urljoin(base_url, src)
            if self._is_internal_url(full_url):
                self.files_to_download.add(full_url)

        # Handle CSS links in <link> tags as well
        for tag in soup.find_all('link', href=True):
            href = tag['href']
            full_url = urljoin(base_url, href)
            if self._is_internal_url(full_url):
                self.files_to_download.add(full_url)

        # Handle <a> tags (hyperlinks) with href that might link to non-HTML files
        for tag in soup.find_all('a', href=True):
            href = tag['href']
            full_url = urljoin(base_url, href)
            if self._is_internal_url(full_url):
                self.files_to_download.add(full_url)

    def _download_files(self):
        """
        Download all the files (images, CSS, JS) and preserve the directory structure, with a progress bar.
        """
        total_files = len(self.files_to_download)
        if total_files == 0:
            print("No files to download.")
            return

        print(f"\nTotal files to download: {total_files}")
        # Progress bar using tqdm
        with tqdm(total=total_files, desc="Downloading files", unit="file") as pbar:
            for file_url in self.files_to_download:
                try:
                    parsed_url = urlparse(file_url)
                    file_path = parsed_url.path.strip('/')
                    # Ensure the file path is correct
                    if '.' not in file_path:
                        file_path += '/'  # Treat it as a directory if no extension
                    save_path = os.path.join(self.backup_dir, file_path)
                    
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    
                    # Download the file only if it doesn't exist yet
                    if not os.path.exists(save_path):
                        response = self.sess.get(file_url, stream=True)
                        if response.status_code == 200:
                            with open(save_path, 'wb') as f:
                                shutil.copyfileobj(response.raw, f)
                            pbar.update(1)  # Update progress bar
                        else:
                            print(f"Failed to download {file_url}, Status Code: {response.status_code}")
                except Exception as e:
                    print(f"Error downloading {file_url}: {str(e)}")

if __name__ == "__main__":
    # URL and backup directory for this specific task
    base_url = "https://docs.frac.gg/introduction"
    backup_dir = "frac"  # Backup folder named 'frac'

    crawler = WebCrawlerBackup(base_url, backup_dir)
    crawler.start_crawl()
    print("Crawl and backup completed.")
    
