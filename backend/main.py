"""CaliB analytics API. Excel is ingested once into DuckDB; all client queries are aggregated server-side."""
from __future__ import annotations
import os
from pathlib import Path
from datetime import date
from typing import Optional
import duckdb
import pandas as pd
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import io, csv

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("CALIB_DB", ROOT / "data" / "calib.duckdb"))
EXCEL_PATH = Path(os.getenv("CALIB_EXCEL", "/Users/sohamsiddharthamishra/Downloads/data.xlsx"))
EXPECTED = ["BillNo", "Outlet_Name", "Order_Datetime", "Group", "Order_Type", "Item", "Price", "Quantity", "Settlement", "Brand"]
app = FastAPI(title="CaliB Business Analytics API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["GET"], allow_headers=["*"])

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH), read_only=DB_PATH.exists())

def ingest():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        with duckdb.connect(str(DB_PATH), read_only=True) as con:
            if con.execute("select count(*) from information_schema.tables where table_name='orders'").fetchone()[0]: return
    if not EXCEL_PATH.exists(): raise RuntimeError(f"Excel dataset not found: {EXCEL_PATH}. Set CALIB_EXCEL to its location.")
    print(f"Reading {EXCEL_PATH} …", flush=True)
    df = pd.read_excel(EXCEL_PATH, engine="openpyxl")
    missing = sorted(set(EXPECTED) - set(df.columns))
    if missing: raise RuntimeError(f"Dataset is missing required columns: {', '.join(missing)}")
    df = df[EXPECTED].copy()
    df["Order_Datetime"] = pd.to_datetime(df["Order_Datetime"], errors="coerce")
    for c in ["Price", "Quantity"]: df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["BillNo", "Outlet_Name", "Group", "Order_Type", "Item", "Settlement", "Brand"]: df[c] = df[c].astype("string").str.strip()
    df = df.dropna(subset=["BillNo", "Order_Datetime", "Price", "Quantity"])
    df = df[(df.Price >= 0) & (df.Quantity >= 0)]
    df["Line_Revenue"] = df["Price"] * df["Quantity"]
    with duckdb.connect(str(DB_PATH)) as con:
        con.register("source_df", df)
        con.execute("CREATE OR REPLACE TABLE orders AS SELECT * FROM source_df")
        con.execute("CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(Order_Datetime)")
    print(f"Ingested {len(df):,} valid order lines into DuckDB", flush=True)

@app.on_event("startup")
def startup(): ingest()

def filters(start: Optional[str], end: Optional[str], outlet: Optional[str], category: Optional[str], order_type: Optional[str], settlement: Optional[str], brand: Optional[str], search: Optional[str] = None):
    clauses, args = [], []
    if start: clauses.append("CAST(Order_Datetime AS DATE) >= ?"); args.append(start)
    if end: clauses.append("CAST(Order_Datetime AS DATE) <= ?"); args.append(end)
    for col, value in [("Outlet_Name", outlet), ("Group", category), ("Order_Type", order_type), ("Settlement", settlement), ("Brand", brand)]:
        if value: clauses.append(f'"{col}" = ?'); args.append(value)
    if search:
        clauses.append("(CAST(BillNo AS VARCHAR) ILIKE ? OR Item ILIKE ? OR Outlet_Name ILIKE ?)"); args += [f"%{search}%"] * 3
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), args

BASE = """start: Optional[str]=None, end: Optional[str]=None, outlet: Optional[str]=None, category: Optional[str]=None, order_type: Optional[str]=None, settlement: Optional[str]=None, brand: Optional[str]=None"""
def run(sql, args=()):
    try:
        with connect() as con: return con.execute(sql, args).fetchdf()
    except Exception as e: raise HTTPException(500, str(e))
def records(df): return df.where(pd.notnull(df), None).to_dict(orient="records")

