# CreditAI — MVP API de Scoring de Crédit PME

> **Pre-Seed 2025–2026 · $500K · MVP fonctionnel**
> Infrastructure d'IA B2B pour le scoring de crédit en temps réel des plateformes de prêt aux PME.

---

## Architecture du projet

```
creditai-mvp/
├── app/
│   ├── main.py                    # FastAPI app + routes
│   ├── models/
│   │   └── schemas.py             # Pydantic v2 schemas (input/output)
│   └── services/
│       ├── scoring_engine.py      # Modèle ML (GBM) + logique de scoring
│       ├── feature_engineering.py # Extraction de features depuis les transactions
│       └── data_simulator.py      # Générateur de données synthétiques (5 archétypes)
├── tests/
│   └── test_api.py                # Suite de tests (16 tests — 16 passent ✅)
├── requirements.txt
└── README.md
```

---

## Installation

```bash
# 1. Cloner le projet
git clone https://github.com/creditai/mvp.git
cd creditai-mvp

# 2. Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Lancer l'API
python -m uvicorn app.main:app --reload --port 8000
```

L'API est disponible sur `http://localhost:8000`
Documentation Swagger : `http://localhost:8000/docs`

---

## Endpoints principaux

### GET `/health`
Vérifie que l'API et le modèle sont opérationnels.

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "healthy",
  "version": "1.0.0-MVP",
  "model_loaded": true,
  "timestamp": "2025-11-15T09:32:11.423Z",
  "message": "CreditAI Scoring API is operational"
}
```

---

### POST `/score/demo`
**Endpoint investisseurs** — Génère des données synthétiques réalistes et retourne un scoring complet.

```bash
curl -X POST http://localhost:8000/score/demo \
  -H "Content-Type: application/json" \
  -d '{
    "archetype": "underrepresented_founder",
    "months": 6,
    "monthly_revenue": 15000,
    "currency": "USD"
  }'
```

**Archétypes disponibles :**
| Archetype | Description | Risque typique |
|-----------|-------------|----------------|
| `healthy_growth` | PME en croissance stable | Faible |
| `seasonal_business` | Forte saisonnalité | Modéré |
| `early_stage` | Jeune entreprise | Élevé |
| `stressed_cashflow` | Flux sous tension | Très élevé |
| `underrepresented_founder` | Bon flux, sans historique formel | **Faible–Modéré** ← cas d'usage clé |

---

### POST `/score`
**Endpoint principal** — Accepte de vraies données Open Banking (format Plaid/Tink).

```bash
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "SME-001",
    "company_name": "Dupont & Co SAS",
    "currency": "EUR",
    "requested_loan_amount": 50000,
    "loan_duration_months": 24,
    "transactions": [
      {
        "transaction_id": "txn_001",
        "date": "2025-10-01",
        "amount": 18500.00,
        "currency": "EUR",
        "category": "client_payment",
        "merchant_name": "Client A",
        "transaction_type": "credit",
        "pending": false
      },
      {
        "transaction_id": "txn_002",
        "date": "2025-10-05",
        "amount": -3200.00,
        "currency": "EUR",
        "category": "rent",
        "merchant_name": "Bailleur SCI",
        "transaction_type": "debit",
        "pending": false
      }
    ]
  }'
