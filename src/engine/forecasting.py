"""Forecasting Engine with Seasonal Naive, Moving Average, and Rolling-Origin Backtesting.

Follows BeverageOps AI specifications:
- Granularity: Daily (D+1)
- Baselines: Seasonal Naive (7-day), Simple Moving Average (7-day), Day-of-Week Moving Average
- Metrics: MAE, WAPE, Bias
- Model Selection via rolling-origin backtest
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import time
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from src.database import SessionLocal
from src.engine.contextual_forecast import contextual_adjustment
from src.engine.weather import VN, WeatherClient, WeatherSettings, WeatherUnavailable
from src.engine.weather_advice import weather_preparation_advice
from src.models import MenuItem, SalesDaily
from src.runtime_settings import resolve_store_id


class ForecastingEngine:
    def __init__(self, db_session=None, *, weather_client=None):
        self.db = db_session or SessionLocal()
        self.weather_client = weather_client
        self.store_id = resolve_store_id(self.db, (weather_client.settings if weather_client else WeatherSettings.from_env()).store_id or None)
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
            SalesDaily.quantity_sold,
            SalesDaily.revenue_vnd
        ).join(MenuItem, SalesDaily.sku_id == MenuItem.sku_id).filter(SalesDaily.store_id == self.store_id).order_by(SalesDaily.business_date).all()

        if not records:
            self.df = pd.DataFrame(columns=["business_date", "sku_id", "sku_name", "quantity_sold", "revenue_vnd"])
            self.dates = []
            self.skus = []
            self._sku_series = {}
            self._forecast_cache = {}
            self._backtest_cache = {}
            return

        self.df = pd.DataFrame(records, columns=["business_date", "sku_id", "sku_name", "quantity_sold", "revenue_vnd"])
        self.df['revenue_vnd'] = self.df['revenue_vnd'].astype(float)
        self.df["business_date"] = pd.to_datetime(self.df["business_date"]).dt.date
        version = int(pd.util.hash_pandas_object(self.df, index=True).sum())
        if version != getattr(self, '_data_version', None):
            self._forecast_cache = {}
            self._backtest_cache = {}
        self._data_version = version
        self._actuals = {(row.sku_id, row.business_date): row.quantity_sold for row in self.df.itertuples()}
        self.dates = sorted(self.df["business_date"].unique())
        self.skus = sorted(self.df["sku_id"].unique())
        self._sku_series = {}
        for sku, grp in self.df.groupby("sku_id"):
            sub = grp.sort_values("business_date")
            self._sku_series[sku] = pd.Series(data=sub["quantity_sold"].values, index=sub["business_date"])

    def get_sku_history(self, sku_id: str, up_to_date: date | None = None) -> pd.Series:
        """Returns time series of sales quantity up to up_to_date (O(1) lookup)."""
        s = getattr(self, "_sku_series", {}).get(sku_id)
        if s is None or s.empty:
            sub = self.df[self.df["sku_id"] == sku_id]
            if up_to_date:
                sub = sub[sub["business_date"] <= up_to_date]
            sub = sub.sort_values("business_date")
            return pd.Series(data=sub["quantity_sold"].values, index=sub["business_date"])
        if up_to_date:
            return s[s.index <= up_to_date]
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

    def predict_sku_single(self, sku_id: str, target_date: date, model: str = "day_of_week_ma", cutoff_date=None) -> dict[str, Any]:
        """Predicts sales for one SKU on target_date."""
        cutoff = min(target_date - timedelta(days=1), cutoff_date) if cutoff_date else target_date - timedelta(days=1)
        history = self.get_sku_history(sku_id, up_to_date=cutoff)
        
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

    def run_backtest(self, start_eval_day: int = 15, as_of=None) -> dict[str, Any]:
        """Runs rolling-origin 1-day ahead backtest for all models across days 15..end.
        
        Calculates:
        - MAE: Mean Absolute Error
        - WAPE: Weighted Absolute Percentage Error = sum(|actual - pred|) / sum(actual)
        - Bias: sum(pred - actual) / sum(actual)
        """
        if not hasattr(self, "_backtest_cache"):
            self._backtest_cache = {}
        cache_key = (start_eval_day, as_of)
        if cache_key in self._backtest_cache:
            return self._backtest_cache[cache_key]

        available_dates = [d for d in self.dates if as_of is None or d <= as_of]
        if len(available_dates) <= start_eval_day:
            return {"error": "Insufficient history for backtest"}

        eval_dates = available_dates[start_eval_day:]
        models = ["seasonal_naive", "moving_average", "day_of_week_ma"]

        results = {m: {"actuals": [], "preds": [], "errors": []} for m in models}
        per_sku_results = {sku: {m: {"actuals": [], "preds": []} for m in models} for sku in self.skus}

        for d in eval_dates:
            for sku in self.skus:
                hist = self.get_sku_history(sku, up_to_date=d - timedelta(days=1))
                actual = float(self._actuals.get((sku, d), 0.0))

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

        res = {
            "evaluation_period": f"{eval_dates[0]} to {eval_dates[-1]} ({len(eval_dates)} days)",
            "total_skus": len(self.skus),
            "aggregate_metrics": metrics,
            "best_model": best_model,
            "per_sku_metrics": self._summarize_per_sku_metrics(per_sku_results, models)
        }
        self._backtest_cache[cache_key] = res
        return res

    def _summarize_per_sku_metrics(self, per_sku_results: dict, models: list) -> list[dict[str, Any]]:
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

    def forecast_demand(self, target_date: date | None = None, horizon_days: int = 1, model: str = "auto") -> pd.DataFrame:
        """Forecasts demand for all SKUs for target_date (D+1).
        
        If model == 'auto', selects the model with lowest WAPE from backtest.
        """
        if not 1 <= horizon_days <= 7:
            raise ValueError('horizon_days must be between 1 and 7')
        self._load_sales_data()
        client = self.weather_client or WeatherClient()
        cache_key = (str(target_date), horizon_days, model, client.settings, int(time.time() // 3600))
        if cache_key in self._forecast_cache:
            return self._forecast_cache[cache_key].copy()

        if not target_date:
            target_date = datetime.now(VN).date() + timedelta(days=1)
        cutoff = target_date - timedelta(days=1)
        if not any(day <= cutoff for day in self.dates):
            empty = pd.DataFrame(columns=['target_date', 'sku_id', 'sku_name', 'predicted_qty', 'lower_bound', 'upper_bound', 'model_used', 'confidence'])
            empty.attrs['forecast_context'] = {'status': 'NO_SALES', 'warnings': ['Chưa có lịch sử trước ngày cần dự báo.']}
            return empty

        selected_model = model
        if model == "auto":
            bt = self.run_backtest(start_eval_day=15, as_of=cutoff)
            selected_model = bt.get("best_model", "day_of_week_ma")

        sku_names = dict(self.df[["sku_id", "sku_name"]].drop_duplicates().values)
        forecast_rows = []

        for day_offset in range(horizon_days):
            current_target = target_date + timedelta(days=day_offset)
            for sku in self.skus:
                res = self.predict_sku_single(sku, current_target, model=selected_model, cutoff_date=cutoff)
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
        if df_res.empty:
            df_res.attrs['forecast_context'] = {'status': 'NO_SALES', 'warnings': ['Chưa có dữ liệu bán hàng.']}
            return df_res
        df_res['baseline_qty'] = df_res['predicted_qty']
        context = self._apply_context(df_res, target_date, cutoff, client, model)
        df_res.attrs['forecast_context'] = context
        self._forecast_cache[cache_key] = df_res.copy()
        return df_res

    def _total_baseline(self, day, requested_model):
        selected = requested_model
        if selected == 'auto':
            selected = self.run_backtest(as_of=day - timedelta(days=1)).get('best_model', 'day_of_week_ma')
        functions = {'seasonal_naive': lambda h: self.predict_seasonal_naive(h, day),
                     'moving_average': self.predict_moving_average,
                     'day_of_week_ma': lambda h: self.predict_day_of_week_ma(h, day)}
        return sum(functions[selected](self.get_sku_history(sku, day - timedelta(days=1))) for sku in self.skus)

    def _use_shift_revenue(self, frame, target, latest, cutoff, before, metadata):
        """Days after the last POS item export may still have approved shift closings.

        Those carry the day's money, not cups per item, so the per-item mix stays on the POS history while the
        day's total is scaled by how recent revenue compares with the POS weeks the baseline learned from.
        """
        try:
            from src.engine.revenue import daily_revenue
            recent = daily_revenue(max(latest + timedelta(days=1), cutoff - timedelta(days=13)), cutoff)
        except Exception:  # noqa: BLE001 - shift files unreadable: keep the POS-only forecast and say so below
            recent = pd.DataFrame()
        shift_days = recent[recent['shift_count'] > 0] if not recent.empty else recent
        fmt = lambda day: day.strftime('%d/%m/%Y')  # noqa: E731
        if shift_days.empty:
            metadata['warnings'].append(f'Chưa có doanh thu ngày {fmt(cutoff)} (chưa có chốt ca được duyệt hay dữ liệu máy POS); '
                                        f'dữ liệu bán gần nhất là ngày {fmt(latest)}.')
            return
        window = before[before['business_date'] > latest - timedelta(days=28)]
        daily = window.groupby('business_date')[['quantity_sold', 'revenue_vnd']].sum()
        cups_total, revenue_total = float(daily['quantity_sold'].sum()), float(daily['revenue_vnd'].sum())
        last_day = max(shift_days['business_date'])
        metadata['as_of_revenue_date'] = str(last_day)
        metadata['source_refs'] = [*metadata['source_refs'], 'shift_reports:approved']
        row = shift_days[shift_days['business_date'] == cutoff]
        if not cups_total or not revenue_total:
            if not row.empty:
                metadata['previous_sales'] = {'date': str(cutoff), 'cups': None, 'source': 'Chốt ca đã duyệt',
                                              'revenue': float(row['shift_collected_vnd'].iloc[0])}
            return
        price = revenue_total / cups_total
        estimated = shift_days['shift_collected_vnd'] / price
        factor = float(np.clip(estimated.mean() / (cups_total / len(daily)), 0.7, 1.3))
        mask = frame['target_date'] == target
        for column in ['predicted_qty', 'lower_bound', 'upper_bound']:
            frame.loc[mask, column] = (frame.loc[mask, column] * factor).round(1)
        if 'baseline_qty' in frame:
            frame.loc[mask, 'baseline_qty'] = (frame.loc[mask, 'baseline_qty'] * factor).round(1)
        frame.loc[mask, 'model_used'] = frame.loc[mask, 'model_used'] + '+doanh_thu_chot_ca'
        frame.loc[mask, 'confidence'] = 'LOW'
        if not row.empty:
            metadata['previous_sales'] = {'date': str(cutoff), 'cups': round(float(estimated[row.index].iloc[0])),
                                          'cups_estimated': True, 'source': 'Chốt ca đã duyệt',
                                          'revenue': float(row['shift_collected_vnd'].iloc[0])}
        days_text = ', '.join(fmt(day) for day in shift_days['business_date'])
        metadata['shift_revenue_adjustment'] = {'days': [str(day) for day in shift_days['business_date']],
                                                'factor': round(factor, 3), 'avg_price_vnd': round(price)}
        metadata['notes'].append(
            f'Đã dùng doanh thu chốt ca đã duyệt ngày {days_text}. Máy POS mới có số ly theo món đến ngày {fmt(latest)}, '
            f'nên tỉ lệ từng món vẫn theo lịch sử đó; tổng số ly được chỉnh ×{factor:.2f} theo doanh thu chốt ca '
            f'(giá trung bình khoảng {price:,.0f} đ/ly).')

    def _apply_context(self, frame, target, cutoff, client, model):
        cfg = client.settings
        before = self.df[self.df['business_date'] <= cutoff]
        latest = max(before['business_date']) if not before.empty else None
        metadata = {'status': 'DISABLED' if not cfg.enabled else 'PENDING',
                    'as_of_sales_date': str(latest) if latest else None, 'target_date': str(target),
                    'location': cfg.location_label, 'opening_hours': f'{cfg.opening_hour:02d}:00–{cfg.closing_hour:02d}:00',
                    'warnings': [], 'days': [], 'source_refs': ['table:sales_daily']}
        previous_rows = before[before['business_date'] == cutoff]
        metadata['previous_sales'] = ({'date': str(cutoff), 'cups': float(previous_rows['quantity_sold'].sum()),
                                       'revenue': float(previous_rows['revenue_vnd'].sum()), 'source': 'Máy POS'}
                                      if not previous_rows.empty else None)
        metadata['notes'] = []
        if latest and latest < cutoff:
            self._use_shift_revenue(frame, target, latest, cutoff, before, metadata)
        if not cfg.enabled or before.empty:
            metadata['warnings'].append('Dự báo chưa tính thời tiết vì tính năng thời tiết đang tắt (bật bằng WEATHER_ENABLED=true).'
                                        if not cfg.enabled else 'Không có lịch sử trước ngày cần dự báo.')
            return metadata
        start = max(min(before['business_date']), cutoff - timedelta(days=100))
        try:
            history = client.history(start, cutoff)
            if target < datetime.now(VN).date():
                target_weather = client.history(target, target)['anticipated'].get(target)
                retrieved_at = history['fetched_at']
            else:
                live = client.forecast(target, target)
                target_weather = live['days'].get(target)
                retrieved_at = live['fetched_at']
            mask = frame['target_date'] == target
            total = float(frame.loc[mask, 'baseline_qty'].sum())
            adjustment = contextual_adjustment(before, target, history, target_weather, total,
                                                lambda day: self._total_baseline(day, model))
            factor = adjustment['factor']
            for column in ['predicted_qty', 'lower_bound', 'upper_bound']:
                frame.loc[mask, column] = (frame.loc[mask, column] * factor).round(1)
            if factor != 1:
                frame.loc[mask, 'model_used'] = frame.loc[mask, 'model_used'] + '+' + adjustment['status'].lower()
            frame.loc[mask, 'confidence'] = 'LOW' if adjustment['status'] not in {'WEATHER_VALIDATED', 'SALES_CONTEXT_ONLY'} else 'MEDIUM'
            metadata.update(status=adjustment['status'], retrieved_at=retrieved_at, days=[{'target_date': str(target), **adjustment}],
                            comparison={'previous_date': str(cutoff), 'previous_weather_estimate': history['reference'].get(cutoff),
                                        'target_weather_forecast': target_weather},
                            source_refs=['table:sales_daily', 'weather:Open-Meteo_ECMWF_IFS'])
            if adjustment['status'] != 'WEATHER_VALIDATED':
                metadata['warnings'].append('Chưa chứng minh được thời tiết cải thiện dự báo; không tự đặt hệ số giảm khi mưa.')
            if len(frame['target_date'].unique()) > 1:
                metadata['warnings'].append('Chỉ ngày đầu có đủ dữ liệu doanh số liền trước để xét mô hình bối cảnh; các ngày sau dùng dự báo nền.')
        except (WeatherUnavailable, ValueError, KeyError, np.linalg.LinAlgError):
            metadata['status'] = 'WEATHER_UNAVAILABLE'
            metadata['warnings'].append('Chưa lấy được thời tiết hợp lệ; giữ dự báo nền, không giả định trời nắng hay mưa.')
            frame['confidence'] = 'LOW'
        advice = weather_preparation_advice(metadata)
        if advice:
            metadata['operational_advice'] = advice
        return metadata


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