@app.get("/api/health")
def health():
    try:
        d=run("SELECT COUNT(*) records, COUNT(DISTINCT BillNo) orders, MIN(Order_Datetime) first_date, MAX(Order_Datetime) last_date FROM orders")
        return {"status":"ok", **records(d)[0]}
    except Exception as e: return {"status":"error", "detail":str(e)}

@app.get("/api/filters")
def filter_options():
    out={}
    for key,col in [("outlets","Outlet_Name"),("categories","Group"),("order_types","Order_Type"),("settlements","Settlement"),("brands","Brand")]:
        col_sql=f'"{col}"'
        out[key]=run(f"SELECT DISTINCT {col_sql} AS value FROM orders WHERE {col_sql} IS NOT NULL ORDER BY 1").value.tolist()
    dates=run("SELECT CAST(MIN(Order_Datetime) AS DATE) min_date, CAST(MAX(Order_Datetime) AS DATE) max_date FROM orders").iloc[0].to_dict()
    out["date_range"]={k:str(v) for k,v in dates.items()}
    return out

@app.get("/api/overview")
def overview(start:Optional[str]=None,end:Optional[str]=None,outlet:Optional[str]=None,category:Optional[str]=None,order_type:Optional[str]=None,settlement:Optional[str]=None,brand:Optional[str]=None):
    w,a=filters(start,end,outlet,category,order_type,settlement,brand)
    k=records(run(f"SELECT COALESCE(SUM(Line_Revenue),0) revenue, COUNT(DISTINCT BillNo) orders, COALESCE(SUM(Quantity),0) units, COUNT(*) records, COALESCE(SUM(Line_Revenue)/NULLIF(COUNT(DISTINCT BillNo),0),0) aov FROM orders{w}",a))[0]
    return {"kpis":k,"trend":records(run(f"SELECT CAST(Order_Datetime AS DATE) date, SUM(Line_Revenue) revenue FROM orders{w} GROUP BY 1 ORDER BY 1",a)),"distribution":records(run(f"SELECT Order_Type name, COUNT(DISTINCT BillNo) value FROM orders{w} GROUP BY 1 ORDER BY 2 DESC",a)),"insights":records(run(f"SELECT Outlet_Name outlet, SUM(Line_Revenue) revenue, COUNT(DISTINCT BillNo) orders FROM orders{w} GROUP BY 1 ORDER BY 2 DESC LIMIT 3",a))}

@app.get("/api/revenue")
def revenue(start:Optional[str]=None,end:Optional[str]=None,outlet:Optional[str]=None,category:Optional[str]=None,order_type:Optional[str]=None,settlement:Optional[str]=None,brand:Optional[str]=None,granularity:str="day"):
    w,a=filters(start,end,outlet,category,order_type,settlement,brand)
    expr={"day":"CAST(Order_Datetime AS DATE)","week":"DATE_TRUNC('week',Order_Datetime)","month":"DATE_TRUNC('month',Order_Datetime)"}.get(granularity)
    if not expr: raise HTTPException(400,"granularity must be day, week, or month")
    trend=records(run(f"SELECT {expr} period, SUM(Line_Revenue) revenue FROM orders{w} GROUP BY 1 ORDER BY 1",a))
    breakdown={}
    for key,col in [("outlets","Outlet_Name"),("categories","Group"),("order_types","Order_Type"),("settlements","Settlement")]: breakdown[key]=records(run(f'SELECT "{col}" AS name, SUM(Line_Revenue) revenue FROM orders{w} GROUP BY 1 ORDER BY 2 DESC',a))
    return {"trend":trend,"breakdown":breakdown}

@app.get("/api/categories")
def categories(start:Optional[str]=None,end:Optional[str]=None,outlet:Optional[str]=None,category:Optional[str]=None,order_type:Optional[str]=None,settlement:Optional[str]=None,brand:Optional[str]=None):
    w,a=filters(start,end,outlet,category,order_type,settlement,brand)
    return {"data":records(run(f'SELECT "Group" AS name, SUM(Line_Revenue) revenue, SUM(Quantity) quantity, COUNT(DISTINCT BillNo) orders FROM orders{w} GROUP BY 1 ORDER BY 2 DESC',a))}

