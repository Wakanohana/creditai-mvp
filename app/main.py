"""
CreditAI — MVP API de Scoring de Crédit PME
Version: 1.0.0-MVP
Stack: Python 3.11 / FastAPI / Scikit-learn / Pandas

Architecture:
  POST /score         → Score de crédit principal (données bancaires JSON)
  POST /score/demo    → Endpoint démo avec données simulées
  GET  /health        → Healthcheck
  GET  /docs          → Swagger UI automatique (FastAPI)

Usage investisseurs:
  Ce MVP démontre la capacité technique à ingérer des flux Open Banking
  (format Plaid/Tink simulé) et à produire un score de risque dynamique
  via un modèle ML entraîné sur des patterns de trésorerie.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from datetime import datetime

from app.models.schemas import (
    ScoringRequest,
    ScoringResponse,
    DemoScoringRequest,
    HealthResponse,
)
from app.services.scoring_engine import ScoringEngine
from app.services.data_simulator import DataSimulator

# ── App initialization ────────────────────────────────────────────────────────

app = FastAPI(
    title="CreditAI Scoring API",
    description="""
## CreditAI — Real-Time SME Credit Scoring API

**MVP Version** — Pre-Seed Demo

### What this API does
Ingests live bank transaction data (Open Banking format: Plaid US / Tink EU),
runs a predictive AI model on cash-flow time-series, and returns a dynamic
credit risk score in under 60 seconds.

### Key endpoints
- `POST /score` — Full scoring with real transaction data
- `POST /score/demo` — Instant demo with simulated SME profiles
- `GET /health` — Service health check

### Data format
Accepts standardized JSON (compatible with Plaid `transactions` and
Tink `account-transactions` response formats).
    """,
    version="1.0.0-MVP",
    contact={
        "name": "CreditAI Team",
        "email": "founders@creditai.io",
    },
    license_info={
        "name": "Proprietary — Confidential MVP",
    },
)

# CORS — Allow demo frontend and investor dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Service instances ─────────────────────────────────────────────────────────

scoring_engine = ScoringEngine()
data_simulator = DataSimulator()


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Service healthcheck — returns model status and API version."""
    return HealthResponse(
        status="healthy",
        version="1.0.0-MVP",
        model_loaded=scoring_engine.is_ready(),
        timestamp=datetime.utcnow().isoformat(),
        message="CreditAI Scoring API is operational",
    )


@app.post("/score", response_model=ScoringResponse, tags=["Scoring"])
async def score_sme(request: ScoringRequest):
    """
    **Main scoring endpoint.**

    Accepts a batch of bank transactions (Open Banking format) for a given SME,
    extracts cash-flow features, and returns a dynamic credit risk score.

    **Input:** Up to 12 months of transaction history (minimum 30 days recommended)
    **Output:** Risk score 0–100, risk band, key signal breakdown, and 90-day default probability
    """
    try:
        result = scoring_engine.score(request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring engine error: {str(e)}")


@app.post("/score/demo", response_model=ScoringResponse, tags=["Demo"])
async def score_demo(request: DemoScoringRequest):
    """
    **Demo endpoint for investors and pilot clients.**

    Generates a realistic simulated SME profile based on the selected archetype,
    runs the full scoring pipeline, and returns results — no real bank data needed.

    **Available archetypes:**
    - `healthy_growth` — Stable SME, growing revenue, low risk
    - `seasonal_business` — Strong seasonality, moderate risk
    - `early_stage` — Young company, thin history, elevated risk
    - `stressed_cashflow` — Payment delays, high default probability
    - `underrepresented_founder` — Good cash flow, no credit history (key use case)
    """
    try:
        # Generate simulated transaction data for the archetype
        simulated_data = data_simulator.generate(
            archetype=request.archetype,
            months=request.months,
            monthly_revenue=request.monthly_revenue,
        )
        # Build a full scoring request from simulated data
        scoring_request = ScoringRequest(
            company_id=f"DEMO-{request.archetype.upper()}",
            company_name=f"Demo SME ({request.archetype})",
            transactions=simulated_data,
            currency=request.currency,
        )
        result = scoring_engine.score(scoring_request)
        result.is_demo = True
        result.demo_archetype = request.archetype
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Demo scoring error: {str(e)}")


@app.get("/", tags=["System"])
async def root():
    """API root — redirects to docs."""
    return JSONResponse({
        "name": "CreditAI Scoring API",
        "version": "1.0.0-MVP",
        "docs": "/docs",
        "health": "/health",
        "demo": "POST /score/demo",
        "message": "Welcome to CreditAI. Visit /docs for the full API reference.",
    })


# ── Dev server ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
