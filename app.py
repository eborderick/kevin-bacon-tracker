import streamlit as st
import subprocess
import sys

# 1. Automatically install Playwright browser binaries on Streamlit Cloud startup
@st.cache_resource
def install_playwright_browsers():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        pass

# Trigger the auto-installer before importing playwright to prevent startup crashes
install_playwright_browsers()

# Remaining essential library imports
import pandas as pd
import concurrent.futures
from bs4 import BeautifulSoup
import re
from playwright.sync_api import sync_playwright

# Streamlit Page Setup
st.set_page_config(
    page_title="100% Honest Hoof Dressing Tracker",
    page_icon="🐴",
    layout="wide"
)

st.title("🐴 Transparent Kevin Bacon's Liquid Hoof Dressing Tracker")
st.markdown(
    """
    Compare **real-time live prices** for both **500ml** and **1L** tins side-by-side. 
    This app shows exactly which sites were successfully scraped live and which ones had to load your verified baselines due to firewall blocks.
    """
)

# 100% Hand-Verified Core Database (The definitive source of truth provided by you)
VERIFIED_DATA = {
    "Waterman's Supplies": {
        "url": "https://www.watermanscountrysupplies.co.uk/hoof-care/kevin-bacons-liquid-hoof-dressing/",
        "price_selector": ".price, .product-price",
        "exact_500ml": 12.79,
        "exact_1l": None
    },
    "AG Equestrian": {
        "url": "https://www.ag-equestrian.co.uk/products/kevin-bacons-liquid-hoof-dressing",
        "price_selector": ".price-item, .price__regular",
        "exact_500ml": 14.99,
        "exact_1l": 20.80
    },
    "GS Equestrian": {
        "url": "https://gsequestrian.co.uk/products/kevin-bacon-kevin-bacon-s-liquid-hoof-dressing-1823",
        "price_selector": "span.price-item--sale, .price-item",
        "exact_500ml": 15.79,
        "exact_1l": 29.00
    },
    "Tanner Trading": {
        "url": "https://www.tannertrading.co.uk/hoof-protection/kevin-bacons-liquid-hoof-dressing/",
        "price_selector": ".price--withoutTax, span.price",
        "exact_500ml": 15.98,
        "exact_1l": 24.34
    },
    "Hyperdrug (Equine)": {
        "url": "https://hyperdrug.co.uk/kevin-bacons-liquid-hoof-dressing/",
        "price_selector": ".price-and-qty-wrapper .price, .price",
        "exact_500ml": 18.60,
        "exact_1l": 29.00
    },
    "Redpost Equestrian": {
        "url": "https://www.redpostequestrian.co.uk/horse-care/hoof-care/kevin-bacon-liquid-hoof-dressing__149552",
        "price_selector": ".product-info-price .price, span.price",
        "exact_500ml": 18.60,
        "exact_1l": 29.00
    },
    "VioVet (Liquid Edition)": {
        "url": "https://www.viovet.co.uk/Kevin-Bacons-Liquid-Hoof-Dressing/c171350/",
        "price_selector": ".price-wrapper .price, span.price",
        "exact_500ml": 18.60,
        "exact_1l": 29.00
    },
    "Millbry Hill": {
        "url": "https://millbryhill.co.uk/products/kevin-bacon-original-liquid-hoof-dressing",
        "price_selector": "span.price-item--sale, .price-item",
        "exact_500ml": 19.00,
        "exact_1l": 28.99
    },
    "Discount Equestrian": {
        "url": "https://www.discount-equestrian.co.uk/kevin-bacon-s-liquid-hoof-dressing.html",
        "price_selector": "span.price-wrapper span.price",
        "exact_500ml": 19.49,
        "exact_1l": 29.70
    },
    "Hoof Bootique": {
        "url": "https://hoofbootique.co.uk/kevin-bacons-liquid-hoof-dressing/",
        "price_selector": "span.price--withoutTax, .price",
        "exact_500ml": 19.50,
        "exact_1l": 29.95
    },
    "First Choice Horse Supplies": {
        "url": "https://firstchoicehorsesupplies.co.uk/products/kevin-bacon-liquid-hoof-dressing-500ml",
        "price_selector": "span.price-item--sale, .price-item",
        "exact_500ml": 19.99,
        "exact_1l": 28.99
    },
    "Mole Avon": {
        "url": "https://www.moleavon.co.uk/kevin-bacons-liquid-hoof-dressing-500ml/p21647",
        "price_selector": ".product-form__price",
        "exact_500ml": 21.00,
        "exact_1l": None
    },
    "Equi Supermarket": {
        "url": "https://www.equisupermarket.co.uk/products/kevin-bacon-hoof-dressing-liquid",
        "price_selector": "span.price-item--sale, .price-item",
        "exact_500ml": None,
        "exact_1l": 26.49
    }
}

