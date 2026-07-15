import streamlit as st
import pandas as pd
import concurrent.futures
import requests
import urllib.parse
from bs4 import BeautifulSoup
import re

# Page Configuration
st.set_page_config(
    page_title="Kevin Bacon Tracker",
    page_icon="",
    layout="wide"
)

st.title("Kevin Bacon Tracker")
st.markdown(
    """
    Compare real-time prices. 
    All requests are securely routed through **Scrape.do** proxies with container-specific selectors to prevent sidebar price leakage.
    """
)

# Securely retrieve the Scrape.do token from Streamlit's secrets environment
try:
    SCRAPE_TOKEN = st.secrets["scrape_do_token"]
except KeyError:
    st.error("🔑 API Key Missing! Please configure your `scrape_do_token` in Streamlit Secrets.")
    st.stop()

# Fully Audited Master Database optimized for non-JS scraping to save credits
STORE_DATABASE = {
    "Waterman's Supplies": {
        "url": "https://www.watermanscountrysupplies.co.uk/hoof-care/kevin-bacons-liquid-hoof-dressing/",
        "price_selector": ".product-actions-wrapper .price, .product-info-main .price",
        "fallback_500ml": 12.79, "fallback_1l": None,
        "is_shopify": False
    },
    "AG Equestrian": {
        "url": "https://www.ag-equestrian.co.uk/products/kevin-bacons-liquid-hoof-dressing",
        "fallback_500ml": 14.99, "fallback_1l": 20.80,
        "is_shopify": True
    },
    "GS Equestrian": {
        "url": "https://gsequestrian.co.uk/products/kevin-bacon-kevin-bacon-s-liquid-hoof-dressing-1823",
        "fallback_500ml": 15.79, "fallback_1l": 29.00,
        "is_shopify": True
    },
    "Tanner Trading": {
        "url": "https://www.tannertrading.co.uk/hoof-protection/kevin-bacons-liquid-hoof-dressing/",
        "price_selector": ".productView-info .price--withoutTax, .productView-options .price--withoutTax",
        "fallback_500ml": 15.98, "fallback_1l": 24.34,
        "is_shopify": False
    },
    "Hyperdrug (Equine)": {
        "url": "https://hyperdrug.co.uk/kevin-bacons-liquid-hoof-dressing/",
        "price_selector": ".product-view .price-and-qty-wrapper .price, .product-view .price",
        "fallback_500ml": 18.60, "fallback_1l": 29.00,
        "is_shopify": False
    },
    "Redpost Equestrian": {
        "url": "https://www.redpostequestrian.co.uk/horse-care/hoof-care/kevin-bacon-liquid-hoof-dressing__149552",
        "price_selector": ".product-info-price .price, .price-box .price",
        "fallback_500ml": 18.60, "fallback_1l": 29.00,
        "is_shopify": False
    },
    "VioVet (Liquid Edition)": {
        "url": "https://www.viovet.co.uk/Kevin-Bacons-Liquid-Hoof-Dressing/c171350/",
        "price_selector": "table.products-table tr.product-row .price, .product-item-details .price",
        "fallback_500ml": 18.60, "fallback_1l": 29.00,
        "is_shopify": False
    },
    "Millbry Hill": {
        "url": "https://millbryhill.co.uk/products/kevin-bacon-original-liquid-hoof-dressing",
        "fallback_500ml": 19.00, "fallback_1l": 28.99,
        "is_shopify": True
    },
    "Discount Equestrian": {
        "url": "https://www.discount-equestrian.co.uk/kevin-bacon-s-liquid-hoof-dressing.html",
        "price_selector": ".product-info-main .price-box .price",
        "fallback_500ml": 19.49, "fallback_1l": 29.70,
        "is_shopify": False
    },
    "Hoof Bootique": {
        "url": "https://hoofbootique.co.uk/kevin-bacons-liquid-hoof-dressing/",
        "price_selector": ".productView-details .price--withoutTax, .productView-details .price",
        "fallback_500ml": 19.50, "fallback_1l": 29.95,
        "is_shopify": False
    },
    "First Choice Horse Supplies": {
        "url": "https://firstchoicehorsesupplies.co.uk/products/kevin-bacon-liquid-hoof-dressing-500ml",
        "fallback_500ml": 19.99, "fallback_1l": 28.99,
        "is_shopify": True
    },
    "Mole Avon": {
        "url": "https://www.moleavon.co.uk/kevin-bacons-liquid-hoof-dressing-500ml/p21647",
        "price_selector": ".product-form__price-wrapper .product-form__price",
        "fallback_500ml": 21.00, "fallback_1l": None,
        "is_shopify": False
    },
    "Equi Supermarket": {
        "url": "https://www.equisupermarket.co.uk/products/kevin-bacon-hoof-dressing-liquid",
        "fallback_500ml": None, "fallback_1l": 26.49,
        "is_shopify": True
    }
}

def clean_extracted_price(text_string):
    if not text_string:
        return None
    clean_str = text_string.replace('\n', '').replace('\r', '').strip()
    match = re.search(r'£?\s*(\d+(?:\.\d{2})?)', clean_str)
    if match:
        val = float(match.group(1))
        if 10.00 < val < 85.00: 
            return val
    return None

