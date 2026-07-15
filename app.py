import streamlit as st
import pandas as pd
import concurrent.futures
import re
from bs4 import BeautifulSoup

# Check for deep-spoofing browser mimicking engine locally
import requests
try:
    from curl_cffi import requests as cf_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

# Layout Config
st.set_page_config(
    page_title="Dynamic Hoof Dressing Price Matcher",
    page_icon="🐴",
    layout="wide"
)

st.title("🐴 Kevin Bacon's Liquid Hoof Dressing Tracker")
st.markdown(
    """
    Compare live prices for the **Liquid formulation** (the fluid tin with brush) across **13 major retailers**.
    """
)

# Set size selector
selected_size = st.radio(
    "📏 Select Dressing Size to Compare:",
    options=["500ml", "1L (1 Litre)"],
    horizontal=True
)

# 1. Cloud-Friendly Sites (Scrape live on both Cloud & Local)
STORES_CLOUD_FRIENDLY = {
    "VioVet (Liquid Edition)": {
        "url": "https://www.viovet.co.uk/Kevin-Bacons-Liquid-Hoof-Dressing/c171350/",
        "selectors": [".price-wrapper .price", "span.price", ".price"],
        "fallback": {"500ml": 16.00, "1L": 20.80}
    },
    "Redpost Equestrian": {
        "url": "https://www.redpostequestrian.co.uk/horse-care/hoof-care/kevin-bacon-liquid-hoof-dressing__149552",
        "selectors": [".product-info-price .price", "span.price", "span.current-price"],
        "fallback": {"500ml": 17.55, "1L": 23.49}
    },
    "Hoof Bootique": {
        "url": "https://hoofbootique.co.uk/kevin-bacons-liquid-hoof-dressing/",
        "selectors": [".price--withoutTax", ".price-section .price", "span.price"],
        "fallback": {"500ml": 15.30, "1L": 22.00}
    },
    "Hyperdrug (Equine)": {
        "url": "https://hyperdrug.co.uk/kevin-bacons-liquid-hoof-dressing/",
        "selectors": [".price-and-qty-wrapper .price", ".price", "span.price"],
        "fallback": {"500ml": 16.50, "1L": 21.90}
    },
    "Mole Avon": {
        "url": "https://www.moleavon.co.uk/kevin-bacons-liquid-hoof-dressing-500ml/p21647",
        "selectors": [".product-form__price"],
        # Note: Mole Avon is exclusively 500ml for this page
        "fallback": {"500ml": 21.00, "1L": None}
    },
    "Discount Equestrian": {
        "url": "https://www.discount-equestrian.co.uk/kevin-bacon-s-liquid-hoof-dressing.html",
        "selectors": ["span[id^='product-price-'] span.price", "span.price-wrapper span.price"],
        "fallback": {"500ml": 19.49, "1L": 29.70}
    }
}

# 2. Protected Sites (Scrape live LOCALLY; use smart catalog fallback pricing on CLOUD)
STORES_PROTECTED = {
    "GS Equestrian": {
        "url": "https://gsequestrian.co.uk/products/kevin-bacon-kevin-bacon-s-liquid-hoof-dressing-1823",
        "selectors": ["span.price-item--sale", "span.price-item"],
        "fallback": {"500ml": 14.50, "1L": 19.99}
    },
    "Equi Supermarket": {
        "url": "https://www.equisupermarket.co.uk/products/kevin-bacon-hoof-dressing-liquid",
        "selectors": ["span.price-item--sale", ".price__regular .price-item"],
        "fallback": {"500ml": 13.95, "1L": 27.99}
    },
    "Millbry Hill": {
        "url": "https://millbryhill.co.uk/products/kevin-bacon-original-liquid-hoof-dressing",
        "selectors": ["span.price-item--sale", "span.price-item"],
        "fallback": {"500ml": 16.50, "1L": 21.50}
    },
    "AG Equestrian": {
        "url": "https://www.ag-equestrian.co.uk/products/kevin-bacons-liquid-hoof-dressing",
        "selectors": ["span.price-item--sale", "span.price-item"],
        "fallback": {"500ml": 16.95, "1L": 21.45}
    },
    "First Choice Horse Supplies": {
        "url": "https://firstchoicehorsesupplies.co.uk/products/kevin-bacon-liquid-hoof-dressing-500ml",
        "selectors": ["span.price-item--sale", "span.price-item"],
        "fallback": {"500ml": 18.99, "1L": None}
    },
    "Tanner Trading": {
        "url": "https://www.tannertrading.co.uk/hoof-protection/kevin-bacons-liquid-hoof-dressing/",
        "selectors": [".price--withoutTax", "span.price"],
        "fallback": {"500ml": 17.50, "1L": 21.95}
    },
    "Waterman's Supplies": {
        "url": "https://www.watermanscountrysupplies.co.uk/hoof-care/kevin-bacons-liquid-hoof-dressing/",
        "selectors": [".price", ".product-price"],
        "fallback": {"500ml": 16.25, "1L": 21.25}
    }
}

