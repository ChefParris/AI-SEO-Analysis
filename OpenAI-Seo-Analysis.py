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
import openai
import json
import tiktoken

SEED_URLS = ["https://example.com"]
MAX_DEPTH = 2  # Start with 2-3 for testing
OUTPUT_CSV = "website_data.csv"
REPORT_FILE = "seo_analysis_report.md"
SLEEP_TIME = 0.5  # Seconds between requests
PAGE_LOAD_TIMEOUT = 30  # Page load timeout
ELEMENT_TIMEOUT = 10    # Element detection timeout
OPENAI_MODEL = "gpt-4-turbo"  # Use "gpt-3.5-turbo" for faster/cheaper analysis
MAX_TOKENS = 4000  # Adjust based on your OpenAI plan
CHROME_PATH = None

# OpenAI API - ADD YOUR OWN API Key
openai.api_key = "sk-your-openai-api-key-here"  # REPLACE WITH YOUR API KEY

SEO_PROMPT = """
**Website SEO Analysis Task**

Analyze the following website data to identify SEO improvements for organic traffic. 
Provide actionable recommendations with priority levels.

**Data Structure:**
- URL: Page address
- Title: Meta title
- Meta Description: Meta description
- H1 Headings: Main headings
- H2 Headings: Subheadings
- Body Text: First 5000 characters of content
- Image Alt Texts: Alt attributes of images
- Word Count: Approximate content length

**Analysis Framework:**

1. **Technical SEO Audit**:
   - Identify pages with missing or duplicate titles/descriptions
   - Find pages with thin content (<500 words)
   - Check for multiple H1 tags on single pages
   - Identify pages with missing alt text on images

2. **Content Quality Assessment**:
   - Analyze keyword usage in titles and headings
   - Identify content gaps and duplication
   - Evaluate content depth and comprehensiveness
   - Spot opportunities for content expansion

3. **On-Page Optimization**:
   - Recommend title and meta description improvements
   - Suggest heading structure enhancements
   - Identify internal linking opportunities
   - Highlight semantic keyword opportunities

4. **Action Plan**:
   - Create prioritized list of fixes (High/Medium/Low)
   - Provide specific examples with URLs
   - Suggest concrete implementation steps
   - Estimate potential impact on organic traffic

**Output Format:**
- Markdown report with clear sections
- Data-driven recommendations
- SEO best practices justification
- Estimated implementation effort

**Important:** Be brutally honest and focus on actionable insights.
"""

def num_tokens(text, model="gpt-3.5-turbo"):
    """Count tokens for OpenAI models"""
    try:
        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
    except:
        # Fallback token estimation
        return len(text) // 4

def is_same_domain(url, base_domain):
    return urlparse(url).netloc == base_domain

def setup_driver():
    """Configure headless Chrome browser"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        return driver
    except Exception as e1:
        print(f"WebDriverManager failed: {str(e1)}")
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
            return driver
        except Exception as e2:
            print(f"System PATH Chrome failed: {str(e2)}")
            if CHROME_PATH and os.path.exists(CHROME_PATH):
                try:
                    chrome_options.binary_location = CHROME_PATH
                    driver = webdriver.Chrome(options=chrome_options)
                    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
                    return driver
                except Exception as e3:
                    print(f"Specified Chrome path failed: {str(e3)}")
            print("Could not initialize Chrome. Please install it from https://www.google.com/chrome/")
            sys.exit(1)

def js_scrape_page(driver, url):
    """Scrape JS-rendered page using Selenium"""
    try:
        driver.get(url)
        WebDriverWait(driver, ELEMENT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract SEO elements
        title = driver.title.strip()
        
        meta_desc = soup.find("meta", attrs={"name": "description"})
        meta_desc = meta_desc["content"].strip() if meta_desc else ""
        
        # Content analysis
        h1 = [h.text.strip() for h in driver.find_elements(By.TAG_NAME, 'h1')]
        h2 = [h.text.strip() for h in driver.find_elements(By.TAG_NAME, 'h2')]
        
        body = driver.find_element(By.TAG_NAME, 'body')
        body_text = body.text.replace('\n', ' ').strip()[:5000]
        
        # Image analysis
        images = [img.get_attribute('alt') or '' 
                 for img in driver.find_elements(By.TAG_NAME, 'img')]
        
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
        return {'url': url, 'status': 'TIMEOUT'}, None
    except Exception as e:
        return {'url': url, 'status': 'ERROR', 'error': str(e)}, None

def crawl_site():
    """Main crawling function with JS support"""
    base_domain = urlparse(SEED_URLS[0]).netloc
    visited = set()
    queue = deque([(url, 0) for url in SEED_URLS])
    data = []
    
    driver = setup_driver()
    
    try:
        while queue:
            url, depth = queue.popleft()
            
            if depth > MAX_DEPTH or url in visited:
                continue
                
            visited.add(url)
            print(f"Crawling: {url} (Depth {depth})")
            
            page_data, soup = js_scrape_page(driver, url)
            data.append(page_data)
            
            if not soup:
                continue
                
            # Get new links using BeautifulSoup
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                try:
                    abs_url = urljoin(url, href)
                    parsed = urlparse(abs_url)
                    
                    # URL filtering
                    if (not parsed.scheme.startswith('http') 
                        or not is_same_domain(abs_url, base_domain)
                        or any(ex in abs_url for ex in ["#", "tel:", "mailto:", ".pdf", "?share="])
                        or abs_url in visited):
                        continue
                    
                    queue.append((abs_url, depth + 1))
                except Exception as e:
                    print(f"  Error processing link: {str(e)}")
                    continue
                    
            time.sleep(SLEEP_TIME)
            
    except Exception as e:
        print(f"Fatal crawling error: {str(e)}")
    finally:
        driver.quit()
    
    return pd.DataFrame(data)

def analyze_with_openai(df):
    """Send scraped data to OpenAI for SEO analysis"""
    # Prepare data for OpenAI
    sample_size = min(10, len(df))  # Analyze top 10 pages by default
    sampled_df = df.sort_values('word_count', ascending=False).head(sample_size)
    data_str = sampled_df.to_csv(index=False)
    
    # Token management
    prompt_tokens = num_tokens(SEO_PROMPT + data_str)
    if prompt_tokens > MAX_TOKENS:
        data_str = sampled_df.head(5).to_csv(index=False)
    
    print(f"Sending data to OpenAI ({num_tokens(data_str)} tokens)...")
    
    try:
        response = openai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert SEO analyst with 15 years experience."},
                {"role": "user", "content": SEO_PROMPT + "\n\n" + data_str}
            ],
            temperature=0.2,
            max_tokens=2000
        )
        
        report = response.choices[0].message.content
        return report
        
    except Exception as e:
        return f"Error in OpenAI analysis: {str(e)}"

if __name__ == "__main__":
    # Step 1: Crawl website
    print("Starting website crawl...")
    df = crawl_site()
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Crawl complete! Saved {len(df)} pages to {OUTPUT_CSV}")
    
    # Step 2: Analyze with OpenAI
    print("Starting SEO analysis with OpenAI...")
    seo_report = analyze_with_openai(df)
    
    # Step 3: Save report
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(seo_report)
    print(f"SEO analysis saved to {REPORT_FILE}")
    
    # Step 4: Print summary
    print("\n===== SEO REPORT SUMMARY =====")
    if len(seo_report) > 2000:
        print(seo_report[:2000] + "...")
    else:
        print(seo_report)
