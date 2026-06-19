"""
CreditAI — Data Simulator
Génère des données de transactions bancaires synthétiques réalistes
pour la démo investisseurs et les tests pilotes.

5 archétypes de PME :
  healthy_growth          — PME en croissance stable, faible risque
  seasonal_business       — Forte saisonnalité (ex: tourisme, retail)
  early_stage             — Jeune entreprise, historique mince
  stressed_cashflow       — Retards de paiement, risque élevé
  underrepresented_founder— Bon flux mais pas d'historique bancaire formel
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import List
import random
import string

from app.models.schemas import Transaction, TransactionType, DemoArchetype


class DataSimulator:
    """Generate realistic synthetic bank transaction data for SME archetypes."""

    def generate(
        self,
        archetype: str,
        months: int = 6,
        monthly_revenue: float = 20000.0,
    ) -> List[Transaction]:
        """
        Generate a list of synthetic transactions for the given archetype.
        """
        np.random.seed(hash(archetype + str(months)) % 2**31)
        random.seed(hash(archetype + str(months)) % 2**31)

        end_date = date.today()
        start_date = end_date - timedelta(days=30 * months)

        transactions = []
        current_date = start_date

        config = self._get_archetype_config(archetype, monthly_revenue)

        month_num = 0
        while current_date < end_date:
            # Monthly revenue (with archetype-specific variation)
            monthly_rev = self._compute_monthly_revenue(
                config, month_num, monthly_revenue
            )
            # Generate this month's transactions
            month_txns = self._generate_month_transactions(
                config, current_date, monthly_rev, month_num
            )
            transactions.extend(month_txns)

            # Move to next month
            current_date = current_date + timedelta(days=30)
            month_num += 1

        # Sort by date
        transactions.sort(key=lambda t: t.date)
        return transactions

    # ── Archetype configs ─────────────────────────────────────────────────────

    def _get_archetype_config(self, archetype: str, base_revenue: float) -> dict:
        configs = {
            DemoArchetype.HEALTHY_GROWTH: {
                "revenue_volatility": 0.08,
                "growth_rate": 0.04,             # 4% MoM
                "expense_ratio": 0.72,            # Expenses are 72% of revenue
                "recurring_client_ratio": 0.70,   # 70% recurring clients
                "n_clients": 8,
                "client_concentration": 0.28,     # Top client = 28% of revenue
                "payment_regularity": 0.90,
                "extra_txn_per_month": 5,
                "fraud_probability": 0.0,
                "negative_month_probability": 0.05,
                "clients": [
                    ("Acme Corp", 0.28), ("Beta Ltd", 0.18), ("Gamma Inc", 0.14),
                    ("Delta Partners", 0.12), ("Other clients", 0.28),
                ],
                "expense_categories": [
                    ("Salaries", 0.45), ("Office rent", 0.12), ("Software subscriptions", 0.08),
                    ("Marketing", 0.10), ("Suppliers", 0.15), ("Misc expenses", 0.10),
                ],
            },
            DemoArchetype.SEASONAL_BUSINESS: {
                "revenue_volatility": 0.20,
                "growth_rate": 0.01,
                "expense_ratio": 0.82,
                "recurring_client_ratio": 0.30,
                "n_clients": 15,
                "client_concentration": 0.20,
                "payment_regularity": 0.65,
                "extra_txn_per_month": 8,
                "fraud_probability": 0.0,
                "negative_month_probability": 0.25,
                "seasonal_peaks": [6, 7, 8, 12],  # Summer + December
                "clients": [
                    ("Tourist Group A", 0.20), ("Event Agency", 0.15), ("Walk-ins", 0.40),
                    ("Corporate", 0.15), ("Online bookings", 0.10),
                ],
                "expense_categories": [
                    ("Staff (seasonal)", 0.40), ("Inventory", 0.25), ("Rent", 0.15),
                    ("Marketing", 0.12), ("Misc", 0.08),
                ],
            },
            DemoArchetype.EARLY_STAGE: {
                "revenue_volatility": 0.35,
                "growth_rate": 0.10,
                "expense_ratio": 1.05,
                "recurring_client_ratio": 0.25,
                "n_clients": 3,
                "client_concentration": 0.55,
                "payment_regularity": 0.50,
                "extra_txn_per_month": 3,
                "fraud_probability": 0.0,
                "negative_month_probability": 0.40,
                "clients": [
                    ("First Client", 0.55), ("Second Client", 0.30), ("Trial User", 0.15),
                ],
                "expense_categories": [
                    ("Founder salary", 0.35), ("Cloud infra", 0.20), ("Legal & admin", 0.25),
                    ("Marketing", 0.15), ("Other", 0.05),
                ],
            },
            DemoArchetype.STRESSED_CASHFLOW: {
                "revenue_volatility": 0.30,
                "growth_rate": -0.03,
                "expense_ratio": 1.15,
                "recurring_client_ratio": 0.20,
                "n_clients": 4,
                "client_concentration": 0.65,
                "payment_regularity": 0.30,
                "extra_txn_per_month": 4,
                "fraud_probability": 0.0,
                "negative_month_probability": 0.60,
                "payment_delays_days": 25,
                "clients": [
                    ("Dominant Client", 0.65), ("Sporadic Client A", 0.20),
                    ("Sporadic Client B", 0.10), ("One-time", 0.05),
                ],
                "expense_categories": [
                    ("Salaries (late)", 0.40), ("Rent", 0.18), ("Overdue suppliers", 0.25),
                    ("Bank charges", 0.08), ("Misc", 0.09),
                ],
            },
            DemoArchetype.UNDERREPRESENTED_FOUNDER: {
                "revenue_volatility": 0.12,
                "growth_rate": 0.06,
                "expense_ratio": 0.78,
                "recurring_client_ratio": 0.55,
                "n_clients": 6,
                "client_concentration": 0.32,
                "payment_regularity": 0.82,
                "extra_txn_per_month": 4,
                "fraud_probability": 0.0,
                "negative_month_probability": 0.08,
                "no_formal_credit_history": True,
                "clients": [
                    ("Community Partner", 0.32), ("Local Business A", 0.22),
                    ("Online Sales", 0.18), ("Consulting Client", 0.15), ("Other", 0.13),
                ],
                "expense_categories": [
                    ("Salaries", 0.42), ("Rent (co-working)", 0.10), ("Suppliers", 0.20),
                    ("Equipment", 0.15), ("Misc", 0.13),
                ],
            },
        }
        return configs.get(archetype, configs[DemoArchetype.HEALTHY_GROWTH])

    # ── Transaction generation ────────────────────────────────────────────────

    def _compute_monthly_revenue(self, config: dict, month_num: int, base: float) -> float:
        """Compute monthly revenue with growth, volatility, and seasonality."""
        growth = (1 + config.get("growth_rate", 0)) ** month_num
        noise = np.random.normal(1.0, config.get("revenue_volatility", 0.1))

        # Seasonal adjustment
        if "seasonal_peaks" in config:
            current_month = (date.today().month - month_num % 12) % 12 + 1
            if current_month in config["seasonal_peaks"]:
                noise *= np.random.uniform(1.8, 2.5)
            elif current_month in [1, 2]:  # Off-season
                noise *= np.random.uniform(0.3, 0.6)

        return max(0, base * growth * noise)

    def _generate_month_transactions(
        self, config: dict, month_start: date, monthly_rev: float, month_num: int
    ) -> List[Transaction]:
        """Generate all transactions for a single month."""
        transactions = []

        # ── CREDITS (revenue) ────────────────────────────────────────────────
        clients = config.get("clients", [("Client", 1.0)])

        for client_name, share in clients:
            if client_name == "Other clients" or client_name.startswith("Other"):
                # Multiple small payments
                n_small = random.randint(2, 5)
                for _ in range(n_small):
                    amount = (monthly_rev * share / n_small) * np.random.uniform(0.7, 1.3)
                    day_offset = random.randint(1, 28)
                    transactions.append(Transaction(
                        transaction_id=self._txn_id(),
                        date=month_start + timedelta(days=day_offset),
                        amount=round(amount, 2),
                        currency="USD",
                        category="client_payment",
                        merchant_name=f"Client-{random.randint(100,999)}",
                        transaction_type=TransactionType.CREDIT,
                        pending=False,
                    ))
            else:
                # Main client payments (with possible delays)
                amount = monthly_rev * share * np.random.uniform(0.85, 1.15)
                if config.get("payment_delays_days", 0) > 0:
                    day_offset = random.randint(
                        config["payment_delays_days"] - 5,
                        config["payment_delays_days"] + 10
                    )
                else:
                    # Regular payments: around day 5-15 of month
                    regularity = config.get("payment_regularity", 0.7)
                    if random.random() < regularity:
                        day_offset = random.randint(5, 15)
                    else:
                        day_offset = random.randint(1, 28)

                day_offset = min(day_offset, 27)

                # Skip payment sometimes for stressed businesses
                skip_prob = 1 - config.get("payment_regularity", 0.9)
                if random.random() < skip_prob * 0.3:
                    continue

                transactions.append(Transaction(
                    transaction_id=self._txn_id(),
                    date=month_start + timedelta(days=day_offset),
                    amount=round(amount, 2),
                    currency="USD",
                    category="client_payment",
                    merchant_name=client_name,
                    transaction_type=TransactionType.CREDIT,
                    pending=False,
                ))

        # ── DEBITS (expenses) ─────────────────────────────────────────────────
        total_expenses = monthly_rev * config.get("expense_ratio", 0.8)
        expense_categories = config.get("expense_categories", [("Misc", 1.0)])

        for category, ratio in expense_categories:
            amount = total_expenses * ratio * np.random.uniform(0.9, 1.1)
            day_offset = random.randint(1, 28)
            transactions.append(Transaction(
                transaction_id=self._txn_id(),
                date=month_start + timedelta(days=day_offset),
                amount=round(-amount, 2),
                currency="USD",
                category=category.lower().replace(" ", "_"),
                merchant_name=category,
                transaction_type=TransactionType.DEBIT,
                pending=False,
            ))

        # ── EXTRA transactions (misc) ─────────────────────────────────────────
        n_extra = config.get("extra_txn_per_month", 3)
        for _ in range(n_extra):
            amount = random.uniform(50, 500)
            day_offset = random.randint(1, 28)
            transactions.append(Transaction(
                transaction_id=self._txn_id(),
                date=month_start + timedelta(days=day_offset),
                amount=round(-amount, 2),
                currency="USD",
                category="misc_expense",
                merchant_name=random.choice(["Amazon Business", "Office Depot", "Uber", "Restaurant", "Postage"]),
                transaction_type=TransactionType.DEBIT,
                pending=False,
            ))

        return transactions

    def _txn_id(self) -> str:
        """Generate a random transaction ID."""
        return "txn_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
