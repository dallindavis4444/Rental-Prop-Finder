import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

st.set_page_config(page_title="High CoC Rental Finder", layout="wide")

st.title("High Cash-on-Cash Return Rental Finder")
st.markdown("**Markets similar to Cleveland • ≥20% CoC • Cash flow ≥20% of the mortgage**")

# Reference deal banner
st.info("""
**Your Reference Deal:** 4070 E 141st St, Cleveland, OH 44128  
Purchased Oct 2026 for **$185,000**. Total cash invested **$37,746**.  
Rents: $1,100 + $1,100 = **$2,200/mo**. Ongoing CoC **24.5%** (Year 1: 21.9%). Cap rate 11.4%.  
This is the template — we are looking for deals that match or beat these numbers.
""")

# Sidebar assumptions
st.sidebar.header("Underwriting Assumptions")
down_pct = st.sidebar.slider("Down Payment %", 10, 30, 20) / 100
interest_rate = st.sidebar.slider("Interest Rate % (DSCR)", 5.0, 10.0, 7.0) / 100
loan_term = st.sidebar.slider("Loan Term (years)", 15, 30, 30)
closing_pct = st.sidebar.slider("Closing Costs % of Price", 1.0, 5.0, 2.5) / 100
inspections = st.sidebar.number_input("Inspections + Appraisal ($)", 500, 5000, 1500)
repairs_pct = st.sidebar.slider("Upfront Repairs % of Price", 0, 20, 5) / 100
vacancy = st.sidebar.slider("Vacancy Rate %", 0, 15, 7) / 100
opex_ratio = st.sidebar.slider("Operating Expense Ratio % (of EGI)", 30, 60, 35) / 100
min_coc = st.sidebar.slider("Minimum CoC %", 10, 40, 20) / 100
min_cf_margin = st.sidebar.slider("Min Cash Flow as % of Mortgage", 0, 100, 20) / 100

show_only_passing = st.sidebar.checkbox("Show only deals that pass filters", value=False)

# Mortgage calculation
def monthly_payment(principal, annual_rate, years):
    if principal <= 0 or annual_rate <= 0:
        return 0
    monthly_rate = annual_rate / 12
    n = years * 12
    return principal * (monthly_rate * (1 + monthly_rate)**n) / ((1 + monthly_rate)**n - 1)

# Underwriting function
def underwrite(price, monthly_rent, repairs_override=None):
    loan = price * (1 - down_pct)
    monthly_mort = monthly_payment(loan, interest_rate, loan_term)
    annual_ds = monthly_mort * 12
    
    repairs = repairs_override if repairs_override is not None else price * repairs_pct
    closing = price * closing_pct
    acquisition = (price * down_pct) + closing + inspections + repairs
    
    gross_annual = monthly_rent * 12
    egi = gross_annual * (1 - vacancy)
    opex = egi * opex_ratio
    noi = egi - opex
    annual_cf = noi - annual_ds
    
    coc = annual_cf / acquisition if acquisition > 0 else 0
    cf_margin = annual_cf / annual_ds if annual_ds > 0 else 0
    dscr = noi / annual_ds if annual_ds > 0 else 0
    
    return {
        "price": price,
        "monthly_rent": monthly_rent,
        "acquisition_cost": acquisition,
        "monthly_mortgage": monthly_mort,
        "annual_ds": annual_ds,
        "noi": noi,
        "annual_cf": annual_cf,
        "coc_pct": coc * 100,
        "cf_margin_pct": cf_margin * 100,
        "dscr": dscr,
        "passes": coc >= min_coc and cf_margin >= min_cf_margin
    }

