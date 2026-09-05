# RippleX

TRACK_ID=PS08

RippleX — AI Supply Chain Disruption Command Center

See the ripple. Stop the disruption.

RippleX is an AI-powered supply chain disruption response assistant that converts messy, unstructured disruption notices into a traceable, quantified impact assessment and recommended response plan.

It helps distributors answer:

What happened? What does it affect? Which customers are at risk? How urgent are they? What can we do about it?

⸻

TRACK_ID=PS6

Hackathon Track: Supply Chain — Disruption Response Assistant
Project: RippleX
Architecture: Python + FastAPI + SQLite + Gemini API
AI Provider: Google Gemini

⸻

1. Problem

Supply chain disruptions rarely arrive as clean structured data.

A distributor may receive a message such as:

“ABC Components Bangalore has announced a production halt that will delay shipments of X-200 and X-300 by 10 days.”

The message may contain no internal IDs and may use ambiguous product or location names.

The real challenge is determining the downstream business impact:

* Which supplier is affected?
* Which products or shipments are involved?
* Where is the affected inventory?
* Which pending customer orders depend on that stock?
* How many units are at risk?
* Which customers should be handled first?
* What response options are available?
* What are the trade-offs between those options?
* Is the disruption actually relevant to the distributor’s current business?

⸻

2. Solution

RippleX creates a complete disruption-response workflow:

Unstructured Disruption Notice
            │
            ▼
     Gemini Extraction
            │
            ▼
     Entity Resolution
            │
            ▼
  Deterministic Impact Engine
            │
            ├── Shipments
            ├── Inventory
            ├── Customer Orders
            └── Shortages
            │
            ▼
   Response Option Engine
            │
            ▼
 Recommendation Engine
            │
            ▼
 Evidence-Backed Command Center

The key design principle is:

Gemini interprets the disruption. Python and the database determine the business impact.

This prevents the LLM from inventing quantities, shortages, orders, or financial impact.

⸻

3. Key Features

🧠 Unstructured Notice Understanding

RippleX accepts natural-language disruption notices instead of requiring structured forms.

Gemini extracts relevant information such as:

* Event type
* Supplier
* Location
* Products
* Shipments
* Warehouse
* Carrier
* Delay duration
* Confidence

⸻

🔎 Deterministic Entity Resolution

Extracted entities are matched against the company’s actual database.

RippleX verifies:

* Suppliers
* Products
* Shipments
* Warehouses

Unknown or ambiguous entities are not guessed.

Instead, RippleX can escalate the case for human review.

⸻

🌊 Supply Chain Impact Tracing

RippleX traces a disruption through:

Supplier
   ↓
Shipment
   ↓
Warehouse
   ↓
Inventory
   ↓
Customer Orders

This allows the system to identify the actual downstream ripple instead of simply reporting that “a supplier is delayed.”

⸻

📦 Warehouse-Level Inventory Analysis

Inventory is evaluated at the warehouse level.

Stock in one warehouse is not automatically assumed to satisfy orders assigned to another warehouse.

This prevents false assumptions about available supply.

⸻

👥 Customer Order Prioritization

Affected orders are ranked using deterministic factors including:

* Customer order priority
* Promised delivery date
* Order value
* Quantity exposed

RippleX identifies which orders require attention first.

⸻

📅 Revised Delivery Dates

When a disruption includes a deterministic delay duration, RippleX calculates:

Revised Delivery Date
=
Promised Delivery Date
+
Disruption Delay

Date arithmetic is performed by Python rather than the LLM.

⸻

💰 Financial Exposure

RippleX calculates:

* Units at risk
* Orders at risk
* Order value at risk

The calculations are derived from database records.

⸻

⚖️ Response Options & Trade-offs

RippleX presents possible responses such as:

* Expedite supply
* Part-ship an order
* Reallocate available inventory
* Inform the customer
* Prioritize critical orders

Each option can be evaluated based on operational trade-offs such as:

* Cost
* Customer impact
* Speed
* Supply availability

⸻

🎯 Recommendation

RippleX recommends a response based on the calculated impact and available options.