def fetch_via_scrapedo(store_name, info, token):
    p_500 = None
    p_1l = None
    status = "🟢 Live Scraped"

    try:
        # A. Direct JSON Parser for Shopify Stores (AG, GS, Millbry, First Choice, Equi)
        if info["is_shopify"]:
            target_url = f"{info['url']}.js"
            encoded_target = urllib.parse.quote(target_url, safe="")
            api_url = f"https://api.scrape.do/?token={token}&url={encoded_target}&render=false"
            
            res = requests.get(api_url, timeout=15)
            if res.status_code == 200:
                data = res.json()
                for variant in data.get("variants", []):
                    title = variant.get("title", "").lower()
                    val = float(variant.get("price", 0)) / 100.00
                    if "500" in title:
                        p_500 = val
                    elif any(x in title for x in ["1l", "1 l", "1ltr", "litre"]):
                        p_1l = val
            else:
                status = f"❌ Error (API Code {res.status_code})"

        # B. Structured HTML parsing for non-Shopify stores (Saves Credits - render=false)
        else:
            encoded_target = urllib.parse.quote(info["url"], safe="")
            api_url = f"https://api.scrape.do/?token={token}&url={encoded_target}&render=false"
            
            res = requests.get(api_url, timeout=15)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, "html.parser")
                body_text = soup.get_text().lower()

                if store_name == "Mole Avon":
                    # Restrict text search to the core product details block to avoid sidebar delivery options
                    product_wrap = soup.select_one(".product-single__meta, .product-form__price-wrapper")
                    scope_text = product_wrap.get_text().lower() if product_wrap else body_text
                    
                    match = re.search(r'£?(\d+\.\d{2})\s*inc\s*vat', scope_text, re.IGNORECASE)
                    if match:
                        p_500 = float(match.group(1))
                    else:
                        price_node = soup.select_one(info["price_selector"])
                        if price_node:
                            p_500 = clean_extracted_price(price_node.get_text())
                else:
                    found_prices = []
                    for element in soup.select(info["price_selector"]):
                        amt = clean_extracted_price(element.get_text())
                        if amt and amt not in found_prices:
                            found_prices.append(amt)

                    if found_prices:
                        found_prices.sort()
                        for price in found_prices:
                            if 11.00 <= price <= 20.00:
                                p_500 = price
                            elif 20.01 <= price <= 32.00:
                                p_1l = price
            else:
                status = f"❌ Error (API Code {res.status_code})"

    except Exception:
        status = "⚠️ Connection Timeout"

    # STRICT size guards: If a retailer does not stock a size, overwrite it to None
    if info["fallback_500ml"] is None:
        p_500 = None
    if info["fallback_1l"] is None:
        p_1l = None

    # Fallback to verified baseline if the live scraper failed to find a valid price
    if p_500 is None and info["fallback_500ml"] is not None:
        p_500 = info["fallback_500ml"]
        if "🟢" in status:
            status = "🟡 Parsed fallback"
            
    if p_1l is None and info["fallback_1l"] is not None:
        p_1l = info["fallback_1l"]
        if "🟢" in status:
            status = "🟡 Parsed fallback"

    return {
        "Retailer": store_name,
        "Price (500ml)": p_500,
        "Price (1L)": p_1l,
        "Link": info["url"],
        "Status": status
    }

# Execution Action button
if st.button("🔄 Scrape Live Prices Now", type="primary"):
    with st.spinner("Routing browser requests securely through Scrape.do proxy gateway..."):
        results = []
        # Concurrency set to 2 to remain safe under free tier restrictions
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(fetch_via_scrapedo, name, cfg, SCRAPE_TOKEN) for name, cfg in STORE_DATABASE.items()]
            for f in concurrent.futures.as_completed(futures):
                res = f.result()
                if res:
                    results.append(res)
                    
        df = pd.DataFrame(results)
        df["sort_val"] = df["Price (500ml)"].fillna(999.00)
        st.session_state["scrapedo_matrix"] = df.sort_values(by="sort_val").drop(columns=["sort_val"])
        st.success("🎉 Live requests updated cleanly via Scrape.do!")

# Default fallback layout on startup
if "scrapedo_matrix" not in st.session_state:
    initial_records = []
    for name, cfg in STORE_DATABASE.items():
        initial_records.append({
            "Retailer": name,
            "Price (500ml)": cfg["fallback_500ml"],
            "Price (1L)": cfg["fallback_1l"],
            "Link": cfg["url"],
            "Status": "⚪ Standby (Click Scrape to update)"
        })
    df_init = pd.DataFrame(initial_records)
    df_init["sort_val"] = df_init["Price (500ml)"].fillna(999.00)
    st.session_state["scrapedo_matrix"] = df_init.sort_values(by="sort_val").drop(columns=["sort_val"])

# Formatted presentation structures
display_df = st.session_state["scrapedo_matrix"].copy()
display_df["500ml Can"] = display_df["Price (500ml)"].apply(lambda x: f"£{x:.2f}" if pd.notna(x) and x is not None else "N/A")
display_df["1 Litre Can"] = display_df["Price (1L)"].apply(lambda x: f"£{x:.2f}" if pd.notna(x) and x is not None else "N/A")

st.subheader("📋 Live Price Comparison Board (500ml vs 1L)")
st.dataframe(
    display_df[["Retailer", "500ml Can", "1 Litre Can", "Link", "Status"]],
    column_config={
        "Retailer": "Equestrian Retailer",
        "500ml Can": "Price (500ml)",
        "1 Litre Can": "Price (1L)",
        "Link": st.column_config.LinkColumn("Purchase Link", display_text="View Product"),
        "Status": "Connection Status"
    },
    hide_index=True,
    use_container_width=True
)
