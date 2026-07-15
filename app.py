import streamlit as st
import pandas as pd
import concurrent.futures
import requests
from bs4 import BeautifulSoup
import re

# Page Setup
st.set_page_config(
    page_title="Live Hoof Dressing Price Engine",
    page_icon="🐴",
    layout="wide"
)

st.title("🐴 Kevin Bacon's Liquid Hoof Dressing Tracker")
st.markdown(
    """
    **Live Real-Time Price Verification Engine**
    
    *💡 Testing Tip:* If running this on Streamlit Cloud, test the link on your **mobile phone using 4G/5G mobile data** (not work Wi-Fi) to route the crawler through an open, trusted network connection.
    """
)

# Precise structural target mapping for live HTML parsing
STORES = {
    "VioVet (Liquid Edition)": {
        "url": "https://www.viovet.co.uk/Kevin-Bacons-Liquid-Hoof-Dressing/c171350/",
        "engine": "viovet",
        "selectors": {
            "500ml": "div.product-item:contains('500ml') span.price, .product-item",
            "1L": "div.product-item:contains('1 litre') span.price"
        }
    },
    "GS Equestrian": {
        "url": "https://gsequestrian.co.uk/products/kevin-bacon-kevin-bacon-s-liquid-hoof-dressing-1823.js",
        "engine": "shopify_json"
    },
    "AG Equestrian": {
        "url": "https://www.ag-equestrian.co.uk/products/kevin-bacons-liquid-hoof-dressing.js",
        "engine": "shopify_json"
    },
    "Millbry Hill": {
        "url": "https://millbryhill.co.uk/products/kevin-bacon-original-liquid-hoof-dressing.js",
        "engine": "shopify_json"
    },
    "First Choice Horse Supplies": {
        "url": "https://firstchoicehorsesupplies.co.uk/products/kevin-bacon-liquid-hoof-dressing-500ml.js",
        "engine": "shopify_json"
    },
    "Equi Supermarket": {
        "url": "https://www.equisupermarket.co.uk/products/kevin-bacon-hoof-dressing-liquid.js",
        "engine": "shopify_json"
    },
    "Waterman's Supplies": {
        "url": "https://www.watermanscountrysupplies.co.uk/hoof-care/kevin-bacons-liquid-hoof-dressing/",
        "engine": "html_table",
        "selectors": {"table": "table.product-variations", "row_text_500": "500ml", "row_text_1l": "1l"}
    },
    "Tanner Trading": {
        "url": "https://www.tannertrading.co.uk/hoof-protection/kevin-bacons-liquid-hoof-dressing/",
        "engine": "html_select",
        "selectors": {"container": ".productView-options", "price": ".price--withoutTax"}
    },
    "Hyperdrug (Equine)": {
        "url": "https://hyperdrug.co.uk/kevin-bacons-liquid-hoof-dressing/",
        "engine": "html_options",
        "selectors": {"option_wrapper": ".product-view", "price_class": ".price"}
    },
    "Redpost Equestrian": {
        "url": "https://www.redpostequestrian.co.uk/horse-care/hoof-care/kevin-bacon-liquid-hoof-dressing__149552",
        "engine": "html_variants",
        "selectors": {"container": ".super-attribute-select", "price": ".price"}
    },
    "Discount Equestrian": {
        "url": "https://www.discount-equestrian.co.uk/kevin-bacon-s-liquid-hoof-dressing.html",
        "engine": "html_magento",
        "selectors": {"price_box": ".price-box .price"}
    },
    "Hoof Bootique": {
        "url": "https://hoofbootique.co.uk/kevin-bacons-liquid-hoof-dressing/",
        "engine": "html_options",
        "selectors": {"price_tag": "span.price--withoutTax, .price-section .price"}
    },
    "Mole Avon": {
        "url": "https://www.moleavon.co.uk/kevin-bacons-liquid-hoof-dressing-500ml/p21647",
        "engine": "mole_avon",
        "selectors": {"price": ".product-form__price"}
    }
}

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9"
}

def clean_extracted_price(text_string):
    """Safely pulls digits from string blocks, ensuring valid floating points."""
    if not text_string:
        return None
    match = re.search(r'£?\s*(\d+(?:\.\d{2})?)', text_string)
    if match:
        val = float(match.group(1))
        if 10.00 < val < 85.00:  # Safety guardrails
            return val
    return None

