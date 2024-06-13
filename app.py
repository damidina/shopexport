from flask import Flask, request, render_template, send_file, jsonify, Response
from flask_cors import CORS
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import pandas as pd
import logging
import os
import csv

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

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
        if not shopify_url:
            logging.error("Missing 'shopify_url' in request")
            return "Missing 'shopify_url' in request", 400

        logging.info(f"Starting scrape for {shopify_url}")
        
        try:
            product_urls = await fetch_sitemap(f"{shopify_url}/sitemap.xml")
            if not product_urls:
                logging.error("Failed to fetch sitemap or no product URLs found")
                return "Failed to fetch sitemap or no product URLs found", 500
            
            products = []
            async with aiohttp.ClientSession() as session:
                tasks = [fetch_product_data(session, url, count+1) for count, url in enumerate(product_urls) if '/products/' in url and 'cdn' not in url]
                products = await asyncio.gather(*tasks)
            
            products = [product for product in products if product]
            logging.info(f"Fetched data for {len(products)} products")

            if not products:
                logging.error("No product data fetched")
                return "No product data fetched", 500

            data = []
            for product in products:
                for variant in product['variants']:
                    for image in product['images']:
                        data.append({
                            'Handle': product['handle'],
                            'Title': product['title'],
                            'Body (HTML)': product['body_html'],
                            'Vendor': product['vendor'],
                            'Product Category': '',  # This field is not available in the JSON data
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
                            'Gift Card': 'FALSE',  # Assuming products are not gift cards
                            'SEO Title': '',  # This field is not available in the JSON data
                            'SEO Description': '',  # This field is not available in the JSON data
                            'Google Shopping / Google Product Category': '',  # This field is not available in the JSON data
            'Google Shopping / Gender': '',  # This field is not available in the JSON data
            'Google Shopping / Age Group': '',  # This field is not available in the JSON data
            'Google Shopping / MPN': '',  # This field is not available in the JSON data
            'Google Shopping / Condition': '',  # This field is not available in the JSON data
            'Google Shopping / Custom Product': '',  # This field is not available in the JSON data
            'Google Shopping / Custom Label 0': '',  # This field is not available in the JSON data
            'Google Shopping / Custom Label 1': '',  # This field is not available in the JSON data
            'Google Shopping / Custom Label 2': '',  # This field is not available in the JSON data
            'Google Shopping / Custom Label 3': '',  # This field is not available in the JSON data
            'Google Shopping / Custom Label 4': '',  # This field is not available in the JSON data
            'Variant Image': variant.get('image_id', ''),
            'Variant Weight Unit': variant.get('weight_unit', ''),
            'Variant Tax Code': '',  # This field is not available in the JSON data
            'Cost per item': '',  # This field is not available in the JSON data
            'Included / Canada': '',  # This field is not available in the JSON data
            'Price / Canada': '',  # This field is not available in the JSON data
            'Compare At Price / Canada': '',  # This field is not available in the JSON data
            'Included / International': '',  # This field is not available in the JSON data
            'Price / International': '',  # This field is not available in the JSON data
            'Compare At Price / International': '',  # This field is not available in the JSON data
            'Included / United States': '',  # This field is not available in the JSON data
            'Price / United States': '',  # This field is not available in the JSON data
            'Compare At Price / United States': '',  # This field is not available in the JSON data
            'Status': 'active'  # Assuming all products are active
        })

            if not data:
                logging.error("No data to write to CSV")
                return "No data to write to CSV", 500

            # Stream the CSV data
            def generate():
                if not data:
                    yield "No data available\n"
                    return

                fieldnames = data[0].keys()
                writer = csv.DictWriter(open('shopify_products.csv', 'w'), fieldnames=fieldnames)
                writer.writeheader()
                for row in data:
                    writer.writerow(row)
                    yield ','.join([str(row[field]) for field in fieldnames]) + '\n'

            return Response(generate(), mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=shopify_products.csv"})

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

if __name__ == "__main__":
    app.run(debug=True)