```

**Réponse type :**
```json
{
  "company_id": "SME-001",
  "score": 74.2,
  "risk_band": "LOW",
  "default_probability_90d": 0.0821,
  "recommendation": "APPROVE",
  "recommendation_reason": "Strong cash flow profile with low default probability.",
  "signals": [
    {
      "name": "Revenus mensuels moyens",
      "value": 18500.0,
      "weight": 0.20,
      "interpretation": "Revenu mensuel moyen de 18 500 — solide",
      "flag": "positive"
    }
  ],
  "avg_monthly_revenue": 18500.0,
  "recurring_revenue_ratio": 0.62,
  "cash_flow_volatility": 1840.5,
  "client_concentration_risk": 0.31,
  "avg_days_positive_balance": 26.4,
  "dscr": 1.84,
  "max_recommended_loan": 67200.0,
  "anomaly_flags": [],
  "round_trip_transactions_detected": false,
  "scored_at": "2025-11-15T09:32:14.201Z",
  "transactions_analyzed": 2,
  "date_range_days": 4,
  "processing_time_ms": 18.43,
  "model_version": "creditai-v1.0-mvp",
  "is_demo": false
}
```

---

## Lancer les tests

```bash
cd creditai-mvp
pytest tests/ -v
```

**Résultat attendu : 16/16 tests ✅**

```
tests/test_api.py::TestHealthEndpoint::test_health_returns_200           PASSED
tests/test_api.py::TestHealthEndpoint::test_health_model_loaded          PASSED
tests/test_api.py::TestDemoEndpoint::test_healthy_growth_archetype       PASSED
tests/test_api.py::TestDemoEndpoint::test_stressed_cashflow_archetype    PASSED
tests/test_api.py::TestDemoEndpoint::test_underrepresented_founder_fair  PASSED
tests/test_api.py::TestDemoEndpoint::test_all_archetypes_valid           PASSED
tests/test_api.py::TestDemoEndpoint::test_response_includes_signals      PASSED
tests/test_api.py::TestScoringEndpoint::test_full_scoring_valid_data     PASSED
tests/test_api.py::TestScoringEndpoint::test_score_below_minimum         PASSED
tests/test_api.py::TestScoringEndpoint::test_loan_capacity_computed      PASSED
tests/test_api.py::TestScoringEngine::test_engine_initializes            PASSED
tests/test_api.py::TestScoringEngine::test_score_range                   PASSED
tests/test_api.py::TestScoringEngine::test_healthy_higher_than_stressed  PASSED
tests/test_api.py::TestDataSimulator::test_generates_transactions        PASSED
tests/test_api.py::TestDataSimulator::test_all_archetypes_generate_data  PASSED
tests/test_api.py::TestDataSimulator::test_revenue_amounts_positive      PASSED
========================= 16 passed in 10.56s =================================
```

---

## Pipeline de scoring (architecture technique)

```
Transaction JSON (Plaid/Tink format)
          │
          ▼
  FeatureEngineer.extract()
  ├── Revenus : avg_monthly_revenue, growth_rate, recurring_ratio
  ├── Stabilité : volatility, net_flow, negative_months
  ├── Risque : concentration, burn_rate, largest_outflow
  ├── Comportement : frequency, payment_regularity
  └── Fraude : round_trip_score, suspicious_patterns
          │
          ▼ (15 features normalisées)
  GradientBoostingClassifier
  (entraîné sur 5 000 profils PME synthétiques)
          │
          ▼
  default_probability_90d ∈ [0, 1]
          │
          ▼
  Score 0–100 + ajustements (boosters / pénalités)
          │
          ▼
  ScoringResponse (JSON)
  ├── score, risk_band, recommendation
  ├── signals[] (explainability)
  ├── anomaly_flags[]
  └── dscr, max_recommended_loan
```

---

## Variables d'environnement (production)

```env
# .env
CREDITAI_ENV=production
CREDITAI_API_KEY=your_api_key_here
PLAID_CLIENT_ID=your_plaid_client_id
PLAID_SECRET=your_plaid_secret
TINK_CLIENT_ID=your_tink_client_id
TINK_CLIENT_SECRET=your_tink_client_secret
DATABASE_URL=postgresql://user:password@localhost/creditai
REDIS_URL=redis://localhost:6379
```

---

## Roadmap technique

| Phase | Période | Objectif |
|-------|---------|---------|
| **MVP actuel** | Now | API FastAPI + modèle GBM + données synthétiques |
| **Pilote v1** | Q3 2026 | Intégration Plaid live (USA) + 3 clients pilotes |
| **Pilote v2** | Q4 2026 | Intégration Tink (UE) + réentraînement sur vraies données |
| **Production** | Q1 2027 | Auth API Key, rate limiting, monitoring, SLA 99.9% |

---

## Stack technique complète (production future)

```
Backend    : FastAPI (Python 3.12)
ML         : Scikit-learn → XGBoost (v2)
Data       : PostgreSQL + Redis (cache scoring)
Open Banking: Plaid (USA) + Tink (UE)
Auth       : API Key + JWT
Infra      : AWS/GCP + Docker + Kubernetes
Monitoring : Prometheus + Grafana
CI/CD      : GitHub Actions
```

---

## Contact équipe fondatrice

**CreditAI — Pre-Seed 2025–2026**
Confidentiel — Usage investisseurs uniquement

*"Nous développons l'infrastructure d'IA qui permet aux plateformes de prêt d'accepter jusqu'à 30% de clients supplémentaires tout en réduisant leurs taux de défaut."*
