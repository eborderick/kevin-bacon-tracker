import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import concurrent.futures
import re
import cloudscraper
import urllib.parse

# Streamlit UI Configuration
st.set_page_config(
    page_title="Ultimate Hoof Dressing Price Tracker",
    page_icon="🐴",
    layout="wide"
)

# Sidebar for Cloudflare Bypass Settings
st.sidebar.header("🛡️ Cloudflare Bypass Options")
st.sidebar.markdown(
    """
    If websites block requests on the hosted cloud server, toggle a free proxy API below.
    """
)
bypass_mode = st.sidebar.selectbox(
    "Bypass Mode", 
    ["Default Browser Emulation (Free)", "Scrape.do API (100% Success)"]
)

api_token = ""
if bypass_mode == "Scrape.do API (100% Success)":
    api_token = st.sidebar.text_input("Enter Scrape.do Token:", type="password")
    st.sidebar.markdown(
        "[Get a free Scrape.do Token](https://scrape.do/) (1,000 free requests per month)"
    )

st.title("🐴 Kevin Bacon's Liquid Hoof Dressing Real-Time Tracker")
st.markdown(
    "Compare live prices across **9 major retailers** instantly. Hit the scan button to retrieve the best deals."
)

# 9 Retailers mapped with fallback selectors
STORES = {
    "VioVet": {
        "url": "https://www.viovet.co.uk/Kevin-Bacons-Hoof-Dressing-For-Horses/c9027/",
        "selectors": [".price", "span.price", ".price-wrapper .price"]
    },
    "GS Equestrian": {
        "url": "https://gsequestrian.co.uk/products/kevin-bacon-kevin-bacon-s-liquid-hoof-dressing-1823",
        "selectors": ["span.price-item--sale", "span.price-item"]
    },
    "Redpost Equestrian": {
        "url": "https://www.redpostequestrian.co.uk/horse-care/hoof-care/kevin-bacon-liquid-hoof-dressing__149552",
        "selectors": [".product-info-price .price", "span.price", "span.current-price"]
    },
    "Equi Supermarket": {
        "url": "https://www.equisupermarket.co.uk/products/kevin-bacon-hoof-dressing-liquid",
        "selectors": ["span.price-item--sale", ".price__regular .price-item", "span.price"]
    },
    "Tanner Trading": {
        "url": "https://www.tannertrading.co.uk/hoof-protection/kevin-bacons-liquid-hoof-dressing/",
        "selectors": ["span.price", ".productView-price .price--withoutTax"]
    },
    "Hoof Bootique": {
        "url": "https://hoofbootique.co.uk/kevin-bacons-liquid-hoof-dressing/",
        "selectors": [".price--withoutTax", ".price-section .price", "span.price"]
    },
    "Millbry Hill": {
        "url": "https://millbryhill.co.uk/products/kevin-bacon-original-liquid-hoof-dressing",
        "selectors": ["span.price-item--sale", "span.price-item"]
    },
    "AG Equestrian": {
        "url": "https://www.ag-equestrian.co.uk/products/kevin-bacons-liquid-hoof-dressing",
        "selectors": ["span.price-item--sale", "span.price-item"]
    },
    "Waterman's Supplies": {
        "url": "https://www.watermanscountrysupplies.co.uk/hoof-care/kevin-bacons-liquid-hoof-dressing/",
        "selectors": [".price", ".product-price", ".price-item"]
    }
}

# Worker thread scraper function
def fetch_store_price(store_name, store_info, mode, token):
    try:
        # Step 1: Execute request based on selected mode
        if mode == "Scrape.do API (100% Success)" and token:
            # Route request through Scrape.do proxy to bypass cloud datacenter bans
            encoded_url = urllib.parse.quote(store_info["url"])
            api_url = f"https://api.scrape.do/?token={token}&url={encoded_url}"
            response = requests.get(api_url, timeout=15)
        else:
            # Create cloudscraper session to bypass local Cloudflare JS checks
            scraper = cloudscraper.create_scraper()
            response = scraper.get(store_info["url"], timeout=10)

        # Step 2: Parse response
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
        return {"Retailer": store_name, "Price": None, "Link": store_info["url"], "Status": "Blocked / Timeout"}

if st.button("⚡ Scan All 9 Retailers Live", type="primary"):
    if bypass_mode == "Scrape.do API (100% Success)" and not api_token:
        st.warning("⚠️ Please enter your Scrape.do API token in the sidebar to use proxy mode.")
    else:
        with st.spinner("Scraping stores in parallel..."):
            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(STORES)) as executor:
                future_to_store = {
                    executor.submit(fetch_store_price, name, info, bypass_mode, api_token): name 
                    for name, info in STORES.items()
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
                cheapest = success_df.iloc[0]

                col1, col2 = st.columns([1, 2])
                with col1:
                    st.markdown("### Best Deal Found! 🏆")
                    st.metric(
                        label=f"Cheapest at {cheapest['Retailer']}", 
                        value=f"£{cheapest['Price']:.2f}"
                    )
                    st.markdown(f"[Go Directly to {cheapest['Retailer']} ↗️]({cheapest['Link']})")
                    
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
                st.error("No prices could be compiled. The hosted server is currently rate-limited by store firewalls. Try enabling proxy mode in the sidebar!")

            if not failed_df.empty:
                with st.expander("🔍 Show Scraper Statuses (Offline / Parsing issues)"):
                    st.dataframe(failed_df[["Retailer", "Status"]], hide_index=True, use_container_width=True)
else:
    st.info("Launch the scanner above to run a fresh query on all 9 retailers.")
