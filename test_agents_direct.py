import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from pillar2_research.mca_agent import lookup_mca_data
from pillar2_research.ecourts_agent import lookup_litigation
from pillar2_research.sector_agent import analyze_sector
from pillar2_research.news_agent import search_company_news

def test(name):
    print(f"\n--- {name} ---")
    mca = lookup_mca_data(name)
    lit = lookup_litigation(name)
    sec = analyze_sector("Technology" if "zomato" in name.lower() else "Automobile")
    news = search_company_news(name)
    
    print(f"MCA Risk: {mca['risk_score']} | Comp: {mca['compliance']['compliance_score']}")
    print(f"LIT Risk: {lit['risk_score']} | Cases: {lit['total_cases']}")
    print(f"SEC Risk: {sec['risk_score']} | Out: {sec['outlook_score']}")
    print(f"NEWS Risk: {news['risk_score']} | Sent: {news['overall_sentiment']}")
    return mca['risk_score'], lit['total_cases']

r1 = test("ola electric")
r2 = test("zomato")

if r1 != r2:
    print("\n✅ SUCCESS: Research metrics are unique and dynamic!")
else:
    print("\n❌ FAILURE: Research metrics are identical.")
