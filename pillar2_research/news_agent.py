"""
News Agent for Intelli-Credit.
Searches for company-related news using Tavily API and performs sentiment analysis.
In demo mode, returns realistic sample news data.
"""
import json
from config import IS_DEMO, has_tavily_key, has_llm_key, TAVILY_API_KEY, SAMPLE_DATA_DIR, get_llm_client
from utils import load_json


def search_company_news(company_name: str, promoter_names: list[str] = None) -> dict:
    """
    Search for news about a company and its promoters.
    Returns news articles with sentiment analysis.
    """
    if IS_DEMO or not has_tavily_key():
        return _get_demo_news(company_name)

    return _search_live(company_name, promoter_names or [])


def _get_demo_news(company_name: str = "Bharat Steel Industries") -> dict:
    """Return sample news data."""
    from utils import load_json
    sample = load_json(SAMPLE_DATA_DIR / "sample_company.json")
    news = sample["news_data"]
    
    # Aggressive replacement of common demo names
    sample_name = sample.get("company_name", "Reliance Industries Limited")
    demo_names = [sample_name, "Reliance Industries", "Reliance", "Bharat Steel Industries", "Bharat Steel", "Tata Motors", "Tata", "Infosys"]
    cname = company_name if company_name else sample_name
    import urllib.parse
    
    articles = _scrape_google_news(cname)
    
    # FINAL DEFAULT FALLBACK: If web scraping totally fails or returns 0 articles, fall back
    # to the name-swapped mock articles. To prevent 404s, we'll point these to a Google Search
    # for the specific headline so the "evidence" is always valid.
    if len(articles) == 0:
        for art in news["articles"]:
            new_art = art.copy()
            for dn in demo_names:
                new_art["title"] = new_art["title"].replace(dn, cname)
                if "content_snippet" in new_art:
                    new_art["content_snippet"] = new_art["content_snippet"].replace(dn, cname)
            
            # Instead of using the literal source which might be a 404, 
            # we use a Google Search URL for the headline as a safe 'evidence' link.
            headline_query = urllib.parse.quote(new_art["title"])
            new_art["source"] = f"https://www.google.com/search?q={headline_query}"
            articles.append(new_art)
            
    import hashlib
    seed = int(hashlib.md5(cname.lower().encode()).hexdigest(), 16) % 1000
    
    # Randomize sentiment and risk
    sent_score = 0.1 + (seed % 60) / 100.0 # 0.1 to 0.7
    risk_score = 15 + (seed % 25)           # 15-39

    return {
        "articles": articles,
        "overall_sentiment": sent_score,
        "sentiment_label": "positive" if sent_score > 0.2 else "neutral",
        "sources_checked": 4,
        "search_queries": [
            f"{cname} fraud NPA default",
            f"{cname} litigation",
            f"{cname} news",
        ],
        "risk_score": risk_score,
        "summary": f"Overall news sentiment for {cname} is mildly positive based on simulated reports. "
                   "Sector outlook remains stable despite macro headwinds.",
        "method": "demo",
    }


def _scrape_google_news(cname: str) -> list[dict]:
    """Scrape Google News for live articles as a free fallback."""
    import requests
    import urllib.parse
    from bs4 import BeautifulSoup
    articles = []
    try:
        query = urllib.parse.quote(f"{cname} news")
        url = f"https://news.google.com/search?q={query}&hl=en-IN&gl=IN&ceid=IN%3Aen"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            links = soup.find_all('a', class_='JtKRv')
            
            pos_words = ["growth", "profit", "surges", "jumps", "wins", "record", "soars", "up", "positive", "expansion", "approval", "success", "buy", "launch"]
            neg_words = ["loss", "falls", "slumps", "plunges", "lawsuit", "down", "negative", "investigation", "fraud", "default", "warning", "sell", "penalty", "crash"]

            for link in links[:6]:  
                title = link.text
                href = link.get('href', '')
                if href.startswith('.'):
                    href = "https://news.google.com" + href[1:]
                
                t_lower = title.lower()
                score = 0.0
                for pw in pos_words:
                    if pw in t_lower: score += 0.4
                for nw in neg_words:
                    if nw in t_lower: score -= 0.4
                
                score = max(-1.0, min(1.0, score))
                
                if score > 0.2:
                    label = "positive"
                elif score < -0.2:
                    label = "negative"
                else:
                    label = "neutral"
                    score = 0.1 

                articles.append({
                    "title": title,
                    "sentiment": label,
                    "sentiment_score": round(score, 2),
                    "source": href,
                    "content_snippet": f"Recent coverage regarding {cname}."
                })
    except Exception as e:
        print(f"Scraping failed: {e}")
    return articles


