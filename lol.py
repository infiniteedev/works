import os
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import aiofiles
import logging
from tqdm import tqdm
from urllib.robotparser import RobotFileParser
import mimetypes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebCrawlerBackup:
    def __init__(self, base_url, backup_dir, max_retries=3, delay=1, max_connections=10):
        """
        Initialize the web crawler to backup a website.

        Args:
            base_url (str): The base URL of the website to crawl.
            backup_dir (str): The local directory to save the backup files.
            max_retries (int): Number of retries for failed requests.
            delay (float): Delay between retries.
            max_connections (int): Maximum number of concurrent connections for downloading.
        """
        self.base_url = base_url
        self.backup_dir = backup_dir
        self.visited_urls = set()
        self.files_to_download = set()
        self.max_retries = max_retries
        self.delay = delay
        self.max_connections = max_connections
        self.semaphore = asyncio.Semaphore(self.max_connections)  # Limit concurrent downloads
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
        """Start crawling the website and downloading files."""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)

        # Start crawling the website
        await self._crawl_page(self.base_url)

        # Download files discovered during the crawl
        await self._download_files()

    async def _crawl_page(self, url):
        """Crawl a webpage, extract links and resources to download.

        Args:
            url (str): The URL of the webpage to crawl.
        """
        if url in self.visited_urls:
            return
        logger.info(f"Crawling: {url}")
        self.visited_urls.add(url)

        try:
            # Check if URL is allowed by robots.txt before crawling
            if not self.robot_parser.can_fetch('*', url):
                logger.warning(f"Skipping {url} due to robots.txt rules.")
                return

            response, _ = await self._get_with_retry(url)
            if response is None:
                return
            soup = BeautifulSoup(response, "html.parser")

            # Add HTML page to the download list
            self._add_file_for_download(url, response)

            # Extract internal links (pages to crawl)
            links = soup.find_all("a", href=True)
            for link in links:
                href = link["href"]
                full_url = urljoin(url, href)
                if self._is_internal_url(full_url):
                    await self._crawl_page(full_url)

            # Extract static resources (images, CSS, JS, etc.)
            await self._extract_assets(soup, url)

        except Exception as e:
            logger.error(f"Error while crawling {url}: {str(e)}")

    def _add_file_for_download(self, url, content=None):
        """Add a file (HTML page or other resource) to the list of files to download.

        Args:
            url (str): The URL of the resource.
            content (str, optional): The content of the page if it's an HTML file.
        """
        parsed_url = urlparse(url)
        path = parsed_url.path if parsed_url.path != '' else 'index.html'

        # Normalize path by removing leading slash
        save_path = self._get_save_path(path)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)  # Ensure directory structure exists

        self.files_to_download.add((url, save_path))

    def _get_save_path(self, path):
        """Generate the local path where the file will be saved.

        Args:
            path (str): The URL path of the file.

        Returns:
            str: The local file path to save the resource.
        """
        # Strip leading slashes and avoid empty paths
        path = path.strip('/')
        if not path:
            path = 'index.html'
        
        # Check MIME type based on URL or file extension
        if not mimetypes.guess_type(path)[0]:
            # If MIME type can't be guessed, default to 'text/html'
            path = f"{path}.html" if '.' not in path else path
        
        # Construct the full save path within the backup directory
        save_path = os.path.join(self.backup_dir, path)
        return save_path

    async def _get_with_retry(self, url):
        """Retrieve a URL with retry mechanism in case of failure.

        Args:
            url (str): The URL to retrieve.

        Returns:
            str: The HTML content if successful, else None.
        """
        attempts = 0
        while attempts < self.max_retries:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            return await response.text(), response.headers.get('Content-Type')
                        else:
                            logger.warning(f"Failed to retrieve {url}, Status: {response.status}")
                            attempts += 1
            except aiohttp.ClientError as e:
                logger.error(f"Error fetching {url}: {str(e)}")
                attempts += 1
            await asyncio.sleep(self.delay)
        return None, None

    async def _download_file(self, url, save_path):
        """Download a file and save it locally.

        Args:
            url (str): The URL of the file.
            save_path (str): The local path where the file will be saved.
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
        """Download all discovered files concurrently with a progress bar."""
        total_files = len(self.files_to_download)
        if total_files == 0:
            logger.info("No files to download.")
            return

        # Set up progress bar
        with tqdm(total=total_files, desc="Downloading files", unit="file") as pbar:
            download_tasks = [self._download_file(url, save_path) for url, save_path in self.files_to_download]

            # Wait for all downloads to complete
            for task in asyncio.as_completed(download_tasks):
                await task
                pbar.update(1)  # Update progress bar for each completed download

    async def _extract_assets(self, soup, base_url):
        """Extract all resources (images, CSS, JS, etc.) from the page.

        Args:
            soup (BeautifulSoup): The parsed HTML page.
            base_url (str): The base URL to resolve relative paths.
        """
        # Extract images, CSS, and JS
        for tag in soup.find_all(['img', 'link', 'script'], src=True):
            src = tag.get('src') or tag.get('href')
            full_url = urljoin(base_url, src)
            if self._is_internal_url(full_url):
                self._add_file_for_download(full_url)

        # Also extract links from <a> tags
        for tag in soup.find_all('a', href=True):
            href = tag['href']
            full_url = urljoin(base_url, href)
            if self._is_internal_url(full_url):
                self._add_file_for_download(full_url)

    def _is_internal_url(self, url):
        """Check if the URL is internal (same domain).

        Args:
            url (str): The URL to check.

        Returns:
            bool: True if the URL is internal, False otherwise.
        """
        return urlparse(url).netloc == urlparse(self.base_url).netloc

# Example usage
async def main():
    crawler = WebCrawlerBackup("https://example.com", "./backup")
    await crawler.start_crawl()

if __name__ == "__main__":
    asyncio.run(main())
            
