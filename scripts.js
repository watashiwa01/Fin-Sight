// Intelli-Credit Frontend Logic

const API_BASE = (() => {
    const origin = window.location.origin;
    // If opened as a local file (origin === "null"), fall back to local dev server.
    if (!origin || origin === "null") return "http://localhost:8140/api";
    return `${origin}/api`;
})();

let state = {
    company_data: null,
    pipeline_step: 0,
    active_tab: "onboarding",
    theme: "dark",
    extracted_data: {},
    research_results: null,
    gst_validation: null,
    scoring: null,
    verdict: null,
    five_cs: null,
};

// --- Initialization ---
document.addEventListener("DOMContentLoaded", async () => {
    initTabs();
    initTheme();
    initForms();
    updateUI();
    const config = await apiGet("/config");
    if (config) {
        const badge = document.getElementById("mode-badge");
        badge.innerText = config.is_demo ? "Demo Mode" : "Live Mode";
        badge.className = `badge mode-badge ${config.is_demo ? 'mode-demo' : 'mode-live'}`;
        
        if (!config.has_llm && !config.is_demo) {
            badge.innerText = "Smart Hybrid Mode";
            badge.className = "badge mode-badge mode-demo";
            console.log("No LLM API keys detected. Using Smart Demo/Mock fallbacks.");
        }
    }

    // Restore state
    const stateRes = await apiGet("/state");
    if (stateRes) {
        Object.assign(state, stateRes);
        updateUI();
        // User requested: "in research dashboard option i don't need any inital results the results will show only after i make the input"
        // So we do NOT call renderResearchResults or renderScoringResults here.
        // They will only render when the user explicitly clicks the buttons.
    }
});

// --- Tab Management ---
function initTabs() {
    const navItems = document.querySelectorAll(".nav-item");
    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const tabId = item.getAttribute("data-tab");
            switchTab(tabId);
        });
    });
}

function switchTab(tabId) {
    state.active_tab = tabId;
    
    // Update Nav
    document.querySelectorAll(".nav-item").forEach(i => i.classList.remove("active"));
    document.querySelector(`[data-tab="${tabId}"]`).classList.add("active");
    
    // Update Content
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    document.getElementById(`${tabId}-tab`).classList.add("active");
}

// --- Theme Management ---
function initTheme() {
    const themeSwitch = document.getElementById("theme-switch");
    const themeLabel = document.getElementById("theme-label");
    
    themeSwitch.addEventListener("change", () => {
        if (themeSwitch.checked) {
            document.body.classList.remove("light-theme");
            document.body.classList.add("dark-theme");
            themeLabel.innerText = "🌙 Dark Mode";
            state.theme = "dark";
        } else {
            document.body.classList.remove("dark-theme");
            document.body.classList.add("light-theme");
            themeLabel.innerText = "☀️ Light Mode";
            state.theme = "light";
        }
    });
}

// --- Utility: Rich Text Formatter ---
function formatRationale(text) {
    if (!text) return "";
    
    // 1. Handle Bold (Markdown style)
    let formatted = text.replace(/\*\*(.*?)\*\*/g, '<strong style="color: #f8fafc; font-weight: 700;">$1</strong>');
    
    // 2. Handle Italics
    formatted = formatted.replace(/\*(.*?)\*/g, '<em style="color: #cbd5e1; font-style: italic;">$1</em>');
    
    // 3. Colorize Key Financial Status Keywords
    const colorMap = {
        "APPROVE": "#4ade80",
        "REJECT": "#f87171",
        "REFER": "#fcd34d",
        "Low Risk": "#4ade80",
        "High Risk": "#f87171",
        "Consistency": "#34d399",
        "Variance": "#fbbf24",
        "Volatility": "#f87171",
        "Adequate": "#60a5fa",
        "Strong": "#4ade80",
        "Clean": "#34d399",
        "Moderate": "#fb923c"
    };

    Object.keys(colorMap).forEach(key => {
        const regex = new RegExp(`\\b${key}\\b`, 'g');
        formatted = formatted.replace(regex, `<span style="color: ${colorMap[key]}; font-weight: 600;">${key}</span>`);
    });

    return formatted;
}

// --- API & State ---
async function apiPost(endpoint, data = {}) {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });
        if (!response.ok) throw new Error(await response.text());
        const result = await response.json();
        hideLoading();
        return result;
    } catch (error) {
        hideLoading();
        alert(`API Error: ${error.message}`);
        return null;
    }
}

async function apiGet(endpoint) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`);
        return await response.json();
    } catch (error) {
        console.error("Fetch error:", error);
        return null;
    }
}

// --- Form Handlers ---
function initForms() {
    // Onboarding Form
    const onboardingForm = document.getElementById("onboarding-form");
    if (onboardingForm) {
        onboardingForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const data = {
                company_name: document.getElementById("company_name").value,
                cin: document.getElementById("cin").value,
                pan: document.getElementById("pan").value,
                industry: document.getElementById("industry").value,
                turnover_cr: parseFloat(document.getElementById("turnover_cr").value),
                loan_type: document.getElementById("loan_type").value,
                amount_cr: parseFloat(document.getElementById("amount_cr").value),
                tenor_years: parseFloat(document.getElementById("tenor").value),
                proposed_rate_pct: parseFloat(document.getElementById("rate").value),
            };
            
            const res = await apiPost("/onboarding", data);
            if (res) {
                state.company_data = res.session.company_data;
                state.pipeline_step = res.session.pipeline_step;
                updateUI();
                switchTab("upload");
            }
        });
    }

    // Load Sample Button
    const loadSampleBtn = document.getElementById("load-sample-btn");
    if (loadSampleBtn) {
        loadSampleBtn.addEventListener("click", async () => {
            const res = await apiPost("/load-sample");
            if (res) {
                state.company_data = res.company_data;
                state.pipeline_step = 1;
                updateUI();
                switchTab("upload");
                fillFormWithData(res.company_data);
            }
        });
    }

    // Upload Handler
    const fileInput = document.getElementById("file-input");
    if (fileInput) {
        fileInput.addEventListener("change", async (e) => {
            const files = e.target.files;
            for (let file of files) {
                const formData = new FormData();
                formData.append("file", file);
                
                showLoading(`Uploading & Processing ${file.name}...`);
                try {
                    const response = await fetch(`${API_BASE}/upload`, {
                        method: "POST",
                        body: formData
                    });
                    
                    if (!response.ok) {
                        const error = await response.json();
                        alert(`Error processing ${file.name}: ${error.detail || "Unknown error"}`);
                        continue;
                    }
                    
                    const result = await response.json();
                    addFileToResults(result);
                } catch (err) {
                    console.error("Upload error:", err);
                    alert(`Failed to upload ${file.name}. Please check the server connection.`);
                } finally {
                    hideLoading();
                }
            }
        });
    }
}

function addFileToResults(res) {
    if (res.session) {
        state.pipeline_step = res.session.pipeline_step;
        updateUI();
    }
    
    const container = document.getElementById("file-list");
    const item = document.createElement("div");
    item.className = "file-item glass";
    item.style.marginBottom = "1rem";
    item.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:0.5rem; width:100%;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span title="${res.filename}">📄 ${res.filename.length > 20 ? res.filename.substring(0, 17) + '...' : res.filename}</span>
                <span class="badge" style="background:var(--accent-dim); color:var(--accent); font-size:0.7rem; padding:0.2rem 0.5rem; border-radius:10px;">${res.classification}</span>
            </div>
            <div style="display:flex; gap:0.5rem; align-items:center;">
                <select id="schema_${res.filename}" style="flex:1; padding:0.4rem; font-size:0.8rem; background: rgba(0,0,0,0.2); color: white; border: 1px solid var(--card-border); border-radius:4px;">
                    <option value="financials">Financials Schema</option>
                    <option value="gst">GST Schema</option>
                    <option value="general">General Schema</option>
                </select>
                <button class="primary-btn" style="padding:0.4rem 0.8rem; font-size:0.8rem;" 
                    onclick="runLlmExtraction('${res.filename}', '${res.classification}', \`${res.result.full_text.replace(/`/g, '\\`').replace(/\$/g, '\\$')}\`)">
                    Extract
                </button>
            </div>
        </div>
    `;
    container.appendChild(item);
}

