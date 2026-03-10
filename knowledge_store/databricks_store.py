"""
Databricks Delta Lake Integration for Intelli-Credit.
Stores financial data, research findings, and credit decisions in Delta tables
as specified in the problem statement's data platform requirement.

Gracefully degrades to SQLite if Databricks credentials are not available.
"""
import json
from datetime import datetime
from config import (
    has_databricks, DATABRICKS_HOST, DATABRICKS_TOKEN,
    DATABRICKS_WAREHOUSE_ID, DATABRICKS_CATALOG, DATABRICKS_SCHEMA,
)


class DatabricksStore:
    """Databricks Delta Lake data store for Intelli-Credit."""

    def __init__(self):
        self.connected = False
        self.connection = None
        if has_databricks():
            self._connect()

    def _connect(self):
        """Establish connection to Databricks SQL Warehouse."""
        try:
            from databricks import sql as databricks_sql

            self.connection = databricks_sql.connect(
                server_hostname=DATABRICKS_HOST,
                http_path=f"/sql/1.0/warehouses/{DATABRICKS_WAREHOUSE_ID}",
                access_token=DATABRICKS_TOKEN,
            )
            self.connected = True
            self._init_tables()
        except ImportError:
            print("[Databricks] databricks-sql-connector not installed. Run: pip install databricks-sql-connector")
            self.connected = False
        except Exception as e:
            print(f"[Databricks] Connection failed: {e}")
            self.connected = False

    def _init_tables(self):
        """Initialize Delta tables in the configured catalog/schema."""
        if not self.connected:
            return

        try:
            cursor = self.connection.cursor()

            # Create catalog and schema if they don't exist
            cursor.execute(f"CREATE CATALOG IF NOT EXISTS {DATABRICKS_CATALOG}")
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}")

            # Company profiles table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.companies (
                    company_id BIGINT GENERATED ALWAYS AS IDENTITY,
                    company_name STRING NOT NULL,
                    cin STRING,
                    industry STRING,
                    registered_office STRING,
                    data_json STRING,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
                )
            """)

            # Financial metrics table (partitioned by fiscal year)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.financial_metrics (
                    id BIGINT GENERATED ALWAYS AS IDENTITY,
                    company_name STRING,
                    fiscal_year STRING,
                    revenue_cr DOUBLE,
                    ebitda_cr DOUBLE,
                    ebitda_margin_pct DOUBLE,
                    pat_cr DOUBLE,
                    total_debt_cr DOUBLE,
                    net_worth_cr DOUBLE,
                    dscr DOUBLE,
                    icr DOUBLE,
                    de_ratio DOUBLE,
                    current_ratio DOUBLE,
                    data_json STRING,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
                )
            """)

            # Research findings table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.research_findings (
                    id BIGINT GENERATED ALWAYS AS IDENTITY,
                    company_name STRING,
                    agent_type STRING,
                    risk_score DOUBLE,
                    findings_json STRING,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
                )
            """)

            # Credit decisions table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.credit_decisions (
                    id BIGINT GENERATED ALWAYS AS IDENTITY,
                    company_name STRING,
                    credit_score DOUBLE,
                    decision STRING,
                    five_cs_json STRING,
                    shap_values_json STRING,
                    loan_amount_cr DOUBLE,
                    loan_type STRING,
                    cam_generated BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
                )
            """)

            # Document extractions table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.document_extractions (
                    id BIGINT GENERATED ALWAYS AS IDENTITY,
                    company_name STRING,
                    document_type STRING,
                    filename STRING,
                    extraction_method STRING,
                    confidence DOUBLE,
                    extracted_data_json STRING,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
                )
            """)

            cursor.close()
            print(f"[Databricks] Tables initialized in {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}")

        except Exception as e:
            print(f"[Databricks] Table initialization failed: {e}")

    def store_company(self, company_data: dict) -> bool:
        """Store company profile in Delta table."""
        if not self.connected:
            return False
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""INSERT INTO {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.companies
                (company_name, cin, industry, registered_office, data_json)
                VALUES (?, ?, ?, ?, ?)""",
                (
                    company_data.get("company_name", ""),
                    company_data.get("cin", ""),
                    company_data.get("industry", ""),
                    company_data.get("registered_office", ""),
                    json.dumps(company_data, default=str),
                ),
            )
            cursor.close()
            return True
        except Exception as e:
            print(f"[Databricks] store_company failed: {e}")
            return False

    def store_financials(self, company_name: str, fiscal_year: str, data: dict) -> bool:
        """Store financial metrics in Delta table."""
        if not self.connected:
            return False
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""INSERT INTO {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.financial_metrics
                (company_name, fiscal_year, revenue_cr, ebitda_cr, ebitda_margin_pct,
                 pat_cr, total_debt_cr, net_worth_cr, dscr, icr, de_ratio, current_ratio, data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    company_name, fiscal_year,
                    data.get("revenue_cr"), data.get("ebitda_cr"), data.get("ebitda_margin_pct"),
                    data.get("pat_cr"), data.get("total_debt_cr"), data.get("net_worth_cr"),
                    data.get("dscr"), data.get("icr"), data.get("de_ratio"),
                    data.get("current_ratio"), json.dumps(data, default=str),
                ),
            )
            cursor.close()
            return True
        except Exception as e:
            print(f"[Databricks] store_financials failed: {e}")
            return False

    def store_research(self, company_name: str, agent_type: str, findings: dict, risk_score: float) -> bool:
        """Store research agent findings in Delta table."""
        if not self.connected:
            return False
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""INSERT INTO {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.research_findings
                (company_name, agent_type, risk_score, findings_json)
                VALUES (?, ?, ?, ?)""",
                (company_name, agent_type, risk_score, json.dumps(findings, default=str)),
            )
            cursor.close()
            return True
        except Exception as e:
            print(f"[Databricks] store_research failed: {e}")
            return False

    def store_decision(self, company_name: str, score: float, decision: str,
                       five_cs: dict, shap_values: dict, loan_amount_cr: float = 0,
                       loan_type: str = "") -> bool:
        """Store credit decision in Delta table."""
        if not self.connected:
            return False
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""INSERT INTO {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.credit_decisions
                (company_name, credit_score, decision, five_cs_json, shap_values_json,
                 loan_amount_cr, loan_type, cam_generated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    company_name, score, decision,
                    json.dumps(five_cs, default=str),
                    json.dumps(shap_values, default=str),
                    loan_amount_cr, loan_type, True,
                ),
            )
            cursor.close()
            return True
        except Exception as e:
            print(f"[Databricks] store_decision failed: {e}")
            return False

    def store_extraction(self, company_name: str, doc_type: str, filename: str,
                         method: str, confidence: float, data: dict) -> bool:
        """Store document extraction results in Delta table."""
        if not self.connected:
            return False
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""INSERT INTO {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.document_extractions
                (company_name, document_type, filename, extraction_method, confidence, extracted_data_json)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (company_name, doc_type, filename, method, confidence, json.dumps(data, default=str)),
            )
            cursor.close()
            return True
        except Exception as e:
            print(f"[Databricks] store_extraction failed: {e}")
            return False

    def get_decision_history(self, company_name: str = None) -> list:
        """Query credit decision history from Delta table."""
        if not self.connected:
            return []
        try:
            cursor = self.connection.cursor()
            if company_name:
                cursor.execute(
                    f"""SELECT company_name, credit_score, decision, loan_amount_cr, created_at
                    FROM {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.credit_decisions
                    WHERE company_name = ?
                    ORDER BY created_at DESC""",
                    (company_name,),
                )
            else:
                cursor.execute(
                    f"""SELECT company_name, credit_score, decision, loan_amount_cr, created_at
                    FROM {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.credit_decisions
                    ORDER BY created_at DESC LIMIT 50""",
                )
            rows = cursor.fetchall()
            cursor.close()
            return [
                {"company": r[0], "score": r[1], "decision": r[2], "amount_cr": r[3], "date": str(r[4])}
                for r in rows
            ]
        except Exception as e:
            print(f"[Databricks] get_decision_history failed: {e}")
            return []

    def close(self):
        """Close Databricks connection."""
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
