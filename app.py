from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
import pandas as pd
import numpy as np
import os
from config import DB_CONFIG

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ------------------ DATABASE SETUP ------------------

def get_db():
    conn = mysql.connector.connect(**DB_CONFIG)
    return conn

def setup_db():
    conn = mysql.connector.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"]
    )
    cur = conn.cursor()
    cur.execute("CREATE DATABASE IF NOT EXISTS finance_db")
    conn.close()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            date DATE,
            description VARCHAR(255),
            amount DECIMAL(10,2),
            category VARCHAR(100)
        )
    """)
    conn.commit()
    conn.close()

setup_db()

# ------------------ COLUMN MATCHING ------------------

# Each key is the required internal column name.
# Each value is a list of aliases (checked after normalising to lowercase,
# stripping whitespace, and removing underscores / hyphens).
COLUMN_ALIASES = {
    "date": [
        "date", "transactiondate", "transdate", "txndate", "txdate",
        "paymentdate", "valuedate", "postingdate", "bookingdate",
    ],
    "description": [
        "description", "desc", "details", "narrative", "narration",
        "memo", "particulars", "transactiondetails", "remarks", "note",
        "reference", "payee", "merchant",
    ],
    "amount": [
        "amount", "amt", "value", "sum", "total", "debit",
        "transactionamount", "txnamount", "price", "cost",
    ],
    "category": [
        "category", "cat", "type", "group", "tag", "label",
        "transactiontype", "expensetype", "spendingcategory",
    ],
}

def _normalise(name):
    """Lowercase, strip, remove spaces/underscores/hyphens and common symbols."""
    return (
        name.lower()
        .strip()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
        .replace("₹", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
    )

def resolve_columns(df):
    """Match CSV columns to required columns using alias lists.
    Returns (renamed_df, error_string | None)."""
    normalised_map = {}           # normalised_csv_name -> original_csv_name
    for col in df.columns:
        normalised_map[_normalise(col)] = col

    rename = {}                   # original_csv_name -> required_name
    missing = []

    for required, aliases in COLUMN_ALIASES.items():
        matched = False
        for alias in aliases:
            if alias in normalised_map:
                rename[normalised_map[alias]] = required
                matched = True
                break
        if not matched:
            missing.append(required)

    if missing:
        return df, (
            f"Could not find columns for: {', '.join(missing)}. "
            f"Your CSV has columns: {', '.join(df.columns.tolist())}. "
            f"Accepted names include: "
            + "; ".join(
                f"{req} → {', '.join(COLUMN_ALIASES[req][:4])}"
                for req in missing
            )
        )

    df = df.rename(columns=rename)
    return df, None

# ------------------ UPLOAD & ANALYSE ------------------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename.endswith(".csv"):
        return jsonify({"error": "Only CSV files are allowed"}), 400

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], "transactions.csv")
    file.save(filepath)

    df = pd.read_csv(filepath)

    # --- Flexible column matching ---
    df, col_error = resolve_columns(df)
    if col_error:
        return jsonify({"error": col_error}), 400

    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna()

    # Import into MySQL
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM transactions")
    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO transactions (date, description, amount, category)
            VALUES (%s, %s, %s, %s)
        """, (row["date"].date(), row["description"], float(row["amount"]), row["category"]))
    conn.commit()
    conn.close()

    # Analysis
    df["month"] = df["date"].dt.strftime("%Y-%m")

    category_totals = df.groupby("category")["amount"].sum().to_dict()
    monthly_totals = df.groupby("month")["amount"].sum().to_dict()

    # NumPy anomaly detection — flag anything above 2 standard deviations
    amounts = df["amount"].to_numpy()
    mean = float(np.mean(amounts))
    std = float(np.std(amounts))
    threshold = mean + 2 * std

    anomalies = df[df["amount"] > threshold].copy()
    anomalies["date"] = anomalies["date"].dt.strftime("%Y-%m-%d")
    anomaly_list = anomalies[["date", "description", "amount", "category"]].to_dict(orient="records")

    # All transactions for table
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    all_transactions = df[["date", "description", "amount", "category"]].to_dict(orient="records")

    return jsonify({
        "category_totals": category_totals,
        "monthly_totals": monthly_totals,
        "anomalies": anomaly_list,
        "all_transactions": all_transactions,
        "mean": round(mean, 2),
        "std": round(std, 2),
        "threshold": round(threshold, 2)
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)