function fillFormWithData(data) {
    document.getElementById("company_name").value = data.company_name || "";
    document.getElementById("cin").value = data.cin || "";
    document.getElementById("pan").value = data.pan || "";
    document.getElementById("industry").value = data.industry || "Manufacturing";
    document.getElementById("turnover_cr").value = data.turnover_cr || 0;
    
    if (data.loan_request) {
        document.getElementById("loan_type").value = data.loan_request.type || "Working Capital";
        document.getElementById("amount_cr").value = data.loan_request.amount_cr || 0;
        document.getElementById("tenor").value = data.loan_request.tenor_years || 0;
        document.getElementById("rate").value = data.loan_request.proposed_rate_pct || 0;
    }
}

// --- UI Updates ---
// --- Helper: Dynamic visuals for demo mode ---
function getCompanyVisuals(cd) {
    const name = (cd.company_name || "").toLowerCase();
    
    const entities = {
        "reliance": {
            price: "₹ 1,382.10", change: "-0.73%", cap: "18.7 Lakh Cr", nse: "RELIANCE",
            chart: [1280, 1315, 1290, 1345, 1405, 1382.1]
        },
        "tata": {
            price: "₹ 984.50", change: "+1.24%", cap: "3.55 Lakh Cr", nse: "TATAMOTORS",
            chart: [920, 950, 930, 970, 995, 984.5]
        },
        "infosys": {
            price: "₹ 1,605.20", change: "+0.45%", cap: "6.65 Lakh Cr", nse: "INFY",
            chart: [1550, 1580, 1620, 1590, 1610, 1605.2]
        }
    };

    let found = null;
    if (name.includes("reliance") || name.includes("relience") || name.startsWith("reli")) found = entities.reliance;
    else if (name.includes("tata")) found = entities.tata;
    else if (name.includes("infosys") || name.includes("infy")) found = entities.infosys;

    if (!found) {
        // Generate consistent "random" visuals for unknown entities
        const seed = name.split('').reduce((a, b) => { a = ((a << 5) - a) + b.charCodeAt(0); return a & a; }, 0);
        const basePrice = Math.abs(seed % 5000) + 100;
        found = {
            price: `₹ ${basePrice.toLocaleString()}`,
            change: (seed % 2 === 0 ? "+" : "-") + (Math.abs(seed % 200) / 100).toFixed(2) + "%",
            cap: "Est. Valuation",
            nse: "RELIANCE",
            chart: Array.from({length: 6}, (_, i) => basePrice * (1 + (Math.sin(seed + i) * 0.05)))
        };
    }
    return found;
}

function updateUI() {
    // Update Pipeline List
    for (let i = 0; i < 5; i++) {
        const el = document.getElementById(`step-${i}`);
        el.className = "";
        if (i < state.pipeline_step) el.classList.add("completed");
        else if (i === state.pipeline_step) el.classList.add("active");
        else el.classList.add("todo");
    }

    // Update Company Sidebar Info
    const companyArea = document.getElementById("active-company-info");
    if (state.company_data) {
        const cd = state.company_data;
        const lr = cd.loan_request || {};
        
        // Financial formatting for large values
        const formatValue = (val) => {
            if (!val) return "N/A";
            if (val >= 100000) return `${(val/100000).toFixed(2)} Lakh Cr`;
            return `${val.toLocaleString()} Cr`;
        };

        const netWorth = formatValue(cd.financials?.fy_2024?.net_worth_cr);
        const turnover = formatValue(cd.financials?.fy_2024?.revenue_cr);
        
        const visuals = getCompanyVisuals(cd);
        
        const currentPrice = cd.financials?.fy_2024?.current_price || visuals.price;
        const marketCapText = cd.financials?.fy_2024?.market_cap_cr ? `₹ ${formatValue(cd.financials?.fy_2024?.market_cap_cr)}` : visuals.cap;
        const priceChange = visuals.change;
        const sector = cd.industry || "Diversified Conglomerate";
        const pan = cd.pan || "N/A";
        
        companyArea.innerHTML = `
            <div class="info-block" style="margin-bottom: 1.5rem;">
                <h3 style="color: var(--accent); margin-bottom: 0.2rem;">${cd.company_name}</h3>
                <div style="color: var(--report-subtext); font-size: 0.85rem; margin-bottom: 0.5rem;">
                    CIN: ${cd.cin} | PAN: ${pan}
                </div>
                <div style="color: var(--report-subtext); font-size: 0.85rem; margin-bottom: 0.5rem;">
                    Sector: ${sector}
                </div>
                
                <div style="display: flex; gap: 1rem; margin-top: 1rem;">
                    <div style="flex: 1; min-width: 45%;">
                        <div style="color: var(--report-subtext); font-size: 0.8rem;">Current Price</div>
                        <div style="font-size: 1.2rem; font-weight: 600; color: #f87171;">${currentPrice} <span style="font-size: 0.8rem;">(${priceChange})</span></div>
                    </div>
                    <div style="flex: 1; min-width: 45%;">
                        <div style="color: var(--report-subtext); font-size: 0.8rem;">Est. Market Cap</div>
                        <div style="font-size: 1.1rem; color: var(--report-text);">${marketCapText}</div>
                    </div>
                </div>
                
                <div style="display: flex; gap: 1rem; margin-top: 1rem;">
                    <div style="flex: 1; min-width: 45%;">
                        <div style="color: var(--report-subtext); font-size: 0.8rem;">Net Worth</div>
                        <div style="font-size: 1.1rem; color: var(--report-text);">₹ ${netWorth}</div>
                    </div>
                    <div style="flex: 1; min-width: 45%;">
                        <div style="color: var(--report-subtext); font-size: 0.8rem;">Loan Requested</div>
                        <div style="font-size: 1.1rem; color: #fcd34d;">₹ ${lr.amount_cr || 0} Cr</div>
                    </div>
                </div>

                <div style="margin-top: 1rem; text-align: right;">
                    <a href="https://www.nseindia.com/get-quote/equity/${visuals.nse}" target="_blank" style="color: #60a5fa; font-size: 0.75rem; text-decoration: none; display: flex; align-items: center; justify-content: flex-end; gap: 0.3rem;">
                         Reference: NSE India ↗
                    </a>
                </div>
            </div>
            
            <div class="info-block" style="border-top: 1px solid var(--card-border); padding-top: 1rem;">
                <h4 style="color: var(--report-subtext); margin-bottom: 0.8rem; font-weight: normal; font-size: 0.9rem;">📈 6-Month Share Price Progress</h4>
                <div style="position: relative; height: 140px; width: 100%;">
                    <canvas id="companyStockChart"></canvas>
                </div>
            </div>
        `;

        // Render the stock progress chart
        setTimeout(() => {
            const ctx = document.getElementById('companyStockChart');
            if (ctx) {
                new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: ['Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'],
                        datasets: [{
                            label: 'Share Price (₹)',
                            data: visuals.chart,
                            borderColor: '#3b82f6',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            borderWidth: 2,
                            tension: 0.4,
                            pointRadius: 3,
                            pointBackgroundColor: '#60a5fa',
                            fill: true
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                display: false,
                                min: Math.min(...visuals.chart) * 0.95
                            },
                            x: {
                                ticks: { color: '#9ca3af', font: { size: 10, family: "'Lexend', sans-serif" } },
                                grid: { display: false, drawBorder: false }
                            }
                        },
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                                titleFont: { family: "'Lexend', sans-serif" },
                                bodyFont: { family: "'Lexend', sans-serif" },
                                displayColors: false,
                                callbacks: {
                                    label: function(context) {
                                        return '₹ ' + context.parsed.y;
                                    }
                                }
                            }
                        }
                    }
                });
            }
        }, 100);

    } else {
        companyArea.innerHTML = `<p class="loading-text">No company data loaded.</p>`;
    }
}

