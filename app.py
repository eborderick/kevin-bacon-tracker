import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import concurrent.futures
import re

# Streamlit UI Configuration
st.set_page_config(
    page_title="Ultimate Hoof Dressing Price Tracker",
    page_icon="🐴",
    layout="wide"
)

st.title("🐴 Kevin Bacon's Liquid Hoof Dressing Real-Time Tracker")
st.markdown(
    "Compare live prices across **9 major retailers** instantly. Simply hit the scan button below to retrieve the best deals."
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

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br"
}

# Worker thread scraper function
def fetch_store_price(store_name, store_info):
    try:
        response = requests.get(store_info["url"], headers=headers, timeout=7)
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
        return {"Retailer": store_name, "Price": None, "Link": store_info["url"], "Status": f"Status code {response.status_code}"}
    except Exception as e:
        return {"Retailer": store_name, "Price": None, "Link": store_info["url"], "Status": "Timeout / Blocked"}

if st.button("⚡ Scan All 9 Retailers Live", type="primary"):
    with st.spinner("Scraping stores in parallel..."):
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(STORES)) as executor:
            future_to_store = {
                executor.submit(fetch_store_price, name, info): name for name, info in STORES.items()
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
            st.error("No prices could be compiled. The websites may be temporarily rate-limiting requests.")

        if not failed_df.empty:
            with st.expander("🔍 Show Scraper Statuses (Offline / Parsing issues)"):
                st.dataframe(failed_df[["Retailer", "Status"]], hide_index=True, use_container_width=True)
else:
    st.info("Launch the scanner above to run a fresh query on all 9 retailers.")