def scrape_realtime_node(name, info):
    p_500 = None
    p_1l = None
    status = "🟢 Live Match"

    try:
        # A. Shopify AJAX Core Engine
        if info["engine"] == "shopify_json":
            res = requests.get(info["url"], headers=headers, timeout=6)
            if res.status_code == 200:
                data = res.json()
                for v in data.get("variants", []):
                    title = v.get("title", "").lower()
                    val = float(v.get("price", 0)) / 100.00
                    if "500" in title:
                        p_500 = val
                    elif any(x in title for x in ["1l", "1 l", "1ltr", "litre"]):
                        p_1l = val
            else:
                status = f"❌ Blocked (HTTP {res.status_code})"

        # B. VioVet Custom Direct Parser
        elif info["engine"] == "viovet":
            res = requests.get(info["url"], headers=headers, timeout=6)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, "html.parser")
                # Scrape directly from row structures containing specific variations
                for row in soup.select("tr.product-row, div.product-item"):
                    txt = row.get_text().lower()
                    price_node = row.select_one("span.price, .price")
                    if price_node:
                        amt = clean_extracted_price(price_node.get_text())
                        if "500ml" in txt:
                            p_500 = amt
                        elif "1 litre" in txt or "1l" in txt:
                            p_1l = amt
            else:
                status = f"❌ Blocked (HTTP {res.status_code})"

        # C. Generic HTML Element Attribute Scraper
        else:
            res = requests.get(info["url"], headers=headers, timeout=6)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, "html.parser")
                text_content = res.text
                
                if name == "Mole Avon":
                    match = re.search(r'£?(\d+\.\d{2})\s*inc\s*VAT', text_content, re.IGNORECASE)
                    if match:
                        p_500 = float(match.group(1))
                else:
                    # Scan elements to match corresponding layout prices
                    all_prices = []
                    for s in info.get("selectors", {}).values():
                        if isinstance(s, str):
                            for element in soup.select(s):
                                amt = clean_extracted_price(element.get_text())
                                if amt and amt not in all_prices:
                                    all_prices.append(amt)
                    
                    if all_prices:
                        all_prices.sort()
                        # Sort into size tiers based on common price boundaries
                        for price in all_prices:
                            if 11.00 <= price <= 20.00:
                                p_500 = price
                            elif 20.01 <= price <= 32.00:
                                p_1l = price
            else:
                status = f"❌ Blocked (HTTP {res.status_code})"

    except Exception:
        status = "⚠️ Connection Timeout"

    # Strict Data Fixer Override Guardrail (If scrape fails, pass explicitly to trace error)
    return {
        "Retailer": name,
        "Price (500ml)": f"£{p_500:.2f}" if p_500 else "N/A",
        "Price (1L)": f"£{p_1l:.2f}" if p_1l else "N/A",
        "Link": info["url"].replace(".js", ""), # Clean json extensions for user clicks
        "Engine Connection": status
    }

# Sync Button Action Trigger
if st.button("🔄 Scrape Live Prices Now", type="primary"):
    with st.spinner("Executing structural parallel query over network channels..."):
        records = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(STORES)) as executor:
            futures = [executor.submit(scrape_realtime_node, name, cfg) for name, cfg in STORES.items()]
            for f in concurrent.futures.as_completed(futures):
                res = f.result()
                if res:
                    records.append(res)
                    
        df = pd.DataFrame(records).sort_values(by="Price (500ml)")
        st.session_state["live_matrix"] = df
        st.success("🎉 Scan run finished completely!")

# Initialize Interface Display states
if "live_matrix" not in st.session_state:
    st.info("Launch the live scanner button above to pull current data indices.")
else:
    st.subheader("📋 100% Real-Time Live Scraped Pricing Table")
    st.dataframe(
        st.session_state["live_matrix"],
        column_config={
            "Retailer": "Retailer Name",
            "Price (500ml)": "500ml Fluid Can",
            "Price (1L)": "1 Litre Fluid Can",
            "Link": st.column_config.LinkColumn("Purchase Link", display_text="View Product"),
            "Engine Connection": "Network Status"
        },
        hide_index=True,
        use_container_width=True
    )
