"""Project an owed balance using fortnightly salary and monthly expenses.

The script prints and graphs every pay, expense and interest transaction, saves
all events to CSV, and creates a PNG bar chart. Negative balances mean money is owed.

Install the chart dependency once with:
    python -m pip install matplotlib
"""

from __future__ import annotations

import calendar
import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    start_date: date
    years: int
    opening_balance: float
    fortnightly_salary: float
    first_pay_date: date
    salary_yearly_increase: float
    monthly_expenses: float
    expenses_yearly_increase: float
    annual_interest: float


@dataclass(frozen=True)
class Correction:
    date: date
    description: str
    amount: float


# ---------------------------------------------------------------------------
# EDIT YOUR VALUES HERE
# Percentages are written as normal percentages: 3 means 3%, and 6.5 means 6.5%.
# ---------------------------------------------------------------------------
SETTINGS = Settings(
    start_date=date(2026, 4, 1),
    years=5,
    opening_balance=-203_250,
    fortnightly_salary=4_028,
    first_pay_date=date(2026, 4, 23),
    salary_yearly_increase=3 / 100,
    monthly_expenses=3_550,
    expenses_yearly_increase=3 / 100,
    annual_interest=6.51 / 100,
)

# Add as many one-off corrections as needed. A positive amount adds money and a
# negative amount removes money. Remove the leading # to activate an example.
CORRECTIONS: list[Correction] = [
    # Correction(date(2026, 4, 15), "Opening balance correction", -4_350),
    # Correction(date(2027, 8, 10), "Unexpected repair", -2_500),
]

CSV_OUTPUT = Path("monthly_projection.csv")
CHART_OUTPUT = Path("income_expense_graph.png")


def full_years_since(start: date, current: date) -> int:
    """Return completed anniversaries, including leap-year-safe handling."""
    years = current.year - start.year
    anniversary = (start.month, start.day)
    if (current.month, current.day) < anniversary:
        years -= 1
    return max(0, years)


def next_month(day: date) -> date:
    return date(day.year + (day.month == 12), 1 if day.month == 12 else day.month + 1, 1)


def project(
    settings: Settings, custom_corrections: list[Correction] | None = None
) -> list[dict[str, object]]:
    end_date = date(settings.start_date.year + settings.years, settings.start_date.month, 1)
    month_start = settings.start_date.replace(day=1)
    pay_date = settings.first_pay_date
    corrections = sorted(
        CORRECTIONS if custom_corrections is None else custom_corrections,
        key=lambda correction: correction.date,
    )
    correction_index = 0
    balance = settings.opening_balance
    rows: list[dict[str, object]] = [
        {
            "date": settings.start_date.isoformat(),
            "event": "Initial balance",
            "income": 0.0,
            "expense": 0.0,
            "interest": 0.0,
            "change": 0.0,
            "balance": balance,
        }
    ]

    # Skip pay dates before the projection starts.
    while pay_date < settings.start_date:
        pay_date += timedelta(days=14)
    while correction_index < len(corrections) and corrections[correction_index].date < settings.start_date:
        correction_index += 1

    while month_start < end_date:
        month_end = date(
            month_start.year,
            month_start.month,
            calendar.monthrange(month_start.year, month_start.month)[1],
        )

        transactions: list[tuple[date, int, str, float]] = []
        while pay_date <= month_end:
            if pay_date >= settings.start_date:
                salary_year = full_years_since(settings.start_date, pay_date)
                salary = settings.fortnightly_salary * (
                    1 + settings.salary_yearly_increase
                ) ** salary_year
                transactions.append((pay_date, 0, "Fortnightly salary", salary))
            pay_date += timedelta(days=14)

        while correction_index < len(corrections) and corrections[correction_index].date <= month_end:
            correction = corrections[correction_index]
            transactions.append(
                (correction.date, 1, f"Correction: {correction.description}", correction.amount)
            )
            correction_index += 1

        expense_date = date(month_start.year, month_start.month, 28)
        if expense_date >= settings.start_date:
            expense_year = full_years_since(settings.start_date, expense_date)
            expenses = settings.monthly_expenses * (
                1 + settings.expenses_yearly_increase
            ) ** expense_year
            transactions.append((expense_date, 2, "Monthly expenses", -expenses))

        for transaction_date, _order, event, amount in sorted(transactions):
            balance += amount
            rows.append(
                {
                    "date": transaction_date.isoformat(),
                    "event": event,
                    "income": amount if amount > 0 else 0.0,
                    "expense": -amount if amount < 0 else 0.0,
                    "interest": 0.0,
                    "change": amount,
                    "balance": balance,
                }
            )

        # Interest is charged only while the balance is below zero (money owed).
        interest = (-balance) * settings.annual_interest / 12 if balance < 0 else 0.0
        if interest > 0:
            balance -= interest
            rows.append(
                {
                    "date": month_end.isoformat(),
                    "event": "Interest on owed balance",
                    "income": 0.0,
                    "expense": 0.0,
                    "interest": interest,
                    "change": -interest,
                    "balance": balance,
                }
            )
        month_start = next_month(month_start)

    return rows


def write_csv(rows: list[dict[str, object]], output: Path) -> None:
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        for row in rows:
            formatted = dict(row)
            for column in ("income", "expense", "interest", "change", "balance"):
                formatted[column] = f"{float(row[column]):.2f}"
            writer.writerow(formatted)


def make_chart(rows: list[dict[str, object]], opening_balance: float, output: Path) -> None:
    try:
        import matplotlib.pyplot as plt
        from matplotlib.ticker import StrMethodFormatter
    except ImportError as exc:
        raise SystemExit("Matplotlib is required. Run: python -m pip install matplotlib") from exc

    labels = [f"{row['date']}\n{row['event']}" for row in rows]
    balances = [float(row["balance"]) for row in rows]
    colours = ["#168de2" if value < 0 else "#27a35a" for value in balances]

    fig, ax = plt.subplots(figsize=(15, 7.5))
    ax.bar(range(len(rows)), balances, color=colours, width=0.82)
    ax.axhline(0, color="#333333", linewidth=0.9)
    ax.set_title(
        f"Balance After Every Pay, Expense, Interest and Correction (opening ${opening_balance:,.0f})"
    )
    ax.set_ylabel("Balance ($) — negative means owed")
    ax.yaxis.set_major_formatter(StrMethodFormatter("${x:,.0f}"))

    # Keep long projections readable by showing at most about 30 x-axis labels.
    label_step = max(1, len(rows) // 30)
    ticks = list(range(0, len(rows), label_step))
    ax.set_xticks(ticks, [labels[index] for index in ticks], rotation=55, ha="right")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.show()


def print_events(rows: list[dict[str, object]]) -> None:
    print(
        f"{'Date':<10}  {'Event':<25} {'Income':>12} {'Expense':>12} "
        f"{'Interest':>12} {'Change':>12} {'Balance':>14}"
    )
    print("-" * 106)
    for row in rows:
        print(
            f"{row['date']:<10}  {row['event']:<25} "
            f"{row['income']:>12,.2f} {row['expense']:>12,.2f} "
            f"{row['interest']:>12,.2f} {row['change']:>12,.2f} "
            f"{row['balance']:>14,.2f}"
        )


def main() -> None:
    rows = project(SETTINGS)
    print_events(rows)
    write_csv(rows, CSV_OUTPUT)
    print(f"\nSaved monthly data to: {CSV_OUTPUT.resolve()}")
    make_chart(rows, SETTINGS.opening_balance, CHART_OUTPUT)
    print(f"Saved chart to: {CHART_OUTPUT.resolve()}")


if __name__ == "__main__":
    main()
