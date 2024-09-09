from flask import Flask, request, render_template, send_file, jsonify, Response
from flask_cors import CORS
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import pandas as pd
import logging
import os
import csv
import json
from asgiref.wsgi import WsgiToAsgi

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
asgi_app = WsgiToAsgi(app)

# Configure logging
logging.basicConfig(level=logging.INFO)

async def fetch(session, url):
    logging.info(f"Fetching URL: {url}")
    async with session.get(url) as response:
        if response.status != 200:
            logging.error(f"Failed to fetch URL: {url} with status code: {response.status}")
            return None
        logging.info(f"Successfully fetched URL: {url}")
        return await response.text()

async def fetch_sitemap(url):
    logging.info(f"Fetching sitemap: {url}")
    async with aiohttp.ClientSession() as session:
        response_text = await fetch(session, url)
        if not response_text:
            logging.error(f"Failed to fetch sitemap: {url}")
            return []
        soup = BeautifulSoup(response_text, features="xml")
        sitemap_urls = [loc.text for loc in soup.find_all('loc')]
        logging.info(f"Found {len(sitemap_urls)} URLs in sitemap")
        product_urls = []
        for sitemap_url in sitemap_urls:
            if 'products' in sitemap_url:
                product_urls.extend(await fetch_product_sitemap(session, sitemap_url))
        logging.info(f"Found {len(product_urls)} product URLs in sitemap")
        return product_urls

async def fetch_product_sitemap(session, url):
    logging.info(f"Fetching product sitemap: {url}")
    response_text = await fetch(session, url)
    if not response_text:
        logging.error(f"Failed to fetch product sitemap: {url}")
        return []
    soup = BeautifulSoup(response_text, features="xml")
    product_urls = [loc.text for loc in soup.find_all('loc') if '/products/' in loc.text and 'cdn' not in loc.text]
    logging.info(f"Found {len(product_urls)} product URLs in product sitemap")
    return product_urls

async def fetch_product_data(session, product_url, count):
    logging.info(f"Fetching product data ({count}): {product_url}")
    product_handle = product_url.split('/')[-1]
    json_url = f"{product_url}.json"
    async with session.get(json_url) as response:
        if response.status != 200:
            logging.error(f"Failed to fetch URL: {json_url} with status code: {response.status}")
            return None
        try:
            json_data = await response.json()
            logging.info(f"Successfully fetched product data ({count}) for: {product_url}")
            return json_data.get('product')
        except ValueError:
            logging.error(f"Invalid JSON response for URL: {json_url}")
            return None

async def scrape_homepage(session, url):
    logging.info(f"Scraping homepage: {url}")
    html = await fetch(session, url)
    if not html:
        return None
    soup = BeautifulSoup(html, 'html.parser')
    
    sections = []
    for section in soup.find_all('section'):
        images = [img['src'] for img in section.find_all('img') if 'src' in img.attrs]
        product_links = [a['href'] for a in section.find_all('a', href=True) if '/products/' in a['href']]
        sections.append({
            'images': images,
            'product_references': product_links
        })
    
    return {
        'url': url,
        'sections': sections
    }

