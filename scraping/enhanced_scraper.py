"""
Enhanced Web Scraper for Public Benefits Websites
Handles dynamic JavaScript sites, PDFs, and ACCORDION/COLLAPSIBLE content
"""

import asyncio
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout
import markdownify
import PyPDF2
import requests
from bs4 import BeautifulSoup


class EnhancedWebScraper:
    def __init__(self, output_file: str = "scraped_data.jsonl", headless: bool = True):
        self.output_file = output_file
        self.headless = headless
        self.browser = None
        self.context = None
        
    async def initialize(self):
        """Initialize Playwright browser"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        
        # Create context with reasonable settings
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        # Block unnecessary resources to speed up loading
        await self.context.route("**/*", self._route_handler)
    
    async def _route_handler(self, route):
        """Block unnecessary resources to speed up page loads"""
        resource_type = route.request.resource_type
        url = route.request.url
        
        # Block common tracking/analytics domains
        blocked_domains = [
            'google-analytics.com',
            'googletagmanager.com',
            'facebook.net',
            'doubleclick.net',
            'hotjar.com',
            'analytics',
        ]
        
        if any(domain in url for domain in blocked_domains):
            await route.abort()
        elif resource_type in ['image', 'media', 'font']:
            # Optionally block images/media/fonts to speed up
            await route.continue_()
        else:
            await route.continue_()
    
    async def close(self):
        """Clean up resources"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def expand_all_accordions(self, page: Page) -> int:
        """
        Find and click all accordion/collapsible elements to reveal hidden content
        Returns the number of elements clicked
        """
        clicks_performed = 0
        
        # Common accordion/collapsible selectors
        accordion_selectors = [
            # Generic patterns
            '[role="button"][aria-expanded="false"]',
            'button[aria-expanded="false"]',
            '.accordion:not(.active)',
            '.accordion-button.collapsed',
            '.accordion-header:not(.active)',
            '[data-toggle="collapse"]:not(.collapsed)',
            'summary',  # HTML5 details/summary
            
            # Common class names
            '.collapsible:not(.active)',
            '.expandable:not(.expanded)',
            '.toggle:not(.active)',
            '.dropdown-toggle',
            
            # Common attributes
            '[data-accordion]',
            '[data-collapsible]',
            '[data-toggle]',
            '[aria-controls]',
            
            # MUI/Material-UI
            '.MuiAccordion-root:not(.Mui-expanded)',
            '.MuiAccordionSummary-root',
            
            # Bootstrap
            '.collapse:not(.show)',
            
            # Custom patterns (add site-specific ones here)
            '.faq-question',
            '.question',
            '.expandable-section',
        ]
        
        print("  Expanding accordions and collapsible content...")
        
        # Try each selector
        for selector in accordion_selectors:
            try:
                # Find all matching elements
                elements = await page.query_selector_all(selector)
                
                for element in elements:
                    try:
                        # Check if element is visible
                        is_visible = await element.is_visible()
                        if not is_visible:
                            continue
                        
                        # Check if it's actually clickable (has click handler or is a button)
                        is_clickable = await element.evaluate("""
                            (element) => {
                                // Check if it's a button or has click handlers
                                if (element.tagName === 'BUTTON' || element.tagName === 'SUMMARY') return true;
                                if (element.onclick) return true;
                                if (element.getAttribute('role') === 'button') return true;
                                
                                // Check for common accordion attributes
                                const hasAccordionAttrs = 
                                    element.hasAttribute('aria-expanded') ||
                                    element.hasAttribute('data-toggle') ||
                                    element.hasAttribute('data-accordion') ||
                                    element.hasAttribute('data-collapsible');
                                
                                return hasAccordionAttrs;
                            }
                        """)
                        
                        if is_clickable:
                            # Scroll element into view
                            await element.scroll_into_view_if_needed()
                            await asyncio.sleep(0.1)
                            
                            # Try to click
                            await element.click(timeout=1000)
                            clicks_performed += 1
                            
                            # Small delay to allow content to expand
                            await asyncio.sleep(0.3)
                            
                    except Exception as e:
                        # Individual element click failed, continue to next
                        continue
                        
            except Exception as e:
                # Selector not found or error, continue to next selector
                continue
        
        # Also try expanding HTML5 details elements via JavaScript
        try:
            details_expanded = await page.evaluate("""
                () => {
                    const details = document.querySelectorAll('details:not([open])');
                    details.forEach(d => d.open = true);
                    return details.length;
                }
            """)
            clicks_performed += details_expanded
        except:
            pass
        
        print(f"  ✓ Expanded {clicks_performed} accordion/collapsible elements")
        
        # Wait a bit for all content to load after expanding
        if clicks_performed > 0:
            await asyncio.sleep(2)
        
        return clicks_performed
    
    async def scroll_page(self, page: Page):
        """Scroll through the page to trigger lazy-loaded content"""
        try:
            await page.evaluate("""
                async () => {
                    const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
                    const scrollHeight = document.body.scrollHeight;
                    const viewportHeight = window.innerHeight;
                    const scrollSteps = Math.ceil(scrollHeight / viewportHeight);
                    
                    for (let i = 0; i < scrollSteps; i++) {
                        window.scrollTo(0, viewportHeight * i);
                        await delay(200);
                    }
                    
                    // Scroll back to top
                    window.scrollTo(0, 0);
                    await delay(200);
                }
            """)
        except:
            pass
    
    def extract_program_name(self, url: str, page_title: str, content: str) -> str:
        """Extract program name from URL, title, or content"""
        # Try to extract from URL
        path = urlparse(url).path
        
        # Common patterns
        if 'calfresh' in path.lower() or 'calfresh' in page_title.lower():
            return "CalFresh"
        if 'snap' in path.lower() or 'snap' in page_title.lower():
            return "SNAP (Food Stamps)"
        if 'medi-cal' in path.lower() or 'medi-cal' in page_title.lower():
            return "Medi-Cal"
        if 'calworks' in path.lower() or 'calworks' in page_title.lower():
            return "CalWORKs"
        if 'wic' in path.lower() or 'wic' in page_title.lower():
            return "WIC"
        
        # Try to extract from title
        if page_title:
            # Remove common suffixes
            clean_title = re.sub(r'\s*[-|]\s*.*$', '', page_title)
            return clean_title.strip()
        
        # Fallback to domain name
        domain = urlparse(url).netloc
        return domain.replace('www.', '').split('.')[0].title()
    
    def extract_page_title(self, html: str, browser_title: str) -> str:
        """Extract the main page title/heading from the HTML content"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script, style, nav, footer, header
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()
        
        # Try to find the main title in order of preference
        
        # 1. Look for h1 in main content areas
        for container in ['main', 'article', '[role="main"]', '.content', '.main-content']:
            main_area = soup.select_one(container)
            if main_area:
                h1 = main_area.find('h1')
                if h1 and h1.get_text().strip():
                    return self.clean_heading(h1.get_text())
        
        # 2. Look for any h1 on the page
        h1 = soup.find('h1')
        if h1 and h1.get_text().strip():
            return self.clean_heading(h1.get_text())
        
        # 3. Look for first h2 if no h1
        h2 = soup.find('h2')
        if h2 and h2.get_text().strip():
            return self.clean_heading(h2.get_text())
        
        # 4. Use browser title as fallback
        if browser_title:
            return browser_title.strip()
        
        # 5. Last resort
        return "Untitled Page"
    
    def clean_heading(self, text: str) -> str:
        """Clean heading text"""
        # Remove anchor links, extra whitespace
        text = re.sub(r'#[\w-]+$', '', text)
        return text.strip()
    
    def extract_sections_from_html(self, html: str, url: str) -> List[Dict]:
        """Extract sections from HTML content with preserved table structure"""
        soup = BeautifulSoup(html, 'html.parser')
        sections = []
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()
        
        # Find all heading elements
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        
        for idx, heading in enumerate(headings):
            section_id = f"{idx+1:03d}_{self._slugify(heading.get_text())}"
            heading_text = self.clean_heading(heading.get_text())
            
            # Get content until next heading
            content_elements = []
            current = heading.find_next_sibling()
            
            while current and current.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                content_elements.append(current)
                current = current.find_next_sibling()
            
            # Check if there are tables in this section
            has_tables = any(elem.name == 'table' or elem.find('table') for elem in content_elements)
            
            # Convert to markdown with table preservation
            content_html = '\n'.join(str(elem) for elem in content_elements)
            
            # Use markdownify with table support
            markdown_content = markdownify.markdownify(
                content_html,
                heading_style="ATX",
                bullets="-",
                strip=['a']  # Remove link tags but keep text
            ).strip()
            
            # Post-process tables to ensure proper formatting
            if has_tables:
                markdown_content = self._ensure_table_formatting(markdown_content)
            
            if markdown_content:  # Only add sections with content
                sections.append({
                    "section_id": section_id,
                    "heading": heading_text,
                    "markdown": markdown_content,
                    "order": idx + 1
                })
        
        # If no sections found, create one section with all content
        if not sections:
            # Get main content area
            main_content = soup.find('main') or soup.find('article') or soup.body
            if main_content:
                has_tables = main_content.find('table') is not None
                
                markdown_content = markdownify.markdownify(
                    str(main_content),
                    heading_style="ATX",
                    bullets="-",
                    strip=['a']
                ).strip()
                
                if has_tables:
                    markdown_content = self._ensure_table_formatting(markdown_content)
                
                sections.append({
                    "section_id": "001_content",
                    "heading": "Main Content",
                    "markdown": markdown_content,
                    "order": 1
                })
        
        return sections
    
    def _ensure_table_formatting(self, markdown: str) -> str:
        """
        Ensure tables are properly formatted in markdown.
        Adds metadata for better RAG retrieval.
        """
        # Split by tables
        lines = markdown.split('\n')
        result = []
        in_table = False
        table_buffer = []
        
        for line in lines:
            # Detect table rows (lines with |)
            if '|' in line and line.strip().startswith('|'):
                if not in_table:
                    # Starting a new table
                    in_table = True
                    result.append('\n**[TABLE START]**\n')
                table_buffer.append(line)
            elif in_table and line.strip().startswith('|'):
                table_buffer.append(line)
            else:
                if in_table:
                    # End of table
                    in_table = False
                    # Add the table
                    result.extend(table_buffer)
                    result.append('\n**[TABLE END]**\n')
                    table_buffer = []
                result.append(line)
        
        # Handle case where table is at the end
        if in_table and table_buffer:
            result.extend(table_buffer)
            result.append('\n**[TABLE END]**\n')
        
        return '\n'.join(result)
    
    def _slugify(self, text: str) -> str:
        """Convert text to slug format"""
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '_', text)
        return text[:50]  # Limit length
    
    def _detect_table_in_text(self, text: str) -> bool:
        """
        Detect if text contains table-like structures.
        Looks for patterns indicating tabular data.
        """
        lines = text.split('\n')
        
        # Look for multiple lines with similar structure
        # Common patterns: numbers, dollar signs, percentages aligned
        aligned_pattern_count = 0
        
        for line in lines[:20]:  # Check first 20 lines
            # Check if line has multiple numeric values or dollar amounts
            if re.findall(r'\$[\d,]+|\d+%|\d+\.\d+|\d+', line):
                num_count = len(re.findall(r'\$[\d,]+|\d+%|\d+\.\d+|\d+', line))
                if num_count >= 2:  # At least 2 numeric values suggest a table row
                    aligned_pattern_count += 1
        
        # If multiple lines have this pattern, likely a table
        return aligned_pattern_count >= 3
    
    def _format_pdf_table(self, text: str) -> str:
        """
        Format PDF table text to be more markdown-friendly.
        Adds table markers for RAG identification.
        """
        lines = text.split('\n')
        result = []
        in_table_section = False
        consecutive_data_rows = 0
        
        for line in lines:
            # Check if this line looks like table data
            has_data = bool(re.findall(r'\$[\d,]+|\d+%|\d+\.\d+', line))
            
            if has_data:
                if not in_table_section and consecutive_data_rows == 0:
                    result.append('\n**[TABLE START]**\n')
                    in_table_section = True
                consecutive_data_rows += 1
                result.append(line)
            else:
                if in_table_section and consecutive_data_rows >= 2:
                    result.append('\n**[TABLE END]**\n')
                    in_table_section = False
                consecutive_data_rows = 0
                result.append(line)
        
        # Close table if still open at end
        if in_table_section:
            result.append('\n**[TABLE END]**\n')
        
        return '\n'.join(result)
    
    async def scrape_with_playwright(self, url: str, max_retries: int = 3) -> Optional[Dict]:
        """Scrape a dynamic website using Playwright with accordion expansion"""
        for attempt in range(max_retries):
            try:
                page = await self.context.new_page()
                
                # Navigate with better wait strategy
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                except PlaywrightTimeout:
                    print(f"  Timeout on domcontentloaded for {url}, trying with load...")
                    await page.goto(url, wait_until='load', timeout=30000)
                
                # Wait a bit for dynamic content
                await asyncio.sleep(2)
                
                # Try to wait for main content indicators
                try:
                    await page.wait_for_selector('main, article, [role="main"], .content', timeout=5000)
                except PlaywrightTimeout:
                    print(f"  No main content selector found, continuing anyway...")
                
                # IMPORTANT: Scroll through page to trigger lazy loading
                await self.scroll_page(page)
                
                # IMPORTANT: Expand all accordions/collapsible content
                clicks = await self.expand_all_accordions(page)
                
                # Wait a bit more for any animations to complete
                await asyncio.sleep(1)
                
                # Get page data AFTER expanding accordions
                title = await page.title()
                html = await page.content()
                
                await page.close()
                
                # Extract sections
                sections = self.extract_sections_from_html(html, url)
                program_name = self.extract_program_name(url, title, html)
                page_title = self.extract_page_title(html, title)
                
                return {
                    "source_url": url,
                    "program_name": program_name,
                    "page_title": page_title,
                    "captured_at": datetime.now().isoformat(),
                    "sections": sections
                }
                
            except Exception as e:
                print(f"  Attempt {attempt + 1} failed for {url}: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    print(f"  Failed to scrape {url} after {max_retries} attempts")
                    return None
            finally:
                if 'page' in locals():
                    await page.close()
        
        return None
    
    def scrape_pdf(self, url: str) -> Optional[Dict]:
        """Scrape a PDF document"""
        try:
            # Download PDF
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Create a temporary file (works on Windows, Mac, Linux)
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(response.content)
                pdf_path = tmp_file.name
            
            try:
                # Extract text
                sections = []
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    
                    for page_num, page in enumerate(pdf_reader.pages):
                        text = page.extract_text()
                        
                        if text.strip():
                            # Try to detect if page contains table-like structures
                            # Look for patterns with multiple columns/rows
                            has_table = self._detect_table_in_text(text)
                            
                            # If table detected, preserve formatting better
                            if has_table:
                                text = self._format_pdf_table(text)
                            
                            sections.append({
                                "section_id": f"{page_num+1:03d}_page_{page_num+1}",
                                "heading": f"Page {page_num + 1}",
                                "markdown": text.strip(),
                                "order": page_num + 1
                            })
                
                # Extract program name from filename
                filename = urlparse(url).path.split('/')[-1]
                program_name = filename.replace('.pdf', '').replace('_', ' ').replace('-', ' ').title()
                
                return {
                    "source_url": url,
                    "program_name": program_name,
                    "page_title": program_name,  # For PDFs, use filename as title
                    "captured_at": datetime.now().isoformat(),
                    "sections": sections
                }
                
            finally:
                # Clean up temporary file
                try:
                    Path(pdf_path).unlink()
                except:
                    pass
            
        except Exception as e:
            print(f"  Failed to scrape PDF {url}: {str(e)}")
            return None
    
    def is_pdf_url(self, url: str) -> bool:
        """Check if URL points to a PDF"""
        return url.lower().endswith('.pdf') or 'pdf' in url.lower()
    
    async def scrape_urls(self, urls: List[str]):
        """Scrape multiple URLs and save to JSONL"""
        await self.initialize()
        
        results = []
        
        for idx, url in enumerate(urls, 1):
            print(f"\nScraping {idx}/{len(urls)}: {url}")
            
            if self.is_pdf_url(url):
                result = self.scrape_pdf(url)
            else:
                result = await self.scrape_with_playwright(url)
            
            if result:
                results.append(result)
                # Append to JSONL file immediately
                with open(self.output_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(result, ensure_ascii=False) + '\n')
                print(f"  ✓ Successfully scraped and saved")
            else:
                print(f"  ✗ Failed to scrape")
            
            # Small delay between requests
            await asyncio.sleep(1)
        
        await self.close()
        
        print(f"\n{'='*60}")
        print(f"Scraping complete!")
        print(f"Successfully scraped: {len(results)}/{len(urls)} URLs")
        print(f"Output saved to: {self.output_file}")
        print(f"{'='*60}")
        
        return results


def load_urls_from_file(file_path: str) -> List[str]:
    """
    Load URLs from a text file (one URL per line)
    Automatically handles:
    - Empty lines (skipped)
    - Lines starting with # (treated as comments, skipped)
    - Leading/trailing whitespace (stripped)
    """
    urls = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                # Strip whitespace
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Validate URL format (basic check)
                if line.startswith('http://') or line.startswith('https://'):
                    urls.append(line)
                else:
                    print(f"Warning: Line {line_num} doesn't look like a valid URL: {line}")
        
        print(f"Loaded {len(urls)} URLs from {file_path}")
        return urls
        
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found!")
        print(f"Please create a text file with one URL per line.")
        return []
    except Exception as e:
        print(f"Error reading file: {str(e)}")
        return []


async def main():
    """Example usage"""
    
    import sys
    
    # Get URL file path from command line argument, or use default
    if len(sys.argv) > 1:
        url_file = sys.argv[1]
    else:
        url_file = "urls.txt"  # Default file name
    
    # Get output file from command line argument, or use default
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        output_file = "california_benefits.jsonl"  # Default output name
    
    # Load URLs from file
    urls = load_urls_from_file(url_file)
    
    if not urls:
        print("\nNo URLs to scrape. Exiting.")
        print("\nUsage:")
        print(f"  python enhanced_scraper.py <url_file> [output_file]")
        print(f"\nExample:")
        print(f"  python enhanced_scraper.py urls.txt output.jsonl")
        print(f"\nOr create a 'urls.txt' file with one URL per line and run:")
        print(f"  python enhanced_scraper.py")
        return
    
    print(f"\nStarting scraper...")
    print(f"Input: {url_file}")
    print(f"Output: {output_file}")
    print(f"URLs to scrape: {len(urls)}\n")
    
    # Initialize scraper
    scraper = EnhancedWebScraper(output_file=output_file, headless=True)
    
    # Scrape all URLs
    await scraper.scrape_urls(urls)


if __name__ == "__main__":
    # Run the scraper
    asyncio.run(main())
