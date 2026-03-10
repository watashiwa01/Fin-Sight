"""
SQLite Structured Store for Intelli-Credit.
Stores parsed financial metrics, research findings, and credit decisions.
"""
import sqlite3
import json
from pathlib import Path
from config import SQLITE_PATH


class StructuredStore:
    """SQLite-based structured data store."""

    def __init__(self):
        self.db_path = str(SQLITE_PATH)
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize database tables."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                cin TEXT,
                industry TEXT,
                data_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS financial_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                fiscal_year TEXT,
                revenue_cr REAL,
                ebitda_cr REAL,
                pat_cr REAL,
                total_debt_cr REAL,
                net_worth_cr REAL,
                dscr REAL,
                icr REAL,
                de_ratio REAL,
                data_json TEXT,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS research_findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                agent_type TEXT,
                findings_json TEXT,
                risk_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS credit_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                credit_score REAL,
                decision TEXT,
                five_cs_json TEXT,
                shap_values_json TEXT,
                cam_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            )
        """)

        conn.commit()
        conn.close()

    def store_company(self, company_name: str, cin: str = "", industry: str = "", data: dict = None) -> int:
        """Store company info and return company_id."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO companies (company_name, cin, industry, data_json) VALUES (?, ?, ?, ?)",
            (company_name, cin, industry, json.dumps(data or {})),
        )
        company_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return company_id

    def store_financials(self, company_id: int, fiscal_year: str, data: dict):
        """Store financial data for a company."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO financial_data
            (company_id, fiscal_year, revenue_cr, ebitda_cr, pat_cr, total_debt_cr, net_worth_cr, dscr, icr, de_ratio, data_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                company_id, fiscal_year,
                data.get("revenue_cr"), data.get("ebitda_cr"), data.get("pat_cr"),
                data.get("total_debt_cr"), data.get("net_worth_cr"),
                data.get("dscr"), data.get("icr"), data.get("de_ratio"),
                json.dumps(data),
            ),
        )
        conn.commit()
        conn.close()

    def store_research(self, company_id: int, agent_type: str, findings: dict, risk_score: float = 0):
        """Store research findings from an agent."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO research_findings (company_id, agent_type, findings_json, risk_score) VALUES (?, ?, ?, ?)",
            (company_id, agent_type, json.dumps(findings), risk_score),
        )
        conn.commit()
        conn.close()

    def store_decision(self, company_id: int, credit_score: float, decision: str,
                       five_cs: dict, shap_values: dict, cam_path: str = ""):
        """Store credit decision."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO credit_decisions
            (company_id, credit_score, decision, five_cs_json, shap_values_json, cam_path)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (company_id, credit_score, decision, json.dumps(five_cs), json.dumps(shap_values), cam_path),
        )
        conn.commit()
        conn.close()

    def get_company(self, company_id: int) -> dict | None:
        """Get company data by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0], "company_name": row[1], "cin": row[2],
                "industry": row[3], "data": json.loads(row[4] or "{}"),
            }
        return None
