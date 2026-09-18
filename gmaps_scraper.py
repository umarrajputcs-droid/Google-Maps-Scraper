import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import urllib.parse
import re
import time

EMAIL_REGEX = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
PHONE_REGEX = r"\(?\b[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b"
OWNER_REGEX_1 = r'\b(?:Founder|Owner|CEO)\b[\s:]+([A-Z][a-z]{2,} [A-Z][a-z]{2,})\b'
OWNER_REGEX_2 = r'\b([A-Z][a-z]{2,} [A-Z][a-z]{2,})\b[\s,]+(?:is the\s+)?(?:Founder|Owner|CEO)\b'

async def extract_website_details(context, website_url):
    details = {'email': '', 'phone': '', 'owner': ''}
    
    if not website_url or "http" not in website_url:
        if website_url:
            website_url = "http://" + website_url
        else:
            return details
            
    try:
        page = await context.new_page()
        # block assets for speed
        await page.route("**/*", lambda route: route.continue_() if route.request.resource_type in ["document", "script"] else route.abort())
        
        async def get_details_from_page():
            content = await page.content()
            
            emails = set(re.findall(EMAIL_REGEX, content))
            emails = {e for e in emails if not e.endswith(('png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'js', 'css')) 
                      and 'sentry' not in e.lower() 
                      and 'react' not in e.lower() 
                      and not re.search(r'@[0-9\.]+$', e)}
                      
            phones = set(re.findall(PHONE_REGEX, content))
            
            clean_text = re.sub(r'<[^>]+>', ' ', content)
            owners = set()
            owners.update(re.findall(OWNER_REGEX_1, clean_text))
            owners.update(re.findall(OWNER_REGEX_2, clean_text))
            
            return emails, phones, owners
                    
        await page.goto(website_url, timeout=10000, wait_until="domcontentloaded")
        found_emails, found_phones, found_owners = await get_details_from_page()
        
        # search contact pages if missing data
        if not found_emails or not found_phones or not found_owners:
            hrefs = await page.evaluate('''() => {
                const links = Array.from(document.querySelectorAll('a'));
                return links.map(a => a.href).filter(href => href.toLowerCase().includes('contact') || href.toLowerCase().includes('about') || href.toLowerCase().includes('team'));
            }''')
            
            hrefs = list(set(hrefs))[:4]
            
            for href in hrefs:
                try:
                    await page.goto(href, timeout=8000, wait_until="domcontentloaded")
                    more_emails, more_phones, more_owners = await get_details_from_page()
                    
                    found_emails.update(more_emails)
                    found_phones.update(more_phones)
                    found_owners.update(more_owners)
                    
                    if found_emails and found_phones and found_owners:
                        break
                except Exception:
                    continue
                    
        await page.close()
        
        if found_emails: details['email'] = ", ".join(found_emails)
        if found_phones: details['phone'] = ", ".join(found_phones)
        if found_owners: details['owner'] = ", ".join(found_owners)
        return details
            
    except Exception:
        try: await page.close()
        except: pass
        
    return details

async def scrape_google_maps(keyword, max_results):
    print(f"Scraping '{keyword}' for {max_results} leads...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()
        
        encoded_keyword = urllib.parse.quote_plus(keyword)
        search_url = f"https://www.google.com/maps/search/{encoded_keyword}"
        
        await page.goto(search_url)
        print("Waiting for results...")
        
        try:
            await page.wait_for_selector('div[role="feed"]', timeout=20000)
            await page.wait_for_timeout(3000) 
        except Exception:
            try:
                accept_button = page.locator('button:has-text("Accept all")')
                if await accept_button.count() > 0:
                    await accept_button.first.click()
                    await page.wait_for_timeout(3000)
                    await page.wait_for_selector('div[role="feed"]', timeout=15000)
            except Exception:
                pass
        
        scraped_data = []
        count = 0
        previously_processed = set()
        feed_locator = page.locator('div[role="feed"]')
        
        while count < max_results:
            try:
                if await feed_locator.count() == 0:
                    break
                    
                listings = await page.locator('a[href*="/maps/place/"]').all()
                new_listings_found = False
                
                for listing in listings:
                    if count >= max_results:
                        break
                        
                    href = await listing.get_attribute('href')
                    if href in previously_processed:
                        continue
                        
                    previously_processed.add(href)
                    new_listings_found = True
                    
                    try:
                        await listing.scroll_into_view_if_needed()
                        await page.wait_for_timeout(500)
                        await listing.evaluate("node => node.click()")
                        
                        try: await page.wait_for_selector('h1.DUwDvf', timeout=5000)
                        except: await page.wait_for_timeout(2000)
                        
                        name = ""
                        address = ""
                        phone = ""
                        website = ""
                        email = ""
                        city = ""
                        state = ""
                        zip_code = ""
                        owner = ""
                        
                        try:
                            name_locator = page.locator('h1.DUwDvf')
                            if await name_locator.count() > 0:
                                name = await name_locator.first.inner_text()
                        except Exception: pass

                        try:
                            address_locator = page.locator('button[data-item-id="address"] .fontBodyMedium')
                            if await address_locator.count() > 0:
                                address = await address_locator.first.inner_text()
                                match = re.search(r'\b([A-Z]{2})\s+(\d{5})\b', address)
                                if match:
                                    state = match.group(1)
                                    zip_code = match.group(2)
                        except Exception: pass
                                
                        try:
                            phone_locator = page.locator('button[data-item-id^="phone:"] .fontBodyMedium')
                            if await phone_locator.count() > 0:
                                phone = await phone_locator.first.inner_text()
                        except Exception: pass
                        
                        try:
                            website_locator = page.locator('a[data-item-id="authority"] .fontBodyMedium')
                            if await website_locator.count() > 0:
                                website = await website_locator.first.inner_text()
                        except Exception: pass
                        
                        if website:
                            web_details = await extract_website_details(context, website)
                            email = web_details['email']
                            owner = web_details['owner']
                            
                            if not phone and web_details['phone']:
                                phone = web_details['phone']
                        
                        email_status = "Yes" if email else "No"
                        print(f"[{count+1}/{max_results}] Found: {name}")
                        
                        scraped_data.append({
                            'Company Name': name,
                            'Owner Name': owner,
                            'Contact': phone,
                            'Email': email,
                            'Website': website,
                            'State': state,
                            'Email Status': email_status
                        })
                        count += 1
                        
                    except Exception as e:
                        pass
                        
                if not new_listings_found or count >= max_results:
                    try:
                        await feed_locator.evaluate("node => node.scrollTop = node.scrollHeight")
                        await page.wait_for_timeout(2000)
                        
                        end_text = page.locator('text="You\'ve reached the end of the list."')
                        if await end_text.count() > 0:
                            break
                    except Exception:
                        pass
            except Exception as e:
                 break
            
        print(f"Finished scraping {len(scraped_data)} leads.")
        await browser.close()
            
        if scraped_data:
            filtered_data = [d for d in scraped_data if d.get('Company Name')]
            
            if not filtered_data:
                return

            df = pd.DataFrame(filtered_data)
            
            try:
                df.to_csv('leads.csv', index=False)
                
                with pd.ExcelWriter('leads.xlsx', engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Leads')
                    worksheet = writer.sheets['Leads']
                    from openpyxl.utils import get_column_letter
                    for idx, col in enumerate(df.columns):
                        series = df[col]
                        max_len = min(100, max(series.astype(str).map(len).max(), len(str(series.name))) * 1.2 + 4)
                        col_letter = get_column_letter(idx + 1)
                        worksheet.column_dimensions[col_letter].width = max_len

                print("Saved to leads.csv and leads.xlsx")
            except Exception as e:
                print("Error saving files. Make sure Excel is closed.")
                backup_name = f'leads_backup_{int(time.time())}.csv'
                try:
                    df.to_csv(backup_name, index=False)
                    print(f"Saved backup to {backup_name}")
                except Exception:
                    pass

if __name__ == "__main__":
    keyword = input("Search keyword (e.g., 'Plumbers in Chicago'): ")
    try:
        max_results = int(input("Max leads: "))
    except ValueError:
        max_results = 10
        
    asyncio.run(scrape_google_maps(keyword, max_results))