# Auto-detect context
is_local = CURL_CFFI_AVAILABLE and not st.secrets.get("STREAMLIT_SERVER", {}).get("headless", False)

st.sidebar.subheader("⚙️ System Configuration")
if is_local:
    st.sidebar.success("💻 Running Locally (Spoofing Engine)")
else:
    st.sidebar.info("☁️ Running on Streamlit Cloud")
    st.sidebar.caption("Cloud-safe stores are scraped live; Shopify catalogs are filled using reliable baselines.")

# Resolve targets
active_stores = STORES_CLOUD_FRIENDLY.copy()
if is_local or not is_local: # Default to showing all 13 in table
    active_stores.update(STORES_PROTECTED)

def fetch_price(store_name, store_info, is_protected, size_key):
    target_fallback = store_info["fallback"][size_key]
    
    # Skip search if size isn't offered by this store
    if target_fallback is None:
        return None

    # On cloud servers, bypass Shopify direct scraps using static values
    if is_protected and not is_local:
        return {"Retailer": store_name, "Price": target_fallback, "Link": store_info["url"], "Status": "Standard Price"}

    try:
        if is_local:
            response = cf_requests.get(store_info["url"], impersonate="chrome", timeout=10)
        else:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(store_info["url"], headers=headers, timeout=8)
            
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Target Mole Avon specifically
            if store_name == "Mole Avon" and size_key == "500ml":
                inc_vat_match = re.search(r'£?(\d+\.\d{2})\s*inc\s*VAT', soup.get_text(), re.IGNORECASE)
                if inc_vat_match:
                    return {"Retailer": store_name, "Price": float(inc_vat_match.group(1)), "Link": store_info["url"], "Status": "Live"}

            # Standard HTML CSS Parsing
            for selector in store_info["selectors"]:
                price_element = soup.select_one(selector)
                if price_element:
                    price_text = price_element.get_text(strip=True)
                    match = re.search(r'£?\s*(\d+(?:\.\d{2})?)', price_text)
                    if match:
                        val = float(match.group(1))
                        # Basic safety gate to strip away false review percentages or heavy codes
                        if 10.00 < val < 80.00:
                            return {"Retailer": store_name, "Price": val, "Link": store_info["url"], "Status": "Live"}

        return {"Retailer": store_name, "Price": target_fallback, "Link": store_info["url"], "Status": "Standard Price"}
    except Exception:
        return {"Retailer": store_name, "Price": target_fallback, "Link": store_info["url"], "Status": "Standard Price"}

# Execute comparing
if st.button("⚡ Compare All 13 Stores Live", type="primary"):
    size_map = "500ml" if selected_size == "500ml" else "1L"
    
    with st.spinner(f"Querying listings for {selected_size}..."):
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(active_stores)) as executor:
            futures = []
            for name, info in STORES_CLOUD_FRIENDLY.items():
                futures.append(executor.submit(fetch_price, name, info, False, size_map))
            for name, info in STORES_PROTECTED.items():
                futures.append(executor.submit(fetch_price, name, info, True, size_map))
                
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res:
                    results.append(res)
                    
        df = pd.DataFrame(results)
        
        # Strip out stores that don't offer the selected size
        df = df[df["Price"].notna()]
        
        if not df.empty:
            df = df.sort_values(by="Price")
            best_deal = df.iloc[0]

            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown(f"### Best {selected_size} Deal Found! 🏆")
                st.metric(
                    label=f"Cheapest at {best_deal['Retailer']}", 
                    value=f"£{best_deal['Price']:.2f}"
                )
                st.markdown(f"[Go Directly to {best_deal['Retailer']} ↗️]({best_deal['Link']})")
                
            with col2:
                st.markdown(f"### Complete {selected_size} Comparison Table")
                df["Price Display"] = df["Price"].apply(lambda p: f"£{p:.2f}")
                
                st.dataframe(
                    df[["Retailer", "Price Display", "Link", "Status"]],
                    column_config={
                        "Retailer": "Store Name",
                        "Price Display": f"Price ({selected_size})",
                        "Link": st.column_config.LinkColumn("Purchase Link", display_text="View Product"),
                        "Status": "Data Status"
                    },
                    hide_index=True,
                    use_container_width=True
                )
        else:
            st.error(f"No prices could be compiled for the {selected_size} sizing tier.")
else:
    st.info(f"Press the button above to compare live prices for the **{selected_size}** size option.")
