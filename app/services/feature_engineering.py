"""
CreditAI — Feature Engineering
Extrait les signaux de trésorerie depuis les transactions brutes Open Banking.

C'est le cœur analytique du MVP : transformer des lignes de transactions bancaires
en features numériques exploitables par le modèle ML.

Features calculées (15 au total) :
  Revenus     : avg_monthly_revenue, revenue_growth_rate, recurring_revenue_ratio
  Stabilité   : cash_flow_volatility, avg_monthly_net_flow, months_negative_balance
  Risque      : client_concentration_risk, largest_single_outflow_ratio
  Comportement: avg_days_positive_balance, transaction_frequency
  Fraude      : round_trip_score, suspicious_pattern_count
  Capacité    : burn_rate_ratio, runway_months, payment_regularity_score
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from datetime import date

from app.models.schemas import Transaction


class FeatureEngineer:
    """
    Transforms raw transaction lists into a feature vector for the scoring model.
    Designed to handle both Plaid (USD) and Tink (EUR) transaction formats.
    """

    # Recurring merchant keywords (heuristic for revenue stability detection)
    RECURRING_KEYWORDS = [
        "subscription", "saas", "monthly", "retainer", "recurring",
        "abonnement", "mensuel", "client", "invoice", "facture",
        "payment", "transfer", "virement", "stripe", "paypal",
    ]

    # Suspicious pattern keywords for basic fraud detection
    SUSPICIOUS_KEYWORDS = ["round", "cash", "atm", "withdrawal", "espèces"]

    def extract(self, transactions: List[Transaction]) -> Tuple[Dict[str, float], Dict[str, Any]]:
        """
        Main extraction method.

        Returns:
            features (dict): Numerical feature vector for ML model
            metadata (dict): Human-readable metrics for the API response
        """
        if not transactions:
            raise ValueError("No transactions provided")

        df = self._to_dataframe(transactions)

        if len(df) < 5:
            raise ValueError("Insufficient transaction history (minimum 5 transactions required)")

        monthly = self._aggregate_monthly(df)
        features = {}
        metadata = {}

        # ── Revenue features ─────────────────────────────────────────────────
        credits = df[df["amount"] > 0]
        monthly_credits = monthly["credits"]

        avg_monthly_revenue = float(monthly_credits.mean()) if len(monthly_credits) > 0 else 0.0
        features["avg_monthly_revenue"] = avg_monthly_revenue
        metadata["avg_monthly_revenue"] = round(avg_monthly_revenue, 2)

        # Revenue growth rate (MoM average)
        if len(monthly_credits) >= 2:
            growth_rates = monthly_credits.pct_change().dropna()
            growth_rate = float(growth_rates.mean())
            features["revenue_growth_rate"] = np.clip(growth_rate, -1.0, 5.0)
            metadata["revenue_growth_rate"] = round(growth_rate, 4)
        else:
            features["revenue_growth_rate"] = 0.0
            metadata["revenue_growth_rate"] = None

        # Recurring revenue ratio
        recurring_ratio = self._compute_recurring_ratio(credits)
        features["recurring_revenue_ratio"] = recurring_ratio
        metadata["recurring_revenue_ratio"] = round(recurring_ratio, 3)

        # ── Cash flow stability ───────────────────────────────────────────────
        monthly_net = monthly["net"]

        volatility = float(monthly_net.std()) if len(monthly_net) > 1 else 0.0
        # Normalize by average absolute revenue to get a relative volatility
        if avg_monthly_revenue > 0:
            features["cash_flow_volatility"] = min(volatility / avg_monthly_revenue, 5.0)
        else:
            features["cash_flow_volatility"] = 5.0
        metadata["cash_flow_volatility"] = round(float(volatility), 2)

        avg_net_flow = float(monthly_net.mean())
        features["avg_monthly_net_flow"] = np.clip(
            avg_net_flow / max(avg_monthly_revenue, 1), -2.0, 2.0
        )

        months_negative = int((monthly_net < 0).sum())
        features["months_negative_balance"] = months_negative / max(len(monthly_net), 1)
        metadata["avg_days_positive_balance"] = round(
            max(0, 30 * (1 - features["months_negative_balance"])), 1
        )

        # ── Client concentration risk ─────────────────────────────────────────
        if "merchant_name" in df.columns:
            top_client_pct = self._compute_concentration_risk(credits)
        else:
            top_client_pct = 0.3  # Assume moderate if no merchant data
        features["client_concentration_risk"] = top_client_pct
        metadata["client_concentration_risk"] = round(top_client_pct, 3)

        # ── Burn rate analysis ────────────────────────────────────────────────
        debits = df[df["amount"] < 0]
        avg_monthly_burn = float(monthly["debits"].abs().mean()) if len(monthly["debits"]) > 0 else 0.0

        if avg_monthly_revenue > 0:
            burn_ratio = avg_monthly_burn / avg_monthly_revenue
            features["burn_rate_ratio"] = min(burn_ratio, 3.0)
        else:
            features["burn_rate_ratio"] = 3.0

        # ── Largest single outflow ────────────────────────────────────────────
        if len(debits) > 0:
            largest_outflow = float(debits["amount"].abs().max())
            features["largest_outflow_ratio"] = min(
                largest_outflow / max(avg_monthly_revenue, 1), 3.0
            )
        else:
            features["largest_outflow_ratio"] = 0.0

        # ── Transaction frequency ─────────────────────────────────────────────
        date_range = (df["date"].max() - df["date"].min()).days
        if date_range > 0:
            freq = len(df) / (date_range / 30)
            features["transaction_frequency"] = min(freq / 50, 1.0)  # Normalize to 50 txn/month
        else:
            features["transaction_frequency"] = 0.1
        metadata["date_range_days"] = date_range

        # ── Payment regularity ────────────────────────────────────────────────
        features["payment_regularity_score"] = self._compute_payment_regularity(df)

        # ── Fraud / anomaly signals ───────────────────────────────────────────
        round_trip_score, round_trip_detected = self._detect_round_trips(df)
        features["round_trip_score"] = round_trip_score
        metadata["round_trip_transactions_detected"] = round_trip_detected

        suspicious_count = self._count_suspicious_patterns(df)
        features["suspicious_pattern_count"] = min(suspicious_count / 10, 1.0)

        anomaly_flags = []
        if round_trip_detected:
            anomaly_flags.append("Round-trip transactions detected — manual review recommended")
        if months_negative > len(monthly_net) * 0.3:
            anomaly_flags.append(f"Negative cash flow in {months_negative} of {len(monthly_net)} months")
        if top_client_pct > 0.7:
            anomaly_flags.append(f"High client concentration: {round(top_client_pct*100)}% of revenue from single source")
        if features["burn_rate_ratio"] > 1.2:
            anomaly_flags.append("Burn rate exceeds revenue — unsustainable spending pattern")
        metadata["anomaly_flags"] = anomaly_flags

        # ── History length (proxy for business maturity) ─────────────────────
        history_months = max(1, date_range / 30)
        features["history_months_normalized"] = min(history_months / 12, 1.0)

        return features, metadata

    # ── Private helpers ───────────────────────────────────────────────────────

    def _to_dataframe(self, transactions: List[Transaction]) -> pd.DataFrame:
        """Convert transaction list to pandas DataFrame."""
        records = []
        for txn in transactions:
            records.append({
                "transaction_id": txn.transaction_id,
                "date": pd.to_datetime(txn.date),
                "amount": txn.amount,
                "currency": txn.currency,
                "category": txn.category or "",
                "merchant_name": txn.merchant_name or "",
                "transaction_type": txn.transaction_type,
                "pending": txn.pending,
            })
        df = pd.DataFrame(records)
        df = df[~df["pending"]]  # Exclude pending transactions
        df = df.sort_values("date")
        return df

    def _aggregate_monthly(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate transactions by month."""
        df = df.copy()
        df["month"] = df["date"].dt.to_period("M")

        monthly = df.groupby("month").apply(
            lambda x: pd.Series({
                "credits": x[x["amount"] > 0]["amount"].sum(),
                "debits":  x[x["amount"] < 0]["amount"].sum(),
                "net":     x["amount"].sum(),
                "count":   len(x),
            })
        )
        return monthly

    def _compute_recurring_ratio(self, credits_df: pd.DataFrame) -> float:
        """
        Estimate what fraction of revenue comes from recurring sources.
        Uses merchant name keyword matching and payment regularity.
        """
        if len(credits_df) == 0:
            return 0.0

        total_credits = credits_df["amount"].sum()
        if total_credits == 0:
            return 0.0

        recurring_credits = credits_df[
            credits_df["merchant_name"].str.lower().str.contains(
                "|".join(self.RECURRING_KEYWORDS), na=False
            ) |
            credits_df["category"].str.lower().str.contains(
                "|".join(self.RECURRING_KEYWORDS), na=False
            )
        ]["amount"].sum()

        # If no merchant data, estimate from amount regularity
        if recurring_credits == 0 and "merchant_name" in credits_df.columns:
            amount_counts = credits_df["amount"].round(-1).value_counts()
            if len(amount_counts) > 0:
                top_recurring = amount_counts[amount_counts > 1].sum()
                return min(top_recurring / len(credits_df), 1.0)

        return min(float(recurring_credits / total_credits), 1.0)

    def _compute_concentration_risk(self, credits_df: pd.DataFrame) -> float:
        """Herfindahl-Hirschman style client concentration."""
        if len(credits_df) == 0 or credits_df["merchant_name"].isna().all():
            return 0.3

        by_client = credits_df.groupby("merchant_name")["amount"].sum()
        total = by_client.sum()
        if total == 0:
            return 0.3

        top_share = float(by_client.max() / total)
        return top_share

    def _detect_round_trips(self, df: pd.DataFrame) -> Tuple[float, bool]:
        """
        Detect suspicious fund round-trips:
        Near-identical amounts going in and out within short windows.
        """
        if len(df) < 4:
            return 0.0, False

        credits = df[df["amount"] > 0]["amount"].values
        debits  = df[df["amount"] < 0]["amount"].abs().values

        suspicious_count = 0
        for c in credits:
            # Check if very similar amount exits within ±5%
            matches = [d for d in debits if abs(d - c) / max(c, 1) < 0.05]
            if matches:
                suspicious_count += 1

        ratio = suspicious_count / max(len(credits), 1)
        detected = ratio > 0.15  # >15% of credits have matching debits

        return min(ratio, 1.0), detected

    def _count_suspicious_patterns(self, df: pd.DataFrame) -> int:
        """Count transactions matching suspicious keyword patterns."""
        suspicious = df[
            df["merchant_name"].str.lower().str.contains(
                "|".join(self.SUSPICIOUS_KEYWORDS), na=False
            )
        ]
        return len(suspicious)

    def _compute_payment_regularity(self, df: pd.DataFrame) -> float:
        """
        Score the regularity of incoming payments (0 = chaotic, 1 = very regular).
        Uses coefficient of variation of inter-payment intervals.
        """
        credits = df[df["amount"] > 0].sort_values("date")
        if len(credits) < 3:
            return 0.5

        intervals = credits["date"].diff().dt.days.dropna()
        if intervals.std() == 0:
            return 1.0

        cv = intervals.std() / max(intervals.mean(), 1)
        # Lower CV = more regular = higher score
        return float(np.clip(1 / (1 + cv), 0, 1))
