# 🍪 OmniStock AI: Agentic AI Supply Chain System for FMCG

[![Version](https://img.shields.io/badge/version-1.0-blue.svg)](https://github.com/yourusername/omnistock-ai)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![AWS](https://img.shields.io/badge/AWS-Serverless-orange.svg)](https://aws.amazon.com)

**OmniStock AI** is an end-to-end, multi-agent AI supply chain intelligence platform built specifically for the Indian FMCG and biscuit distribution sector.

---

## 🎯 The Problem: The ₹15,000 Crore Visibility Gap
Indian FMCG distributors lose an estimated **8–15% of potential revenue annually** due to:
- Stockouts of high-velocity SKUs.
- Over-stocking of slow-moving inventory (leading to expiry waste).
- Missed festive demand peaks (e.g., Diwali, Durga Puja).
- Lack of real-time visibility into secondary and tertiary sales (The "Bullwhip Effect").

## 🧠 Our Solution: Agentic AI
Unlike traditional predictive AI that just says *"Demand will spike 22%"*, OmniStock AI is an **Agentic System**. It doesn't just predict; it acts. It automatically raises Purchase Orders (POs), alerts distributors via WhatsApp/Telegram, and adjusts delivery beat plans with optional human-in-the-loop oversight.

### 🌟 Core Capabilities
1. **Area × SKU Demand Heatmap:** Geospatial intelligence showing exactly which areas need which products.
2. **Offer / Promotion Generator:** LLM-driven generation of regional, hyper-local promotions (e.g., Hindi/Bengali SMS alerts) to clear overstocked/near-expiry items.
3. **Weekly Auto Stock Order:** Automated, FIFO-aware, safety-stock optimized Purchase Order generation.
4. **Festive & Batch Demand Forecasting:** ML-driven spike alerts (XGBoost + Prophet) incorporating local festive calendars (Diwali, Holi, regional melas).
5. **Distribution Planning:** OR-Tools powered vehicle routing and daily beat plan optimization.
6. **Quick Commerce Integration:** Real-time dark store (Blinkit/Zepto) replenishment triggers.

---

## 🏗️ Architecture & Pipeline

### The Medallion Data Pipeline
Our system leverages a highly robust Bronze-Silver-Gold medallion architecture:
* **Bronze Layer:** Raw ingestion of Tally/DMS exports, Weather APIs, Festive Calendars, and Q-Commerce Webhooks.
* **Silver Layer:** Cleaned, standardized, normalized units, and FIFO batch age calculated.
* **Gold Layer:** Analytics-ready mart tables powering the Dashboards, ML Models, and Autonomous Agents.

### The Agent Orchestration Layer
We utilize a multi-agent orchestration pattern:
* **Orchestrator Agent:** Decomposes goals and manages conflicts.
* **Worker Agents:** Specialized agents for Demand Forecasting, Inventory Management, Promotions, Distribution, and Q-Commerce.
* **Critic Agent:** Validates decisions against business constraints before execution.
* **Human-in-the-loop:** A dedicated dashboard for distributor approval/modification of AI-generated POs.

---

## 💻 Technology Stack

* **Frontend:** Next.js 14 App Router, Tailwind CSS, Mapbox GL JS (Geo Heatmaps), React Query.
* **Backend:** Python FastAPI, AWS Lambda (Serverless Monolith), API Gateway.
* **Database:** DynamoDB (On-Demand) / PostgreSQL (Transactional), TimescaleDB (Time-series).
* **AI/ML:** XGBoost / LightGBM (Demand Forecasting), Facebook Prophet (Seasonal), Gemini / GPT-4 (Promotion LLM), LangGraph (Agent Orchestration).
* **Cloud & DevOps:** AWS S3, AWS EC2, GitHub Actions CI/CD.
* **Communication:** Telegram/Twilio WhatsApp API for real-time distributor alerts.

---

## 📈 Market Opportunity & ROI
Implementations of AI in FMCG Supply Chains have demonstrated massive returns:
- **Stockout Rate Reduction:** 15–30%
- **Forecast Error Improvement:** 20–50%
- **Inventory Holding Cost Reduction:** 25–35%

OmniStock AI targets the massive **₹12,000 Crore SAM** (Serviceable Addressable Market) of FMCG Distribution Tech in India.

---

## 🚀 Get Started

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/omnistock-ai.git
   ```
2. **Setup AWS Infrastructure**
   ```bash
   cd backend
   sam deploy --guided
   ```
3. **Run the Frontend**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

*Built with ❤️ for the Future of Indian Retail.*
