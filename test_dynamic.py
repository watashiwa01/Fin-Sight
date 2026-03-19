import requests
import json

base_url = 'http://127.0.0.1:8140/api'

def test_company(name):
    print(f"\nTesting: {name}")
    try:
        r = requests.post(f"{base_url}/research", json={"company_name": name}, timeout=120)
        data = r.json()
        
        research = data['research']
        mca = research['mca']
        lit = research['litigation']
        sector = research['sector']
        news = research['news']
        
        print(f"MCA: Risk={mca['risk_score']}, Compliance={mca['compliance']['compliance_score']}%")
        print(f"LIT: Risk={lit['risk_score']}, Total Cases={lit['total_cases']}")
        print(f"SECTOR: Risk={sector['risk_score']}, Outlook={sector['outlook_score']}")
        print(f"NEWS: Risk={news['risk_score']}, Sentiment={news['overall_sentiment']}")
        print(f"Summary: {mca['summary'][:80]}...")
        
        return {
            "mca_risk": mca['risk_score'],
            "lit_cases": lit['total_cases'],
            "sector_risk": sector['risk_score']
        }
    except Exception as e:
        print(f"❌ Error testing {name}: {e}")
        return None

ola = test_company("ola electric")
zomato = test_company("zomato")

if ola and zomato:
    diff_mca = ola['mca_risk'] != zomato['mca_risk']
    diff_lit = ola['lit_cases'] != zomato['lit_cases']
    
    print("\n" + "="*40)
    if diff_mca and diff_lit:
        print("SUCCESS: Data is uniquely dynamic for different companies!")
    else:
        print("WARNING: Some data points are still identical.")
    print("="*40)
