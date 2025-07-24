import time
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import os
import sys

# CONFIGURATION
SEED_URLS = ["https://example.com"]  # Start with homepage
MAX_DEPTH = 3  # Crawl depth limit
OUTPUT_CSV = "website_data.csv"
SLEEP_TIME = 1  # Seconds between requests
PAGE_LOAD_TIMEOUT = 30  # Seconds for page load
ELEMENT_TIMEOUT = 10  # Seconds for element detection
CHROME_PATH = None  # Set if Chrome is installed in non-standard location

def is_same_domain(url, base_domain):
    """Check if URL belongs to same domain"""
    return urlparse(url).netloc == base_domain

def setup_driver():
    """Configure headless Chrome browser with fallbacks"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--window-size=1280,1024")
    
    try:
        # Try to use ChromeDriverManager first
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        return driver
    except Exception as e:
        print(f"WebDriverManager failed: {str(e)}")
    
    try:
        # Fallback to system PATH Chrome
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        return driver
    except Exception as e:
        print(f"System PATH Chrome failed: {str(e)}")
    
    if CHROME_PATH and os.path.exists(CHROME_PATH):
        try:
            # Use explicitly specified Chrome path
            chrome_options.binary_location = CHROME_PATH
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
            return driver
        except Exception as e:
            print(f"Specified Chrome path failed: {str(e)}")
    
    print("""
    Could not initialize Chrome. Possible solutions:
    1. Install Google Chrome: https://www.google.com/chrome/
    2. Set CHROME_PATH in the script to your Chrome installation
    3. Use a different browser by modifying setup_driver()
    """)
    sys.exit(1)

def js_scrape_page(driver, url):
    """Scrape JS-rendered page using Selenium"""
    try:
        # Navigate to URL with timeout
        driver.get(url)
        
        # Wait for body to load (indicates page is ready)
        WebDriverWait(driver, ELEMENT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Get JS-rendered HTML
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract SEO elements
        title = driver.title.strip()
        meta_desc = soup.find("meta", attrs={"name": "description"})
        meta_desc = meta_desc["content"].strip() if meta_desc else ""
        
        # Content analysis
        try:
            h1 = [h.text.strip() for h in driver.find_elements(By.TAG_NAME, 'h1')]
        except:
            h1 = []
        
        try:
            h2 = [h.text.strip() for h in driver.find_elements(By.TAG_NAME, 'h2')]
        except:
            h2 = []
        
        try:
            body = driver.find_element(By.TAG_NAME, 'body')
            body_text = body.text.replace('\n', ' ').strip()[:5000]  # First 5K chars
        except:
            body_text = ""
        
        # Image analysis
        try:
            images = [img.get_attribute('alt') or '' 
                     for img in driver.find_elements(By.TAG_NAME, 'img')]
        except:
            images = []
        
        return {
            'url': url,
            'title': title,
            'meta_description': meta_desc,
            'h1_headings': ' | '.join(h1),
            'h2_headings': ' | '.join(h2),
            'body_text': body_text,
            'image_alt_texts': ' | '.join(filter(None, images)),
            'word_count': len(body_text.split())
        }, soup
    
    except TimeoutException:
        print(f"  Timeout loading {url}")
        return {
            'url': url,
            'status': 'TIMEOUT',
            'error': f"Page load timeout ({PAGE_LOAD_TIMEOUT}s)"
        }, None
    except Exception as e:
        print(f"  Error scraping {url}: {str(e)}")
        return {
            'url': url,
            'status': 'ERROR',
            'error': str(e)
        }, None

def crawl_site():
    """Main crawling function with JS support"""
    base_domain = urlparse(SEED_URLS[0]).netloc
    visited = set()
    queue = deque([(url, 0) for url in SEED_URLS])
    data = []
    
    # Initialize single browser instance
    driver = setup_driver()
    
    try:
        while queue:
            url, depth = queue.popleft()
            
            # Depth and URL checks
            if depth > MAX_DEPTH:
                continue
            if url in visited:
                continue
                
            visited.add(url)
            print(f"Crawling: {url} (Depth {depth})")
            
            # Scrape page with Selenium
            page_data, soup = js_scrape_page(driver, url)
            data.append(page_data)
            
            # Skip link discovery if we didn't get valid content
            if not soup:
                print(f"  Skipping link discovery for {url}")
                continue
                
            # Get new links using BeautifulSoup (FASTER than Selenium)
            links = soup.find_all('a', href=True)
            print(f"  Found {len(links)} links on page")
            
            for link in links:
                href = link.get('href')
                if not href:
                    continue
                    
                # Normalize URL
                try:
                    abs_url = urljoin(url, href)
                    parsed = urlparse(abs_url)
                    
                    # Filter URLs
                    if not parsed.scheme.startswith('http'):
                        continue
                    if not is_same_domain(abs_url, base_domain):
                        continue
                    if any(ex in abs_url for ex in ["#", "tel:", "mailto:", ".pdf", "?share=", ".jpg", ".png", ".gif"]):
                        continue
                    if abs_url in visited:
                        continue
                    
                    # Add to queue
                    queue.append((abs_url, depth + 1))
                except Exception as e:
                    print(f"  Error processing link {href}: {str(e)}")
                    
            # Be polite to your server
            time.sleep(SLEEP_TIME)
            
    except Exception as e:
        print(f"Fatal error during crawl: {str(e)}")
    finally:
        # Close browser when done
        driver.quit()
    
    return pd.DataFrame(data)

# Execute and save
if __name__ == "__main__":
    print("Starting crawl...")
    df = crawl_site()
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Crawl complete! Saved {len(df)} pages to {OUTPUT_CSV}")
