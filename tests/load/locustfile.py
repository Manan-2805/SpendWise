# tests/load/locustfile.py
"""
Locust Load Testing Script for SpendWise API.

Supports two concurrent user profiles:
1. SpendWiseStandardUser (Weight: 3): Performs transactional CRUD operations.
   - 70% probability: uses pre-seeded users (loadtest_user_1 to 100) to test
     concurrency on high-volume data.
   - 30% probability: registers a new dynamic user using Faker to test
     onboarding and fresh CRUD workflows.
2. SpendWiseReportHeavyUser (Weight: 1): Read-only dashboards querying summaries,
   breakdowns, and trends on the pre-seeded 10,000+ transactions.

Usage (Automated via Makefile):
  make load-test users=100 rate=10 time=60s
"""

import random
from datetime import date, timedelta
from typing import Any

from faker import Faker
from locust import HttpUser, between, task

fake = Faker()


class SpendWiseBaseUser(HttpUser):
    """Base class providing shared login, category loading, and utility logic."""

    abstract = True
    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.categories: list[dict[str, Any]] = []
        self.transactions: list[dict[str, Any]] = []
        self.auth_token: str = ""

        # Abstract method implemented by child classes
        self.authenticate_user()
        self.load_categories()

    def authenticate_user(self) -> None:
        raise NotImplementedError

    def load_categories(self) -> None:
        """Fetch categories available to the authenticated user."""
        with self.client.get("/api/v1/categories/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                self.categories = response.json()
            else:
                response.failure(f"Failed to load categories: {response.text}")

    def execute_login(self, email: str) -> bool:
        """Helper to login as a pre-seeded user (password: SecurePassword123!)."""
        payload = {"email": email, "password": "SecurePassword123!"}
        with self.client.post(
            "/api/v1/auth/login", json=payload, catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
                # Cookies are automatically stored in the HTTP client session
                return True
            else:
                response.failure(f"Login failed for {email}: {response.text}")
                return False


class SpendWiseStandardUser(SpendWiseBaseUser):
    """Standard transactional user creating categories and transactions."""

    weight = 3

    def authenticate_user(self) -> None:
        # 70% chance to act as an existing pre-seeded user, 30% chance to register a new user
        if random.random() < 0.70:
            user_idx = random.randint(1, 100)
            email = f"loadtest_user_{user_idx}@example.com"
            self.execute_login(email)
        else:
            # Register a new dynamic user
            email = f"loadtest_{fake.uuid4()[:8]}@example.com"
            username = f"user_{fake.uuid4()[:8]}"
            password = "SecurePassword123!"

            payload = {
                "email": email,
                "username": username,
                "password": password,
                "confirm_password": password,
            }
            with self.client.post(
                "/api/v1/auth/register", json=payload, catch_response=True
            ) as response:
                if response.status_code == 201:
                    response.success()
                else:
                    response.failure(f"Dynamic signup failed: {response.text}")

    # --- Categories Tasks ---

    @task(3)
    def list_categories(self) -> None:
        self.client.get("/api/v1/categories/")

    @task(1)
    def create_category(self) -> None:
        types = ["income", "expense", "both"]
        cat_payload = {
            "name": f"Cat_{fake.word()[:12]}_{random.randint(100, 999)}",
            "description": fake.sentence(nb_words=5),
            "icon": "food",
            "color": "#FF6B6B",
            "type": random.choice(types),
        }
        with self.client.post(
            "/api/v1/categories/", json=cat_payload, catch_response=True
        ) as response:
            if response.status_code == 201:
                response.success()
                self.categories.append(response.json())
            else:
                response.failure(f"Create category failed: {response.text}")

    # --- Transactions Tasks ---

    @task(15)
    def list_transactions(self) -> None:
        params = {
            "page": random.randint(1, 2),
            "per_page": 20,
            "sort_by": random.choice(["transaction_date", "amount"]),
            "sort_order": "desc",
        }
        self.client.get("/api/v1/transactions/", params=params)

    @task(10)
    def create_transaction(self) -> None:
        if not self.categories:
            return

        category = random.choice(self.categories)
        t_type = "expense" if category["type"] == "both" else category["type"]
        amount = round(random.uniform(5.0, 500.0), 2)
        payload = {
            "amount": str(amount),
            "description": f"Purchase {fake.word()}",
            "transaction_date": date.today().isoformat(),
            "category_id": category["id"],
            "type": t_type,
            "notes": "Load test standard transaction",
            "tags": [t_type, "load-test"],
        }

        with self.client.post(
            "/api/v1/transactions/", json=payload, catch_response=True
        ) as response:
            if response.status_code == 201:
                response.success()
                self.transactions.append(response.json())
            else:
                response.failure(f"Create transaction failed: {response.text}")

    @task(4)
    def update_transaction(self) -> None:
        if not self.transactions:
            return
        tx = random.choice(self.transactions)
        payload = {"amount": str(round(random.uniform(5.0, 500.0), 2))}
        with self.client.patch(
            f"/api/v1/transactions/{tx['id']}", json=payload, catch_response=True
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"Update transaction failed: {response.text}")

    @task(2)
    def delete_transaction(self) -> None:
        if not self.transactions:
            return
        tx = self.transactions.pop(random.randint(0, len(self.transactions) - 1))
        with self.client.delete(
            f"/api/v1/transactions/{tx['id']}", catch_response=True
        ) as response:
            if response.status_code in (204, 404):
                response.success()
            else:
                response.failure(f"Delete transaction failed: {response.text}")


class SpendWiseReportHeavyUser(SpendWiseBaseUser):
    """Read-only user querying dashboard reports on seeded high-volume data."""

    weight = 1

    def authenticate_user(self) -> None:
        # Always use one of the pre-seeded volume data accounts
        user_idx = random.randint(1, 100)
        email = f"loadtest_user_{user_idx}@example.com"
        self.execute_login(email)

    @task(10)
    def get_monthly_summary(self) -> None:
        year = date.today().year
        month = random.randint(1, 12)
        self.client.get(f"/api/v1/reports/monthly-summary?year={year}&month={month}")

    @task(10)
    def get_category_breakdown(self) -> None:
        date_to = date.today()
        date_from = date_to - timedelta(days=90)
        self.client.get(
            f"/api/v1/reports/category-breakdown?date_from={date_from}&date_to={date_to}&type=expense"
        )

    @task(10)
    def get_balance_trend(self) -> None:
        date_to = date.today()
        date_from = date_to - timedelta(days=180)
        self.client.get(
            f"/api/v1/reports/balance-trend?date_from={date_from}&date_to={date_to}"
        )

    @task(5)
    def list_transactions_historical(self) -> None:
        """Query large history list."""
        self.client.get("/api/v1/transactions/?page=1&per_page=50")

    @task(1)
    def check_health(self) -> None:
        self.client.get("/health")
        self.client.get("/health/ready")