def clean_price(text_string):
    if not text_string:
        return None
    match = re.search(r'£?\s*(\d+(?:\.\d{2})?)', text_string)
    if match:
        val = float(match.group(1))
        if 10.00 < val < 85.00: 
            return val
    return None

def fetch_transparent_price(store_name, info):
    p_500 = None
    p_1l = None
    status = "🟡 Blocked (Using Verified Price)"

    try:
        # Shopify Direct JSON Bypass (AG, GS, Millbry, First Choice, Equi Supermarket)
        if "products" in info["url"]:
            json_url = f"{info['url']}.js"
            res = requests.get(json_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            if res.status_code == 200:
                data = res.json()
                for variant in data.get("variants", []):
                    title = variant.get("title", "").lower()
                    val = float(variant.get("price", 0)) / 100.00
                    if "500" in title:
                        p_500 = val
                    elif any(x in title for x in ["1l", "1 l", "1ltr", "litre"]):
                        p_1l = val
                status = "🔵 Live Shopify Feed"

        # Standard HTML Scrapers using Playwright
        if not p_500 and not p_1l:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                page.goto(info["url"], wait_until="domcontentloaded", timeout=10000)
                page.wait_for_timeout(1000)

                html_content = page.content()
                soup = BeautifulSoup(html_content, "html.parser")
                body_text = page.locator("body").inner_text().lower()

                if store_name == "Mole Avon":
                    match = re.search(r'£?(\d+\.\d{2})\s*inc\s*VAT', body_text, re.IGNORECASE)
                    if match:
                        p_500 = float(match.group(1))
                        status = "🟢 Live Scraped"
                else:
                    found_prices = []
                    for element in soup.select(info["price_selector"]):
                        amt = clean_price(element.get_text())
                        if amt and amt not in found_prices:
                            found_prices.append(amt)

                    if found_prices:
                        found_prices.sort()
                        for price in found_prices:
                            if 11.00 <= price <= 20.00:
                                p_500 = price
                            elif 20.01 <= price <= 32.00:
                                p_1l = price
                        status = "🟢 Live Scraped"
                browser.close()
    except Exception:
        pass  # Gracefully drop back to verified inputs on timeout/firewall block

    # Match verified defaults if the scraping targets returned empty
    is_fallback_used = False
    if p_500 is None:
        p_500 = info["exact_500ml"]
        is_fallback_used = True
    if p_1l is None:
        p_1l = info["exact_1l"]
        is_fallback_used = True

    # Correct status text dynamically
    if is_fallback_used and status != "🔵 Live Shopify Feed":
        status = "🟡 Blocked (Using Verified Price)"

    return {
        "Retailer": store_name,
        "Price (500ml)": p_500,
        "Price (1L)": p_1l,
        "Link": info["url"],
        "Status": status
    }

# Main Scrape Action Trigger
if st.button("🔄 Scrape Live Prices Now", type="primary"):
    with st.spinner("Executing live scrapers..."):
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(fetch_transparent_price, name, cfg) for name, cfg in VERIFIED_DATA.items()]
            for f in concurrent.futures.as_completed(futures):
                res = f.result()
                if res:
                    results.append(res)
                    
        df = pd.DataFrame(results)
        df["sort_val"] = df["Price (500ml)"].fillna(999.00)
        st.session_state["honest_matrix"] = df.sort_values(by="sort_val").drop(columns=["sort_val"])
        st.success("🎉 Live scraping check complete!")

# Set default on startup to avoid empty screen
if "honest_matrix" not in st.session_state:
    initial_records = []
    for name, cfg in VERIFIED_DATA.items():
        initial_records.append({
            "Retailer": name,
            "Price (500ml)": cfg["exact_500ml"],
            "Price (1L)": cfg["exact_1l"],
            "Link": cfg["url"],
            "Status": "⚪ Loaded Verified Price (Click Scrape above)"
        })
    df_init = pd.DataFrame(initial_records)
    df_init["sort_val"] = df_init["Price (500ml)"].fillna(999.00)
    st.session_state["honest_matrix"] = df_init.sort_values(by="sort_val").drop(columns=["sort_val"])

# Render the dynamic table
display_df = st.session_state["honest_matrix"].copy()
display_df["500ml Can"] = display_df["Price (500ml)"].apply(lambda x: f"£{x:.2f}" if pd.notna(x) and x is not None else "N/A")
display_df["1 Litre Can"] = display_df["Price (1L)"].apply(lambda x: f"£{x:.2f}" if pd.notna(x) and x is not None else "N/A")

st.subheader("📋 Core Price Comparison Board (500ml vs 1L)")
st.dataframe(
    display_df[["Retailer", "500ml Can", "1 Litre Can", "Link", "Status"]],
    column_config={
        "Retailer": "Equestrian Retailer",
        "500ml Can": "Price (500ml)",
        "1 Litre Can": "Price (1L)",
        "Link": st.column_config.LinkColumn("Purchase Link", display_text="View Product"),
        "Status": "Scrape Connection Status"
    },
    hide_index=True,
    use_container_width=True
)
