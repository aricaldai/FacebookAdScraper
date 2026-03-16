"""
Facebook Ads Library Scraper - WORKING VERSION
Finds ads by Library ID text directly
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse, parse_qs, unquote
import time
import json
import pandas as pd
from datetime import datetime
import re

class FacebookAdsLibraryScraper:
    def __init__(self, headless=False, ad_type="all"):
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        
        self.ad_type = ad_type
        
        print("🌐 Starting Chrome browser...")
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        self.wait = WebDriverWait(self.driver, 20)
        self.ads_data = []
        self.seen_library_ids = set()

    def is_duplicate(self, library_id):
        if library_id and library_id in self.seen_library_ids:
            return True
        if library_id:
            self.seen_library_ids.add(library_id)
        return False

    def decode_facebook_redirect(self, url):
        try:
            if 'l.facebook.com' in url or 'lm.facebook.com' in url:
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                if 'u' in params:
                    return unquote(params['u'][0])
            return url
        except:
            return url

    def extract_images_from_element(self, element):
        images = []
        try:
            img_elements = element.find_elements(By.TAG_NAME, "img")
            
            for img in img_elements:
                src = (img.get_attribute('src') or 
                       img.get_attribute('data-src') or 
                       img.get_attribute('data-lazy-src'))
                
                if src and 'http' in src:
                    if any(x in src.lower() for x in ['emoji', '/static_', 'icon', 'avatar']):
                        continue
                    
                    if any(x in src for x in ['scontent', 'fbcdn', 'external']):
                        try:
                            width = img.size['width']
                            height = img.size['height']
                            
                            if width > 40 and height > 40:
                                images.append({
                                    'url': src,
                                    'alt': img.get_attribute('alt') or '',
                                    'width': width,
                                    'height': height
                                })
                        except:
                            images.append({
                                'url': src,
                                'alt': img.get_attribute('alt') or '',
                                'width': 'unknown',
                                'height': 'unknown'
                            })
        except:
            pass
        
        return images

    def extract_library_id(self, full_text):
        patterns = [
            r'Library ID:\s*(\d+)',
            r'Ad Library ID:\s*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return ""

    def scroll_and_expand(self, scroll_pause_time=3, max_scrolls=10):
        scrolls = 0
        
        while scrolls < max_scrolls:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause_time)
            scrolls += 1
            print(f"Scroll {scrolls}/{max_scrolls}")
        
        print("⏳ Waiting...")
        time.sleep(3)

    def extract_all_links(self, element):
        links = []
        try:
            link_elements = element.find_elements(By.TAG_NAME, "a")
            for link in link_elements:
                href = link.get_attribute('href')
                if href and href.startswith('http'):
                    links.append({
                        'url': href,
                        'text': link.text.strip(),
                        'aria_label': link.get_attribute('aria-label') or ''
                    })
        except:
            pass
        return links

    def extract_page_name(self, full_text, links):
        for link in links:
            text = link['text']
            if text and 3 < len(text) < 100:
                skip_phrases = ['this ad', 'multiple versions', 'see ad', 'started running', 
                               'open dropdown', 'eu transparency', 'see all', 'library id']
                if not any(skip in text.lower() for skip in skip_phrases):
                    if '.' not in text or ' ' in text:
                        return text
        
        lines = [l.strip() for l in full_text.split('\n') if l.strip()]
        for line in lines[:10]:
            if 3 < len(line) < 100:
                skip = ['active', 'library id', 'started running', 'platforms', 
                       'see ad', 'sponsored', 'open dropdown', 'this ad']
                if not any(s in line.lower() for s in skip):
                    return line
        
        return ""

    def extract_ad_data(self, ad_element, index):
        full_text = ad_element.text
        
        ad_data = {
            'ad_position': index,
            'full_text': full_text,
            'links': [],
            'images': [],
            'library_id': '',
            'page_name': '',
            'ad_creative': '',
            'destination_url': '',
            'display_url': '',
            'cta_button': '',
            'platforms': [],
            'date_info': '',
            'impressions': '',
            'scraped_at': datetime.now().isoformat()
        }
        
        try:
            ad_data['library_id'] = self.extract_library_id(full_text)
            ad_data['links'] = self.extract_all_links(ad_element)
            ad_data['images'] = self.extract_images_from_element(ad_element)
            ad_data['page_name'] = self.extract_page_name(full_text, ad_data['links'])
            
            for link in ad_data['links']:
                url = link['url']
                
                if 'facebook.com' not in url or 'l.facebook.com' in url:
                    real_url = self.decode_facebook_redirect(url)
                    
                    if real_url and real_url != url:
                        domain = urlparse(real_url).netloc.lower()
                        if domain and 'facebook.com' not in domain and 'instagram.com' not in domain:
                            ad_data['destination_url'] = real_url
                            break
            
            display_url_match = re.search(r'([A-Z0-9]+\.[A-Z]{2,})', full_text)
            if display_url_match:
                ad_data['display_url'] = display_url_match.group(1)
            
            cta_patterns = [
                r'(Shop [Nn]ow)', r'(Learn [Mm]ore)', r'(Get [Dd]irections)',
                r'(Sign [Uu]p)', r'(Buy [Nn]ow)', r'(Download)',
                r'(Visit [^\n]+)', r'(See [Mm]ore)', r'(Get [Ss]tarted)', r'(Install [Nn]ow)'
            ]
            for pattern in cta_patterns:
                cta_match = re.search(pattern, full_text)
                if cta_match:
                    ad_data['cta_button'] = cta_match.group(1).strip()
                    break
            
            platforms = []
            if 'facebook' in full_text.lower():
                platforms.append('Facebook')
            if 'instagram' in full_text.lower():
                platforms.append('Instagram')
            if 'messenger' in full_text.lower():
                platforms.append('Messenger')
            ad_data['platforms'] = platforms if platforms else ['Facebook']
            
            date_match = re.search(r'Started running on ([^\n]+)', full_text)
            if date_match:
                ad_data['date_info'] = date_match.group(1).strip()
            
            impressions_match = re.search(r'([\d,]+-[\d,]+)\s*impressions', full_text, re.IGNORECASE)
            if impressions_match:
                ad_data['impressions'] = impressions_match.group(1)
            
            lines = [l.strip() for l in full_text.split('\n') if l.strip()]
            creative_lines = []
            skip_keywords = ['active', 'library id', 'started running', 'platforms', 
                           'see ad', 'sponsored', 'open dropdown', 'this ad']
            
            capturing = False
            for line in lines:
                line_lower = line.lower()
                
                if 'sponsored' in line_lower:
                    capturing = True
                    continue
                
                if re.match(r'^[A-Z0-9]+\.[A-Z]{2,}$', line) or line in ['Shop Now', 'Learn more']:
                    break
                
                if capturing and len(line) > 20:
                    if not any(skip in line_lower for skip in skip_keywords):
                        creative_lines.append(line)
                        if len(creative_lines) >= 5:
                            break
            
            if creative_lines:
                ad_data['ad_creative'] = '\n'.join(creative_lines)
            
        except Exception as e:
            print(f"    ⚠ Error: {e}")
        
        return ad_data

    def scrape_ads(self, url, max_ads=100, scroll_pause=3):
        try:
            print(f"🚀 Loading URL...")
            self.driver.get(url)
            time.sleep(8)
            
            print("📜 Scrolling...")
            self.scroll_and_expand(scroll_pause_time=scroll_pause, max_scrolls=10)
            
            print("🔍 Finding ads by Library ID text...")
            
            # NEW APPROACH: Find all elements containing "Library ID:" text
            library_id_elements = self.driver.find_elements(By.XPATH, 
                "//*[contains(text(), 'Library ID:')]")
            
            print(f"Found {len(library_id_elements)} elements with 'Library ID:' text\n")
            
            ad_containers = []
            
            # For each Library ID element, find its ad container
            for idx, elem in enumerate(library_id_elements[:max_ads * 2], 1):
                try:
                    # Get the parent that contains the full ad
                    # Start from the element with Library ID and go up
                    best_parent = None
                    
                    # Try going up 1-7 levels
                    current = elem
                    for level in range(1, 8):
                        current = current.find_element(By.XPATH, "..")
                        text = current.text
                        text_len = len(text)
                        
                        # Check if this looks like a single ad:
                        # - Has "Library ID:"
                        # - Has "Sponsored"  
                        # - Reasonable length (200-2000 chars)
                        # - Has exactly 1 Library ID
                        if ('Library ID:' in text and 
                            'Sponsored' in text and 
                            200 < text_len < 2000 and
                            text.count('Library ID:') == 1):
                            best_parent = current
                            break
                    
                    if best_parent and best_parent not in ad_containers:
                        ad_containers.append(best_parent)
                        if idx <= 5:
                            lib_id = self.extract_library_id(best_parent.text)
                            print(f"  ✓ Found ad #{len(ad_containers)}: Library ID {lib_id}")
                    
                except Exception as e:
                    if idx <= 3:
                        print(f"  ❌ Element #{idx} error: {e}")
                    continue
            
            print(f"\n✓ Found {len(ad_containers)} individual ads\n")
            
            if not ad_containers:
                print("❌ No ads found")
                return []
            
            duplicates_skipped = 0
            
            for i, ad in enumerate(ad_containers[:max_ads], 1):
                try:
                    ad_data = self.extract_ad_data(ad, len(self.ads_data) + 1)
                    
                    if not ad_data['library_id']:
                        print(f"[{i}] ❌ No Library ID")
                        continue
                    
                    if self.is_duplicate(ad_data['library_id']):
                        duplicates_skipped += 1
                        print(f"[{i}] ⏭️  Duplicate: {ad_data['library_id']}")
                        continue
                    
                    self.ads_data.append(ad_data)
                    
                    print(f"[{i}] ✓ #{len(self.ads_data)} | ID: {ad_data['library_id']} | {ad_data['page_name'][:30]}")
                    
                except Exception as e:
                    print(f"[{i}] ❌ Error: {e}")
                    continue
            
            print(f"\n✅ Extracted {len(self.ads_data)} unique ads")
            print(f"⏭️  Skipped {duplicates_skipped} duplicates")
            return self.ads_data
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def save_to_json(self, filename='facebook_ads_complete.json'):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.ads_data, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved {filename}")

    def save_to_csv(self, filename='facebook_ads_complete.csv'):
        if not self.ads_data:
            return
        
        flattened = []
        for ad in self.ads_data:
            flattened.append({
                'ad_position': ad['ad_position'],
                'library_id': ad['library_id'],
                'page_name': ad['page_name'],
                'ad_creative': ad['ad_creative'][:500] if ad['ad_creative'] else '',
                'cta_button': ad['cta_button'],
                'destination_url': ad['destination_url'],
                'display_url': ad['display_url'],
                'platforms': ', '.join(ad['platforms']),
                'date_info': ad['date_info'],
                'impressions': ad['impressions'],
                'num_images': len(ad['images']),
                'num_links': len(ad['links']),
                'first_image_url': ad['images'][0]['url'] if ad['images'] else '',
                'scraped_at': ad['scraped_at']
            })
        
        df = pd.DataFrame(flattened)
        df.to_csv(filename, index=False)
        print(f"💾 Saved {filename}")

    def save_readable_report(self, filename='facebook_ads_report.txt'):
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 100 + "\n")
            f.write("FACEBOOK ADS LIBRARY - SCRAPING REPORT\n")
            f.write("=" * 100 + "\n\n")
            
            f.write(f"Total Ads: {len(self.ads_data)}\n")
            f.write(f"Scraped: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"With Library ID: {sum(1 for ad in self.ads_data if ad['library_id'])}\n")
            f.write(f"With Images: {sum(1 for ad in self.ads_data if ad['images'])}\n")
            f.write(f"With URL: {sum(1 for ad in self.ads_data if ad['destination_url'])}\n\n")
            f.write("=" * 100 + "\n\n")
            
            for i, ad in enumerate(self.ads_data, 1):
                f.write(f"\n{'='*100}\n")
                f.write(f"AD #{i}\n")
                f.write(f"{'='*100}\n\n")
                
                f.write(f"Library ID: {ad['library_id']}\n")
                f.write(f"Page: {ad['page_name']}\n")
                f.write(f"Date: {ad['date_info']}\n")
                f.write(f"Platforms: {', '.join(ad['platforms'])}\n")
                f.write(f"CTA: {ad['cta_button']}\n")
                f.write(f"Destination URL: {ad['destination_url']}\n")
                f.write(f"Display URL: {ad['display_url']}\n")
                f.write(f"Impressions: {ad['impressions']}\n")
                f.write(f"Images: {len(ad['images'])}\n")
                f.write(f"Links: {len(ad['links'])}\n\n")
                
                if ad['ad_creative']:
                    f.write("Ad Creative:\n")
                    f.write(ad['ad_creative'] + "\n\n")
                
                if ad['images']:
                    f.write(f"Images ({len(ad['images'])}):\n")
                    for idx, img in enumerate(ad['images'], 1):
                        f.write(f"  {idx}. {img['url']} ({img['width']}x{img['height']})\n")
                    f.write("\n")
                
                f.write("-" * 100 + "\n\n")
        
        print(f"📄 Saved {filename}")

    def close(self):
        self.driver.quit()


if __name__ == "__main__":
    url = "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&q=watches&search_type=keyword_unordered"
    
    print("\n" + "=" * 80)
    print("FACEBOOK ADS SCRAPER - LIBRARY ID METHOD")
    print("=" * 80 + "\n")
    
    scraper = FacebookAdsLibraryScraper(headless=False, ad_type="all")
    
    try:
        ads = scraper.scrape_ads(url=url, max_ads=100, scroll_pause=3)
        
        if ads:
            scraper.save_to_json('facebook_ads_complete.json')
            scraper.save_to_csv('facebook_ads_complete.csv')
            scraper.save_readable_report('facebook_ads_report.txt')
            
            print("\n" + "=" * 80)
            print("SUCCESS!")
            print("=" * 80)
            print(f"✓ Total ads: {len(ads)}")
            print(f"✓ With Library ID: {sum(1 for ad in ads if ad['library_id'])}")
            print(f"✓ With images: {sum(1 for ad in ads if ad['images'])}")
            print(f"✓ With URL: {sum(1 for ad in ads if ad['destination_url'])}")
            print(f"✓ With CTA: {sum(1 for ad in ads if ad['cta_button'])}")
            print("=" * 80 + "\n")
    
    except KeyboardInterrupt:
        print("\n⚠️  Stopped")
    finally:
        scraper.close()