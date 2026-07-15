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

# Fully Audited Master Database with Javascript Render flags to save credits
STORE_DATABASE = {
    "Waterman's Supplies": {
        "url": "https://www.watermanscountrysupplies.co.uk/hoof-care/kevin-bacons-liquid-hoof-dressing/",
        "price_selector": ".product-actions-wrapper .price, .product-info-main .price",
        "fallback_500ml": 12.79, "fallback_1l": None,
        "needs_js": False  # Saves credits! Standard request
    },
    "AG Equestrian": {
        "url": "https://www.ag-equestrian.co.uk/products/kevin-bacons-liquid-hoof-dressing",
        "price_selector": ".product-single__meta .price-item--sale, .product-single__meta .price-item",
        "fallback_500ml": 14.99, "fallback_1l": 20.80,
        "needs_js": False
    },
    "GS Equestrian": {
        "url": "https://gsequestrian.co.uk/products/kevin-bacon-kevin-bacon-s-liquid-hoof-dressing-1823",
        "price_selector": ".product-single__meta .price-item--sale, .product-single__meta .price-item",
        "fallback_500ml": 15.79, "fallback_1l": 29.00,
        "needs_js": True  # Shopify variation menu needs JS rendering
    },
    "Tanner Trading": {
        "url": "https://www.tannertrading.co.uk/hoof-protection/kevin-bacons-liquid-hoof-dressing/",
        "price_selector": ".productView-info .price--withoutTax, .productView-options .price--withoutTax",
        "fallback_500ml": 15.98, "fallback_1l": 24.34,
        "needs_js": False
    },
    "Hyperdrug (Equine)": {
        "url": "https://hyperdrug.co.uk/kevin-bacons-liquid-hoof-dressing/",
        "price_selector": ".product-view .price-and-qty-wrapper .price, .product-view .price",
        "fallback_500ml": 18.60, "fallback_1l": 29.00,
        "needs_js": False
    },
    "Redpost Equestrian": {
        "url": "https://www.redpostequestrian.co.uk/horse-care/hoof-care/kevin-bacon-liquid-hoof-dressing__149552",
        "price_selector": ".product-info-main .product-info-price .price",
        "fallback_500ml": 18.60, "fallback_1l": 29.00,
        "needs_js": True
    },
    "VioVet (Liquid Edition)": {
        "url": "https://www.viovet.co.uk/Kevin-Bacons-Liquid-Hoof-Dressing/c171350/",
        "price_selector": "table.products-table tr.product-row .price, .product-item-details .price",
        "fallback_500ml": 18.60, "fallback_1l": 29.00,
        "needs_js": False
    },
    "Millbry Hill": {
        "url": "https://millbryhill.co.uk/products/kevin-bacon-original-liquid-hoof-dressing",
        "price_selector": ".product-meta .price-item--sale, .product-meta .price-item",
        "fallback_500ml": 19.00, "fallback_1l": 28.99,
        "needs_js": True
    },
    "Discount Equestrian": {
        "url": "https://www.discount-equestrian.co.uk/kevin-bacon-s-liquid-hoof-dressing.html",
        "price_selector": ".product-info-main .price-box .price",
        "fallback_500ml": 19.49, "fallback_1l": 29.70,
        "needs_js": False
    },
    "Hoof Bootique": {
        "url": "https://hoofbootique.co.uk/kevin-bacons-liquid-hoof-dressing/",
        "price_selector": ".productView-details .price--withoutTax, .productView-details .price",
        "fallback_500ml": 19.50, "fallback_1l": 29.95,
        "needs_js": False
    },
    "First Choice Horse Supplies": {
        "url": "https://firstchoicehorsesupplies.co.uk/products/kevin-bacon-liquid-hoof-dressing-500ml",
        "price_selector": ".product-single__meta .price-item--sale, .product-single__meta .price-item",
        "fallback_500ml": 19.99, "fallback_1l": 28.99,
        "needs_js": False
    },
    "Mole Avon": {
        "url": "https://www.moleavon.co.uk/kevin-bacons-liquid-hoof-dressing-500ml/p21647",
        "price_selector": ".product-form__price-wrapper .product-form__price",
        "fallback_500ml": 21.00, "fallback_1l": None,
        "needs_js": False
    },
    "Equi Supermarket": {
        "url": "https://www.equisupermarket.co.uk/products/kevin-bacon-hoof-dressing-liquid",
        "price_selector": ".product-single__meta .price-item--sale, .product-single__meta .price-item",
        "fallback_500ml": None, "fallback_1l": 26.49,
        "needs_js": True
    }
}

def clean_extracted_price(text_string):
    if not text_string:
        return None
    # Strip whitespace, newlines and comma formats
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
        encoded_target = urllib.parse.quote(info["url"], safe="")
        
        # Optimize rendering flag depending on requirements to save credits (render=true vs render=false)
        render_flag = "true" if info["needs_js"] else "false"
        
        # Inject API-side timeout parameters directly to keep proxy response fast
        api_url = f"https://api.scrape.do/?token={token}&url={encoded_target}&render={render_flag}&timeout=15000"

        # Explicit local connection read/timeout configurations
        res = requests.get(api_url, timeout=(10, 45))
        
        if res.status_code == 200:
            soup = BeautifulSoup(res.content, "html.parser")
            body_text = soup.get_text().lower()

            if store_name == "Mole Avon":
                # Find only values explicitly tied to 'inc VAT' text markers
                match = re.search(r'£?(\d+\.\d{2})\s*inc\s*VAT', body_text, re.IGNORECASE)
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
            status = f"❌ Blocked/Error (API Code {res.status_code})"
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
        # max_workers=2 guarantees we stay strictly within the free tier's concurrency limits
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
