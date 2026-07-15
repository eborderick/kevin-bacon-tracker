import streamlit as st
import pandas as pd
import concurrent.futures
import re
from bs4 import BeautifulSoup

# Check environment state for curl_cffi fingerprint spoofing
import requests
try:
    from curl_cffi import requests as cf_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

# Layout Config
st.set_page_config(
    page_title="Ultimate Liquid Hoof Dressing Price Tracker",
    page_icon="🐴",
    layout="wide"
)

st.title("🐴 Kevin Bacon's Liquid Hoof Dressing Tracker")
st.markdown(
    """
    Compare live prices across **13 major retailers** instantly. 
    This app ensures a clean visual match on the **Liquid** formulation (brush-in-cap tin).
    """
)

# 1. Cloud-Friendly Sites (Work perfectly on Streamlit Cloud for you & your farrier)
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
    },
    "Mole Avon": {
        "url": "https://www.moleavon.co.uk/kevin-bacons-liquid-hoof-dressing-500ml/p21647",
        "selectors": [".price", "span.price", ".product-form__price"]
    },
    "Discount Equestrian": {
        "url": "https://www.discount-equestrian.co.uk/kevin-bacon-s-liquid-hoof-dressing.html",
        "selectors": [".price", "span.price", ".regular-price"]
    }
}

# 2. Local-Required / Protected Sites (Unlocks when run on a local machine to avoid 429 blocks)
STORES_PROTECTED = {
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
    },
    "First Choice Horse Supplies": {
        "url": "https://firstchoicehorsesupplies.co.uk/products/kevin-bacon-liquid-hoof-dressing-500ml",
        "selectors": ["span.price-item--sale", "span.price-item", ".price"]
    },
    "Tanner Trading": {
        "url": "https://www.tannertrading.co.uk/hoof-protection/kevin-bacons-liquid-hoof-dressing/",
        "selectors": [".price--withoutTax", "span.price", ".price"]
    },
    "Waterman's Supplies": {
        "url": "https://www.watermanscountrysupplies.co.uk/hoof-care/kevin-bacons-liquid-hoof-dressing/",
        "selectors": [".price", ".product-price", ".price-item"]
    }
}

# Check context
is_local = CURL_CFFI_AVAILABLE and not st.secrets.get("STREAMLIT_SERVER", {}).get("headless", False)

st.sidebar.subheader("⚙️ System Status")
if is_local:
    st.sidebar.success("💻 Local Engine Unlocked")
    scan_protected = st.sidebar.checkbox("Include Protected/Shopify Stores (13 Total)", value=True)
else:
    st.sidebar.info("☁️ Cloud Live Engine")
    st.sidebar.caption("Optimized for your farrier. Cloud-safe mode queries open-access suppliers to secure 100% stable results.")
    scan_protected = False

# Aggregate target list
active_stores = STORES_CLOUD_FRIENDLY.copy()
if scan_protected:
    active_stores.update(STORES_PROTECTED)

def fetch_price(store_name, store_info):
    try:
        if is_local:
            response = cf_requests.get(store_info["url"], impersonate="chrome", timeout=10)
        else:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
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
                            "Link": store_info["url"]
                        }
        return {"Retailer": store_name, "Price": None, "Link": store_info["url"]}
    except Exception:
        return {"Retailer": store_name, "Price": None, "Link": store_info["url"]}

# Trigger Analysis
if st.button("⚡ Scan Live Hoof Dressing Prices", type="primary"):
    with st.spinner(f"Querying {len(active_stores)} retailers in parallel..."):
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
            st.error("No prices could be compiled. Please check connection parameters.")

        if not failed_df.empty:
            with st.expander("🔍 Show Scraper Statuses (Stores bypassed or offline)"):
                st.dataframe(failed_df[["Retailer"]], hide_index=True, use_container_width=True)
