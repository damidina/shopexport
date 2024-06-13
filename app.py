from flask import Flask, request, render_template, send_file
import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
import os

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

def fetch_sitemap(url):
    response = requests.get(url)
    if response.status_code != 200:
        logging.error(f"Failed to fetch sitemap: {response.status_code}")
        return []
    soup = BeautifulSoup(response.content, features="xml")
    sitemap_urls = [loc.text for loc in soup.find_all('loc')]
    product_urls = []
    for sitemap_url in sitemap_urls:
        if 'products' in sitemap_url:
            product_urls.extend(fetch_product_sitemap(sitemap_url))
    logging.info(f"Found {len(product_urls)} product URLs in sitemap")
    return product_urls

def fetch_product_sitemap(url):
    response = requests.get(url)
    if response.status_code != 200:
        logging.error(f"Failed to fetch product sitemap: {response.status_code}")
        return []
    soup = BeautifulSoup(response.content, features="xml")
    return [loc.text for loc in soup.find_all('loc') if '/products/' in loc.text and 'cdn' not in loc.text]

def fetch_product_data(product_url):
    product_handle = product_url.split('/')[-1]
    json_url = f"{product_url}.json"
    response = requests.get(json_url)
    if response.status_code != 200:
        logging.error(f"Failed to fetch product data: {response.status_code} for URL: {json_url}")
        return None
    try:
        return response.json().get('product')
    except ValueError:
        logging.error(f"Invalid JSON response for URL: {json_url}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    shopify_url = request.form['shopify_url']
    logging.info(f"Starting scrape for {shopify_url}")
    
    product_urls = fetch_sitemap(f"{shopify_url}/sitemap.xml")
    if not product_urls:
        return "Failed to fetch sitemap or no product URLs found", 500
    
    products = []
    for url in product_urls:
        if '/products/' in url and 'cdn' not in url:
            logging.info(f"Processing URL: {url}")
            product_data = fetch_product_data(url)
            if product_data:
                products.append(product_data)
    logging.info(f"Fetched data for {len(products)} products")

    if not products:
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

    df = pd.DataFrame(data)
    csv_path = 'shopify_products.csv'
    df.to_csv(csv_path, index=False)
    logging.info(f"CSV file created at {csv_path}")

    return send_file(csv_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)