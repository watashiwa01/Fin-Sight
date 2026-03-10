"""
Agent Orchestrator for Intelli-Credit — Pillar 2.
Uses a proper LangGraph StateGraph with parallel sub-agent nodes (Send API).
Each agent (News, MCA, e-Courts, Sector) runs independently and results
are aggregated by a supervisor node.
"""
from __future__ import annotations

import operator
from typing import TypedDict, Annotated

from pillar2_research.news_agent    import search_company_news
from pillar2_research.mca_agent     import lookup_mca_data
from pillar2_research.ecourts_agent import lookup_litigation
from pillar2_research.sector_agent  import analyze_sector


# ─── State Schema ────────────────────────────────────────────────

class ResearchState(TypedDict):
    company_name:      str
    cin:               str
    industry:          str
    promoter_names:    list[str]
    qualitative_notes: list[str]
    news_results:      dict
    mca_results:       dict
    litigation_results: dict
    sector_results:    dict
    overall_research:  dict
    errors:            Annotated[list[str], operator.add]  # merges error lists


# ─── Agent Node Functions ─────────────────────────────────────────

def _node_news(state: ResearchState) -> dict:
    try:
        return {"news_results": search_company_news(
            state["company_name"], state.get("promoter_names", [])
        )}
    except Exception as e:
        return {"news_results": {}, "errors": [f"news_agent: {e}"]}


def _node_mca(state: ResearchState) -> dict:
    try:
        return {"mca_results": lookup_mca_data(
            state["company_name"], state.get("cin", "")
        )}
    except Exception as e:
        return {"mca_results": {}, "errors": [f"mca_agent: {e}"]}


def _node_ecourts(state: ResearchState) -> dict:
    try:
        return {"litigation_results": lookup_litigation(
            state["company_name"], state.get("promoter_names", [])
        )}
    except Exception as e:
        return {"litigation_results": {}, "errors": [f"ecourts_agent: {e}"]}


def _node_sector(state: ResearchState) -> dict:
    try:
        return {"sector_results": analyze_sector(state.get("industry", ""))}
    except Exception as e:
        return {"sector_results": {}, "errors": [f"sector_agent: {e}"]}


def _node_supervisor(state: ResearchState) -> dict:
    """Aggregate all agent results into a unified research report."""
    news_risk      = state.get("news_results",      {}).get("risk_score", 50)
    mca_risk       = state.get("mca_results",       {}).get("risk_score", 50)
    lit_risk       = state.get("litigation_results",{}).get("risk_score", 50)
    sector_risk    = state.get("sector_results",    {}).get("risk_score", 50)

    composite = (
        news_risk   * 0.25 +
        mca_risk    * 0.25 +
        lit_risk    * 0.30 +
        sector_risk * 0.20
    )

    def risk_level(s: float) -> str:
        return "LOW" if s < 25 else "MODERATE" if s < 50 else "HIGH" if s < 75 else "CRITICAL"

    provenance = []
    for key, label in [
        ("news_results",       "News & Sentiment"),
        ("mca_results",        "MCA21 Filings"),
        ("litigation_results", "Litigation / NJDG"),
        ("sector_results",     "Sector Analysis"),
    ]:
        r = state.get(key, {})
        provenance.append({
            "agent":      label,
            "method":     r.get("method", "unknown"),
            "risk_score": r.get("risk_score", 0),
            "summary":    r.get("summary", "No data"),
        })

    return {
        "overall_research": {
            "company_name":           state["company_name"],
            "composite_risk_score":   round(composite, 1),
            "risk_level":             risk_level(composite),
            "news":                   state.get("news_results", {}),
            "mca":                    state.get("mca_results", {}),
            "litigation":             state.get("litigation_results", {}),
            "sector":                 state.get("sector_results", {}),
            "qualitative_notes":      state.get("qualitative_notes", []),
            "provenance":             provenance,
            "errors":                 state.get("errors", []),
            "summary":                _build_summary(state, composite, risk_level(composite)),
        }
    }