async def scrape_key_page(session, url):
    logging.info(f"Scraping key page: {url}")
    html = await fetch(session, url)
    if not html:
        return None
    soup = BeautifulSoup(html, 'html.parser')
    
    content = soup.get_text()
    images = [img['src'] for img in soup.find_all('img') if 'src' in img.attrs]
    
    return {
        'url': url,
        'content': content,
        'images': images
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
async def scrape():
    logging.info(f"Request content type: {request.content_type}")
    logging.info(f"Request data: {request.data}")
    logging.info(f"Request headers: {request.headers}")

    if request.is_json:
        data = request.get_json()
        logging.info(f"Parsed JSON data: {data}")
        shopify_url = data.get('shopify_url')
        scrape_homepage = data.get('scrape_homepage', False)
        scrape_products = data.get('scrape_products', False)
        key_pages = data.get('key_pages', [])

        if not shopify_url:
            logging.error("Missing 'shopify_url' in request")
            return "Missing 'shopify_url' in request", 400

        logging.info(f"Starting scrape for {shopify_url}")
        
        try:
            result = {}
            
            async with aiohttp.ClientSession() as session:
                tasks = []
                
                if scrape_homepage:
                    tasks.append(scrape_homepage(session, shopify_url))
                
                if scrape_products:
                    product_urls = await fetch_sitemap(f"{shopify_url}/sitemap.xml")
                    if not product_urls:
                        logging.error("Failed to fetch sitemap or no product URLs found")
                        return "Failed to fetch sitemap or no product URLs found", 500
                    tasks.extend([fetch_product_data(session, url, count+1) for count, url in enumerate(product_urls) if '/products/' in url and 'cdn' not in url])
                
                for page in key_pages:
                    tasks.append(scrape_key_page(session, f"{shopify_url}/{page.strip('/')}"))
                
                results = await asyncio.gather(*tasks)
            
            if scrape_homepage:
                result['homepage'] = results.pop(0)
            
            if scrape_products:
                products = [product for product in results if isinstance(product, dict) and 'handle' in product]
                result['products'] = products
                
                # Existing CSV generation logic
                csv_data = []
                for product in products:
                    for variant in product['variants']:
                        for image in product['images']:
                            csv_data.append({
                                'Handle': product['handle'],
                                'Title': product['title'],
                                'Body (HTML)': product['body_html'],
                                'Vendor': product['vendor'],
                                'Product Category': '',
                                'Type': product['product_type'],
                                'Tags': ', '.join(product['tags']),
                                'Published': product['published_at'],
                                'Option1 Name': product['options'][0]['name'] if len(product['options']) > 0 else '',
                                'Option1 Value': variant.get('option1', ''),
                                'Option2 Name': product['options'][1]['name'] if len(product['options']) > 1 else '',
                                'Option2 Value': variant.get('option2', ''),
                                'Option3 Name': product['options'][2]['name'] if len(product['options']) > 2 else '',
                                'Option3 Value': variant.get('option3', ''),
                                'Variant SKU': variant['sku'],
                                'Variant Grams': variant['grams'],
                                'Variant Inventory Tracker': variant.get('inventory_management', ''),
                                'Variant Inventory Policy': variant.get('inventory_policy', 'continue'),
                                'Variant Fulfillment Service': variant.get('fulfillment_service', ''),
                                'Variant Price': variant['price'],
                                'Variant Compare At Price': variant.get('compare_at_price', ''),
                                'Variant Requires Shipping': variant['requires_shipping'],
                                'Variant Taxable': variant['taxable'],
                                'Variant Barcode': variant.get('barcode', ''),
                                'Image Src': image['src'],
                                'Image Position': image['position'],
                                'Image Alt Text': image.get('alt', ''),
                                'Gift Card': 'FALSE',
                                'SEO Title': '',
                                'SEO Description': '',
                                'Google Shopping / Google Product Category': '',
                                'Google Shopping / Gender': '',
                                'Google Shopping / Age Group': '',
                                'Google Shopping / MPN': '',
                                'Google Shopping / Condition': '',
                                'Google Shopping / Custom Product': '',
                                'Google Shopping / Custom Label 0': '',
                                'Google Shopping / Custom Label 1': '',
                                'Google Shopping / Custom Label 2': '',
                                'Google Shopping / Custom Label 3': '',
                                'Google Shopping / Custom Label 4': '',
                                'Variant Image': variant.get('image_id', ''),
                                'Variant Weight Unit': variant.get('weight_unit', ''),
                                'Variant Tax Code': '',
                                'Cost per item': '',
                                'Status': 'active'
                            })
                
                if csv_data:
                    with open('shopify_products.csv', 'w', newline='') as csvfile:
                        fieldnames = csv_data[0].keys()
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        for row in csv_data:
                            writer.writerow(row)
            
            result['key_pages'] = [page for page in results if isinstance(page, dict) and 'content' in page]
            
            # Save the result as a JSON file
            with open('shopify_data.json', 'w') as f:
                json.dump(result, f)
            
            return jsonify({"message": "Scraping completed successfully"}), 200

        except Exception as e:
            logging.error(f"An error occurred during scraping: {e}")
            return f"An error occurred: {e}", 500
    else:
        logging.error("Unsupported Media Type")
        return "Unsupported Media Type", 415

@app.route('/download_csv', methods=['GET'])
def download_csv():
    csv_path = 'shopify_products.csv'
    if os.path.exists(csv_path):
        return send_file(csv_path, as_attachment=True)
    else:
        return "CSV file not found", 404

@app.route('/download_json', methods=['GET'])
def download_json():
    json_path = 'shopify_data.json'
    if os.path.exists(json_path):
        return send_file(json_path, as_attachment=True, mimetype='application/json')
    else:
        return "JSON file not found", 404

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(asgi_app, host="127.0.0.1", port=5091)