The system recommends actions but does not automatically execute them.

Human decision-makers remain in control.

⸻

🧾 Evidence & Traceability

Important impact claims can be traced back to their underlying records.

For example:

Order ORD101
      ↓
Requires 40 X-200 units
      ↓
WH001 has insufficient available inventory
      ↓
25 units available
      ↓
15 units exposed

This makes the reasoning auditable rather than a black-box AI response.

⸻

4. Handling Uncertainty

RippleX is designed to avoid hallucinating business impact.

Unknown entities

If a supplier or product cannot be confidently matched to company data, RippleX does not invent a match.

Ambiguous products

For example:

“X-series products will be delayed.”

RippleX does not automatically assume that this means X-200, X-300, and X-400.

It flags the ambiguity for human review.

No-impact disruptions

An alarming disruption does not automatically mean business impact.

If the affected entity cannot be connected to active shipments, inventory exposure, or pending orders, RippleX can return:

NO CURRENT BUSINESS IMPACT

This is important because a disruption should only be considered a business problem when it actually affects the company’s current operations.

⸻

5. Architecture

                    ┌─────────────────────┐
                    │  Disruption Notice  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Gemini Parser     │
                    │                     │
                    │ Extract structured  │
                    │ disruption facts    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Entity Resolver     │
                    │                     │
                    │ Match against       │
                    │ company data        │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Deterministic       │
                    │ Impact Engine       │
                    │                     │
                    │ Inventory           │
                    │ Shipments           │
                    │ Orders              │
                    │ Shortages           │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Response Engine     │
                    │                     │
                    │ Evaluate possible   │
                    │ response strategies │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Recommendation      │
                    │ Engine              │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ RippleX Command     │
                    │ Center              │
                    └─────────────────────┘

⸻

6. Separation of AI and Deterministic Logic

A major architectural principle of RippleX is keeping AI reasoning separate from business truth.

Gemini handles

* Natural-language interpretation
* Disruption classification
* Entity extraction
* Ambiguous language
* Human-readable explanations
* Recommendation reasoning

Python + SQLite handle

* Entity verification
* Inventory quantities
* Shipment quantities
* Pending orders
* Shortage calculations
* Order prioritization
* Order value at risk
* Revised delivery dates
* Evidence generation

Therefore:

The LLM never decides how much inventory exists or how many orders are actually at risk.

⸻

7. Project Structure

RippleX/
│
├── README.md
├── app.py
├── requirements.txt
│
├── backend/
│   ├── database.py
│   ├── disruption_parser.py
│   ├── entity_resolver.py
│   ├── impact_engine.py
│   ├── response_engine.py
│   └── recommendation_engine.py
│
├── data/
│   ├── seed.py
│   └── ripplex.db
│
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js

Components

app.py

FastAPI application and API endpoints.

disruption_parser.py

Uses Gemini to convert an unstructured disruption notice into a structured disruption event.

entity_resolver.py

Deterministically maps extracted entities to company records.

impact_engine.py

Calculates the actual business impact using database data.

response_engine.py

Generates possible response strategies and evaluates their trade-offs.

recommendation_engine.py

Produces the recommended course of action.

database.py

SQLite data access layer.

seed.py

Creates the demonstration supply-chain dataset.

frontend/

RippleX command-center interface.

⸻

8. Technology Stack

Layer	Technology
Backend	Python
API	FastAPI
Database	SQLite
LLM	Google Gemini API
Data Validation	Pydantic
Environment Configuration	python-dotenv
Frontend	HTML, CSS, JavaScript
Version Control	Git

⸻

9. Getting Started

Prerequisites

* Python 3.10+
* Git
* Gemini API key

⸻

Clone the repository

git clone <YOUR_GITHUB_REPOSITORY_URL>
cd RippleX

⸻

Create a virtual environment

macOS / Linux

python3 -m venv .venv
source .venv/bin/activate

Windows

python -m venv .venv
.venv\Scripts\activate

⸻

Install dependencies

pip install -r requirements.txt

⸻

Configure Gemini

Create a .env file in the project root:

