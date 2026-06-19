"""
CreditAI — Scoring Engine
Modèle ML de scoring de crédit + logique de recommandation.

Architecture du modèle (MVP) :
  - Algorithme : GradientBoostingClassifier (scikit-learn)
  - Entraînement : Données synthétiques réalistes (5 000 profils PME simulés)
  - Features : 15 features de trésorerie extraites par FeatureEngineer
  - Output  : Probabilité de défaut à 90 jours → score 0–100 (inversé)

Note pour les investisseurs :
  Ce MVP utilise des données d'entraînement simulées pour la démo.
  En phase pilote, le modèle sera réentraîné sur de vraies données Open Banking
  fournies par les partenaires prêteurs (avec consentement des PME).
"""

import numpy as np
import time
from datetime import datetime
from typing import List

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler

from app.models.schemas import (
    ScoringRequest,
    ScoringResponse,
    ScoreSignal,
    RiskBand,
)
from app.services.feature_engineering import FeatureEngineer


# ── Feature names (must match FeatureEngineer output order) ───────────────────

FEATURE_NAMES = [
    "avg_monthly_revenue",
    "revenue_growth_rate",
    "recurring_revenue_ratio",
    "cash_flow_volatility",
    "avg_monthly_net_flow",
    "months_negative_balance",
    "client_concentration_risk",
    "burn_rate_ratio",
    "largest_outflow_ratio",
    "transaction_frequency",
    "payment_regularity_score",
    "round_trip_score",
    "suspicious_pattern_count",
    "history_months_normalized",
    "payment_regularity_score",  # used twice intentionally as proxy for missing feature
]

# ── Signal weights (used for explainability breakdown) ────────────────────────

SIGNAL_WEIGHTS = {
    "Revenus mensuels moyens":         0.20,
    "Stabilité des flux de trésorerie":0.18,
    "Taux de revenus récurrents":      0.15,
    "Régularité des paiements":        0.14,
    "Taux de combustion (burn rate)":  0.12,
    "Concentration client":            0.10,
    "Historique disponible":           0.06,
    "Signaux de fraude":               0.05,
}


