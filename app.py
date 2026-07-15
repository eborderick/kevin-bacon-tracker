import streamlit as st
import pandas as pd
import concurrent.futures
import re
from bs4 import BeautifulSoup

# We import standard requests and curl_cffi for local spoofing
import requests
try:
    from curl_cffi import requests as cf_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

# Streamlit UI Setup
st.set_page_config(
    page_title="Kevin Bacon's Liquid Price Matcher",
    page_icon="🐴",
    layout="wide"
)

st.title("🐴 Kevin Bacon's Liquid Hoof Dressing Tracker")
st.markdown(
    """
    Compare live prices for the **Liquid version** (usually comes in a tin with a brush cap). 
    This app is split to work flawlessly on both **Streamlit Cloud** (for you and your farrier) and **Locally** on your laptop.
    """
)

# Retailer configurations (Strictly mapped to the LIQUID version)
STORES_CLOUD_FRIENDLY = {
    "VioVet (Liquid Edition)": {
        "url": "https://www.viovet.co.uk/Kevin-Bacons-Liquid-Hoof-Dressing/c171350/",
        "selectors": [".price", "span.price", ".price-wrapper .price"]
    },
    "Redpost Equestrian": {
        "url": "https://www.redpostequestrian.co.uk/horse-care/hoof-care/kevin-bacon-liquid-hoof-dressing__149552",
        "selectors": [".product-info-price .price", "span.price", "span.current-price"]
    },
    "Hoof Bootique": {
        "url": "https://hoofbootique.co.uk/kevin-bacons-liquid-hoof-dressing/",
        "selectors": [".price--withoutTax", ".price-section .price", "span.price"]
    },
    "Hyperdrug (Equine)": {
        "url": "https://hyperdrug.co.uk/kevin-bacons-liquid-hoof-dressing/",
        "selectors": [".price-and-qty-wrapper .price", ".price", "span.price"]
    }
}

STORES_PROTECTED_SHOPIFY = {
    "GS Equestrian": {
        "url": "https://gsequestrian.co.uk/products/kevin-bacon-kevin-bacon-s-liquid-hoof-dressing-1823",
        "selectors": ["span.price-item--sale", "span.price-item"]
    },
    "Equi Supermarket": {
        "url": "https://www.equisupermarket.co.uk/products/kevin-bacon-hoof-dressing-liquid",
        "selectors": ["span.price-item--sale", ".price__regular .price-item", "span.price"]
    },
    "Millbry Hill": {
        "url": "https://millbryhill.co.uk/products/kevin-bacon-original-liquid-hoof-dressing",
        "selectors": ["span.price-item--sale", "span.price-item"]
    },
    "AG Equestrian": {
        "url": "https://www.ag-equestrian.co.uk/products/kevin-bacons-liquid-hoof-dressing",
        "selectors": ["span.price-item--sale", "span.price-item"]
    }
}

# Auto-detect if running locally or on Streamlit Cloud
is_local = CURL_CFFI_AVAILABLE and not st.secrets.get("STREAMLIT_SERVER", {}).get("headless", False)

# Sidebar indicator
st.sidebar.subheader("⚙️ System Status")
if is_local:
    st.sidebar.success("💻 Running Locally (Spoofing Mode Unlocked)")
    scan_all = st.sidebar.checkbox("Include Protected Shopify Stores", value=True)
else:
    st.sidebar.info("☁️ Running on Streamlit Cloud")
    st.sidebar.caption("To prevent Cloudflare blocks, standard Cloud scans target highly cooperative, cloud-friendly stores.")
    scan_all = False

# Choose stores list based on status
active_stores = STORES_CLOUD_FRIENDLY.copy()
if scan_all:
    active_stores.update(STORES_PROTECTED_SHOPIFY)

# Scraper Logic
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def fetch_price(store_name, store_info):
    try:
        # If running locally, use curl_cffi to mimic browser fingerprints. On cloud, use standard requests.
        if is_local:
            response = cf_requests.get(store_info["url"], impersonate="chrome", timeout=10)
        else:
            response = requests.get(store_info["url"], headers=headers, timeout=8)
            
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            for selector in store_info["selectors"]:
                price_element = soup.select_one(selector)
                if price_element:
                    price_text = price_element.get_text(strip=True)
                    match = re.search(r'\d+(?:\.\d{2})?', price_text)
                    if match:
                        return {
                            "Retailer": store_name,
                            "Price": float(match.group(0)),
                            "Link": store_info["url"],
                            "Status": "Online"
                        }
        return {"Retailer": store_name, "Price": None, "Link": store_info["url"], "Status": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"Retailer": store_name, "Price": None, "Link": store_info["url"], "Status": "Timeout/Blocked"}

# Trigger Button
if st.button("⚡ Scan Live Hoof Dressing Prices", type="primary"):
    with st.spinner("Fetching prices..."):
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(active_stores)) as executor:
            future_to_store = {
                executor.submit(fetch_price, name, info): name for name, info in active_stores.items()
            }
            for future in concurrent.futures.as_completed(future_to_store):
                res = future.result()
                if res:
                    results.append(res)
                    
        df = pd.DataFrame(results)
        success_df = df[df["Price"].notna()].copy()
        failed_df = df[df["Price"].isna()].copy()

        if not success_df.empty:
            success_df = success_df.sort_values(by="Price")
            best_deal = success_df.iloc[0]

            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown("### Best Deal Found! 🏆")
                st.metric(
                    label=f"Cheapest at {best_deal['Retailer']}", 
                    value=f"£{best_deal['Price']:.2f}"
                )
                st.markdown(f"[Go Directly to {best_deal['Retailer']} ↗️]({best_deal['Link']})")
                
            with col2:
                st.markdown("### All Available Live Prices")
                success_df["Price Display"] = success_df["Price"].apply(lambda p: f"£{p:.2f}")
                success_df["Shop Link"] = success_df["Link"].apply(lambda url: f"[View Product]({url})")
                
                st.dataframe(
                    success_df[["Retailer", "Price Display", "Shop Link"]],
                    column_config={
                        "Retailer": "Store",
                        "Price Display": "Price",
                        "Shop Link": st.column_config.LinkColumn("Purchase Link")
                    },
                    hide_index=True,
                    use_container_width=True
                )
        else:
            st.error("No prices could be compiled. Please try scanning again.")

        if not failed_df.empty:
            with st.expander("🔍 Show Scraper Statuses (Offline / Restricted Stores)"):
                st.dataframe(failed_df[["Retailer", "Status"]], hide_index=True, use_container_width=True)
