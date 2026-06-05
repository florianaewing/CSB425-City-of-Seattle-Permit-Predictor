"""
Seattle Permit Predictor — FastAPI Backend
Serves quantile model predictions (optimistic / typical / pessimistic)
from ModelWeights_Quantile.joblib.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import numpy as np
import pandas as pd
import joblib
import datetime
import os
from pathlib import Path

# ── Load model bundle at startup ──────────────────────────────────
MODEL_PATH = Path(__file__).parent / 'ModelWeights_Quantile.joblib'

print(f'Loading model from {MODEL_PATH}...')
bundle = joblib.load(MODEL_PATH)
preprocessor  = bundle['preprocessor']
models        = bundle['models']       # {'optimistic': lgb, 'typical': lgb, 'pessimistic': lgb}
cat_features  = bundle['cat_features']
num_features  = bundle['num_features']
all_features  = bundle['feature_names']
print('Model loaded successfully.')

# ── App setup ─────────────────────────────────────────────────────
app = FastAPI(
    title='Seattle Permit Predictor API',
    description='Quantile regression model for permit review time prediction',
    version='1.0.0'
)

# Allow requests from GitHub Pages and localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'https://florianaewing.github.io',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'http://localhost:3000',
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# ── Request / Response schemas ─────────────────────────────────────
class PredictRequest(BaseModel):
    permittypedesc:            str
    permitclass:               str
    zone_family:               str
    review_complexity_max:     Optional[str]  = 'Unknown'
    latitude:                  Optional[float] = None
    longitude:                 Optional[float] = None
    housingunitsadded:         Optional[float] = None
    app_year:                  Optional[int]   = None
    app_month:                 Optional[int]   = None
    comment_n_distinct_cycles: Optional[float] = None
    comment_n_rows:            Optional[float] = None

class TimelineEstimate(BaseModel):
    days:   int
    months: float
    label:  str   # formatted string e.g. "4.3 months (132 days)"

class PredictResponse(BaseModel):
    optimistic:  TimelineEstimate
    typical:     TimelineEstimate
    pessimistic: TimelineEstimate

# ── Helper ─────────────────────────────────────────────────────────
def format_timeline(days: float) -> TimelineEstimate:
    months = days / 30.44
    return TimelineEstimate(
        days=int(round(days)),
        months=round(months, 1),
        label=f'{months:.1f} months ({int(round(days))} days)'
    )

# ── Endpoints ──────────────────────────────────────────────────────
@app.get('/')
def root():
    return {
        'status': 'online',
        'model':  'Seattle Permit Predictor — Quantile Model',
        'endpoints': ['/predict', '/health']
    }

@app.get('/health')
def health():
    return {'status': 'healthy', 'timestamp': datetime.datetime.now().isoformat()}

@app.post('/predict', response_model=PredictResponse)
def predict(req: PredictRequest):
    try:
        now = datetime.datetime.now()

        row = pd.DataFrame([{
            'permittypedesc':            req.permittypedesc,
            'permitclass':               req.permitclass,
            'zone_family':               req.zone_family,
            'review_complexity_max':     req.review_complexity_max or 'Unknown',
            'latitude':                  req.latitude            if req.latitude            is not None else np.nan,
            'longitude':                 req.longitude           if req.longitude           is not None else np.nan,
            'log_housingunitsadded':     np.log1p(req.housingunitsadded) if req.housingunitsadded is not None else np.nan,
            'app_year':                  req.app_year            if req.app_year            is not None else now.year,
            'app_month':                 req.app_month           if req.app_month           is not None else now.month,
            'comment_n_distinct_cycles': req.comment_n_distinct_cycles if req.comment_n_distinct_cycles is not None else np.nan,
            'comment_n_rows':            req.comment_n_rows            if req.comment_n_rows            is not None else np.nan,
        }])

        X_row = preprocessor.transform(row)

        results = {}
        for name, model in models.items():
            pred_log  = model.predict(X_row)[0]
            pred_days = float(np.expm1(pred_log))
            pred_days = max(1.0, pred_days)
            results[name] = format_timeline(pred_days)

        return PredictResponse(
            optimistic=results['optimistic'],
            typical=results['typical'],
            pessimistic=results['pessimistic'],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))