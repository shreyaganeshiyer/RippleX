# RippleX

**Enterprise Supply Chain Disruption Response Engine**  
*Hackathon Track PS8: Supply Chain — Disruption Response Assistant*

---

## Overview

Modern supply chain disruptions rarely surface as structured data. Incidents arrive through disparate, unstructured channels—such as vendor emails, logistics alerts, and freight carrier updates. Without unique system keys or cross-referenced line items, supply chain teams spend hours manually assessing blast radius, inventory levels, and order fulfillment risks.

**RippleX** unifies natural-language incident ingestion with deterministic relational supply chain modeling. By separating language comprehension from transactional accounting, RippleX enables operators to evaluate downstream exposure, prioritize pending customer obligations, and explore evaluated trade-offs in real time.

---

## Core System Architecture

RippleX enforces a strict pipeline to guarantee data integrity and operational auditability:

1. **Ingestion & Natural Language Parsing:** Google Gemini extracts operational entities, location references, and incident parameters from raw text notices.
2. **Deterministic Entity Resolution:** The extraction payload is validated against relational records. Ambiguous or missing entities trigger manual intervention flags rather than inferred records.
3. **Deterministic Impact Analysis:** Python and SQLite traverse the dependency graph—from inbound logistics down to individual customer line items—to calculate exposure.
4. **Mitigation Strategy Formulation:** The system analyzes viable response paths (e.g., inventory reallocation, split-shipments, expedited transit).
5. **Decision Synthesis:** Recommendations rank mitigation paths based on cost, delivery variance, and operational feasibility.
6. **Command Center Visualization:** All findings are published to an auditable operator console backed by clear chain-of-evidence references.

---

## Architectural Principle: AI vs. Deterministic Execution

To prevent Large Language Model hallucinations from corrupting inventory accounting and delivery schedules, RippleX strictly isolates cognitive comprehension from arithmetic execution.

| Operational Domain | Engine | Functional Responsibility |
| :--- | :--- | :--- |
| **Notice Interpretation** | Google Gemini | Extracts event classification, entity mentions, durations, and confidence levels. |
| **Entity Validation** | Relational Database | Verifies and maps textual entities against registered master records. |
| **Inventory & Shortage Analysis** | Python Runtime | Calculates physical on-hand stock, safety stock reserves, and facility-isolated shortfalls. |
| **Financial Exposure** | Python Runtime | Computes total contract value and units at risk based on master data. |
| **Delivery Date Adjustments** | Python Engine | Computes revised fulfillment dates via programmatic date arithmetic. |
| **Action Contextualization** | Google Gemini | Generates readable strategic summaries and operational trade-off narratives. |

---

## Core Capabilities

* **Unstructured Notice Ingestion:** Parses incoming unstructured text without requiring standardized input forms.
* **Strict Entity Resolution:** Confirms the existence of suppliers, locations, purchase orders, and SKUs before downstream calculation.
* **Multi-Tier Graph Tracing:** Traces dependencies across the fulfillment chain: `Supplier → Inbound PO → Distribution Center → Stock Allocation → Customer Order`.
* **Facility-Isolated Inventory Auditing:** Evaluates buffer quantities strictly at the individual warehouse level to avoid false assumptions regarding multi-site availability.
* **Deterministic Order Prioritization:** Sorts affected customer line items using business heuristics: contractual SLA, customer account tier, order value, and unit exposure.
* **Zero-Impact Detection:** Accurately distinguishes critical alerts from noise. If an incident affects non-critical lines or well-buffered SKUs, RippleX reports **No Current Business Impact**.
* **Auditable Evidence Chains:** Displays transparent, end-to-end operational lineage behind every flagged shortage and suggested delivery revision.

---

## Command Center Workflow

The user interface guides operators through five distinct operational phases:

* **01 — Understand:** Analyzes the core incident facts (event type, primary supplier, location, disruption duration, and extraction confidence).
* **02 — Trace:** Identifies all impacted supply chain nodes (purchase orders, transit carriers, and receiving distribution centers).
* **03 — Customer Impact:** Displays a ranked register of affected customer orders, shortage volumes, updated delivery dates, and financial exposure.
* **04 — Response Options:** Compares viable remediation strategies, detailing cost implications, speed, and customer impact.
* **05 — Recommendation:** Delivers an actionable course of action for operator sign-off.

---

## Technology Stack

* **Application Runtime:** Python 3.10+
* **API Layer:** FastAPI
* **Data Storage:** SQLite
* **Language Model Integration:** Google Gemini API
* **Data Validation:** Pydantic v2
* **Configuration Management:** python-dotenv
* **Frontend:** HTML5, CSS3, JavaScript (ES6)

---

## Repository Structure

RippleX/
├── app.py                      # FastAPI application entry point and routes
├── requirements.txt             # Python runtime dependencies
├── backend/
│   ├── database.py              # SQLite connection and query layer
│   ├── disruption_parser.py     # Gemini extraction prompts and structured schemas
│   ├── entity_resolver.py       # Deterministic database entity resolution
│   ├── impact_engine.py         # Relational graph traversal and shortage calculations
│   ├── response_engine.py       # Strategy generator and trade-off evaluator
│   └── recommendation_engine.py # Decision synthesis engine
├── data/
│   ├── seed.py                  # Seed script for realistic demo supply chain data
│   └── ripplex.db               # SQLite database instance
└── frontend/
├── index.html               # Operator command center dashboard
├── style.css                # UI design and responsive styles
└── app.js                   # Client-side state and API interaction


---

## Getting Started

### Prerequisites
* Python 3.10 or higher
* Git
* Valid Google Gemini API key

### 1. Installation
Clone the repository and set up a local environment:

```bash
git clone [https://github.com/your-org/RippleX.git](https://github.com/your-org/RippleX.git)
cd RippleX
Set up and activate a virtual environment:

Bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
Install dependencies:

Bash
pip install -r requirements.txt
2. Environment Configuration
Create a .env file in the project root:

Code snippet
GEMINI_API_KEY="your-gemini-api-key-here"
3. Database Initialization
Seed the SQLite database with the baseline supply chain dataset:

Bash
python data/seed.py
4. Running the Service
Start the local FastAPI development server:

Bash
uvicorn app:app --reload --port 8000
Access the Command Center at:
http://127.0.0.1:8000

Verification Scenarios
Scenario 1: Active Supply Disruption
Input:

"ABC Components  has announced a production halt that will delay shipments of X-200 and X-300 by 10 days."

System Action: Resolves vendor and product records, verifies inbound shipment schedules, detects warehouse shortages, ranks impacted accounts by SLA, and recommends targeted mitigation.

Scenario 2: No Operational Impact
Input:

"ABC Components has announced a production halt affecting X-300 shipments by 10 days."

System Action: Validates that warehouse inventory meets buffer thresholds and that no pending orders rely on incoming deliveries during the affected window. Flags incident as No Current Business Impact.

Scenario 3: Ambiguous Incident Notice
Input:

"ABC Components  has announced that its X-series products will be delayed by 7 days."

System Action: Flags "X-series" as an ambiguous entity. Stops downstream automated processing and requests operator clarification instead of guessing affected SKUs.

System Governance & Guardrails
No Synthetic Entities: The system does not guess or interpolate unknown vendor names, locations, or product IDs.

Deterministic Quantities: Numeric fields—including on-hand balances, units at risk, and contract revenue—are sourced exclusively from database records.

Human-in-the-Loop: System recommendations do not mutate database states, initiate vendor orders, or contact customers without explicit operator approval.