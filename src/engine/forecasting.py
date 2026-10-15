# -*- coding: utf-8 -*-
"""Forecasting Engine with Seasonal Naive, Moving Average, and Rolling-Origin Backtesting.

Follows BeverageOps AI specifications:
- Granularity: Daily (D+1)
- Baselines: Seasonal Naive (7-day), Simple Moving Average (7-day), Day-of-Week Moving Average
- Metrics: MAE, WAPE, Bias
- Model Selection via rolling-origin backtest
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from sqlalchemy import func
from src.database import SessionLocal
from src.models import MenuItem, SalesDaily


class ForecastingEngine:
    def __init__(self, db_session=None):
        self.db = db_session or SessionLocal()
        self._load_sales_data()

    def close(self):
        if self.db:
            self.db.close()

    def _load_sales_data(self):
        """Loads all daily sales records into a clean pivoted DataFrame."""
        records = self.db.query(
            SalesDaily.business_date,
            SalesDaily.sku_id,
            MenuItem.sku_name,
            SalesDaily.quantity_sold
        ).join(MenuItem, SalesDaily.sku_id == MenuItem.sku_id).order_by(SalesDaily.business_date).all()

        if not records:
            self.df = pd.DataFrame(columns=["business_date", "sku_id", "sku_name", "quantity_sold"])
            self.dates = []
            self.skus = []
            return

        self.df = pd.DataFrame(records, columns=["business_date", "sku_id", "sku_name", "quantity_sold"])
        self.df["business_date"] = pd.to_datetime(self.df["business_date"]).dt.date
        self.dates = sorted(self.df["business_date"].unique())
        self.skus = sorted(self.df["sku_id"].unique())

    def get_sku_history(self, sku_id: str, up_to_date: Optional[date] = None) -> pd.Series:
        """Returns time series of sales quantity up to up_to_date."""
        sub = self.df[self.df["sku_id"] == sku_id]
        if up_to_date:
            sub = sub[sub["business_date"] <= up_to_date]
        sub = sub.sort_values("business_date")
        s = pd.Series(data=sub["quantity_sold"].values, index=sub["business_date"])
        return s

    # --- FORECAST BASELINES ---

    @staticmethod
    def predict_seasonal_naive(history: pd.Series, target_date: date, season_length: int = 7) -> float:
        """Seasonal Naive: y_t = y_{t - season_length}."""
        source_date = target_date - timedelta(days=season_length)
        if source_date in history.index:
            return float(history.loc[source_date])
        # Fallback to last known value or mean
        if not history.empty:
            return float(history.iloc[-1])
        return 0.0

    @staticmethod
    def predict_moving_average(history: pd.Series, window: int = 7) -> float:
        """Simple Moving Average over last `window` observations."""
        if history.empty:
            return 0.0
        recent = history.iloc[-window:]
        return float(np.mean(recent))

    @staticmethod
    def predict_day_of_week_ma(history: pd.Series, target_date: date, weeks: int = 3) -> float:
        """Moving average of the same day-of-week over previous `weeks`."""
        target_dow = target_date.weekday()
        matches = [val for d, val in history.items() if d.weekday() == target_dow and d < target_date]
        if not matches:
            return ForecastingEngine.predict_moving_average(history, window=7)
        recent_matches = matches[-weeks:]
        return float(np.mean(recent_matches))

    def predict_sku_single(self, sku_id: str, target_date: date, model: str = "day_of_week_ma") -> Dict[str, Any]:
        """Predicts sales for one SKU on target_date."""
        history = self.get_sku_history(sku_id, up_to_date=target_date - timedelta(days=1))
        
        if history.empty:
            return {
                "sku_id": sku_id,
                "target_date": target_date,
                "model": model,
                "prediction": 0.0,
                "uncertainty_low": 0.0,
                "uncertainty_high": 0.0,
                "confidence": "NO_DATA"
            }

        if model == "seasonal_naive":
            pred = self.predict_seasonal_naive(history, target_date, season_length=7)
        elif model == "moving_average":
            pred = self.predict_moving_average(history, window=7)
        elif model == "day_of_week_ma":
            pred = self.predict_day_of_week_ma(history, target_date, weeks=3)
        else:
            pred = self.predict_day_of_week_ma(history, target_date, weeks=3)

        # Uncertainty estimate based on rolling residual std
        std = float(np.std(history.iloc[-14:])) if len(history) >= 7 else float(pred * 0.15)
        low = max(0.0, pred - 1.96 * std)
        high = pred + 1.96 * std

        confidence = "HIGH" if len(history) >= 21 else ("MEDIUM" if len(history) >= 7 else "LOW")

        return {
            "sku_id": sku_id,
            "target_date": target_date,
            "model": model,
            "prediction": round(pred, 1),
            "uncertainty_low": round(low, 1),
            "uncertainty_high": round(high, 1),
            "confidence": confidence
        }

    # --- ROLLING-ORIGIN BACKTESTING ---

    def run_backtest(self, start_eval_day: int = 15) -> Dict[str, Any]:
        """Runs rolling-origin 1-day ahead backtest for all models across days 15..end.
        
        Calculates:
        - MAE: Mean Absolute Error
        - WAPE: Weighted Absolute Percentage Error = sum(|actual - pred|) / sum(actual)
        - Bias: sum(pred - actual) / sum(actual)
        """
        if len(self.dates) <= start_eval_day:
            return {"error": "Insufficient history for backtest"}

        eval_dates = self.dates[start_eval_day:]
        models = ["seasonal_naive", "moving_average", "day_of_week_ma"]

        results = {m: {"actuals": [], "preds": [], "errors": []} for m in models}
        per_sku_results = {sku: {m: {"actuals": [], "preds": []} for m in models} for sku in self.skus}

        for d in eval_dates:
            for sku in self.skus:
                hist = self.get_sku_history(sku, up_to_date=d - timedelta(days=1))
                act_row = self.df[(self.df["business_date"] == d) & (self.df["sku_id"] == sku)]
                actual = float(act_row["quantity_sold"].iloc[0]) if not act_row.empty else 0.0

                for m in models:
                    if m == "seasonal_naive":
                        pred = self.predict_seasonal_naive(hist, d, 7)
                    elif m == "moving_average":
                        pred = self.predict_moving_average(hist, 7)
                    else:
                        pred = self.predict_day_of_week_ma(hist, d, 3)

                    results[m]["actuals"].append(actual)
                    results[m]["preds"].append(pred)
                    results[m]["errors"].append(abs(actual - pred))

                    per_sku_results[sku][m]["actuals"].append(actual)
                    per_sku_results[sku][m]["preds"].append(pred)

        # Aggregate summary metrics
        metrics = {}
        for m in models:
            actuals = np.array(results[m]["actuals"])
            preds = np.array(results[m]["preds"])
            sum_actual = np.sum(actuals)
            sum_pred = np.sum(preds)
            sum_abs_err = np.sum(np.abs(actuals - preds))

            mae = float(np.mean(np.abs(actuals - preds)))
            wape = float((sum_abs_err / sum_actual) * 100) if sum_actual > 0 else 0.0
            bias = float(((sum_pred - sum_actual) / sum_actual) * 100) if sum_actual > 0 else 0.0

            metrics[m] = {
                "MAE": round(mae, 2),
                "WAPE_pct": round(wape, 2),
                "Bias_pct": round(bias, 2),
                "Total_Actual": int(sum_actual),
                "Total_Predicted": round(float(sum_pred), 1)
            }

        # Determine best model
        best_model = min(metrics.keys(), key=lambda m: metrics[m]["WAPE_pct"])

        return {
            "evaluation_period": f"{eval_dates[0]} to {eval_dates[-1]} ({len(eval_dates)} days)",
            "total_skus": len(self.skus),
            "aggregate_metrics": metrics,
            "best_model": best_model,
            "per_sku_metrics": self._summarize_per_sku_metrics(per_sku_results, models)
        }

    def _summarize_per_sku_metrics(self, per_sku_results: dict, models: list) -> List[Dict[str, Any]]:
        sku_name_map = dict(self.df[["sku_id", "sku_name"]].drop_duplicates().values)
        summary = []
        for sku, model_data in per_sku_results.items():
            row = {"sku_id": sku, "sku_name": sku_name_map.get(sku, sku)}
            for m in models:
                acts = np.array(model_data[m]["actuals"])
                preds = np.array(model_data[m]["preds"])
                sum_act = np.sum(acts)
                wape = round(float((np.sum(np.abs(acts - preds)) / sum_act) * 100), 1) if sum_act > 0 else 0.0
                mae = round(float(np.mean(np.abs(acts - preds))), 1)
                row[f"{m}_WAPE"] = wape
                row[f"{m}_MAE"] = mae
            summary.append(row)
        return summary

    def forecast_demand(self, target_date: Optional[date] = None, horizon_days: int = 1, model: str = "auto") -> pd.DataFrame:
        """Forecasts demand for all SKUs for target_date (D+1).
        
        If model == 'auto', selects the model with lowest WAPE from backtest.
        """
        if not target_date:
            last_date = self.dates[-1] if self.dates else date.today()
            target_date = last_date + timedelta(days=1)

        selected_model = model
        if model == "auto":
            bt = self.run_backtest(start_eval_day=15)
            selected_model = bt.get("best_model", "day_of_week_ma")

        sku_names = dict(self.df[["sku_id", "sku_name"]].drop_duplicates().values)
        forecast_rows = []

        for day_offset in range(horizon_days):
            current_target = target_date + timedelta(days=day_offset)
            for sku in self.skus:
                res = self.predict_sku_single(sku, current_target, model=selected_model)
                forecast_rows.append({
                    "target_date": current_target,
                    "sku_id": sku,
                    "sku_name": sku_names.get(sku, sku),
                    "predicted_qty": res["prediction"],
                    "lower_bound": res["uncertainty_low"],
                    "upper_bound": res["uncertainty_high"],
                    "model_used": selected_model,
                    "confidence": res["confidence"]
                })

        df_res = pd.DataFrame(forecast_rows)
        return df_res


if __name__ == "__main__":
    fe = ForecastingEngine()
    print("=== BACKTEST EVALUATION (DAYS 15-30) ===")
    bt = fe.run_backtest()
    print(f"Period: {bt['evaluation_period']}")
    print(f"Best Model: {bt['best_model']}")
    for m, vals in bt['aggregate_metrics'].items():
        print(f"Model: {m:<18} -> MAE: {vals['MAE']:<6} | WAPE: {vals['WAPE_pct']:<6}% | Bias: {vals['Bias_pct']}%")

    print("\n=== SAMPLE D+1 FORECAST (TOP 10 SKUs) ===")
    fc = fe.forecast_demand(horizon_days=1, model="auto")
    print(fc.sort_values(by="predicted_qty", ascending=False).head(10).to_string(index=False))
    fe.close()