# Expanded sample properties grouped by region
SAMPLE_PROPERTIES = [
    # Your actual deal as reference
    {"address": "4070 E 141st St", "city": "Cleveland", "state": "OH", "price": 185000, "beds": 4, "units": 2, "est_rent": 2200, "sqft": None, "is_reference": True,
     "image": "https://t2.realgeeks.media/thumbnail/pM0SgbTPX2hcLMo_wX-aiYa5kPc=/https://property-images.realgeeks.com/ohmlsnow/a160db7d5fb320b1ed7125637e9cab9c.jpg",
     "listing_url": "https://www.redfin.com/OH/Cleveland/4070-E-141st-St-44128/home/70794434"},
    # Real Cleveland listings with full URLs
    {"address": "3405 W 126th St", "city": "Cleveland", "state": "OH", "price": 179000, "beds": 4, "units": 2, "est_rent": 1900, "sqft": 3118,
     "image": "https://photos.zillowstatic.com/fp/d1d4402ce4832d5d9d3e167c6c04eb07-cc_ft_1536.jpg",
     "listing_url": "https://www.zillow.com/homedetails/3405-W-126th-St-Cleveland-OH-44111/33365726_zpid/"},
    {"address": "3643 W 48th St", "city": "Cleveland", "state": "OH", "price": 150000, "beds": 5, "units": 2, "est_rent": 1800, "sqft": 2492,
     "image": "https://images-listings.era.com/OH_NORMLS/52/55/73/7/_P/5255737_P00.jpg",
     "listing_url": "https://www.ezhomesearch.com/propertydetails/us/oh/cleveland/3643-w-48th-street-44102/5255737/"},
    {"address": "3720 W 117th St", "city": "Cleveland", "state": "OH", "price": 180000, "beds": 4, "units": 2, "est_rent": 1950, "sqft": 1798,
     "image": "https://photos.zillowstatic.com/fp/28b5ddf26f14e13bc931c17f58967605-cc_ft_1536.jpg",
     "listing_url": "https://www.zillow.com/homedetails/3424-W-117th-St-Cleveland-OH-44111/33359268_zpid/"},
    # Detroit
    {"address": "14543 Sussex St", "city": "Detroit", "state": "MI", "price": 77500, "beds": 4, "units": 2, "est_rent": 1600, "sqft": 2302,
     "image": "https://www.trulia.com/pictures/thumbs_6/zillowstatic/fp/19b875d173531e62b963416a364e2eaa-full.jpg",
     "listing_url": "https://www.trulia.com/home/14543-sussex-st-detroit-mi-48227-88350959"},
    # Pittsburgh
    {"address": "1453 Woodbine St", "city": "Pittsburgh", "state": "PA", "price": 369000, "beds": 4, "units": 2, "est_rent": 2800, "sqft": None,
     "image": "https://images-listings.era.com/PA_WPN/17/81/32/4/_P/1781324_P00.jpg",
     "listing_url": "https://www.era.com/property/detail/pa/pittsburgh/1453-woodbine-st/lid-P00800000HJcacqmt8vBmcYRL5YgjFvUAU5od8k4"},
    {"address": "102 Stewart Ave", "city": "Pittsburgh", "state": "PA", "price": 179900, "beds": 4, "units": 2, "est_rent": 1900, "sqft": None,
     "image": "https://images-listings.coldwellbanker.com/PA_WPN/17/68/40/1/_P/1768401_P00.jpg",
     "listing_url": "https://www.coldwellbanker.com/pa/pittsburgh/102-stewart-ave/lid-P00800000HFEvP9JkfDVngtRNrdiioE5qNk5gwyI"},
    {"address": "117 Cleveland Ave", "city": "Pittsburgh", "state": "PA", "price": 150000, "beds": 4, "units": 2, "est_rent": 1700, "sqft": None,
     "image": "https://ssl.cdn-redfin.com/photo/162/mbpaddedwide/786/genMid.1766786_0.jpg",
     "listing_url": "https://www.redfin.com/PA/Pittsburgh/117-Cleveland-Ave-15202/home/73546783"},
    # Indianapolis
    {"address": "817-819 N Dearborn", "city": "Indianapolis", "state": "IN", "price": 190000, "beds": 4, "units": 2, "est_rent": 2125, "sqft": None,
     "image": "https://imagedelivery.net/fWVa4wuRZ2I5RStnrvkU3A/roots/mls/019c9aeed6d4e74b4f05093b757f171b3d958b70fde2dc7836dfc0295d74b2ca/w=1200,q=80,format=jpeg",
     "listing_url": "https://www.zillow.com/homedetails/817-819-N-Dearborn-St-Indianapolis-IN-46201/"},
    # Additional Cleveland
    {"address": "3514 Mapledale Ave", "city": "Cleveland", "state": "OH", "price": 84900, "beds": 4, "units": 2, "est_rent": 1400, "sqft": 2177,
     "image": "https://ssl.cdn-redfin.com/photo/159/mbpaddedwide/746/genMid.5180746_2.jpg",
     "listing_url": "https://www.redfin.com/OH/Cleveland/3418-Mapledale-Ave-44109/home/70737695"},
    {"address": "1919 Holmden Ave", "city": "Cleveland", "state": "OH", "price": 119900, "beds": 7, "units": 2, "est_rent": 1800, "sqft": 2550,
     "image": "https://images-listings.century21.com/OH_NORMLS/52/56/33/5/_P/5256335_P00.jpg",
     "listing_url": "https://www.zillow.com/homedetails/1919-Holmden-Ave-Cleveland-OH-44109/33337929_zpid/"},
    # Additional Detroit
    {"address": "9810 Chenlot St", "city": "Detroit", "state": "MI", "price": 74900, "beds": 6, "units": 2, "est_rent": 1500, "sqft": 2686,
     "image": "https://cdn.listingphotos.sierrastatic.com/large/v1786101773/183/183_20261062182_01.jpg",
     "listing_url": "https://www.zillow.com/homedetails/9810-Chenlot-St-Detroit-MI-48204/88075609_zpid/"},
    {"address": "15796 14th St", "city": "Detroit", "state": "MI", "price": 69900, "beds": 4, "units": 2, "est_rent": 1400, "sqft": 2520,
     "image": "https://cdn.listingphotos.sierrastatic.com/large/v1786802795/183/183_20261055511_01.jpg",
     "listing_url": "https://www.trulia.com/home/15796-14th-st-detroit-mi-48238-88242575"},
    # Memphis
    {"address": "518 Harahan Rd", "city": "Memphis", "state": "TN", "price": 135000, "beds": 4, "units": 2, "est_rent": 1600, "sqft": 1922,
     "image": "https://photos.zillowstatic.com/fp/28bc2c1cd6bcf302f65144ba82ad04be-cc_ft_1536.jpg",
     "listing_url": "https://www.zillow.com/homedetails/518-Harahan-Rd-Memphis-TN-38109/42242096_zpid/"},
    {"address": "2452 Saratoga Ave", "city": "Memphis", "state": "TN", "price": 120000, "beds": 2, "units": 2, "est_rent": 1400, "sqft": 1107,
     "image": "https://photos.zillowstatic.com/fp/6f8a8d1cb1a4959057e90a836e74bd5c-cc_ft_1536.jpg",
     "listing_url": "https://www.zillow.com/homedetails/2452-Saratoga-Ave-Memphis-TN-38114/42203366_zpid/"},
    # St. Louis
    {"address": "4201 San Francisco Ave", "city": "St. Louis", "state": "MO", "price": 140000, "beds": 4, "units": 2, "est_rent": 1700, "sqft": 2350,
     "image": "https://images-listings.century21.com/MO_MARIS/26/06/68/96/_P/26066896_P00.jpg",
     "listing_url": "https://www.trulia.com/home/4201-san-francisco-ave-saint-louis-mo-63115-2961506"},
    {"address": "3926 Dunnica Ave", "city": "St. Louis", "state": "MO", "price": 179900, "beds": 4, "units": 2, "est_rent": 1900, "sqft": 2526,
     "image": "https://www.trulia.com/pictures/thumbs_6/zillowstatic/fp/87541bc74be38896560e91908c47626b-full.jpg",
     "listing_url": "https://www.trulia.com/home/3926-dunnica-ave-saint-louis-mo-63116-2974473"},
    # Birmingham
    {"address": "7100 1st Ave S", "city": "Birmingham", "state": "AL", "price": 80000, "beds": 4, "units": 2, "est_rent": 1300, "sqft": 2166,
     "image": "https://images.ezhomesearch.com/1206/82ccaf8415df229b66dd33098f2f1029/936813901.jpeg",
     "listing_url": "https://www.trulia.com/home/7100-1st-ave-s-birmingham-al-35206-953901"},
    {"address": "2304 22nd St", "city": "Birmingham", "state": "AL", "price": 120000, "beds": 3, "units": 2, "est_rent": 1500, "sqft": 1968,
     "image": "https://photos.zillowstatic.com/fp/6a3da6c14795dd96535aa6358b58bc80-cc_ft_1536.jpg",
     "listing_url": "https://www.zillow.com/homedetails/2304-22nd-St-Birmingham-AL-35208/2069042129_zpid/"},
    # Toledo
    {"address": "1688 Avondale Ave", "city": "Toledo", "state": "OH", "price": 99900, "beds": 4, "units": 2, "est_rent": 1500, "sqft": 1806,
     "image": "https://www.trulia.com/pictures/thumbs_6/zillowstatic/fp/b68a4354f0b5bc1ffec6d50f768337df-full.jpg",
     "listing_url": "https://www.trulia.com/home/1688-avondale-ave-toledo-oh-43607-34625235"},
    {"address": "1547 Airline Ave", "city": "Toledo", "state": "OH", "price": 117000, "beds": 4, "units": 2, "est_rent": 1400, "sqft": 1248,
     "image": "https://ssl.cdn-redfin.com/photo/282/mbpaddedwide/608/genMid.10014608_0.jpg",
     "listing_url": "https://www.redfin.com/OH/Toledo/1547-Airline-Ave-43609/home/122586161"},
    # Akron
    {"address": "382 Madison Ave", "city": "Akron", "state": "OH", "price": 135000, "beds": 6, "units": 2, "est_rent": 1700, "sqft": 3277,
     "image": "https://ssl.cdn-redfin.com/photo/159/mbpaddedwide/537/genMid.5237537_0.jpg",
     "listing_url": "https://www.redfin.com/OH/Akron/382-Madison-Ave-44320/home/100654487"},
    {"address": "756 Brown St", "city": "Akron", "state": "OH", "price": 49500, "beds": 5, "units": 2, "est_rent": 1200, "sqft": 2132,
     "image": "https://photos.zillowstatic.com/fp/088cd57a381871f71729119334b41bd3-cc_ft_1536.jpg",
     "listing_url": "https://www.zillow.com/homedetails/756-Brown-St-Akron-OH-44311/35470593_zpid/"},
    # More Indianapolis
    {"address": "28 N Lasalle St", "city": "Indianapolis", "state": "IN", "price": 179000, "beds": 4, "units": 2, "est_rent": 2000, "sqft": None,
     "image": "https://images.ezhomesearch.com/497/ba0ad81e7a52277679df2f3be05b87f9/129992879.jpeg",
     "listing_url": "https://www.zillow.com/homedetails/28-N-Lasalle-St-Indianapolis-IN-46201/1088757_zpid/"},
    {"address": "2267 Adams St", "city": "Indianapolis", "state": "IN", "price": 125000, "beds": 6, "units": 2, "est_rent": 1600, "sqft": None,
     "image": "https://ssl.cdn-redfin.com/photo/147/mbpaddedwide/007/genMid.22129007_1.jpg",
     "listing_url": "https://www.redfin.com/IN/Indianapolis/2267-Adams-St-46218/home/60182238"},
    # Kansas City
    {"address": "4509 Monroe Ave", "city": "Kansas City", "state": "MO", "price": 130000, "beds": 4, "units": 2, "est_rent": 1600, "sqft": 1728,
     "image": "https://photos.zillowstatic.com/fp/f9c8a139bea7123abc07424ac8502971-cc_ft_1536.jpg",
     "listing_url": "https://www.zillow.com/homedetails/4509-Monroe-Ave-Kansas-City-MO-64130/2357914_zpid/"},
    {"address": "2023 College Ave", "city": "Kansas City", "state": "MO", "price": 154950, "beds": 4, "units": 2, "est_rent": 1700, "sqft": None,
     "image": "https://images-listings.coldwellbanker.com/MOKS_HL/26/04/00/3/_P/2604003_P00.jpg",
     "listing_url": "https://www.zillow.com/homedetails/2023-College-Ave-Kansas-City-MO-64127/2326510_zpid/"},
    # Cincinnati
    {"address": "2117 Saint Leo Pl", "city": "Cincinnati", "state": "OH", "price": 185000, "beds": 5, "units": 2, "est_rent": 2000, "sqft": 2100,
     "image": "https://s3.amazonaws.com/ShowMojo-Dev/55368401/02df0b802f/WM/large.jpg?1782317332",
     "listing_url": "https://www.zillow.com/homedetails/2117-Saint-Leo-Pl-Cincinnati-OH-45211/34253317_zpid/"},
    {"address": "2055 Queen City Ave", "city": "Cincinnati", "state": "OH", "price": 137000, "beds": 3, "units": 2, "est_rent": 1600, "sqft": 1845,
     "image": "https://photos.zillowstatic.com/fp/d73490acf656795e0b853b3ada26825e-cc_ft_1536.jpg",
     "listing_url": "https://www.zillow.com/homedetails/2055-Queen-City-Ave-Cincinnati-OH-45214/34252575_zpid/"},
    # Buffalo
    {"address": "77 Littlefield Ave", "city": "Buffalo", "state": "NY", "price": 119900, "beds": 3, "units": 2, "est_rent": 1600, "sqft": 1420,
     "image": "https://photos.zillowstatic.com/fp/c912b0b420f1dda681a486c76d76ab31-cc_ft_1536.jpg",
     "listing_url": "https://www.zillow.com/homedetails/77-Littlefield-Ave-Buffalo-NY-14211/30196192_zpid/"},
    {"address": "115 Goembel Ave", "city": "Buffalo", "state": "NY", "price": 49900, "beds": 4, "units": 2, "est_rent": 1300, "sqft": 2187,
     "image": "https://photos.zillowstatic.com/fp/ff5c55d4854c7640ba156480f312030a-cc_ft_1536.jpg",
     "listing_url": "https://www.zillow.com/homedetails/115-Goembel-Ave-Buffalo-NY-14211/30195583_zpid/"},
    # Milwaukee
    {"address": "4700 N 50th St", "city": "Milwaukee", "state": "WI", "price": 159900, "beds": 4, "units": 2, "est_rent": 1800, "sqft": 2215,
     "image": "https://ssl.cdn-redfin.com/photo/128/mbpaddedwide/795/genMid.1973795_0.jpg",
     "listing_url": "https://www.redfin.com/WI/Milwaukee/4700-N-50th-St-53218/home/58054515"},
    {"address": "2463 W Chambers St", "city": "Milwaukee", "state": "WI", "price": 119900, "beds": 5, "units": 2, "est_rent": 1600, "sqft": 2318,
     "image": "https://cdn02.deltamediagroup.com/listing_photos/active/19013/190128544/1.jpg?hash=499cb635abd9ccfcadeaa93690ab3a81",
     "listing_url": "https://www.trulia.com/home/2463-w-chambers-st-2465-milwaukee-wi-53206-2078420261"},
    # Louisville
    {"address": "2733 Dumesnil St", "city": "Louisville", "state": "KY", "price": 96000, "beds": 3, "units": 2, "est_rent": 1507, "sqft": 2219,
     "image": "https://ssl.cdn-redfin.com/photo/185/mbpaddedwide/930/genMid.1717930_0.jpg",
     "listing_url": "https://www.redfin.com/KY/Louisville/2733-Dumesnil-St-40211/home/71257680"},
    {"address": "1443 S 32nd St", "city": "Louisville", "state": "KY", "price": 149900, "beds": 2, "units": 2, "est_rent": 1600, "sqft": 1143,
     "image": "https://cdn.listingphotos.sierrastatic.com/large/v1782201806/3/3_1721232_01.jpg",
     "listing_url": "https://www.zillow.com/homedetails/1443-S-32nd-St-Louisville-KY-40211/73664772_zpid/"},
    # Columbus
    {"address": "2445-2447 Hiawatha St", "city": "Columbus", "state": "OH", "price": 129900, "beds": 2, "units": 2, "est_rent": 1500, "sqft": 984,
     "image": "https://cdn.listingphotos.sierrastatic.com/large/v1787381197/111/111_226031935_01.jpg",
     "listing_url": "https://www.redfin.com/OH/Columbus/2447-Hiawatha-St-43211/home/197184234"},
    {"address": "413 S Napoleon Ave", "city": "Columbus", "state": "OH", "price": 175000, "beds": 4, "units": 2, "est_rent": 1800, "sqft": None,
     "image": "https://cdn.listingphotos.sierrastatic.com/large/v1793118312/111/111_226040807_01.jpg",
     "listing_url": "https://www.era.com/property/detail/oh/columbus/413-s-napoleon-ave/lid-P00800000HJW8qCq9dQt0CyuNQI5g2jhktgh5EPb"},
]