@app.get("/api/products")
def products(start:Optional[str]=None,end:Optional[str]=None,outlet:Optional[str]=None,category:Optional[str]=None,order_type:Optional[str]=None,settlement:Optional[str]=None,brand:Optional[str]=None,sort:str="revenue",limit:int=100):
    w,a=filters(start,end,outlet,category,order_type,settlement,brand); order={"revenue":"revenue","quantity":"quantity","name":"name"}.get(sort)
    if not order: raise HTTPException(400,"sort must be revenue, quantity or name")
    return {"data":records(run(f'SELECT Item AS name, "Group" AS category, Brand AS brand, SUM(Quantity) quantity, SUM(Line_Revenue) revenue, SUM(Line_Revenue)/NULLIF(SUM(SUM(Line_Revenue)) OVER (),0)*100 AS contribution, COUNT(DISTINCT BillNo) orders FROM orders{w} GROUP BY 1,2,3 ORDER BY {order} {"ASC" if sort=="name" else "DESC"} LIMIT ?',a+[min(max(limit,1),500)]))}

@app.get("/api/outlets")
def outlets(start:Optional[str]=None,end:Optional[str]=None,outlet:Optional[str]=None,category:Optional[str]=None,order_type:Optional[str]=None,settlement:Optional[str]=None,brand:Optional[str]=None):
    w,a=filters(start,end,outlet,category,order_type,settlement,brand)
    data=records(run(f"SELECT Outlet_Name name, SUM(Line_Revenue) revenue, COUNT(DISTINCT BillNo) orders, SUM(Quantity) units, SUM(Line_Revenue)/NULLIF(COUNT(DISTINCT BillNo),0) aov FROM orders{w} GROUP BY 1 ORDER BY 2 DESC",a))
    best=records(run(f'SELECT Outlet_Name outlet, "Group" AS category, SUM(Line_Revenue) revenue, ROW_NUMBER() OVER(PARTITION BY Outlet_Name ORDER BY SUM(Line_Revenue) DESC) rn FROM orders{w} GROUP BY 1,2 QUALIFY rn=1',a))
    return {"data":data,"best_categories":best}

@app.get("/api/orders")
def orders(start:Optional[str]=None,end:Optional[str]=None,outlet:Optional[str]=None,category:Optional[str]=None,order_type:Optional[str]=None,settlement:Optional[str]=None,brand:Optional[str]=None,search:Optional[str]=None,page:int=1,page_size:int=25):
    w,a=filters(start,end,outlet,category,order_type,settlement,brand,search)
    total=run(f"SELECT COUNT(*) n FROM orders{w}",a).iloc[0,0]; size=min(max(page_size,1),100); page=max(page,1)
    rows=run(f'SELECT BillNo, Order_Datetime, Outlet_Name, Item, "Group", Order_Type, Price, Quantity, Line_Revenue, Settlement FROM orders{w} ORDER BY Order_Datetime DESC LIMIT ? OFFSET ?',a+[size,(page-1)*size])
    return {"data":records(rows),"page":page,"page_size":size,"total":int(total),"pages":(int(total)+size-1)//size}

@app.get("/api/export")
def export(start:Optional[str]=None,end:Optional[str]=None,outlet:Optional[str]=None,category:Optional[str]=None,order_type:Optional[str]=None,settlement:Optional[str]=None,brand:Optional[str]=None,search:Optional[str]=None):
    w,a=filters(start,end,outlet,category,order_type,settlement,brand,search)
    df=run(f'SELECT BillNo, Order_Datetime, Outlet_Name, Item, "Group", Order_Type, Price, Quantity, Line_Revenue, Settlement FROM orders{w} ORDER BY Order_Datetime DESC',a)
    s=io.StringIO(); df.to_csv(s,index=False)
    return StreamingResponse(iter([s.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=calib-transactions.csv"})
