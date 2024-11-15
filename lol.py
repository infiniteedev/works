import os
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import aiofiles
import logging
from tqdm import tqdm
from urllib.robotparser import RobotFileParser

# Configure logging for better monitoring and debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebCrawlerBackup:
    def __init__(self, base_url, backup_dir, max_retries=3, delay=1, max_connections=10):
        """
        Initialize the web crawler for backing up a website.

        Args:
            base_url (str): The base URL of the website to crawl.
            backup_dir (str): The local directory to save the backup files.
            max_retries (int): Maximum number of retry attempts for failed requests.
            delay (float): Delay between retries to prevent overloading the server.
            max_connections (int): Maximum number of concurrent connections for downloading files.
        """
        self.base_url = base_url
        self.backup_dir = backup_dir
        self.visited_urls = set()
        self.files_to_download = set()
        self.max_retries = max_retries
        self.delay = delay
        self.max_connections = max_connections
        self.semaphore = asyncio.Semaphore(self.max_connections)  # Limit the number of concurrent downloads
        self.robot_parser = RobotFileParser()
        self._initialize_robot_parser()

    def _initialize_robot_parser(self):
        """Initialize the robots.txt parser to respect the site's crawling rules."""
        robot_url = urljoin(self.base_url, "/robots.txt")
        self.robot_parser.set_url(robot_url)
        try:
            self.robot_parser.read()
        except Exception as e:
            logger.warning(f"Error reading robots.txt: {str(e)}")

    async def start_crawl(self):
        """Start the website crawling process and file backup."""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)

        # Crawl the website to discover all files to download
        await self._crawl_page(self.base_url)

        # Download the discovered files with a progress bar
        await self._download_files()

    async def _crawl_page(self, url):
        """Crawl a webpage, extract links, and find resources to download.

        Args:
            url (str): The URL of the webpage to crawl.
        """
        if url in self.visited_urls:
            return
        logger.info(f"Crawling: {url}")
        self.visited_urls.add(url)

        try:
            response = await self._get_with_retry(url)
            if response is None:
                return
            soup = BeautifulSoup(response, "html.parser")

            # Add the HTML page to the download list
            self._add_file_for_download(url, response)

            # Extract all internal links (pages to crawl)
            links = soup.find_all("a", href=True)
            for link in links:
                href = link["href"]
                full_url = urljoin(url, href)
                if self._is_internal_url(full_url):
                    await self._crawl_page(full_url)

            # Extract static assets (images, CSS, JS, etc.)
            await self._extract_assets(soup, url)

        except Exception as e:
            logger.error(f"Error while crawling {url}: {str(e)}")

    def _add_file_for_download(self, url, content=None):
        """Add a file (HTML page or other resource) to the download queue.

        Args:
            url (str): The URL of the resource.
            content (str, optional): The content of the page if it's an HTML file.
        """
        parsed_url = urlparse(url)
        path = parsed_url.path if parsed_url.path != '' else 'index.html'

        # Save files to their respective directories based on URL structure
        save_path = self._get_save_path(path)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        self.files_to_download.add((url, save_path))

    def _get_save_path(self, path):
        """Determine the save path for a file based on its type.

        Args:
            path (str): The URL path of the file.

        Returns:
            str: The local file path to save the resource.
        """
        # Normalize path and replace multiple slashes with a single one
        path = path.strip('/')
        if path.endswith(".html"):
            save_path = os.path.join(self.backup_dir, path)
        elif path.endswith((".css", ".js")):
            save_path = os.path.join(self.backup_dir, 'assets', path)
        elif path.endswith((".jpg", ".jpeg", ".png", ".gif", ".svg")):
            save_path = os.path.join(self.backup_dir, 'images', path)
        elif path.endswith((".woff", ".woff2", ".ttf", ".eot")):
            save_path = os.path.join(self.backup_dir, 'fonts', path)
        else:
            save_path = os.path.join(self.backup_dir, 'other', path)
        return save_path

    async def _get_with_retry(self, url):
        """Attempt to GET the URL with retries and a delay in case of failure.

        Args:
            url (str): The URL to retrieve.

        Returns:
            str: The content of the page if successful, else None.
        """
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
        """Download a file asynchronously and save it in the correct directory.

        Args:
            url (str): The URL of the file.
            save_path (str): The local path where the file should be saved.
        """
        async with self.semaphore:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
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
        """Download all files concurrently with a progress bar showing status."""
        total_files = len(self.files_to_download)
        if total_files == 0:
            logger.info("No files to download.")
            return

        # Set up a progress bar
        with tqdm(total=total_files, desc="Downloading files", unit="file") as pbar:
            download_tasks = [self._download_file(url, save_path) for url, save_path in self.files_to_download]

            # Wait for all download tasks to complete
            for task in asyncio.as_completed(download_tasks):
                await task
                pbar.update(1)  # Update progress bar for each completed download

    async def _extract_assets(self, soup, base_url):
        """Extract resources (images, CSS, JS) and schedule them for download.

        Args:
            soup (BeautifulSoup): The parsed HTML page.
            base_url (str): The base URL to resolve relative paths.
        """
        # Extract all resource links (images, CSS, JS)
        for tag in soup.find_all(['img', 'link', 'script'], src=True):
            src = tag.get('src') or tag.get('href')
            full_url = urljoin(base_url, src)
            if self._is_internal_url(full_url):
                self._add_file_for_download(full_url)

        # Also extract links from <a> tags and other href attributes
        for tag in soup.find_all('a', href=True):
            href = tag['href']
            full_url = urljoin(base_url, href)
            if self._is_internal_url(full_url):
                self._add_file_for_download(full_url)

    def _is_internal_url(self, url):
        """Check if a URL is internal, based on the base URL.

        Args:
            url (str): The URL to check.

        Returns:
            bool: True if the URL is internal, False otherwise.
        """
        return urlparse(url).netloc == urlparse(self.base_url).netloc


if __name__ == "__main__":
    # Ask for the base URL and backup directory from the user
    base_url = input("Enter the website URL to crawl (e.g., https://example.com): ").strip()
    backup_dir = input("Enter the directory to save the backup files (e.g., 'backup'): ").strip()

    # Check if backup directory is provided, if not, set a default value
    if not backup_dir:
        backup_dir = "backup"

    # Initialize the web crawler and start crawling and downloading
    crawler = WebCrawlerBackup(base_url, backup_dir)
    asyncio.run(crawler.start_crawl())

    logger.info("Crawl and backup completed successfully!")
            