GEMINI_API_KEY=your_gemini_api_key

The API key must not be committed to Git.

⸻

Run the application

uvicorn app:app --reload --port 8000

Open:

http://127.0.0.1:8000

⸻

10. Demo Scenarios

Scenario 1 — Real Supplier Disruption

Use:

ABC Components Bangalore has announced a production halt that will delay shipments of X-200 and X-300 by 10 days. Assess the downstream impact on inventory and pending customer orders, rank the affected orders by urgency, and recommend the best response.

This demonstrates the complete RippleX workflow:

Notice
 ↓
Supplier resolution
 ↓
Product resolution
 ↓
Shipment tracing
 ↓
Inventory analysis
 ↓
Customer impact
 ↓
Order prioritization
 ↓
Response options
 ↓
Recommendation

⸻

Scenario 2 — No Current Business Impact

Use:

ABC Components Bangalore has announced a production halt affecting X-300 shipments by 10 days. Assess whether there is any current business impact and explain why.

This demonstrates that RippleX does not automatically treat every disruption as a customer-impacting event.

⸻

Scenario 3 — Ambiguous Disruption

Use:

ABC Components Bangalore has announced that its X-series products will be delayed by 7 days. Assess the impact and recommend a response.

RippleX should recognize that X-series is not a verified product entity and avoid inventing which products are affected.

⸻

11. Command Center Workflow

The UI is organized around the operational questions a supply-chain manager needs answered.

01 — UNDERSTAND

What happened?

* Event type
* Supplier
* Location
* Products
* Delay
* Confidence

02 — TRACE

What does it touch?

* Shipments
* Warehouses
* Inventory
* Products

03 — CUSTOMER IMPACT

Who is affected?

* Orders at risk
* Units at risk
* Shortages
* Customers
* Delivery dates
* Order value at risk
* Urgency

04 — RESPONSE

What can we do?

* Expedite
* Reallocate
* Part-ship
* Customer communication
* Other response strategies

05 — RECOMMENDATION

What should we do first?

RippleX presents the recommended response together with the reasoning and trade-offs.

⸻

12. Data Model

The demonstration database contains:

* Suppliers
* Products
* Warehouses
* Inventory
* Shipments
* Customer orders

The data is intentionally structured to demonstrate realistic disruption propagation across multiple stages of the supply chain.

⸻

13. Safety & Guardrails

RippleX follows several important guardrails:

No hallucinated entities

Unknown suppliers, products, shipments, or warehouses are not silently mapped.

No invented impact

Business impact must come from verified company data.

No LLM calculations

Critical numerical calculations are performed deterministically.

No automatic actions

RippleX recommends actions but does not execute:

* Shipment changes
* Inventory transfers
* Customer communications
* Purchase orders

Human review

Ambiguous or unresolved cases can be escalated rather than guessed.

⸻

14. Why RippleX?

Traditional supply-chain workflows often require an operator to manually connect several pieces of information:

Email
 ↓
Supplier
 ↓
Shipment spreadsheet
 ↓
Warehouse inventory
 ↓
Order system
 ↓
Customer priority
 ↓
Manual decision

RippleX compresses this investigation into one workflow:

Messy Notice
     ↓
RippleX
     ↓
Traceable Impact
     ↓
Ranked Customers
     ↓
Response Options
     ↓
Recommended Action

The value is not simply generating an AI answer.

The value is connecting an unstructured disruption to verified operational data and turning it into a decision-ready response.

⸻

15. Future Improvements

Potential production extensions include:

* Live ERP/WMS/TMS integrations
* Real-time shipment tracking
* Multi-disruption correlation
* Supplier reliability history
* Historical disruption learning
* More sophisticated optimization of inventory reallocation
* Cost-aware response optimization
* Automated notification workflows with human approval
* Role-based dashboards for supply-chain teams

⸻

16. Project Philosophy

RippleX is built around one principle:

AI should help people understand and decide — not invent operational truth.

The system combines the language understanding capabilities of Gemini with deterministic business logic and traceable company data.

See the ripple. Stop the disruption.
