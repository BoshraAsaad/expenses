"""Streamlit web interface for the income and expense projection."""

from __future__ import annotations

from datetime import date

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from matplotlib.ticker import StrMethodFormatter

from income_expense_graph import Correction, SETTINGS, Settings, project


st.set_page_config(page_title="Income and Expense Projection", layout="wide")
st.title("Income and Expense Projection")
st.caption("Negative balances represent money owed. Interest is charged monthly while the balance is negative.")


with st.sidebar:
    st.header("Projection settings")
    start_date = st.date_input("Start date", SETTINGS.start_date)
    years = st.number_input("Projection years", min_value=1, max_value=100, value=SETTINGS.years)
    opening_balance = st.number_input(
        "Opening balance ($)", value=float(SETTINGS.opening_balance), step=1000.0
    )
    fortnightly_salary = st.number_input(
        "Fortnightly salary ($)", min_value=0.0, value=float(SETTINGS.fortnightly_salary), step=100.0
    )
    first_pay_date = st.date_input("First pay date", SETTINGS.first_pay_date)
    salary_increase = st.number_input(
        "Yearly salary increase (%)",
        min_value=0.0,
        value=SETTINGS.salary_yearly_increase * 100,
        step=0.1,
    )
    monthly_expenses = st.number_input(
        "Monthly expenses ($)", min_value=0.0, value=float(SETTINGS.monthly_expenses), step=100.0
    )
    expenses_increase = st.number_input(
        "Yearly expense increase (%)",
        min_value=0.0,
        value=SETTINGS.expenses_yearly_increase * 100,
        step=0.1,
    )
    annual_interest = st.number_input(
        "Annual interest on owed balance (%)",
        min_value=0.0,
        value=SETTINGS.annual_interest * 100,
        step=0.01,
    )


st.subheader("Corrections")
st.write("Add one-off adjustments below. Positive amounts add money; negative amounts remove money.")

default_corrections = pd.DataFrame(
    {
        "Date": pd.Series(dtype="datetime64[ns]"),
        "Description": pd.Series(dtype="str"),
        "Amount": pd.Series(dtype="float"),
    }
)
correction_table = st.data_editor(
    default_corrections,
    num_rows="dynamic",
    hide_index=True,
    width="stretch",
    column_config={
        "Date": st.column_config.DateColumn("Date", required=True),
        "Description": st.column_config.TextColumn("Description", required=True),
        "Amount": st.column_config.NumberColumn("Amount ($)", format="$%.2f", required=True),
    },
)


corrections: list[Correction] = []
for _, correction_row in correction_table.dropna(how="all").iterrows():
    if pd.isna(correction_row["Date"]) or pd.isna(correction_row["Amount"]):
        continue
    correction_date = pd.Timestamp(correction_row["Date"]).date()
    corrections.append(
        Correction(
            date=correction_date,
            description=str(correction_row["Description"] or "Manual correction"),
            amount=float(correction_row["Amount"]),
        )
    )

settings = Settings(
    start_date=start_date,
    years=int(years),
    opening_balance=float(opening_balance),
    fortnightly_salary=float(fortnightly_salary),
    first_pay_date=first_pay_date,
    salary_yearly_increase=float(salary_increase) / 100,
    monthly_expenses=float(monthly_expenses),
    expenses_yearly_increase=float(expenses_increase) / 100,
    annual_interest=float(annual_interest) / 100,
)

rows = project(settings, corrections)
results = pd.DataFrame(rows)
results["date"] = pd.to_datetime(results["date"])

balances = results["balance"].astype(float)
colours = ["#168de2" if value < 0 else "#27a35a" for value in balances]
fig, ax = plt.subplots(figsize=(15, 6.5))
ax.bar(range(len(results)), balances, color=colours, width=0.82)
ax.axhline(0, color="#333333", linewidth=0.9)
ax.set_title("Balance After Every Pay, Expense, Interest and Correction")
ax.set_ylabel("Balance ($) — negative means owed")
ax.yaxis.set_major_formatter(StrMethodFormatter("${x:,.0f}"))
label_step = max(1, len(results) // 25)
ticks = list(range(0, len(results), label_step))
labels = [
    f"{row.date:%d %b %Y}\n{row.event}" for row in results.itertuples(index=False)
]
ax.set_xticks(ticks, [labels[index] for index in ticks], rotation=55, ha="right")
ax.grid(axis="y", alpha=0.25)
fig.tight_layout()
st.pyplot(fig)
plt.close(fig)

final_balance = float(results.iloc[-1]["balance"])
st.metric("Final projected balance", f"${final_balance:,.2f}")

st.subheader("All transactions")
display_results = results.copy()
display_results["date"] = display_results["date"].dt.strftime("%d %b %Y")
st.dataframe(
    display_results,
    hide_index=True,
    width="stretch",
    column_config={
        "date": "Date",
        "event": "Event",
        "income": st.column_config.NumberColumn("Income", format="$%.2f"),
        "expense": st.column_config.NumberColumn("Expense", format="$%.2f"),
        "interest": st.column_config.NumberColumn("Interest", format="$%.2f"),
        "change": st.column_config.NumberColumn("Change", format="$%.2f"),
        "balance": st.column_config.NumberColumn("Balance", format="$%.2f"),
    },
)

csv_data = display_results.to_csv(index=False, float_format="%.2f").encode("utf-8")
st.download_button(
    "Download CSV",
    data=csv_data,
    file_name="income_expense_projection.csv",
    mime="text/csv",
)
