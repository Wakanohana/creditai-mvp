"""
CreditAI — Schémas Pydantic v2 (validation des données entrantes/sortantes)
Compatible Plaid (USA) et Tink (EU) transaction formats.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional, Literal
from datetime import date
from enum import Enum


class RiskBand(str, Enum):
    VERY_LOW  = "VERY_LOW"
    LOW       = "LOW"
    MODERATE  = "MODERATE"
    HIGH      = "HIGH"
    VERY_HIGH = "VERY_HIGH"

class DemoArchetype(str, Enum):
    HEALTHY_GROWTH           = "healthy_growth"
    SEASONAL_BUSINESS        = "seasonal_business"
    EARLY_STAGE              = "early_stage"
    STRESSED_CASHFLOW        = "stressed_cashflow"
    UNDERREPRESENTED_FOUNDER = "underrepresented_founder"

class TransactionType(str, Enum):
    CREDIT = "credit"
    DEBIT  = "debit"


class Transaction(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    transaction_id:   str
    date:             date
    amount:           float
    currency:         str = "USD"
    category:         Optional[str] = None
    merchant_name:    Optional[str] = None
    transaction_type: TransactionType = TransactionType.DEBIT
    pending:          bool = False


class ScoringRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "company_id": "SME-001",
                "company_name": "Dupont & Co",
                "currency": "EUR",
                "transactions": []
            }
        }
    )

    company_id:             str
    company_name:           Optional[str] = None
    transactions:           List[Transaction]
    currency:               str = "USD"
    requested_loan_amount:  Optional[float] = None
    loan_duration_months:   Optional[int] = None

    @field_validator("transactions")
    @classmethod
    def validate_min_transactions(cls, v):
        if len(v) < 5:
            raise ValueError("At least 5 transactions required.")
        return v


class DemoScoringRequest(BaseModel):
    archetype:       DemoArchetype = DemoArchetype.HEALTHY_GROWTH
    months:          int = Field(default=6, ge=1, le=12)
    monthly_revenue: float = Field(default=20000.0, gt=0)
    currency:        str = "USD"


class ScoreSignal(BaseModel):
    name:           str
    value:          float
    weight:         float
    interpretation: str
    flag:           Optional[str] = None


class ScoringResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    company_id:                      str
    score:                           float = Field(..., ge=0, le=100)
    risk_band:                       RiskBand
    default_probability_90d:         float = Field(..., ge=0, le=1)
    recommendation:                  str
    recommendation_reason:           str
    signals:                         List[ScoreSignal]
    avg_monthly_revenue:             float
    revenue_growth_rate:             Optional[float] = None
    cash_flow_volatility:            float
    recurring_revenue_ratio:         float
    client_concentration_risk:       float
    avg_days_positive_balance:       float
    anomaly_flags:                   List[str] = Field(default_factory=list)
    round_trip_transactions_detected: bool = False
    dscr:                            Optional[float] = None
    max_recommended_loan:            Optional[float] = None
    scored_at:                       str
    transactions_analyzed:           int
    date_range_days:                 int
    processing_time_ms:              float
    model_version:                   str = "creditai-v1.0-mvp"
    is_demo:                         bool = False
    demo_archetype:                  Optional[str] = None


class HealthResponse(BaseModel):
    status:       str
    version:      str
    model_loaded: bool
    timestamp:    str
    message:      str