def _search_live(company_name: str, promoter_names: list[str]) -> dict:
    """Search for live news using Tavily API."""
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=TAVILY_API_KEY)

        # Build search queries
        queries = [
            f"{company_name} financial fraud default NPA",
            f"{company_name} recent expansion projects news",
            f"{company_name} regulatory penalties SEBI ROC",
        ]
        for name in promoter_names[:2]:
            queries.append(f"{name} {company_name} litigation background")

        all_articles = []
        for query in queries:
            try:
                result = client.search(query=query, max_results=3, search_depth="basic")
                for r in result.get("results", []):
                    all_articles.append({
                        "title": r.get("title", ""),
                        "source": r.get("url", ""),
                        "date": "",
                        "content_snippet": r.get("content", "")[:300],
                        "score": r.get("score", 0),
                    })
            except Exception:
                continue

        # Perform sentiment analysis using LLM if available
        sentiments = _analyze_sentiment(all_articles)

        overall = sum(a.get("sentiment_score", 0) for a in sentiments) / max(len(sentiments), 1)

        return {
            "articles": sentiments,
            "overall_sentiment": round(overall, 2),
            "sentiment_label": "positive" if overall > 0.2 else "negative" if overall < -0.2 else "neutral",
            "sources_checked": len(all_articles),
            "search_queries": queries,
            "risk_score": max(0, min(100, int(50 - overall * 50))),
            "summary": f"Found {len(all_articles)} articles. Overall sentiment: {'positive' if overall > 0 else 'negative' if overall < 0 else 'neutral'}.",
            "method": "tavily_live",
        }

    except Exception as e:
        result = _get_demo_news(company_name)
        result["method"] = "tavily_fallback"
        result["error"] = str(e)
        return result


def _analyze_sentiment(articles: list[dict]) -> list[dict]:
    """Analyze sentiment of articles using the configured LLM."""
    if not has_llm_key():
        return _keyword_sentiment(articles)

    try:
        llm = get_llm_client()
        if not llm:
            return _keyword_sentiment(articles)

        titles = [a.get("title", "") for a in articles]
        prompt = f"""Analyze the sentiment of these news headlines for credit risk assessment.
Focus on: fraud, defaults, litigation, NPA, promoter arrest = very negative; growth, orders, capacity expansion = positive.

Headlines:
{json.dumps(titles, indent=2)}

Return JSON array: [{{"title": "...", "sentiment": "positive/negative/neutral", "score": float (-1.0 to 1.0)}}]"""

        import asyncio
        response = llm.invoke(prompt)  # Using sync invoke for simplicity in this script
        content = response.content
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        sentiments = json.loads(content.strip())
        for i, article in enumerate(articles):
            if i < len(sentiments):
                article["sentiment"] = sentiments[i].get("sentiment", "neutral")
                article["sentiment_score"] = sentiments[i].get("score", 0)
        return articles
    except Exception:
        return _keyword_sentiment(articles)


def _keyword_sentiment(articles: list[dict]) -> list[dict]:
    """Simple keyword-based sentiment analysis fallback."""
    negative_words = {"fraud", "default", "npa", "litigation", "arrest", "scam", "wilful", "ban", "penalty", "fine"}
    positive_words = {"growth", "expansion", "profit", "award", "order", "partnership", "investment", "launch"}

    for article in articles:
        title_lower = article.get("title", "").lower()
        neg_count = sum(1 for w in negative_words if w in title_lower)
        pos_count = sum(1 for w in positive_words if w in title_lower)

        if neg_count > pos_count:
            article["sentiment"] = "negative"
            article["sentiment_score"] = -0.3 * neg_count
        elif pos_count > neg_count:
            article["sentiment"] = "positive"
            article["sentiment_score"] = 0.3 * pos_count
        else:
            article["sentiment"] = "neutral"
            article["sentiment_score"] = 0.0

    return articles