def _build_summary(state: dict, risk_score: float, risk_lvl: str) -> str:
    news = state.get("news_results", {})
    lit  = state.get("litigation_results", {})
    mca  = state.get("mca_results", {})
    parts = [
        f"Research completed for {state['company_name']}.",
        f"Composite Research Risk Score: {risk_score:.0f}/100 ({risk_lvl}).",
    ]
    sent = news.get("overall_sentiment", 0)
    if   sent > 0.2:  parts.append("News sentiment: Positive — no major adverse media.")
    elif sent < -0.2: parts.append("News sentiment: Negative — adverse media detected.")
    else:             parts.append("News sentiment: Neutral.")
    parts.append(f"Litigation: {lit.get('total_cases', 0)} total cases, {lit.get('pending_cases', 0)} pending.")
    mca_score = mca.get("compliance", {}).get("compliance_score", "N/A")
    parts.append(f"MCA compliance score: {mca_score}.")
    if state.get("qualitative_notes"):
        parts.append(f"Credit officer notes: {len(state['qualitative_notes'])} qualitative inputs recorded.")
    return " ".join(parts)


# ─── Build LangGraph ─────────────────────────────────────────────

def _build_graph():
    """Build and compile the LangGraph StateGraph."""
    try:
        from langgraph.graph import StateGraph, END, START

        builder = StateGraph(ResearchState)

        # Register all nodes
        builder.add_node("news_agent",    _node_news)
        builder.add_node("mca_agent",     _node_mca)
        builder.add_node("ecourts_agent", _node_ecourts)
        builder.add_node("sector_agent",  _node_sector)
        builder.add_node("supervisor",    _node_supervisor)

        # Fan-out from START → all 4 agents (parallel)
        builder.add_edge(START,    "news_agent")
        builder.add_edge(START,    "mca_agent")
        builder.add_edge(START,    "ecourts_agent")
        builder.add_edge(START,    "sector_agent")

        # Fan-in: all agents → supervisor
        builder.add_edge("news_agent",    "supervisor")
        builder.add_edge("mca_agent",     "supervisor")
        builder.add_edge("ecourts_agent", "supervisor")
        builder.add_edge("sector_agent",  "supervisor")

        # Supervisor → END
        builder.add_edge("supervisor", END)

        return builder.compile()

    except Exception as e:
        print(f"[Orchestrator] LangGraph build failed ({e}), using sequential fallback.")
        return None


_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


# ─── Public API ──────────────────────────────────────────────────

def run_research_pipeline(
    company_name:      str,
    cin:               str       = "",
    industry:          str       = "",
    promoter_names:    list[str] = None,
    qualitative_notes: list[str] = None,
    progress_callback            = None,
) -> dict:
    """
    Run the full research pipeline via LangGraph (parallel) or sequential fallback.

    Args:
        company_name      : Name of the company
        cin               : Corporate Identity Number
        industry          : Industry sector
        promoter_names    : List of promoter / director names
        qualitative_notes : Credit officer observations
        progress_callback : Optional fn(agent_name, status) for UI spinner updates

    Returns:
        Aggregated research results dict (from supervisor node)
    """
    promoter_names    = promoter_names    or []
    qualitative_notes = qualitative_notes or []

    initial_state: ResearchState = {
        "company_name":       company_name,
        "cin":                cin,
        "industry":           industry,
        "promoter_names":     promoter_names,
        "qualitative_notes":  qualitative_notes,
        "news_results":       {},
        "mca_results":        {},
        "litigation_results": {},
        "sector_results":     {},
        "overall_research":   {},
        "errors":             [],
    }

    graph = _get_graph()

    if graph is not None:
        # ── LangGraph parallel execution ──
        if progress_callback:
            progress_callback("langgraph", "Running 4 agents in parallel via LangGraph...")
        try:
            final_state = graph.invoke(initial_state)
            if progress_callback:
                progress_callback("langgraph", "✅ All agents complete")
            return final_state.get("overall_research", {})
        except Exception as e:
            if progress_callback:
                progress_callback("langgraph", f"LangGraph error: {e} — using sequential fallback")
            # fall through to sequential

    # ── Sequential fallback ──
    agents = [
        ("news_agent",    lambda s: {**s, **_node_news(s)}),
        ("mca_agent",     lambda s: {**s, **_node_mca(s)}),
        ("ecourts_agent", lambda s: {**s, **_node_ecourts(s)}),
        ("sector_agent",  lambda s: {**s, **_node_sector(s)}),
    ]
    state = initial_state
    for name, fn in agents:
        if progress_callback:
            progress_callback(name, f"Running {name}...")
        state = fn(state)
        if progress_callback:
            progress_callback(name, "✅ Complete")

    result = _node_supervisor(state)
    state.update(result)
    return state.get("overall_research", {})