class ScoringEngine:
    """
    Main scoring engine. Trains a GBM model on synthetic data at startup,
    then uses it for real-time scoring.
    """

    MODEL_VERSION = "creditai-v1.0-mvp"

    def __init__(self):
        self.feature_engineer = FeatureEngineer()
        self.model = None
        self.scaler = StandardScaler()
        self._ready = False
        self._train()

    def is_ready(self) -> bool:
        return self._ready

    def score(self, request: ScoringRequest) -> ScoringResponse:
        """Run full scoring pipeline on a ScoringRequest."""
        start_time = time.time()

        if not self._ready:
            raise RuntimeError("Scoring model not initialized")

        # 1. Extract features
        features, metadata = self.feature_engineer.extract(request.transactions)

        # 2. Build feature vector
        feature_vector = self._build_vector(features)

        # 3. Scale + predict
        X = self.scaler.transform([feature_vector])
        default_prob = float(self.model.predict_proba(X)[0][1])

        # 4. Convert to score (0-100, higher = better)
        score = self._prob_to_score(default_prob, features)

        # 5. Risk band
        risk_band = self._score_to_band(score)

        # 6. Recommendation
        recommendation, reason = self._recommend(score, default_prob, metadata)

        # 7. Signals breakdown (explainability)
        signals = self._build_signals(features, score)

        # 8. Loan capacity (if requested)
        dscr, max_loan = self._compute_loan_capacity(
            features,
            request.requested_loan_amount,
            request.loan_duration_months,
        )

        processing_ms = (time.time() - start_time) * 1000

        return ScoringResponse(
            company_id=request.company_id,
            score=round(score, 1),
            risk_band=risk_band,
            default_probability_90d=round(default_prob, 4),
            recommendation=recommendation,
            recommendation_reason=reason,
            signals=signals,
            avg_monthly_revenue=metadata.get("avg_monthly_revenue", 0.0),
            revenue_growth_rate=metadata.get("revenue_growth_rate"),
            cash_flow_volatility=metadata.get("cash_flow_volatility", 0.0),
            recurring_revenue_ratio=features.get("recurring_revenue_ratio", 0.0),
            client_concentration_risk=features.get("client_concentration_risk", 0.0),
            avg_days_positive_balance=metadata.get("avg_days_positive_balance", 0.0),
            anomaly_flags=metadata.get("anomaly_flags", []),
            round_trip_transactions_detected=metadata.get("round_trip_transactions_detected", False),
            dscr=dscr,
            max_recommended_loan=max_loan,
            scored_at=datetime.utcnow().isoformat(),
            transactions_analyzed=len(request.transactions),
            date_range_days=metadata.get("date_range_days", 0),
            processing_time_ms=round(processing_ms, 2),
            model_version=self.MODEL_VERSION,
        )

    # ── Private methods ───────────────────────────────────────────────────────

    def _train(self):
        """
        Train GBM model on synthetic SME profiles.
        In production: replace with real labeled data from lending partners.
        """
        np.random.seed(42)
        n_samples = 5000

        # Generate synthetic training data
        X_train, y_train = self._generate_training_data(n_samples)

        # Scale features
        X_scaled = self.scaler.fit_transform(X_train)

        # Train GBM
        self.model = GradientBoostingClassifier(
            n_estimators=150,
            learning_rate=0.08,
            max_depth=4,
            min_samples_split=20,
            subsample=0.85,
            random_state=42,
        )
        self.model.fit(X_scaled, y_train)
        self._ready = True

    def _generate_training_data(self, n: int):
        """
        Generate realistic synthetic training data for 5 SME archetypes.
        Default rate (~15%) reflects real-world SME lending benchmarks.
        """
        X, y = [], []

        profiles = [
            # (archetype_name, default_rate, feature_means, feature_stds)
            ("healthy",      0.03, [25000, 0.08, 0.65, 0.2, 0.6, 0.1, 0.25, 0.75, 0.3, 0.7, 0.8, 0.02, 0.05, 0.8, 0.8], 0.12),
            ("seasonal",     0.12, [18000, 0.02, 0.40, 0.6, 0.3, 0.3, 0.35, 0.95, 0.5, 0.5, 0.6, 0.05, 0.08, 0.6, 0.6], 0.18),
            ("early_stage",  0.22, [8000,  0.15, 0.30, 0.8, 0.2, 0.4, 0.50, 1.10, 0.6, 0.4, 0.5, 0.03, 0.06, 0.3, 0.5], 0.20),
            ("stressed",     0.55, [12000,-0.05, 0.20, 1.2,-0.2, 0.6, 0.60, 1.40, 0.8, 0.3, 0.3, 0.15, 0.20, 0.5, 0.3], 0.22),
            ("underrep",     0.08, [15000, 0.05, 0.55, 0.3, 0.5, 0.1, 0.30, 0.80, 0.3, 0.6, 0.75, 0.01, 0.02, 0.4, 0.75], 0.14),
        ]

        per_profile = n // len(profiles)
        for _, default_rate, means, noise in profiles:
            for _ in range(per_profile):
                features = [
                    max(0, means[i] + np.random.normal(0, abs(means[i]) * noise + 0.01))
                    for i in range(15)
                ]
                # Clip normalized features to [0, 1]
                for j in [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]:
                    features[j] = float(np.clip(features[j], 0, max(1, abs(means[j]) * 3)))
                X.append(features)
                y.append(1 if np.random.random() < default_rate else 0)

        return np.array(X), np.array(y)

    def _build_vector(self, features: dict) -> List[float]:
        """Build ordered feature vector matching training data structure."""
        return [
            features.get("avg_monthly_revenue", 0) / 50000,  # Normalize revenue
            features.get("revenue_growth_rate", 0),
            features.get("recurring_revenue_ratio", 0),
            features.get("cash_flow_volatility", 1),
            features.get("avg_monthly_net_flow", 0),
            features.get("months_negative_balance", 0.5),
            features.get("client_concentration_risk", 0.5),
            features.get("burn_rate_ratio", 1),
            features.get("largest_outflow_ratio", 0.5),
            features.get("transaction_frequency", 0.5),
            features.get("payment_regularity_score", 0.5),
            features.get("round_trip_score", 0),
            features.get("suspicious_pattern_count", 0),
            features.get("history_months_normalized", 0.5),
            features.get("payment_regularity_score", 0.5),
        ]

    def _prob_to_score(self, default_prob: float, features: dict) -> float:
        """
        Convert default probability to a 0–100 score.
        Base: 100 * (1 - default_prob), then adjusted by positive signals.
        """
        base_score = 100 * (1 - default_prob)

        # Positive boosters (max +5 each)
        boosts = 0.0
        if features.get("recurring_revenue_ratio", 0) > 0.6:
            boosts += 4.0
        if features.get("revenue_growth_rate", 0) > 0.05:
            boosts += 3.0
        if features.get("payment_regularity_score", 0) > 0.75:
            boosts += 3.0

        # Penalties
        penalties = 0.0
        if features.get("round_trip_score", 0) > 0.1:
            penalties += 8.0
        if features.get("months_negative_balance", 0) > 0.4:
            penalties += 5.0
        if features.get("client_concentration_risk", 0) > 0.7:
            penalties += 4.0

        return float(np.clip(base_score + boosts - penalties, 0, 100))

    def _score_to_band(self, score: float) -> RiskBand:
        if score >= 80:  return RiskBand.VERY_LOW
        if score >= 65:  return RiskBand.LOW
        if score >= 50:  return RiskBand.MODERATE
        if score >= 35:  return RiskBand.HIGH
        return RiskBand.VERY_HIGH

    def _recommend(self, score: float, prob: float, metadata: dict):
        if score >= 70:
            return "APPROVE", "Strong cash flow profile with low default probability. Recommend proceeding with standard loan terms."
        elif score >= 55:
            return "REVIEW", "Moderate risk profile. Recommend manual review of cash flow seasonality and client concentration before approval."
        elif score >= 40:
            return "CONDITIONAL", "Elevated risk signals detected. Consider reduced loan amount, shorter duration, or additional guarantees."
        else:
            return "DECLINE", "High default probability based on cash flow analysis. Significant negative patterns detected."

    def _build_signals(self, features: dict, score: float) -> list:
        """Build explainability signal breakdown."""
        signals = []

        rev = features.get("avg_monthly_revenue", 0) * 50000  # De-normalize
        signals.append(ScoreSignal(
            name="Revenus mensuels moyens",
            value=round(rev, 0),
            weight=0.20,
            interpretation=f"Revenu mensuel moyen de {rev:,.0f} — {'solide' if rev > 15000 else 'faible'}",
            flag="positive" if rev > 15000 else "warning",
        ))

        vol = features.get("cash_flow_volatility", 1)
        signals.append(ScoreSignal(
            name="Stabilité des flux de trésorerie",
            value=round(vol, 3),
            weight=0.18,
            interpretation=f"Volatilité {'faible ✓' if vol < 0.4 else 'élevée — flux irréguliers'}",
            flag="positive" if vol < 0.4 else ("warning" if vol < 0.8 else "critical"),
        ))

        rec = features.get("recurring_revenue_ratio", 0)
        signals.append(ScoreSignal(
            name="Taux de revenus récurrents",
            value=round(rec * 100, 1),
            weight=0.15,
            interpretation=f"{round(rec*100,1)}% des revenus sont récurrents — {'prédictibilité élevée ✓' if rec > 0.5 else 'revenus peu prévisibles'}",
            flag="positive" if rec > 0.5 else "warning",
        ))

        reg = features.get("payment_regularity_score", 0.5)
        signals.append(ScoreSignal(
            name="Régularité des paiements",
            value=round(reg * 100, 1),
            weight=0.14,
            interpretation=f"Score de régularité : {round(reg*100,1)}/100",
            flag="positive" if reg > 0.65 else "warning",
        ))

        burn = features.get("burn_rate_ratio", 1)
        signals.append(ScoreSignal(
            name="Taux de combustion (burn rate)",
            value=round(burn, 2),
            weight=0.12,
            interpretation=f"Ratio dépenses/revenus : {round(burn*100,0)}% — {'sain' if burn < 0.9 else 'attention: dépenses élevées'}",
            flag="positive" if burn < 0.85 else ("warning" if burn < 1.1 else "critical"),
        ))

        conc = features.get("client_concentration_risk", 0.5)
        signals.append(ScoreSignal(
            name="Concentration client",
            value=round(conc * 100, 1),
            weight=0.10,
            interpretation=f"{round(conc*100,1)}% des revenus proviennent d'un seul client — {'diversifié ✓' if conc < 0.5 else 'risque de concentration'}",
            flag="positive" if conc < 0.5 else ("warning" if conc < 0.7 else "critical"),
        ))

        hist = features.get("history_months_normalized", 0.5)
        signals.append(ScoreSignal(
            name="Historique disponible",
            value=round(hist * 12, 1),
            weight=0.06,
            interpretation=f"{round(hist*12,1)} mois d'historique analysés",
            flag="positive" if hist > 0.5 else "warning",
        ))

        fraud = features.get("round_trip_score", 0)
        signals.append(ScoreSignal(
            name="Signaux de fraude",
            value=round(fraud * 100, 1),
            weight=0.05,
            interpretation=f"Score de risque fraude : {round(fraud*100,1)}/100 — {'aucun signal détecté ✓' if fraud < 0.1 else 'transactions suspectes détectées'}",
            flag="positive" if fraud < 0.1 else "critical",
        ))

        return signals

    def _compute_loan_capacity(self, features, requested_amount, duration_months):
        """Estimate Debt Service Coverage Ratio and maximum loan capacity."""
        avg_net_normalized = features.get("avg_monthly_net_flow", 0)
        avg_revenue = features.get("avg_monthly_revenue", 0) * 50000

        # Estimate actual monthly net flow
        avg_net = avg_net_normalized * max(avg_revenue, 1)

        if avg_net <= 0 or not requested_amount or not duration_months:
            # Even without loan request, compute max recommended
            if avg_net > 0:
                max_monthly_payment = avg_net * 0.4  # 40% coverage rule
                # Simple annuity formula at 8% annual rate
                monthly_rate = 0.08 / 12
                if monthly_rate > 0:
                    max_loan = max_monthly_payment * (1 - (1 + monthly_rate)**(-36)) / monthly_rate
                else:
                    max_loan = max_monthly_payment * 36
                return None, round(max_loan, 0)
            return None, None

        # Monthly payment for requested loan (8% annual rate, simple)
        monthly_rate = 0.08 / 12
        monthly_payment = requested_amount * (monthly_rate * (1 + monthly_rate)**duration_months) / \
                          ((1 + monthly_rate)**duration_months - 1)

        dscr = avg_net / max(monthly_payment, 1)

        # Max loan (40% of net flow, 36-month horizon)
        max_monthly_payment = avg_net * 0.4
        if monthly_rate > 0:
            max_loan = max_monthly_payment * (1 - (1 + monthly_rate)**(-36)) / monthly_rate
        else:
            max_loan = max_monthly_payment * 36

        return round(dscr, 2), round(max_loan, 0)
