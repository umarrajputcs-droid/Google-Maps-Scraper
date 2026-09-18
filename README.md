# Google Maps & Website Scraper (Async/Playwright)

A Python web scraper I built to automate extracting business leads from Google Maps. It doesn't just scrape Maps though—it also visits the company's website to find missing contact info like emails, phone numbers, and owner/founder names.

## Why I Built This
I wanted to get hands-on experience with asynchronous programming (`asyncio`) and headless browser automation (`playwright`). Scraping Google Maps is notoriously difficult because the DOM changes frequently and relies heavily on JavaScript, so it was a great challenge to figure out how to reliably extract data without getting blocked. 

## Features
* **Async Processing:** Uses Playwright's async API to run quickly without blocking the main thread.
* **Deep Scanning:** If an email or phone number isn't listed on Google Maps, the scraper opens a background tab, navigates to the business's website, blocks images/CSS to save bandwidth, and uses Regular Expressions to extract missing data and owner names from the HTML.
* **Contact Page Hunting:** If the homepage doesn't have an email, it automatically looks for `/contact` or `/about` links and scans those too.
* **Auto-Formatting:** Dumps the cleaned data into CSV and Excel files, using `openpyxl` to automatically resize the Excel columns so it looks neat.

## Tech Stack
* Python 3
* `playwright` (async API)
* `pandas` & `openpyxl` (for data export)
* `re` (Regex for email/phone parsing)

## Setup
1. Clone the repo
2. Install dependencies: `pip install -r requirements.txt`
3. Install Chromium for Playwright: `python -m playwright install chromium`
4. Run it: `python gmaps_scraper.py`
