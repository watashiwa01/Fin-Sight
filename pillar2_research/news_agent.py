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
        return _get_demo_news()

    return _search_live(company_name, promoter_names or [])


def _get_demo_news() -> dict:
    """Return sample news data."""
    sample = load_json(SAMPLE_DATA_DIR / "sample_company.json")
    news = sample["news_data"]
    return {
        "articles": news["articles"],
        "overall_sentiment": news["overall_sentiment"],
        "sentiment_label": news["sentiment_label"],
        "sources_checked": 4,
        "search_queries": [
            "Bharat Steel Industries fraud NPA default",
            "Rajesh Kumar Agarwal Bharat Steel litigation",
            "Bharat Steel Industries Pune news",
        ],
        "risk_score": 25,  # Low risk
        "summary": "Overall news sentiment is mildly positive. Company recently won a Rs 10 Cr order from L&T. "
                   "Steel sector faces headwinds from Chinese imports but domestic infrastructure demand remains strong.",
        "method": "demo",
    }


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
        result = _get_demo_news()
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
