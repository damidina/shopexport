# Shopify Product Scraper

This Flask application scrapes product data from a Shopify store and exports it to a CSV file.

## Features
- Fetches product URLs from the Shopify sitemap.
- Extracts product data including variants and images.
- Exports the data to a CSV file.

## Requirements
- Python 3.x
- Flask
- requests
- beautifulsoup4
- pandas
- lxml

## Installation

1. Clone the repository:
git clone https://github.com/yourusername/shopify-product-scraper.git

cd shopify-product-scraper


2. Install the required packages:

sh

pip install -r requirements.txt



## Usage

1. Run the Flask app:

sh

python app.py


2. Open your web browser and go to `http://127.0.0.1:5000/`.

3. Enter the Shopify store URL in the form and click "Scrape".

4. The application will process the product data and generate a CSV file named `shopify_products.csv`.

## Additional Debugging Steps

1. **Check the Terminal Logs**: Look for any error messages or warnings in the terminal where you run the Flask app.

2. **Verify the Shopify URL**: Ensure the Shopify URL you are entering in the form is correct and accessible.

3. **Inspect the Sitemap**: Manually check the sitemap URL (e.g., `https://your-shopify-store.myshopify.com/sitemap.xml`) to ensure it contains product URLs.

4. **Check Product JSON URLs**: Manually check a few product JSON URLs (e.g., `https://your-shopify-store.myshopify.com/products/product-handle.json`) to ensure they return valid product data.

## License
This project is licensed under the MIT License.