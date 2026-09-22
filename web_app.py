"""Streamlit web interface for the income and expense projection."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from income_expense_graph import Correction, SETTINGS, Settings, project


st.set_page_config(layout="wide")
CORRECTIONS_FILE = Path(__file__).with_name("corrections.csv")


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


# These placeholders keep the calculated output above the corrections editor,
# even though Streamlit must read the editor before performing the calculation.
chart_area = st.empty()
balance_area = st.empty()
table_area = st.empty()
download_area = st.empty()

st.subheader("Corrections")
st.caption("Loaded from corrections.csv in the GitHub repository.")

if CORRECTIONS_FILE.exists():
    correction_table = pd.read_csv(CORRECTIONS_FILE)
else:
    correction_table = pd.DataFrame(columns=["date", "description", "amount"])
    st.warning("corrections.csv was not found, so no corrections were applied.")

required_columns = {"date", "description", "amount"}
if not required_columns.issubset(correction_table.columns):
    st.error("corrections.csv must contain these columns: date, description, amount")
    correction_table = pd.DataFrame(columns=["date", "description", "amount"])

corrections: list[Correction] = []
valid_correction_rows: list[dict[str, object]] = []
for row_number, correction_row in correction_table.iterrows():
    try:
        correction_date = pd.to_datetime(correction_row["date"], errors="raise").date()
        amount = float(correction_row["amount"])
        description = str(correction_row["description"] or "Manual correction")
        corrections.append(Correction(correction_date, description, amount))
        valid_correction_rows.append(
            {"Date": correction_date, "Description": description, "Amount": amount}
        )
    except (TypeError, ValueError):
        st.error(f"Invalid correction on CSV line {row_number + 2}; that row was skipped.")

st.dataframe(
    pd.DataFrame(valid_correction_rows),
    hide_index=True,
    width="stretch",
    column_config={"Amount": st.column_config.NumberColumn("Amount", format="$%.2f")},
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
positions = list(range(len(results)))
custom_data = results[["date", "event", "income", "expense", "interest", "change"]].copy()
custom_data["date"] = custom_data["date"].dt.strftime("%d %b %Y")

fig = go.Figure(
    go.Bar(
        x=positions,
        y=balances,
        marker_color=colours,
        customdata=custom_data.to_numpy(),
        hovertemplate=(
            "<b>%{customdata[1]}</b><br>"
            "Date: %{customdata[0]}<br>"
            "Income: $%{customdata[2]:,.2f}<br>"
            "Expense: $%{customdata[3]:,.2f}<br>"
            "Interest: $%{customdata[4]:,.2f}<br>"
            "Change: $%{customdata[5]:,.2f}<br>"
            "<b>Balance: $%{y:,.2f}</b>"
            "<extra></extra>"
        ),
    )
)
label_step = max(1, len(results) // 25)
tick_positions = positions[::label_step]
tick_labels = [results.iloc[index]["date"].strftime("%d %b %Y") for index in tick_positions]
fig.update_layout(
    xaxis={"title": "Transaction date", "tickmode": "array", "tickvals": tick_positions, "ticktext": tick_labels},
    yaxis={"title": "Balance ($) — negative means owed", "tickprefix": "$", "tickformat": ",.0f"},
    hovermode="closest",
    height=650,
    margin={"l": 30, "r": 20, "t": 60, "b": 100},
)
fig.add_hline(y=0, line_color="#333333", line_width=1)
chart_area.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": True})

final_balance = float(results.iloc[-1]["balance"])
balance_area.metric("Final projected balance", f"${final_balance:,.2f}")

display_results = results.copy()
display_results["date"] = display_results["date"].dt.strftime("%d %b %Y")
table_area.dataframe(
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
download_area.download_button(
    "Download CSV",
    data=csv_data,
    file_name="income_expense_projection.csv",
    mime="text/csv",
)
