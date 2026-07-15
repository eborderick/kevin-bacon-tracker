import streamlit as st
import pandas as pd
import concurrent.futures
import requests
from bs4 import BeautifulSoup
import re

st.set_page_config(
    page_title="100% Real-Time Hoof Dressing Tracker",
    page_icon="🐴",
    layout="wide"
)

st.title("🐴 Live Kevin Bacon's Liquid Hoof Dressing Tracker")
st.markdown(
    """
    This app performs **genuine, real-time scrapes** on all 13 UK retailers.
    *Note: If running on Streamlit Cloud, some sites protected by Cloudflare/Shopify will block the cloud server's datacenter IP.*
    """
)

# Detailed configurations for direct text-pattern matching
STORES = {
    "Waterman's Supplies": {
        "url": "https://www.watermanscountrysupplies.co.uk/hoof-care/kevin-bacons-liquid-hoof-dressing/",
        "engine": "regex",
        "patterns": {
            "500ml": r"(?:500ml|liquid hoof dressing)[^\d]*£\s*(\d+\.\d{2})",
            "1L": r"(?:1l|1 litre|1lt)[^\d]*£\s*(\d+\.\d{2})"
        }
    },
    "AG Equestrian": {
        "url": "https://www.ag-equestrian.co.uk/products/kevin-bacons-liquid-hoof-dressing",
        "engine": "shopify"
    },
    "GS Equestrian": {
        "url": "https://gsequestrian.co.uk/products/kevin-bacon-kevin-bacon-s-liquid-hoof-dressing-1823",
        "engine": "shopify"
    },
    "Tanner Trading": {
        "url": "https://www.tannertrading.co.uk/hoof-protection/kevin-bacons-liquid-hoof-dressing/",
        "engine": "regex",
        "patterns": {
            "500ml": r"500ml[^\d]*£\s*(\d+\.\d{2})",
            "1L": r"1lt[^\d]*£\s*(\d+\.\d{2})"
        }
    },
    "Hyperdrug (Equine)": {
        "url": "https://hyperdrug.co.uk/kevin-bacons-liquid-hoof-dressing/",
        "engine": "regex",
        "patterns": {
            "500ml": r"500ml[^\d]*£\s*(\d+\.\d{2})",
            "1L": r"(?:1l|1 litre|1lt)[^\d]*£\s*(\d+\.\d{2})"
        }
    },
    "Redpost Equestrian": {
        "url": "https://www.redpostequestrian.co.uk/horse-care/hoof-care/kevin-bacon-liquid-hoof-dressing__149552",
        "engine": "regex",
        "patterns": {
            "500ml": r"500ml\s*-\s*£\s*(\d+\.\d{2})",
            "1L": r"1l\s*-\s*£\s*(\d+\.\d{2})"
        }
    },
    "VioVet (Liquid Edition)": {
        "url": "https://www.viovet.co.uk/Kevin-Bacons-Liquid-Hoof-Dressing/c171350/",
        "engine": "regex",
        "patterns": {
            "500ml": r"500ml Tin with Brush[^\d]*£\s*(\d+\.\d{2})",
            "1L": r"1 litre Tin with Brush[^\d]*£\s*(\d+\.\d{2})"
        }
    },
    "Millbry Hill": {
        "url": "https://millbryhill.co.uk/products/kevin-bacon-original-liquid-hoof-dressing",
        "engine": "shopify"
    },
    "Discount Equestrian": {
        "url": "https://www.discount-equestrian.co.uk/kevin-bacon-s-liquid-hoof-dressing.html",
        "engine": "regex",
        "patterns": {
            "500ml": r"500ml[^\d]*£\s*(\d+\.\d{2})",
            "1L": r"(?:1l|1ltr|1 litre)[^\d]*£\s*(\d+\.\d{2})"
        }
    },
    "Hoof Bootique": {
        "url": "https://hoofbootique.co.uk/kevin-bacons-liquid-hoof-dressing/",
        "engine": "regex",
        "patterns": {
            "500ml": r"500ml[^\d]*£\s*(\d+\.\d{2})",
            "1L": r"(?:1l|1ltr|1-litre)[^\d]*£\s*(\d+\.\d{2})"
        }
    },
    "First Choice Horse Supplies": {
        "url": "https://firstchoicehorsesupplies.co.uk/products/kevin-bacon-liquid-hoof-dressing-500ml",
        "engine": "shopify"
    },
    "Mole Avon": {
        "url": "https://www.moleavon.co.uk/kevin-bacons-liquid-hoof-dressing-500ml/p21647",
        "engine": "regex",
        "patterns": {
            "500ml": r"£?(\d+\.\d{2})\s*inc\s*VAT",
            "1L": r"NON_EXISTENT_PATTERN"
        }
    },
    "Equi Supermarket": {
        "url": "https://www.equisupermarket.co.uk/products/kevin-bacon-hoof-dressing-liquid",
        "engine": "shopify"
    }
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

def scrape_live_store(store_name, info):
    price_500 = None
    price_1l = None
    status = "🟢 Live Scraped"

    try:
        # Engine A: Shopify AJAX JSON Endpoint
        if info["engine"] == "shopify":
            json_url = f"{info['url']}.js"
            res = requests.get(json_url, headers=headers, timeout=6)
            if res.status_code == 200:
                data = res.json()
                for variant in data.get("variants", []):
                    title = variant.get("title", "").lower()
                    v_price = float(variant.get("price", 0)) / 100.00
                    if "500" in title:
                        price_500 = v_price
                    elif any(k in title for k in ["1l", "1 l", "1ltr", "litre"]):
                        price_1l = v_price
            else:
                status = f"❌ Blocked (HTTP {res.status_code})"

        # Engine B: Deep Regex Text-Pattern Extraction
        else:
            res = requests.get(info["url"], headers=headers, timeout=6)
            if res.status_code == 200:
                html_text = res.text
                soup = BeautifulSoup(res.content, "html.parser")
                clean_text = soup.get_text(separator=" ").strip()
                
                # 500ml extraction
                m_500 = re.search(info["patterns"]["500ml"], clean_text, re.IGNORECASE)
                if m_500:
                    price_500 = float(m_500.group(1))
                
                # 1L extraction
                m_1l = re.search(info["patterns"]["1L"], clean_text, re.IGNORECASE)
                if m_1l:
                    price_1l = float(m_1l.group(1))
            else:
                status = f"❌ Blocked (HTTP {res.status_code})"
                
    except Exception as e:
        status = f"⚠️ Connection Error"

    return {
        "Retailer": store_name,
        "Price (500ml)": f"£{price_500:.2f}" if price_500 else "N/A",
        "Price (1L)": f"£{price_1l:.2f}" if price_1l else "N/A",
        "Link": info["url"],
        "Scrape Status": status
    }

# Dynamic Trigger Button
if st.button("🔄 Scrape Live Prices Now", type="primary"):
    with st.spinner("Connecting to UK retailers in parallel..."):
        records = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(STORES)) as executor:
            futures = [executor.submit(scrape_live_store, name, cfg) for name, cfg in STORES.items()]
            for f in concurrent.futures.as_completed(futures):
                res = f.result()
                if res:
                    records.append(res)
                    
        df = pd.DataFrame(records).sort_values(by="Scrape Status")
        st.session_state["live_df"] = df
        st.success("🎉 Live scrape completed!")

# Initial State Setup
if "live_df" not in st.session_state:
    st.info("Click the button above to launch the real-time web scraper.")
else:
    st.subheader("📋 Real-Time Scraping Results")
    st.dataframe(
        st.session_state["live_df"],
        column_config={
            "Retailer": "Store Name",
            "Price (500ml)": "500ml Can",
            "Price (1L)": "1 Litre Can",
            "Link": st.column_config.LinkColumn("Purchase Link", display_text="View Product"),
            "Scrape Status": "Scraper Status"
        },
        hide_index=True,
        use_container_width=True
    )
