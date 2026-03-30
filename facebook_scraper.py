"""
Facebook Ads Library Scraper - FINAL VERSION
Clicks modal, then expands "About the advertiser" section
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
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
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.wait = WebDriverWait(self.driver, 20)
        self.ads_data = []
        self.seen_library_ids = set()
        self.advertiser_cache = {}

    def normalize_follower_count(self, text):
        if not text:
            return 0
        text = text.strip().upper().replace(',', '')
        match = re.search(r'([\d.]+)\s*([KMB])?', text)
        if not match:
            return 0
        number = float(match.group(1))
        multiplier = match.group(2)
        if multiplier == 'K':
            return int(number * 1000)
        elif multiplier == 'M':
            return int(number * 1000000)
        elif multiplier == 'B':
            return int(number * 1000000000)
        else:
            return int(number)

    def expand_about_advertiser_section(self):
        try:
            print(f"        📂 Looking for 'About the advertiser' to expand...")
            about_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'About the advertiser')]")
            print(f"        🔍 Found {len(about_elements)} 'About the advertiser' elements")
            for idx, elem in enumerate(about_elements):
                try:
                    if not elem.is_displayed():
                        continue
                    parent = elem.find_element(By.XPATH, "..")
                    role = parent.get_attribute('role')
                    print(f"          #{idx+1}: Parent role={role}")
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                    time.sleep(0.3)
                    try:
                        elem.click()
                        print(f"          ✅ Clicked 'About the advertiser'")
                    except:
                        try:
                            parent.click()
                            print(f"          ✅ Clicked parent of 'About the advertiser'")
                        except:
                            self.driver.execute_script("arguments[0].click();", elem)
                            print(f"          ✅ JS clicked 'About the advertiser'")
                    time.sleep(2)
                    body_text = self.driver.find_element(By.TAG_NAME, "body").text
                    if "followers" in body_text.lower():
                        print(f"          🎉 Section expanded - followers visible!")
                        return True
                except Exception as e:
                    print(f"          ⚠️ Error with element #{idx+1}: {e}")
                    continue
            print(f"        ⚠️ Could not expand 'About the advertiser'")
            return False
        except Exception as e:
            print(f"        ❌ Error expanding section: {e}")
            return False

    def click_see_ad_details(self, ad_container):
        try:
            print(f"        🔎 Looking for 'See ad details' button...")
            container_text = ad_container.text
            if "About the advertiser" in container_text:
                print(f"        ✓ 'About the advertiser' already visible in container!")
                return True
            button_variations = ["See ad details", "see ad details", "See details"]
            for text_variant in button_variations:
                try:
                    elements = ad_container.find_elements(By.XPATH, f".//*[contains(text(), '{text_variant}')]")
                    print(f"        🔍 Found {len(elements)} elements with '{text_variant}'")
                    for idx, elem in enumerate(elements):
                        try:
                            if not elem.is_displayed():
                                continue
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                            time.sleep(0.5)
                            print(f"          🖱️  Clicking '{text_variant}'...")
                            try:
                                elem.click()
                            except:
                                self.driver.execute_script("arguments[0].click();", elem)
                            print(f"          ✅ Clicked successfully!")
                            time.sleep(2)
                            body_text = self.driver.find_element(By.TAG_NAME, "body").text
                            if "About the advertiser" in body_text:
                                print(f"          🎉 Modal opened!")
                                if self.expand_about_advertiser_section():
                                    return True
                                else:
                                    print(f"          ⚠️ Modal opened but couldn't expand section")
                                    return True
                            else:
                                print(f"          ⚠️ Clicked but modal didn't open")
                                self.close_modal()
                        except Exception as e:
                            print(f"          ❌ Error: {e}")
                            continue
                except Exception as e:
                    continue
            print(f"        ❌ Could not find 'See ad details' button")
            return False
        except Exception as e:
            print(f"        ❌ Error: {e}")
            return False

    def close_modal(self):
        try:
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(0.5)
            return True
        except:
            pass
        try:
            close_selectors = ["//div[@aria-label='Close']", "//button[@aria-label='Close']", "//*[text()='Close']"]
            for selector in close_selectors:
                try:
                    close_btn = self.driver.find_element(By.XPATH, selector)
                    if close_btn.is_displayed():
                        close_btn.click()
                        time.sleep(0.3)
                        return True
                except:
                    continue
        except:
            pass
        return False

    def extract_social_following_from_page(self):
        social_data = {'facebook_followers': 0, 'instagram_followers': 0, 'facebook_handle': '', 'instagram_handle': '', 'advertiser_category': ''}
        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            full_text = body.text
            print(f"        📄 Analyzing page (length: {len(full_text)} chars)...")
            
            if "About the advertiser" in full_text:
                about_pos = full_text.find("About the advertiser")
                sample = full_text[about_pos:about_pos+800]
                print(f"        📝 About section sample:")
                print(f"{sample}\n")
            
            # FIXED: Find ALL instances of @handle + followers (even duplicates)
            # This captures: @mrbeast\n38.7M followers • Reel creator
            # AND also:      @mrbeast\n85.3M followers
            
            pattern = r'@(\w+)\s+([\d.,]+[KMB]?)\s+followers\s*[•·]?\s*([^\n@]*?)(?=\n|$)'
            matches = re.finditer(pattern, full_text, re.IGNORECASE | re.MULTILINE)
            
            followers_found = []
            for match in matches:
                handle = match.group(1)
                count_str = match.group(2)
                category = match.group(3).strip() if match.group(3) else ''
                count = self.normalize_follower_count(count_str)
                
                # Filter out obvious noise (like "1 followers" or "5 followers")
                if count < 100:
                    continue
                
                print(f"        ✓ Found: @{handle} = {count_str} ({count:,}) | Category: {category[:30]}")
                followers_found.append({
                    'handle': f"@{handle}",
                    'count': count,
                    'category': category
                })
            
            # Assign: First = Facebook, Second = Instagram (order matters on FB page)
            if len(followers_found) >= 2:
                # First mention is typically Facebook page
                social_data['facebook_handle'] = followers_found[0]['handle']
                social_data['facebook_followers'] = followers_found[0]['count']
                if followers_found[0]['category']:
                    social_data['advertiser_category'] = followers_found[0]['category']
                
                # Second mention is typically Instagram
                social_data['instagram_handle'] = followers_found[1]['handle']
                social_data['instagram_followers'] = followers_found[1]['count']
                
                print(f"        ✅ Facebook: {followers_found[0]['handle']} ({followers_found[0]['count']:,})")
                print(f"        ✅ Instagram: {followers_found[1]['handle']} ({followers_found[1]['count']:,})")
            
            elif len(followers_found) == 1:
                # Only one found - check context or default to Facebook
                item = followers_found[0]
                
                # Check if "Instagram" appears near the handle
                handle_pos = full_text.find(item['handle'])
                context = full_text[max(0, handle_pos-100):handle_pos+200]
                
                if 'instagram' in context.lower():
                    social_data['instagram_handle'] = item['handle']
                    social_data['instagram_followers'] = item['count']
                    print(f"        ℹ️ Single handle found - assigned to Instagram (context)")
                else:
                    social_data['facebook_handle'] = item['handle']
                    social_data['facebook_followers'] = item['count']
                    print(f"        ℹ️ Single handle found - assigned to Facebook (default)")
                
                if item['category']:
                    social_data['advertiser_category'] = item['category']
            
            if not followers_found:
                print(f"        ⚠️  No follower patterns matched")
        
        except Exception as e:
            print(f"        ❌ Error extracting social data: {e}")
            import traceback
            traceback.print_exc()
        
        return social_data

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
                src = img.get_attribute('src') or img.get_attribute('data-src') or img.get_attribute('data-lazy-src')
                if src and 'http' in src:
                    if any(x in src.lower() for x in ['emoji', '/static_', 'icon', 'avatar']):
                        continue
                    if any(x in src for x in ['scontent', 'fbcdn', 'external']):
                        try:
                            width = img.size['width']
                            height = img.size['height']
                            if width > 40 and height > 40:
                                images.append({'url': src, 'alt': img.get_attribute('alt') or '', 'width': width, 'height': height})
                        except:
                            images.append({'url': src, 'alt': img.get_attribute('alt') or '', 'width': 'unknown', 'height': 'unknown'})
        except:
            pass
        return images

    def extract_library_id(self, full_text):
        patterns = [r'Library ID:\s*(\d+)', r'Ad Library ID:\s*(\d+)']
        for pattern in patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    def scroll_and_expand(self, scroll_pause_time=3, max_scrolls=100):
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
                    links.append({'url': href, 'text': link.text.strip(), 'aria_label': link.get_attribute('aria-label') or ''})
        except:
            pass
        return links

    def extract_page_name(self, full_text, links):
        for link in links:
            text = link['text']
            if text and 3 < len(text) < 100:
                skip_phrases = ['this ad', 'multiple versions', 'see ad', 'started running', 'open dropdown', 'eu transparency', 'see all', 'library id']
                if not any(skip in text.lower() for skip in skip_phrases):
                    if '.' not in text or ' ' in text:
                        return text
        lines = [l.strip() for l in full_text.split('\n') if l.strip()]
        for line in lines[:10]:
            if 3 < len(line) < 100:
                skip = ['active', 'library id', 'started running', 'platforms', 'see ad', 'sponsored', 'open dropdown', 'this ad']
                if not any(s in line.lower() for s in skip):
                    return line
        return ""

    def extract_ad_data(self, ad_element, index):
        full_text = ad_element.text
        ad_data = {'ad_position': index, 'full_text': full_text, 'links': [], 'images': [], 'library_id': '', 'page_name': '', 'ad_creative': '', 'destination_url': '', 'display_url': '', 'cta_button': '', 'platforms': [], 'date_info': '', 'impressions': '', 'facebook_followers': 0, 'instagram_followers': 0, 'facebook_handle': '', 'instagram_handle': '', 'advertiser_category': '', 'scraped_at': datetime.now().isoformat()}
        try:
            ad_data['library_id'] = self.extract_library_id(full_text)
            ad_data['links'] = self.extract_all_links(ad_element)
            ad_data['images'] = self.extract_images_from_element(ad_element)
            ad_data['page_name'] = self.extract_page_name(full_text, ad_data['links'])
            print(f"    🔍 Extracting social data for: {ad_data['page_name'][:30]}...")
            if ad_data['page_name'] in self.advertiser_cache:
                cached = self.advertiser_cache[ad_data['page_name']]
                ad_data.update(cached)
                print(f"        ✓ Used cached: FB:{cached['facebook_followers']:,} IG:{cached['instagram_followers']:,}")
            else:
                if self.click_see_ad_details(ad_element):
                    social_data = self.extract_social_following_from_page()
                    ad_data.update(social_data)
                    self.advertiser_cache[ad_data['page_name']] = social_data
                    if social_data['facebook_followers'] > 0 or social_data['instagram_followers'] > 0:
                        print(f"        ✅ Extracted: FB:{social_data['facebook_followers']:,} IG:{social_data['instagram_followers']:,}")
                    else:
                        print(f"        ⚠️  No followers found")
                    self.close_modal()
                else:
                    print(f"        ❌ Could not expand ad")
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
            cta_patterns = [r'(Shop [Nn]ow)', r'(Learn [Mm]ore)', r'(Get [Dd]irections)', r'(Sign [Uu]p)', r'(Buy [Nn]ow)', r'(Download)', r'(Visit [^\n]+)', r'(See [Mm]ore)', r'(Get [Ss]tarted)', r'(Install [Nn]ow)']
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
            skip_keywords = ['active', 'library id', 'started running', 'platforms', 'see ad', 'sponsored', 'open dropdown', 'this ad']
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
            import traceback
            traceback.print_exc()
        return ad_data

    def scrape_ads(self, url, max_ads=100, scroll_pause=3):
        try:
            print(f"🚀 Loading URL...")
            self.driver.get(url)
            time.sleep(8)
            print("📜 Scrolling...")
            self.scroll_and_expand(scroll_pause_time=scroll_pause, max_scrolls=10)
            print("🔍 Finding ads by Library ID text...")
            library_id_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Library ID:')]")
            print(f"Found {len(library_id_elements)} elements with 'Library ID:' text\n")
            ad_containers = []
            for idx, elem in enumerate(library_id_elements[:max_ads * 2], 1):
                try:
                    best_parent = None
                    current = elem
                    for level in range(1, 8):
                        current = current.find_element(By.XPATH, "..")
                        text = current.text
                        text_len = len(text)
                        if ('Library ID:' in text and 'Sponsored' in text and 200 < text_len < 3000 and text.count('Library ID:') == 1):
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
                    social_info = ""
                    if ad_data['facebook_followers'] > 0 or ad_data['instagram_followers'] > 0:
                        social_info = f" | 📘 FB:{ad_data['facebook_followers']:,} 📸 IG:{ad_data['instagram_followers']:,}"
                    print(f"[{i}] ✓ #{len(self.ads_data)} | ID: {ad_data['library_id']} | {ad_data['page_name'][:30]}{social_info}")
                except Exception as e:
                    print(f"[{i}] ❌ Error: {e}")
                    continue
            print(f"\n✅ Extracted {len(self.ads_data)} unique ads")
            print(f"⏭️  Skipped {duplicates_skipped} duplicates")
            print(f"📊 Cached {len(self.advertiser_cache)} unique advertisers")
            with_fb = sum(1 for ad in self.ads_data if ad['facebook_followers'] > 0)
            with_ig = sum(1 for ad in self.ads_data if ad['instagram_followers'] > 0)
            print(f"📘 {with_fb} ads with Facebook followers")
            print(f"📸 {with_ig} ads with Instagram followers")
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
            flattened.append({'ad_position': ad['ad_position'], 'library_id': ad['library_id'], 'page_name': ad['page_name'], 'facebook_followers': ad['facebook_followers'], 'instagram_followers': ad['instagram_followers'], 'facebook_handle': ad['facebook_handle'], 'instagram_handle': ad['instagram_handle'], 'advertiser_category': ad['advertiser_category'], 'ad_creative': ad['ad_creative'][:500] if ad['ad_creative'] else '', 'cta_button': ad['cta_button'], 'destination_url': ad['destination_url'], 'display_url': ad['display_url'], 'platforms': ', '.join(ad['platforms']), 'date_info': ad['date_info'], 'impressions': ad['impressions'], 'num_images': len(ad['images']), 'num_links': len(ad['links']), 'first_image_url': ad['images'][0]['url'] if ad['images'] else '', 'scraped_at': ad['scraped_at']})
        df = pd.DataFrame(flattened)
        df.to_csv(filename, index=False)
        print(f"💾 Saved {filename}")

    def save_readable_report(self, filename='facebook_ads_report.txt'):
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 100 + "\n")
            f.write("FACEBOOK ADS LIBRARY - SCRAPING REPORT (WITH SOCIAL FOLLOWING)\n")
            f.write("=" * 100 + "\n\n")
            f.write(f"Total Ads: {len(self.ads_data)}\n")
            f.write(f"Scraped: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"With Library ID: {sum(1 for ad in self.ads_data if ad['library_id'])}\n")
            f.write(f"With Images: {sum(1 for ad in self.ads_data if ad['images'])}\n")
            f.write(f"With URL: {sum(1 for ad in self.ads_data if ad['destination_url'])}\n")
            f.write(f"With Facebook Followers: {sum(1 for ad in self.ads_data if ad['facebook_followers'] > 0)}\n")
            f.write(f"With Instagram Followers: {sum(1 for ad in self.ads_data if ad['instagram_followers'] > 0)}\n\n")
            f.write("=" * 100 + "\n\n")
            for i, ad in enumerate(self.ads_data, 1):
                f.write(f"\n{'='*100}\n")
                f.write(f"AD #{i}\n")
                f.write(f"{'='*100}\n\n")
                f.write(f"Library ID: {ad['library_id']}\n")
                f.write(f"Page: {ad['page_name']}\n")
                f.write(f"\n--- SOCIAL FOLLOWING ---\n")
                f.write(f"Facebook: {ad['facebook_handle']} - {ad['facebook_followers']:,} followers\n")
                f.write(f"Instagram: {ad['instagram_handle']} - {ad['instagram_followers']:,} followers\n")
                f.write(f"Category: {ad['advertiser_category']}\n")
                f.write(f"------------------------\n\n")
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
    print("FACEBOOK ADS SCRAPER - FINAL VERSION")
    print("=" * 80 + "\n")
    scraper = FacebookAdsLibraryScraper(headless=False, ad_type="all")
    try:
        ads = scraper.scrape_ads(url=url, max_ads =50, scroll_pause=3)
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
            print(f"✓ With Facebook followers: {sum(1 for ad in ads if ad['facebook_followers'] > 0)}")
            print(f"✓ With Instagram followers: {sum(1 for ad in ads if ad['instagram_followers'] > 0)}")
            print("=" * 80 + "\n")
    except KeyboardInterrupt:
        print("\n⚠️  Stopped by user")
    finally:
        scraper.close()