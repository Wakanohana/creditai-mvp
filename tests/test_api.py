"""
CreditAI MVP — Test Suite
Pytest tests for the scoring engine and API endpoints.

Run: pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from datetime import date, timedelta

# ── Add parent to path for imports ────────────────────────────────────────────
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.services.scoring_engine import ScoringEngine
from app.services.data_simulator import DataSimulator
from app.models.schemas import DemoArchetype, ScoringRequest, Transaction

client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine():
    return ScoringEngine()

@pytest.fixture(scope="module")
def simulator():
    return DataSimulator()

def make_transactions(n=20, start_days_ago=90):
    """Generate minimal valid transaction list for testing."""
    txns = []
    base = date.today() - timedelta(days=start_days_ago)
    for i in range(n):
        txns.append(Transaction(
            transaction_id=f"test_txn_{i:04d}",
            date=base + timedelta(days=i * (start_days_ago // n)),
            amount=5000.0 if i % 3 == 0 else -1500.0,
            currency="USD",
            category="client_payment" if i % 3 == 0 else "expense",
            merchant_name="Test Client" if i % 3 == 0 else "Test Supplier",
            transaction_type="credit" if i % 3 == 0 else "debit",
            pending=False,
        ))
    return txns


# ── API Endpoint Tests ────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_model_loaded(self):
        resp = client.get("/health")
        data = resp.json()
        assert data["model_loaded"] is True
        assert data["status"] == "healthy"


class TestDemoEndpoint:
    def test_healthy_growth_archetype(self):
        resp = client.post("/score/demo", json={
            "archetype": "healthy_growth",
            "months": 6,
            "monthly_revenue": 20000,
            "currency": "USD",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] > 40, "Healthy growth should score above stressed profiles"
        assert data["risk_band"] in ["VERY_LOW", "LOW", "MODERATE"]
        assert data["is_demo"] is True
        assert data["demo_archetype"] == "healthy_growth"

    def test_stressed_cashflow_archetype(self):
        resp = client.post("/score/demo", json={
            "archetype": "stressed_cashflow",
            "months": 6,
            "monthly_revenue": 15000,
            "currency": "USD",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] < 60, "Stressed cashflow should have lower score"
        assert data["risk_band"] in ["HIGH", "VERY_HIGH", "MODERATE"]

    def test_underrepresented_founder_gets_fair_score(self):
        """
        Key test: an underrepresented founder with good cash flow but
        no formal credit history should still get a reasonable score.
        This is the main value proposition vs traditional scoring.
        """
        resp = client.post("/score/demo", json={
            "archetype": "underrepresented_founder",
            "months": 6,
            "monthly_revenue": 15000,
            "currency": "USD",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] > 50, (
            "Underrepresented founder with good cashflow should score above 50 "
            "(traditional scoring would fail them due to lack of credit history)"
        )

    def test_all_archetypes_return_valid_response(self):
        archetypes = [a.value for a in DemoArchetype]
        for archetype in archetypes:
            resp = client.post("/score/demo", json={
                "archetype": archetype,
                "months": 3,
                "monthly_revenue": 10000,
            })
            assert resp.status_code == 200, f"Failed for archetype: {archetype}"
            data = resp.json()
            assert 0 <= data["score"] <= 100
            assert data["risk_band"] in ["VERY_LOW", "LOW", "MODERATE", "HIGH", "VERY_HIGH"]
            assert len(data["signals"]) > 0
            assert data["processing_time_ms"] < 5000, "Scoring should complete in < 5 seconds"

    def test_response_includes_signals(self):
        resp = client.post("/score/demo", json={"archetype": "healthy_growth"})
        data = resp.json()
        assert "signals" in data
        assert len(data["signals"]) >= 5
        for signal in data["signals"]:
            assert "name" in signal
            assert "value" in signal
            assert "weight" in signal
            assert "interpretation" in signal


class TestScoringEndpoint:
    def test_full_scoring_with_valid_data(self):
        txns = [t.dict() for t in make_transactions(30)]
        # Convert dates to string
        for t in txns:
            t["date"] = str(t["date"])
        resp = client.post("/score", json={
            "company_id": "TEST-001",
            "company_name": "Test SME",
            "transactions": txns,
            "currency": "USD",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["company_id"] == "TEST-001"
        assert 0 <= data["score"] <= 100

    def test_score_below_minimum_transactions(self):
        txns = [t.dict() for t in make_transactions(3)]
        for t in txns:
            t["date"] = str(t["date"])
        resp = client.post("/score", json={
            "company_id": "TEST-MIN",
            "transactions": txns,
        })
        assert resp.status_code == 422

    def test_loan_capacity_computed_when_requested(self):
        txns = [t.dict() for t in make_transactions(30)]
        for t in txns:
            t["date"] = str(t["date"])
        resp = client.post("/score", json={
            "company_id": "TEST-LOAN",
            "transactions": txns,
            "requested_loan_amount": 50000,
            "loan_duration_months": 24,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["dscr"] is not None or data["max_recommended_loan"] is not None


# ── Unit Tests ────────────────────────────────────────────────────────────────

class TestScoringEngine:
    def test_engine_initializes(self, engine):
        assert engine.is_ready() is True

    def test_score_range(self, engine, simulator):
        txns = simulator.generate("healthy_growth", months=6, monthly_revenue=20000)
        req = ScoringRequest(
            company_id="UNIT-TEST",
            transactions=txns,
        )
        result = engine.score(req)
        assert 0 <= result.score <= 100
        assert 0 <= result.default_probability_90d <= 1

    def test_healthy_scores_higher_than_stressed(self, engine, simulator):
        healthy_txns = simulator.generate("healthy_growth", 6, 20000)
        stressed_txns = simulator.generate("stressed_cashflow", 6, 20000)

        healthy_req = ScoringRequest(company_id="H", transactions=healthy_txns)
        stressed_req = ScoringRequest(company_id="S", transactions=stressed_txns)

        healthy_result = engine.score(healthy_req)
        stressed_result = engine.score(stressed_req)

        assert healthy_result.score > stressed_result.score, (
            f"Healthy ({healthy_result.score}) should score higher than stressed ({stressed_result.score})"
        )


class TestDataSimulator:
    def test_generates_transactions(self, simulator):
        txns = simulator.generate("healthy_growth", months=3, monthly_revenue=15000)
        assert len(txns) > 0
        assert all(isinstance(t, Transaction) for t in txns)

    def test_all_archetypes_generate_data(self, simulator):
        for archetype in [a.value for a in DemoArchetype]:
            txns = simulator.generate(archetype, months=3, monthly_revenue=10000)
            assert len(txns) >= 5, f"Not enough transactions for {archetype}"

    def test_revenue_amounts_are_positive(self, simulator):
        txns = simulator.generate("healthy_growth", months=3, monthly_revenue=20000)
        credits = [t for t in txns if t.amount > 0]
        assert len(credits) > 0
        assert all(t.amount > 0 for t in credits)