# Live Market Scan (RentCast)
st.sidebar.header("Live Market Scan")
api_key = st.sidebar.text_input("RentCast API Key", type="password", help="Get a free key at app.rentcast.io (50 free requests/month)")
search_city = st.sidebar.text_input("City", value="Cleveland")
search_state = st.sidebar.text_input("State (2-letter)", value="OH", max_chars=2)
search_limit = st.sidebar.slider("Max listings to pull", 5, 50, 10)
run_live = st.sidebar.button("Scan Live Listings")

# Live scan logic
live_results = []
if run_live and api_key:
    with st.spinner(f"Pulling multi-family listings in {search_city}, {search_state}..."):
        try:
            headers = {"Accept": "application/json", "X-Api-Key": api_key}
            params = {
                "city": search_city,
                "state": search_state.upper(),
                "type": "Multi-Family",
                "status": "Active",
                "limit": search_limit,
                "price": "*:250000"
            }
            resp = requests.get("https://api.rentcast.io/v1/listings/sale", headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            listings = resp.json()
            
            for listing in listings:
                price = listing.get("price") or listing.get("listPrice") or 0
                if not price:
                    continue
                beds = listing.get("bedrooms") or 4
                address = listing.get("address") or listing.get("formattedAddress") or "Unknown"
                city = listing.get("city") or search_city
                state = listing.get("state") or search_state
                
                # Better rent estimate via RentCast AVM if possible
                est_rent = max(price * 0.01, beds * 450)
                try:
                    rent_params = {
                        "address": f"{address}, {city}, {state}",
                        "propertyType": "Multi-Family",
                        "bedrooms": beds
                    }
                    rent_resp = requests.get(
                        "https://api.rentcast.io/v1/avm/rent/long-term",
                        headers=headers,
                        params=rent_params,
                        timeout=15
                    )
                    if rent_resp.status_code == 200:
                        rent_data = rent_resp.json()
                        if rent_data.get("rent"):
                            est_rent = rent_data["rent"]
                except:
                    pass  # fall back to heuristic
                
                photo = None
                if listing.get("photos"):
                    photo = listing["photos"][0] if isinstance(listing["photos"], list) else None
                listing_url = listing.get("url") or listing.get("listingUrl") or f"https://www.zillow.com/homes/{address.replace(' ', '-')}_{city}-{state}/"
                
                res = underwrite(price, est_rent)
                res.update({
                    "address": address,
                    "city": city,
                    "state": state,
                    "beds": beds,
                    "units": listing.get("units") or 2,
                    "image": photo or "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800",
                    "listing_url": listing_url,
                    "is_live": True
                })
                live_results.append(res)
            
            st.success(f"Found {len(live_results)} multi-family listings.")
        except Exception as e:
            st.error(f"API error: {str(e)}. Check your key or try again.")

# Use live results if available, otherwise samples
if live_results:
    df = pd.DataFrame(live_results)
    st.header(f"Live Listings — {search_city}, {search_state}")
else:
    results = []
    for prop in SAMPLE_PROPERTIES:
        res = underwrite(prop["price"], prop["est_rent"])
        res.update(prop)
        results.append(res)
    df = pd.DataFrame(results)
    st.header("Suggested Listings by State")

# Filter if requested
if show_only_passing:
    df = df[df["passes"] == True]

# Group by state
states = sorted(df["state"].unique()) if not df.empty else []

st.caption("Scroll through cards. Key numbers are shown on each listing so you can decide quickly. Adjust assumptions in the sidebar — everything updates live.")

if df.empty:
    st.warning("No properties match the current filters.")
else:
    # Tabs by state
    tabs = st.tabs(states)
    for i, state in enumerate(states):
        with tabs[i]:
            state_df = df[df["state"] == state]
            st.subheader(f"{state} — {len(state_df)} properties")
            
            # Display in a grid of cards (2 per row)
            for idx in range(0, len(state_df), 2):
                cols = st.columns(2)
                for j in range(2):
                    if idx + j < len(state_df):
                        prop = state_df.iloc[idx + j]
                        with cols[j]:
                            with st.container(border=True):
                                # Clickable property photo
                                if "image" in prop and prop["image"]:
                                    listing_url = prop.get("listing_url", "#")
                                    st.markdown(
                                        f'<a href="{listing_url}" target="_blank"><img src="{prop["image"]}" style="width:100%; border-radius:8px; cursor:pointer;"></a>',
                                        unsafe_allow_html=True
                                    )
                                
                                # Header with pass badge
                                badge = "🟢 PASS" if prop["passes"] else "🔴 FAIL"
                                live_tag = " 🔴 LIVE" if prop.get("is_live") else ""
                                st.markdown(f"**{prop['address']}**{live_tag}")
                                st.markdown(f"{prop['city']}, {prop['state']} &nbsp;&nbsp; {badge}")
                                
                                # Key metrics in columns
                                m1, m2, m3 = st.columns(3)
                                m1.metric("Price", f"${prop['price']:,.0f}")
                                m2.metric("Est. Rent", f"${prop['monthly_rent']:,.0f}/mo")
                                m3.metric("CoC Return", f"{prop['coc_pct']:.1f}%")
                                
                                m4, m5, m6 = st.columns(3)
                                m4.metric("Annual CF", f"${prop['annual_cf']:,.0f}")
                                m5.metric("Mortgage", f"${prop['monthly_mortgage']:,.0f}/mo")
                                m6.metric("DSCR", f"{prop['dscr']:.2f}")
                                
                                # Extra details + listing link
                                st.caption(f"{prop['units']} units • {prop['beds']} beds • CF margin {prop['cf_margin_pct']:.1f}% of mortgage • Acquisition ${prop['acquisition_cost']:,.0f}")
                                if "listing_url" in prop and prop["listing_url"]:
                                    st.link_button("View Listing →", prop["listing_url"], use_container_width=True)

# Quick calculator still available
with st.expander("Quick Underwriting Calculator (any property)"):
    col1, col2 = st.columns(2)
    with col1:
        price_in = st.number_input("Purchase Price ($)", min_value=50000, max_value=1000000, value=160000, step=5000)
        rent_in = st.number_input("Estimated Monthly Rent (total all units) ($)", min_value=500, max_value=10000, value=1600, step=50)
    with col2:
        repairs_in = st.number_input("Upfront Repairs Override ($ , 0 = use %)", min_value=0, max_value=100000, value=0, step=500)
    
    if price_in:
        result = underwrite(price_in, rent_in, repairs_in if repairs_in > 0 else None)
        metrics = st.columns(4)
        metrics[0].metric("Cash-on-Cash", f"{result['coc_pct']:.1f}%", delta="PASS" if result['passes'] else "FAIL")
        metrics[1].metric("Annual Cash Flow", f"${result['annual_cf']:,.0f}")
        metrics[2].metric("Monthly Mortgage", f"${result['monthly_mortgage']:,.0f}")
        metrics[3].metric("DSCR", f"{result['dscr']:.2f}")

st.caption(f"Last updated {datetime.now().strftime('%Y-%m-%d %H:%M')}. Change any assumption on the left to refresh all cards.")
