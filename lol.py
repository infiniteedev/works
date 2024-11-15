import os
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import aiofiles
import logging
from tqdm import tqdm
from urllib.robotparser import RobotFileParser
import time
from collections import deque

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebCrawlerBackup:
    def __init__(self, base_url, backup_dir, max_retries=3, delay=1, max_connections=10):
        self.base_url = base_url
        self.backup_dir = backup_dir
        self.visited_urls = set()
        self.files_to_download = set()
        self.max_retries = max_retries
        self.delay = delay
        self.max_connections = max_connections
        self.robot_parser = RobotFileParser()
        self._initialize_robot_parser()
        self.semaphore = asyncio.Semaphore(self.max_connections)  # Limit the number of concurrent downloads

    def _initialize_robot_parser(self):
        """Initialize the robot.txt parser for the base URL."""
        robot_url = urljoin(self.base_url, "/robots.txt")
        self.robot_parser.set_url(robot_url)
        try:
            self.robot_parser.read()
        except Exception as e:
            logger.warning(f"Error reading robots.txt: {str(e)}")

    async def start_crawl(self):
        """Start crawling the website and back up its content."""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)

        # First, crawl the website to discover all the files to download
        await self._crawl_page(self.base_url)

        # Then, show progress and download the files
        await self._download_files()

    async def _crawl_page(self, url):
        """Crawl a webpage, extract links, and find files to download."""
        if url in self.visited_urls:
            return
        logger.info(f"Crawling: {url}")
        self.visited_urls.add(url)

        try:
            response = await self._get_with_retry(url)
            if response is None:
                return
            soup = BeautifulSoup(response, "html.parser")

            # Add the HTML page to the list of files to be downloaded
            self._add_file_for_download(url, response)

            # Extract all internal links (pages to crawl)
            links = soup.find_all("a", href=True)
            for link in links:
                href = link["href"]
                full_url = urljoin(url, href)
                if self._is_internal_url(full_url):
                    await self._crawl_page(full_url)

            # Extract all assets (images, CSS, JS, etc.)
            await self._extract_assets(soup, url)

        except Exception as e:
            logger.error(f"Error while crawling {url}: {str(e)}")

    def _add_file_for_download(self, url, content=None):
        """Add a file (HTML page or other resource) to the list of files to download."""
        parsed_url = urlparse(url)
        path = parsed_url.path if parsed_url.path != '' else 'index.html'
        # Convert path to be safe for file names
        safe_path = path.strip('/').replace('/', '_') + '.html' if not content else path.strip('/')
        save_path = os.path.join(self.backup_dir, safe_path)

        self.files_to_download.add((url, save_path))  # Store both URL and the local save path

    def _is_internal_url(self, url):
        """Checks if the URL is an internal URL based on the base URL."""
        return urlparse(url).netloc == urlparse(self.base_url).netloc

    async def _extract_assets(self, soup, base_url):
        """Extract resources like images, CSS, and JS files and schedule them for download."""
        # Extract all resources such as images, CSS, JS
        for tag in soup.find_all(['img', 'link', 'script'], src=True):
            src = tag.get('src') or tag.get('href')
            full_url = urljoin(base_url, src)
            if self._is_internal_url(full_url):
                self._add_file_for_download(full_url)

        for tag in soup.find_all('link', href=True):
            href = tag['href']
            full_url = urljoin(base_url, href)
            if self._is_internal_url(full_url):
                self._add_file_for_download(full_url)

        for tag in soup.find_all('a', href=True):
            href = tag['href']
            full_url = urljoin(base_url, href)
            if self._is_internal_url(full_url):
                self._add_file_for_download(full_url)

    async def _get_with_retry(self, url):
        """Attempt to GET the URL with retries and delay."""
        attempts = 0
        while attempts < self.max_retries:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            return await response.text()
                        else:
                            logger.warning(f"Failed to retrieve {url}, Status: {response.status}")
                            attempts += 1
            except aiohttp.ClientError as e:
                logger.error(f"Error fetching {url}: {str(e)}")
                attempts += 1
            await asyncio.sleep(self.delay)
        return None

    async def _download_file(self, url, save_path):
        """Download a file asynchronously and save it in the correct directory."""
        async with self.semaphore:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            # Ensure the save directory exists
                            os.makedirs(os.path.dirname(save_path), exist_ok=True)
                            async with aiofiles.open(save_path, 'wb') as f:
                                while True:
                                    chunk = await response.content.read(1024)
                                    if not chunk:
                                        break
                                    await f.write(chunk)
                            logger.info(f"Downloaded: {url}")
                        else:
                            logger.error(f"Failed to download {url}, Status: {response.status}")
            except Exception as e:
                logger.error(f"Error downloading {url}: {str(e)}")

    async def _download_files(self):
        """Download all files concurrently with progress."""
        total_files = len(self.files_to_download)
        if total_files == 0:
            logger.info("No files to download.")
            return

        # Set up progress bar
        with tqdm(total=total_files, desc="Downloading files", unit="file") as pbar:
            download_tasks = []
            for file_url, save_path in self.files_to_download:
                task = self._download_file(file_url, save_path)
                download_tasks.append(task)

            # Wait for all downloads to complete
            for task in download_tasks:
                await task
                pbar.update(1)  # Update progress bar

if __name__ == "__main__":
    base_url = "https://docs.frac.gg/introduction"
    backup_dir = "frac"  # Backup folder named 'frac'

    crawler = WebCrawlerBackup(base_url, backup_dir)

    # Start the crawling and downloading asynchronously
    asyncio.run(crawler.start_crawl())
    logger.info("Crawl and Website is Extracted Completely")                  