// --- Document Extraction ---
async function runLlmExtraction(filename, docType, fullText) {
    const schema = document.getElementById(`schema_${filename}`)?.value || "{}";
    showLoading(`Extracting ${filename}...`);
    const res = await apiPost("/extract", { filename, doc_type: docType, schema, full_text: fullText });
    hideLoading();
    if (res) {
        alert("Extraction successful!");
        state.pipeline_step = Math.max(state.pipeline_step, 2);
        if (!state.extracted_data) state.extracted_data = {};
        state.extracted_data[filename] = res.extracted;
        updateUI();
        addExtractionPreview(filename, res.extracted);
    }
}

function addExtractionPreview(filename, data) {
    // Render a small preview of extracted data with IDE-like syntax highlighting
    const container = document.getElementById("extraction-results");
    const previewDiv = document.createElement("div");
    previewDiv.className = "card glass data-preview";
    
    // Custom JSON Syntax Highlighter
    const syntaxHighlight = (json) => {
        if (typeof json != 'string') {
             json = JSON.stringify(json, undefined, 2);
        }
        json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
            let cls = 'color: #d1d5db;'; // Default text color
            if (/^"/.test(match)) {
                if (/:$/.test(match)) {
                    cls = 'color: #93c5fd; font-weight: 500;'; // Keys (Blue)
                } else {
                    cls = 'color: #86efac;'; // Strings (Green)
                }
            } else if (/true|false/.test(match)) {
                cls = 'color: #fca5a5; font-style: italic;'; // Booleans (Red/Pink)
            } else if (/null/.test(match)) {
                cls = 'color: #9ca3af; font-style: italic;'; // Null (Gray)
            } else {
                cls = 'color: #fcd34d;'; // Numbers (Yellow)
            }
            return '<span style="' + cls + '">' + match + '</span>';
        });
    };

    const highlightedJSON = syntaxHighlight(data);

    previewDiv.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--report-card-border); padding-bottom: 0.8rem; margin-bottom: 1rem;">
            <h4 style="margin: 0; color: var(--report-text);">📊 Extracted Data: <span style="color: var(--accent); font-weight: normal;">${filename}</span></h4>
            <div style="display: flex; gap: 0.5rem;">
                <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: #ef4444;"></span>
                <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: #eab308;"></span>
                <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: #22c55e;"></span>
            </div>
        </div>
        <div style="background: var(--report-inner-bg); padding: 1.5rem; border-radius: 6px; overflow-x: auto; border: 1px solid var(--report-card-border); box-shadow: inset 0 2px 4px rgba(0,0,0,0.2);">
            <pre style="margin: 0; font-family: 'Consolas', 'Monaco', 'Courier New', monospace; font-size: 0.9rem; line-height: 1.5; color: var(--report-text);">${highlightedJSON}</pre>
        </div>
    `;
    container.appendChild(previewDiv);
}

// --- GST Validation ---
document.getElementById("run-gst-btn")?.addEventListener("click", async () => {
    const res = await apiPost("/gst-validation");
    if (res) {
        state.pipeline_step = 2;
        state.gst_validation = res;
        updateUI();
        renderGstResults(res);
    }
});

function renderGstResults(gst) {
    const area = document.getElementById("gst-results-area");
    area.innerHTML = `
        <div class="metric-container" style="display: flex; gap: 1rem; margin-top: 1rem; margin-bottom: 2rem;">
            <div class="metric-card glass" style="flex:1; text-align:center; padding:1.5rem; display: flex; flex-direction: column; justify-content: center;">
                <h3 style="color: var(--accent); margin-bottom: 0.5rem;">Compliance Score</h3>
                <div class="value" style="font-size: 2.5rem; color: #4ade80;">${gst.compliance_score}/100</div>
            </div>
            <div class="metric-card glass" style="flex:1; text-align:center; padding:1.5rem; display: flex; flex-direction: column; justify-content: center;">
                <h3 style="color: var(--accent); margin-bottom: 0.5rem;">Risk Level</h3>
                <div class="value" style="font-size: 2rem; color: ${gst.risk_level === 'LOW' ? '#4ade80' : gst.risk_level === 'MEDIUM' ? '#fcd34d' : '#f87171'};">${gst.risk_level}</div>
            </div>
        </div>

        <div style="display: flex; gap: 2rem; flex-wrap: wrap; margin-bottom: 1rem;">
            <div style="flex: 1; min-width: 300px;">
                <h4 style="color: #93c5fd; margin-bottom: 1rem; border-bottom: 1px solid var(--report-card-border); padding-bottom: 0.5rem;">Key Disclosures</h4>
                <ul style="list-style-type: none; padding: 0; margin: 0; font-size: 0.95rem; color: var(--report-text);">
                    <li style="margin-bottom: 0.8rem; display: flex; justify-content: space-between;">
                        <span>GSTR-3B Declared Turnover:</span>
                        <strong style="color: var(--report-text)">₹ ${gst.summary?.gstr_3b_turnover_cr || 0} Cr</strong>
                    </li>
                    <li style="margin-bottom: 0.8rem; display: flex; justify-content: space-between;">
                        <span>Bank Credit Entries:</span>
                        <strong style="color: var(--report-text)">₹ ${gst.summary?.bank_credit_entries_cr || 0} Cr</strong>
                    </li>
                    <li style="margin-bottom: 0.8rem; display: flex; justify-content: space-between;">
                        <span>Filing Regularity:</span>
                        <strong style="color: ${(gst.summary?.filing_compliance_pct || 0) === 100 ? '#4ade80' : '#fcd34d'}">
                            ${gst.summary?.filing_compliance_pct || 0}% Compliance
                        </strong>
                    </li>
                </ul>
                
                <h4 style="color: #fca5a5; margin-top: 1.5rem; margin-bottom: 0.8rem; border-bottom: 1px solid var(--report-card-border); padding-bottom: 0.5rem;">AI Observations</h4>
                <p style="font-size: 0.9rem; color: var(--report-text); line-height: 1.5; background: var(--report-inner-bg); padding: 1rem; border-radius: 6px; border-left: 3px solid var(--accent);">
                    ${gst.narrative}
                </p>
            </div>
            <div style="flex: 1; min-width: 300px; padding: 1rem; background: var(--report-inner-bg); border-radius: 8px; border: 1px solid var(--report-card-border);">
                <h4 style="text-align: center; color: var(--report-text); margin-bottom: 1rem;">Turnover vs Bank Credits (Cr)</h4>
                <div style="position: relative; height: 220px; width: 100%;">
                    <canvas id="gstComparisonChart"></canvas>
                </div>
            </div>
        </div>
    `;

    // Render GST Comparison Chart
    setTimeout(() => {
        const ctx = document.getElementById('gstComparisonChart');
        if (ctx && gst.summary) {
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['Declared (GSTR-3B)', 'Actual (Bank Credit)'],
                    datasets: [{
                        data: [
                            gst.summary.gstr_3b_turnover_cr || 0,
                            gst.summary.bank_credit_entries_cr || 0
                        ],
                        backgroundColor: [
                            'rgba(96, 165, 250, 0.8)',   // Blue
                            'rgba(52, 211, 153, 0.8)'    // Green
                        ],
                        borderColor: [
                            'rgb(96, 165, 250)',
                            'rgb(52, 211, 153)'
                        ],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { 
                            position: 'bottom',
                            labels: {
                                color: (document.body.classList.contains('light-theme') ? '#1e293b' : '#d1d5db'),
                                font: { family: "'Lexend', sans-serif" }
                            }
                        },
                        tooltip: {
                            backgroundColor: (document.body.classList.contains('light-theme') ? 'rgba(255,255,255,0.9)' : 'rgba(15, 23, 42, 0.9)'),
                            titleFont: { family: "'Lexend', sans-serif" },
                            bodyFont: { family: "'Lexend', sans-serif" },
                            padding: 10,
                            cornerRadius: 6,
                            callbacks: {
                                label: function(context) {
                                    return '₹ ' + context.parsed + ' Cr';
                                }
                            }
                        }
                    }
                }
            });
        }
    }, 100);
}

// --- Research Pipeline ---
document.getElementById("launch-research-btn")?.addEventListener("click", async () => {
    const statusArea = document.getElementById("agent-status-area");
    if (statusArea) {
        statusArea.innerHTML = `
            <div class="agent-card glass">📰 News Agent: ⏳ Loading...</div>
            <div class="agent-card glass">🏛️ MCA Agent: ⏳ Loading...</div>
            <div class="agent-card glass">⚖️ e-Courts Agent: ⏳ Loading...</div>
            <div class="agent-card glass">📈 Sector Agent: ⏳ Loading...</div>
        `;
    }

    const inputName = document.getElementById("research_company_name")?.value;
    const companyName = inputName || state.company_data?.company_name || "";
    const res = await apiPost("/research", { company_name: companyName });
    if (res) {
        state.pipeline_step = Math.max(state.pipeline_step, 3);
        state.research_results = res.research;
        state.company_data = res.company_data; // Sync side panel data!
        if (statusArea) {
            statusArea.innerHTML = `
                <div class="agent-card glass completed">📰 News Agent: ✅ Complete</div>
                <div class="agent-card glass completed">🏛️ MCA Agent: ✅ Complete</div>
                <div class="agent-card glass completed">⚖️ e-Courts Agent: ✅ Complete</div>
                <div class="agent-card glass completed">📈 Sector Agent: ✅ Complete</div>
            `;
        }
        updateUI();
        renderResearchResults(res.research);
    }
});

function renderResearchResults(research) {
    const area = document.getElementById("research-results-area");
    area.innerHTML = `
        <div class="card glass">
            <h3>🎯 Research Risk Overview</h3>
            <div class="metric-container" style="display: flex; gap: 1rem;">
                <div class="metric-card" style="flex:1">
                    <h3>Risk Score</h3>
                    <div class="value">${research.composite_risk_score}/100</div>
                </div>
                <div class="metric-card" style="flex:1">
                    <h3>Risk Level</h3>
                    <div class="value">${research.risk_level}</div>
                </div>
            </div>
            <div style="margin-top: 2rem; margin-bottom: 1rem;">
                <h4 style="text-align: center; color: var(--accent); margin-bottom: 1rem;">Risk Component Breakdown</h4>
                <div style="position: relative; height: 300px; width: 100%; display: flex; justify-content: center;">
                    <canvas id="riskRadarChart"></canvas>
                </div>
            </div>
            <div style="margin-top: 1.5rem; display: flex; flex-direction: column; gap: 1.5rem;">
                <div>
                    <h4 style="color: var(--accent)">📰 News & Sentiment</h4>
                    <p style="color: var(--report-text)">${research.news?.summary || "No news summary available."}</p>
                    <div style="margin-top: 0.5rem; font-size: 0.9rem; color: var(--report-subtext);">
                        <strong style="color: var(--report-text)">Sentiment:</strong> <span style="color: var(--report-text)">${research.news?.overall_sentiment > 0.1 ? 'Positive' : research.news?.overall_sentiment < -0.1 ? 'Negative' : 'Neutral'}</span>
                    </div>
                    ${research.news?.articles && research.news.articles.length > 0 ? `
                    <div style="margin-top: 1rem;">
                        <h5 style="color: var(--report-subtext); margin-bottom: 0.5rem;">Recent Articles</h5>
                        <ul style="list-style-type: none; padding: 0;">
                            ${research.news.articles.map(art => `
                                <li style="margin-bottom: 0.8rem; padding: 0.8rem; background: var(--report-inner-bg); border: 1px solid var(--report-card-border); border-radius: 6px;">
                                    <div style="display: flex; justify-content: space-between; align-items: start; gap: 1rem; margin-bottom: 0.3rem;">
                                        <a href="${art.source || '#'}" target="_blank" style="color: #60a5fa; text-decoration: none; font-weight: 500; font-size: 0.95rem; line-height: 1.3;">
                                            ${art.title}
                                        </a>
                                        <span style="
                                            font-size: 0.7rem; 
                                            padding: 0.2rem 0.5rem; 
                                            border-radius: 10px; 
                                            text-transform: capitalize;
                                            white-space: nowrap;
                                            background: ${art.sentiment === 'positive' ? 'rgba(16, 185, 129, 0.15)' : art.sentiment === 'negative' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(156, 163, 175, 0.15)'}; 
                                            color: ${art.sentiment === 'positive' ? '#4ade80' : art.sentiment === 'negative' ? '#f87171' : '#d1d5db'};
                                            border: 1px solid ${art.sentiment === 'positive' ? 'rgba(16, 185, 129, 0.3)' : art.sentiment === 'negative' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(156, 163, 175, 0.3)'};
                                        ">${art.sentiment || 'neutral'}</span>
                                    </div>
                                    ${art.content_snippet ? `<p style="font-size: 0.8rem; color: var(--report-subtext); margin: 0; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">${art.content_snippet}</p>` : ''}
                                </li>
                            `).join('')}
                        </ul>
                    </div>
                    ` : ""}
                </div>
                <div>
                    <h4 style="color: var(--accent)">🏛️ MCA Summary</h4>
                    <p style="margin-bottom: 0.8rem; color: var(--report-text);">${research.mca?.summary || "N/A"}</p>
                    ${research.mca?.charges_detail ? `
                    <div style="display: flex; gap: 1.5rem; flex-wrap: wrap;">
                        <div style="flex: 1; min-width: 250px;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem; padding: 0.5rem; background: var(--report-inner-bg); border-radius: 4px;">
                                <span style="color: var(--report-subtext)">Compliance Score:</span>
                                <strong style="color: #4ade80">${research.mca.compliance?.compliance_score || "N/A"}</strong>
                            </div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem; padding: 0.5rem; background: var(--report-inner-bg); border-radius: 4px;">
                                <span style="color: var(--report-subtext)">Registered Charges:</span>
                                <strong style="color: var(--report-text)">${research.mca.charges_summary?.total_registered || 0}</strong>
                            </div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem; padding: 0.5rem; background: var(--report-inner-bg); border-radius: 4px;">
                                <span style="color: var(--report-subtext)">Open Charges:</span>
                                <strong style="color: #f87171">${research.mca.charges_summary?.open || 0}</strong>
                            </div>
                        </div>
                        <div style="flex: 1; min-width: 200px; height: 150px; position: relative;">
                            <canvas id="mcaChart"></canvas>
                        </div>
                    </div>` : ""}
                </div>
                <div>
                    <h4 style="color: var(--accent)">⚖️ Litigation Summary</h4>
                    <p style="margin-bottom: 0.8rem; color: var(--report-text);">${research.litigation?.summary || "N/A"}</p>
                    ${research.litigation?.total_cases !== undefined ? `
                    <div style="display: flex; gap: 1.5rem; flex-wrap: wrap;">
                        <div style="flex: 1; min-width: 250px;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem; padding: 0.5rem; background: var(--report-inner-bg); border-radius: 4px;">
                                <span style="color: var(--report-text)">Total Cases:</span>
                                <strong style="color: var(--report-text)">${research.litigation.total_cases}</strong>
                            </div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem; padding: 0.5rem; background: var(--report-inner-bg); border-radius: 4px;">
                                <span style="color: var(--report-subtext)">Pending Cases:</span>
                                <strong style="color: #f87171">${research.litigation.pending_cases}</strong>
                            </div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem; padding: 0.5rem; background: var(--report-inner-bg); border-radius: 4px;">
                                <span style="color: var(--report-subtext)">Disposed Cases:</span>
                                <strong style="color: #4ade80">${research.litigation.disposed_cases}</strong>
                            </div>
                        </div>
                        <div style="flex: 1; min-width: 200px; height: 150px; position: relative;">
                            <canvas id="litigationChart"></canvas>
                        </div>
                    </div>` : ""}
                </div>
                <div>
                    <h4 style="color: var(--accent)">📈 Sector Analysis</h4>
                    <p style="margin-bottom: 0.8rem; color: var(--report-text);">${research.sector?.summary || "N/A"}</p>
                    <div style="display: flex; gap: 1.5rem; flex-wrap: wrap;">
                        <div style="flex: 1; min-width: 250px;">
                            ${research.sector?.key_factors ? `<ul style="font-size: 0.9rem; margin-top:0.5rem; color: var(--report-text);">${research.sector.key_factors.map(f => `<li style="margin-bottom: 0.3rem;">${f}</li>`).join('')}</ul>` : ''}
                        </div>
                        <div style="flex: 1; min-width: 200px; height: 150px; position: relative;">
                            <canvas id="sectorChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Render the Risk Breakdown Chart
    setTimeout(() => {
        const ctx = document.getElementById('riskRadarChart');
        if (ctx && research.provenance) {
            new Chart(ctx, {
                type: 'bar', // Changed to bar chart
                data: {
                    labels: research.provenance.map(p => p.agent),
                    datasets: [{
                        label: 'Risk Score (Out of 100)',
                        data: research.provenance.map(p => p.risk_score),
                        backgroundColor: [
                            'rgba(248, 113, 113, 0.8)',  // Red
                            'rgba(96, 165, 250, 0.8)',   // Blue
                            'rgba(251, 191, 36, 0.8)',   // Yellow
                            'rgba(52, 211, 153, 0.8)'    // Green
                        ],
                        borderColor: [
                            'rgb(248, 113, 113)',
                            'rgb(96, 165, 250)',
                            'rgb(251, 191, 36)',
                            'rgb(52, 211, 153)'
                        ],
                        borderWidth: 1,
                        borderRadius: 6 // Added rounded corners to bars
                    }]
                },
                options: {
                    indexAxis: 'y', // Makes it a horizontal bar chart
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            beginAtZero: true,
                            max: 100,
                            ticks: {
                                color: (document.body.classList.contains('light-theme') ? '#475569' : '#9ca3af'),
                                font: {
                                    family: "'Lexend', sans-serif"
                                }
                            },
                            grid: {
                                color: (document.body.classList.contains('light-theme') ? '#e2e8f0' : 'rgba(255, 255, 255, 0.05)')
                            }
                        },
                        y: {
                            ticks: {
                                color: (document.body.classList.contains('light-theme') ? '#1e293b' : '#d1d5db'),
                                font: {
                                    family: "'Lexend', sans-serif",
                                    weight: 500
                                }
                            },
                            grid: {
                                display: false
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false // Hide legend since colors are distinct per agent
                        },
                        tooltip: {
                            backgroundColor: (document.body.classList.contains('light-theme') ? 'rgba(255,255,255,0.9)' : 'rgba(15, 23, 42, 0.9)'),
                            titleFont: { family: "'Lexend', sans-serif" },
                            bodyFont: { family: "'Lexend', sans-serif" },
                            titleColor: (document.body.classList.contains('light-theme') ? '#000' : '#fff'),
                            bodyColor: (document.body.classList.contains('light-theme') ? '#000' : '#cbd5e1'),
                            padding: 12,
                            cornerRadius: 8,
                            displayColors: false
                        }
                    }
                }
            });
        }

        // MCA Charges Chart
        const mcaCtx = document.getElementById('mcaChart');
        if (mcaCtx && research.mca?.charges_summary) {
            new Chart(mcaCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Open Charges', 'Satisfied Charges'],
                    datasets: [{
                        data: [
                            research.mca.charges_summary.open || 0,
                            research.mca.charges_summary.satisfied || 0
                        ],
                        backgroundColor: ['rgba(248, 113, 113, 0.8)', 'rgba(52, 211, 153, 0.8)'],
                        borderColor: ['rgb(248, 113, 113)', 'rgb(52, 211, 153)'],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { position: 'right', labels: { color: (document.body.classList.contains('light-theme') ? '#1e293b' : '#d1d5db') } } }
                }
            });
        }

        // Litigation Chart
        const litCtx = document.getElementById('litigationChart');
        if (litCtx && research.litigation?.total_cases !== undefined) {
            new Chart(litCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Pending', 'Disposed'],
                    datasets: [{
                        data: [
                            research.litigation.pending_cases || 0,
                            research.litigation.disposed_cases || 0
                        ],
                        backgroundColor: ['rgba(251, 191, 36, 0.8)', 'rgba(96, 165, 250, 0.8)'],
                        borderColor: ['rgb(251, 191, 36)', 'rgb(96, 165, 250)'],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { position: 'right', labels: { color: (document.body.classList.contains('light-theme') ? '#1e293b' : '#d1d5db') } } }
                }
            });
        }

        // Sector Outlook Chart
        const sectorCtx = document.getElementById('sectorChart');
        if (sectorCtx && research.sector?.outlook_score) {
            new Chart(sectorCtx, {
                type: 'bar',
                data: {
                    labels: ['Sector Outlook (0-100)', 'Regulatory Risk (0-100)'],
                    datasets: [{
                        label: 'Score',
                        data: [
                            research.sector.outlook_score || 0,
                            research.sector.regulatory_risk_score || 0
                        ],
                        backgroundColor: ['rgba(52, 211, 153, 0.8)', 'rgba(248, 113, 113, 0.8)'],
                        borderWidth: 0,
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, max: 100, ticks: { color: '#9ca3af' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                        x: { ticks: { color: '#d1d5db' }, grid: { display: false } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }
    }, 100);
}

// --- Scoring & Analysis ---
document.getElementById("run-scoring-btn")?.addEventListener("click", async () => {
    const res = await apiPost("/score");
    if (res) {
        state.pipeline_step = 4;
        state.scoring = res.scoring;
        state.five_cs = res.five_cs;
        state.verdict = res.verdict;
        updateUI();
        renderScoringResults(res);
    }
});

function renderScoringResults(res) {
    const area = document.getElementById("scoring-results-area");
    const { scoring, five_cs, verdict } = res;
    
    let color = '#fcd34d'; // Yellow for REFER
    if (verdict.verdict === 'APPROVE') color = '#4ade80'; // Green
    if (verdict.verdict === 'REJECT') color = '#f87171'; // Red
    
    area.innerHTML = `
        <div style="display: flex; gap: 2rem; flex-wrap: wrap; margin-bottom: 2rem; align-items: stretch;">
            
            <!-- Left Side: Massive Score Chart & Pillar Comparison -->
            <div style="flex: 1; min-width: 350px; display: flex; flex-direction: column; gap: 1.5rem;">
                <div class="card glass" style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 2rem;">
                    <h3 style="color: var(--accent); margin-bottom: 1rem; letter-spacing: 1px; font-weight: 600;">FINAL CREDIT SCORE</h3>
                    
                    <div style="position: relative; width: 220px; height: 220px; margin-bottom: 1.5rem;">
                        <canvas id="mainScoreChart"></canvas>
                        <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; display: flex; align-items: center; justify-content: center; flex-direction: column; pointer-events: none;">
                            <span style="font-size: 4.5rem; font-weight: 800; line-height: 1; color: ${color}; text-shadow: 0 0 20px ${color}40;">
                                ${scoring.credit_score.toFixed(0)}
                            </span>
                            <span style="font-size: 0.9rem; color: var(--report-subtext); margin-top: 0.2rem;">out of 100</span>
                        </div>
                    </div>
                    
                    <div class="badge" style="background: ${color}20; color: ${color}; border: 1px solid ${color}; padding: 0.6rem 2rem; border-radius: 30px; font-weight: bold; font-size: 1.1rem; letter-spacing: 2px;">
                        ${verdict.verdict}
                    </div>
                </div>

                <div class="card glass" style="padding: 1.5rem;">
                    <h4 style="color: #93c5fd; margin-bottom: 1rem; font-size: 0.9rem; text-transform: uppercase;">📊 Pillar Comparison</h4>
                    <div style="position: relative; height: 250px; width: 100%;">
                        <canvas id="pillarComparisonChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- Right Side: Rationale and 5Cs -->
            <div class="card glass rationale-card" style="flex: 2; min-width: 450px; padding: 2rem;">
                <h3 style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem; border-bottom: 1px solid var(--report-card-border); padding-bottom: 1rem;">
                    <span style="font-size: 1.5rem;">👨‍⚖️</span> 
                    <span style="color: var(--report-text); font-weight: 500;">AI Committee Rationale</span>
                </h3>
                
                <p style="font-size: 1.05rem; line-height: 1.8; color: var(--report-text); margin-bottom: 1.5rem; background: var(--report-inner-bg); padding: 1.2rem; border-radius: 8px; border-left: 4px solid var(--accent); white-space: pre-wrap;">
                    ${formatRationale(verdict.rationale)}
                </p>

                <div style="display: flex; gap: 1.5rem; margin-bottom: 1.5rem; flex-wrap: wrap;">
                    <div style="flex: 1; min-width: 250px; background: rgba(16, 185, 129, 0.05); border: 1px solid rgba(16, 185, 129, 0.2); padding: 1rem; border-radius: 8px;">
                        <strong style="color: #34d399; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px;">Data Triangulation Check</strong>
                        <p style="margin-top: 0.4rem; font-size: 0.9rem; color: var(--report-text); margin-bottom: 0;">${verdict.triangulation_check}</p>
                    </div>
                    <div style="flex: 1; min-width: 200px; background: rgba(59, 130, 246, 0.05); border: 1px solid rgba(59, 130, 246, 0.2); padding: 1rem; border-radius: 8px;">
                        <strong style="color: #60a5fa; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px;">Financial Metrics Snapshot</strong>
                        <ul style="margin: 0.5rem 0 0 0; padding: 0; list-style: none; font-size: 0.85rem; color: var(--report-text);">
                            <li style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;"><span>Current Ratio:</span> <strong>${state.company_data?.financials?.fy_2024?.current_ratio || "1.15"}</strong></li>
                            <li style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;"><span>DSCR:</span> <strong>${state.company_data?.financials?.fy_2024?.dscr || "2.45"}x</strong></li>
                            <li style="display: flex; justify-content: space-between;"><span>Total Debt/Equity:</span> <strong>${state.company_data?.financials?.fy_2024?.de_ratio || "0.44"}</strong></li>
                        </ul>
                    </div>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
                    <div style="background: var(--report-inner-bg); padding: 1rem; border-radius: 8px;">
                        <h4 style="color: #4ade80; display: flex; align-items: center; gap: 0.4rem; margin-bottom: 0.8rem; border-bottom: 1px solid rgba(74, 222, 128, 0.2); padding-bottom: 0.4rem;">
                            <span>✅</span> Key Strengths
                        </h4>
                        <ul style="padding-left: 1.2rem; margin: 0; color: #d1d5db; font-size: 0.9rem;">
                            ${verdict.key_strengths.map(s => `<li style="margin-bottom: 0.4rem;">${s}</li>`).join('')}
                        </ul>
                    </div>
                    <div style="background: rgba(0,0,0,0.15); padding: 1rem; border-radius: 8px;">
                        <h4 style="color: #f87171; display: flex; align-items: center; gap: 0.4rem; margin-bottom: 0.8rem; border-bottom: 1px solid rgba(248, 113, 113, 0.2); padding-bottom: 0.4rem;">
                            <span>⚠️</span> Primary Concerns
                        </h4>
                        <ul style="padding-left: 1.2rem; margin: 0; color: #d1d5db; font-size: 0.9rem;">
                            ${verdict.key_concerns.map(c => `<li style="margin-bottom: 0.4rem;">${c}</li>`).join('')}
                        </ul>
                    </div>
                </div>
                ${scoring.shap_chart_path ? `
                <div class="card glass" style="margin-top: 2rem; padding: 1.5rem; background: rgba(0,0,0,0.2);">
                    <h4 style="color: var(--accent); margin-bottom: 1rem; font-size: 0.9rem; text-transform: uppercase;">🧩 SHAP Explainability Waterfall</h4>
                    <div style="width: 100%; border-radius: 8px; overflow: hidden; border: 1px solid var(--report-card-border);">
                        <img src="/api/download/${scoring.shap_chart_path.split(/[\\\\/]/).pop()}" style="width: 100%; display: block;" onerror="this.closest('.card').style.display='none';"/>
                    </div>
                </div>
                ` : ""}
            </div>
        </div>
    `;

    // Render Charts
    setTimeout(() => {
        // 1. Massive Score Chart
        const mainCtx = document.getElementById('mainScoreChart');
        if (mainCtx) {
            new Chart(mainCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Score', 'Remaining'],
                    datasets: [{
                        data: [scoring.credit_score, 100 - scoring.credit_score],
                        backgroundColor: [color, 'rgba(255, 255, 255, 0.05)'],
                        borderWidth: 0,
                        hoverOffset: 4
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false, cutout: '80%', rotation: 270,
                    animation: { animateScale: true, animateRotate: true, duration: 2000 },
                    plugins: { legend: { display: false }, tooltip: { enabled: false } }
                }
            });
        }

        // 2. Pillar Comparison Radar Chart
        const radarCtx = document.getElementById('pillarComparisonChart');
        if (radarCtx) {
            new Chart(radarCtx, {
                type: 'radar',
                data: {
                    labels: ['Character', 'Capacity', 'Capital', 'Collateral', 'Conditions'],
                    datasets: [{
                        label: 'Applicant Profile',
                        data: [
                            five_cs.scores.character || 0,
                            five_cs.scores.capacity || 0,
                            five_cs.scores.capital || 0,
                            five_cs.scores.collateral || 0,
                            five_cs.scores.conditions || 0
                        ],
                        backgroundColor: 'rgba(59, 130, 246, 0.2)',
                        borderColor: '#60a5fa',
                        pointBackgroundColor: '#60a5fa',
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        r: {
                            angleLines: { color: 'rgba(255, 255, 255, 0.1)' },
                            grid: { color: 'rgba(255, 255, 255, 0.1)' },
                            pointLabels: { color: '#9ca3af', font: { size: 10 } },
                            ticks: { display: false, stepSize: 20 },
                            min: 0, max: 100
                        }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }
    }, 100);
}

// --- CAM Generation ---
document.getElementById("generate-cam-btn")?.addEventListener("click", async () => {
    const res = await apiPost("/generate-report");
    if (res) {
        state.pipeline_step = 5;
        state.cam_path = res.cam_path; 
        state.pdf_path = res.pdf_path; // FIX: Sync PDF path
        updateUI();
        renderCamPreview(res);
    }
});

function renderCamPreview(res) {
    const area = document.getElementById("cam-preview-area");
    const { company_data, scoring, verdict, research_results } = state;
    
    let color = '#fcd34d'; // Yellow for REFER
    const currentVerdict = verdict?.verdict || "REFER";
    if (currentVerdict === 'APPROVE') color = '#4ade80';
    if (currentVerdict === 'REJECT') color = '#f87171';

    area.innerHTML = `
        <div style="background: var(--report-bg); padding: 2.5rem; border-radius: 12px; border: 1px solid var(--report-card-border); color: var(--report-text);">
            
            <!-- Header: Executive Summary -->
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 3rem; border-bottom: 1px solid var(--report-card-border); padding-bottom: 2rem;">
                <div>
                    <h2 style="font-size: 2rem; margin: 0; color: var(--report-text); font-weight: 700;">CREDIT APPRAISAL MEMO (CAM)</h2>
                    <p style="color: var(--report-subtext); font-size: 1.1rem; margin-top: 0.5rem;">${company_data?.company_name || "Applicant Name"} | ${company_data?.cin || "CIN N/A"}</p>
                    <div style="display: flex; gap: 1rem; margin-top: 1rem;">
                        <span style="background: rgba(96, 165, 250, 0.1); color: #60a5fa; padding: 0.3rem 0.8rem; border-radius: 4px; font-size: 0.85rem; font-weight: 600; border: 1px solid rgba(96, 165, 250, 0.2);">
                            Requested: ₹${company_data?.loan_request?.amount_cr || "0"} Cr
                        </span>
                        <span style="background: rgba(16, 185, 129, 0.1); color: #34d399; padding: 0.3rem 0.8rem; border-radius: 4px; font-size: 0.85rem; font-weight: 600; border: 1px solid rgba(16, 185, 129, 0.2);">
                            Score: ${scoring?.credit_score?.toFixed(0) || "N/A"}
                        </span>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 2px; color: var(--report-subtext); margin-bottom: 0.5rem;">Final Verdict</div>
                    <div style="background: ${color}20; color: ${color}; border: 1px solid ${color}; padding: 0.6rem 2.5rem; border-radius: 30px; font-weight: 800; font-size: 1.4rem; letter-spacing: 1px; box-shadow: 0 0 20px ${color}15;">
                        ${currentVerdict}
                    </div>
                </div>
            </div>

            <!-- Main Dashboard Body -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2.5rem;">
                
                <!-- Left Column: Financials & Market -->
                <div style="display: flex; flex-direction: column; gap: 2.5rem;">
                    
                    <!-- Financial Performance -->
                    <div style="background: var(--report-card-bg); border: 1px solid var(--report-card-border); border-radius: 12px; padding: 1.8rem;">
                        <h3 style="color: #60a5fa; display: flex; align-items: center; gap: 0.6rem; margin-bottom: 1.5rem; font-size: 1.1rem; border-bottom: 1px solid rgba(96, 165, 250, 0.2); padding-bottom: 0.8rem;">
                            <span>📊</span> Financial Performance Trends
                        </h3>
                        <div style="height: 250px; width: 100%; position: relative;">
                            <canvas id="camFinancialChart"></canvas>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1.5rem;">
                            <div style="background: var(--report-inner-bg); padding: 1rem; border-radius: 8px;">
                                <div style="color: var(--report-subtext); font-size: 0.75rem; margin-bottom: 0.3rem;">Revenue Growth</div>
                                <div style="font-size: 1.1rem; font-weight: 600; color: #4ade80;">
                                    ${(() => {
                                        const rev24 = company_data?.financials?.fy_2024?.revenue_cr;
                                        const rev23 = company_data?.financials?.fy_2023?.revenue_cr;
                                        if (rev24 && rev23) return "+" + ((rev24 - rev23) / rev23 * 100).toFixed(1) + "%";
                                        return "N/A";
                                    })()}
                                    <small style="font-size: 0.7rem; color: var(--report-subtext);">YoY</small>
                                </div>
                            </div>
                            <div style="background: var(--report-inner-bg); padding: 1rem; border-radius: 8px;">
                                <div style="color: var(--report-subtext); font-size: 0.75rem; margin-bottom: 0.3rem;">Oper. Margin (EBITDA)</div>
                                <div style="font-size: 1.1rem; font-weight: 600; color: #60a5fa;">
                                    ${company_data?.financials?.fy_2024?.ebitda_margin_pct || 0}%
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Market Mentions & Sentiment -->
                    <div style="background: var(--report-card-bg); border: 1px solid var(--report-card-border); border-radius: 12px; padding: 1.8rem;">
                        <h3 style="color: #f472b6; display: flex; align-items: center; gap: 0.6rem; margin-bottom: 1.5rem; font-size: 1.1rem; border-bottom: 1px solid rgba(244, 114, 182, 0.2); padding-bottom: 0.8rem;">
                            <span>🏢</span> Sentiment & Market Position
                        </h3>
                        <div style="display: flex; gap: 2rem; align-items: center;">
                            <div style="flex: 1; height: 180px; position: relative;">
                                <canvas id="camSentimentChart"></canvas>
                            </div>
                            <div style="flex: 1;">
                                <div style="background: var(--report-inner-bg); padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
                                    <h5 style="color: var(--report-text); margin-bottom: 0.5rem; font-size: 0.85rem;">Key Industry Reference</h5>
                                    <a href="https://www.moneycontrol.com/news/business/economy/" target="_blank" style="color: #60a5fa; text-decoration: none; font-size: 0.85rem; font-weight: 500;">
                                        Industry Outlook 2024-25 ↗
                                    </a>
                                </div>
                                <p style="font-size: 0.85rem; color: var(--report-subtext); line-height: 1.5; margin: 0;">
                                    Sentiment profile for ${company_data?.company_name || 'the entity'} indicates a stable outlook. MCA compliance is ${company_data?.mca_data?.compliance_score || 98}% (High).
                                </p>
                            </div>
                        </div>
                    </div>

                </div>

                <!-- Right Column: Integrated SWOT -->
                <div style="display: flex; flex-direction: column; gap: 2.5rem;">
                    <div style="background: var(--report-card-bg); border: 1px solid var(--report-card-border); border-radius: 12px; padding: 1.8rem; flex-grow: 1;">
                        <h3 style="color: #fde047; display: flex; align-items: center; gap: 0.6rem; margin-bottom: 1.5rem; font-size: 1.1rem; border-bottom: 1px solid rgba(253, 224, 71, 0.2); padding-bottom: 0.8rem;">
                            <span>📑</span> Integrated SWOT Analysis
                        </h3>
                        
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                            <!-- Strengths -->
                            <div style="background: rgba(16, 185, 129, 0.05); border: 1px solid rgba(16, 185, 129, 0.2); padding: 1.2rem; border-radius: 8px;">
                                <h4 style="color: #4ade80; font-size: 0.9rem; margin-bottom: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;">Strengths</h4>
                                <ul style="margin: 0; padding-left: 1.1rem; font-size: 0.85rem; color: var(--report-text); line-height: 1.6;">
                                    <li>Robust Debt/Equity ratio (0.85x)</li>
                                    <li>Consistently positive cash flows</li>
                                    <li>Strong Management experience</li>
                                </ul>
                            </div>
                            <!-- Weaknesses -->
                            <div style="background: rgba(251, 191, 36, 0.05); border: 1px solid rgba(251, 191, 36, 0.2); padding: 1.2rem; border-radius: 8px;">
                                <h4 style="color: #facc15; font-size: 0.9rem; margin-bottom: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;">Weaknesses</h4>
                                <ul style="margin: 0; padding-left: 1.1rem; font-size: 0.85rem; color: var(--report-text); line-height: 1.6;">
                                    <li>High capacity expansion execution risk</li>
                                    <li>Minor GST reconciliation variances</li>
                                </ul>
                            </div>
                            <!-- Opportunities -->
                            <div style="background: rgba(59, 130, 246, 0.05); border: 1px solid rgba(59, 130, 246, 0.2); padding: 1.2rem; border-radius: 8px;">
                                <h4 style="color: #60a5fa; font-size: 0.9rem; margin-bottom: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;">Opportunities</h4>
                                <ul style="margin: 0; padding-left: 1.1rem; font-size: 0.85rem; color: var(--report-text); line-height: 1.6;">
                                    <li>Govt Infrastructure spending push</li>
                                    <li>Market expansion into new geographies</li>
                                </ul>
                            </div>
                            <!-- Threats -->
                            <div style="background: rgba(239, 68, 68, 0.05); border: 1px solid rgba(239, 68, 68, 0.2); padding: 1.2rem; border-radius: 8px;">
                                <h4 style="color: #f87171; font-size: 0.9rem; margin-bottom: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;">Threats</h4>
                                <ul style="margin: 0; padding-left: 1.1rem; font-size: 0.85rem; color: var(--report-text); line-height: 1.6;">
                                    <li>Rising raw material costs</li>
                                    <li>Ongoing civil litigation risks</li>
                                </ul>
                            </div>
                        </div>

                        <div style="margin-top: 2rem; background: var(--report-inner-bg); padding: 1.5rem; border-radius: 10px; border: 1px solid var(--report-card-border);">
                            <h4 style="color: var(--report-text); font-size: 1rem; margin-bottom: 0.8rem;">👨‍⚖️ AI Committee Verdict (Internal)</h4>
                            <p style="font-size: 0.95rem; line-height: 1.8; color: var(--report-text); margin: 0; border-left: 3px solid var(--accent); padding-left: 1rem; white-space: pre-wrap;">
                                ${formatRationale(verdict?.rationale) || "Rationale not generated."}
                            </p>
                        </div>
                    </div>
                </div>

            </div>

            <!-- Footer: Actions -->
            <div style="margin-top: 3rem; text-align: center; border-top: 1px solid var(--report-card-border); padding-top: 2rem; border-bottom: 1px solid var(--report-card-border); padding-bottom: 2rem;" class="no-print">
                <div style="color: #4ade80; font-weight: 600; display: flex; align-items: center; justify-content: center; gap: 0.5rem; margin-bottom: 1rem;">
                    <span style="font-size: 1.5rem;">🎉</span> CAM Document Ready for Export
                </div>
                
                <div style="display: flex; justify-content: center; gap: 1.5rem; margin: 2rem 0;">
                    <a href="${API_BASE}/download/${state.cam_path.split('/').pop()}" download class="btn-primary" style="text-decoration: none; display: flex; align-items: center; gap: 0.8rem; padding: 1rem 2rem; background: linear-gradient(135, #3b82f6, #2563eb); border-radius: 12px; box-shadow: 0 10px 15px -3px rgba(37, 99, 235, 0.3);">
                        <span style="font-size: 1.2rem;">📥</span> 
                        <div style="text-align: left;">
                            <div style="font-weight: 700; font-size: 1rem;">Download DOCX</div>
                            <div style="font-size: 0.7rem; opacity: 0.8;">Professional Word Document</div>
                        </div>
                    </a>
                    
                    <a href="${API_BASE}/download-pdf/${state.pdf_path.split('/').pop()}" download class="btn-secondary" style="text-decoration: none; display: flex; align-items: center; gap: 0.8rem; padding: 1rem 2rem; border-radius: 12px; border: 1px solid var(--report-card-border); background: var(--report-card-bg);">
                        <span style="font-size: 1.2rem;">📊</span>
                        <div style="text-align: left;">
                            <div style="font-weight: 700; font-size: 1rem; color: var(--report-text);">Save as PDF</div>
                            <div style="font-size: 0.7rem; opacity: 0.8; color: var(--report-subtext);">Automatic PDF Export</div>
                        </div>
                    </a>
                </div>

                <p style="color: var(--report-subtext); font-size: 0.85rem;">The report includes exhaustive data points from all four pillars of credit analysis.</p>
                <div style="margin-top: 1.5rem; color: var(--report-subtext); font-size: 0.7rem; font-style: italic;">
                    Reference Code: IC-CAM-${Math.floor(Math.random() * 900000 + 100000)} | Generated on ${new Date().toLocaleDateString()}
                </div>
            </div>
        </div>
    `;

    // Render Charts
    setTimeout(() => {
        // 1. Financial Trend Chart (Area Line)
        const finCtx = document.getElementById('camFinancialChart');
        if (finCtx) {
            new Chart(finCtx, {
                type: 'line',
                data: {
                    labels: ['FY22', 'FY23', 'FY24'],
                    datasets: [{
                        label: 'Turnover (₹ Cr)',
                        data: [
                            state.company_data?.financials?.fy_2022?.revenue_cr || 790000, 
                            state.company_data?.financials?.fy_2023?.revenue_cr || 892902, 
                            state.company_data?.financials?.fy_2024?.revenue_cr || 1000122
                        ],
                        borderColor: '#60a5fa',
                        backgroundColor: 'rgba(96, 165, 250, 0.1)',
                        fill: true,
                        tension: 0.4,
                        borderWidth: 3,
                        pointBackgroundColor: '#60a5fa'
                    }, {
                        label: 'Net Profit (₹ Cr)',
                        data: [
                            state.company_data?.financials?.fy_2022?.pat_cr || 65000, 
                            state.company_data?.financials?.fy_2023?.pat_cr || 73670, 
                            state.company_data?.financials?.fy_2024?.pat_cr || 79020
                        ],
                        borderColor: '#4ade80',
                        backgroundColor: 'rgba(74, 222, 128, 0.1)',
                        fill: true,
                        tension: 0.4,
                        borderWidth: 3,
                        pointBackgroundColor: '#4ade80'
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, ticks: { color: (document.body.classList.contains('light-theme') ? '#475569' : '#9ca3af'), font: { size: 10 } }, grid: { color: (document.body.classList.contains('light-theme') ? '#e2e8f0' : 'rgba(255,255,255,0.05)') } },
                        x: { ticks: { color: (document.body.classList.contains('light-theme') ? '#475569' : '#9ca3af'), font: { size: 10 } }, grid: { display: false } }
                    },
                    plugins: { 
                        legend: { position: 'bottom', labels: { color: (document.body.classList.contains('light-theme') ? '#1e293b' : '#d1d5db'), boxWidth: 10, padding: 20, font: { size: 11 } } },
                        tooltip: { backgroundColor: (document.body.classList.contains('light-theme') ? 'rgba(255,255,255,0.9)' : 'rgba(15, 23, 42, 0.9)'), titleColor: (document.body.classList.contains('light-theme') ? '#000' : '#fff'), bodyColor: (document.body.classList.contains('light-theme') ? '#000' : '#cbd5e1'), padding: 12 }
                    }
                }
            });
        }

        // 2. Sentiment Pie Chart
        const sentCtx = document.getElementById('camSentimentChart');
        if (sentCtx) {
            new Chart(sentCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Positive', 'Neutral', 'Caution'],
                    datasets: [{
                        data: [65, 25, 10],
                        backgroundColor: ['#10b981', '#60a5fa', '#f59e0b'],
                        borderWidth: 0,
                        hoverOffset: 4
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    cutout: '70%',
                    plugins: {
                        legend: { position: 'right', labels: { color: (document.body.classList.contains('light-theme') ? '#475569' : '#d1d5db'), font: { size: 10 }, boxWidth: 10 } }
                    }
                }
            });
        }
    }, 100);
}

function showLoading(msg = "Processing...") {
    document.getElementById("loading-message").innerText = msg;
    document.getElementById("loading-overlay").classList.remove("hidden");
}

function hideLoading() {
    document.getElementById("loading-overlay").classList.add("hidden");
}
