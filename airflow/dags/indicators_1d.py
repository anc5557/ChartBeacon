"""
ChartBeacon daily indicators DAG
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
import os

# Import plugin functions
import sys

sys.path.append("/opt/airflow/plugins")
from fetcher import fetch_ticker_data
from calculator import calculate_indicators
from scorer import score_indicators
from notifier import check_and_notify_discord
from utils import get_active_symbols

# Default arguments
default_args = {
    "owner": "chartbeacon",
    "depends_on_past": False,
    "start_date": datetime(2025, 5, 29),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}

# DAG definition
dag = DAG(
    "indicators_1d",
    default_args=default_args,
    description="Calculate daily technical indicators",
    schedule_interval="15 22 * * *",  # 07:15 KST (22:15 UTC)
    catchup=False,
    max_active_runs=1,
    tags=["indicators", "1d"],
)

# Get active tickers from database
try:
    TICKERS = get_active_symbols()
except Exception:
    # Fallback to environment variable
    TICKERS = os.getenv("TICKER_SYMBOLS", "005930.KS,AAPL,TSLA,SPY").split(",")

TIMEFRAME = "1d"

# Start task
start = DummyOperator(
    task_id="start",
    dag=dag,
)

# End task
end = DummyOperator(
    task_id="end",
    dag=dag,
)

# Create tasks for each ticker
for ticker in TICKERS:
    ticker_clean = ticker.replace(".", "_").replace("-", "_")

    # Fetch data task
    fetch_task = PythonOperator(
        task_id=f"fetch_{ticker_clean}",
        python_callable=fetch_ticker_data,
        op_kwargs={"ticker": ticker, "timeframe": TIMEFRAME},
        dag=dag,
    )

    # Calculate indicators task
    calc_task = PythonOperator(
        task_id=f"calc_{ticker_clean}",
        python_callable=calculate_indicators,
        op_kwargs={"ticker": ticker, "timeframe": TIMEFRAME},
        dag=dag,
    )

    # Score indicators task
    score_task = PythonOperator(
        task_id=f"score_{ticker_clean}",
        python_callable=score_indicators,
        op_kwargs={"ticker": ticker, "timeframe": TIMEFRAME},
        dag=dag,
    )

    # Notify task
    notify_task = PythonOperator(
        task_id=f"notify_{ticker_clean}",
        python_callable=check_and_notify_discord,
        op_kwargs={"ticker": ticker, "timeframe": TIMEFRAME},
        dag=dag,
    )

    # Set dependencies
    start >> fetch_task >> calc_task >> score_task >> notify_task >> end
