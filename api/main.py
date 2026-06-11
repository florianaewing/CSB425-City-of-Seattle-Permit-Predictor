"""
Seattle Permit  FastAPI BackendPredictor 
Serves quantile model predictions + SDCI permit history lookup
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import numpy as np
import pandas as pd
import joblib
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from sdci_scraper import SDCIScraper

MODEL_PATH = Path(__file__).parent / 'ModelWeights_Quantile.joblib'
print(f'Loading model from {MODEL_PATH}...')
bundle = joblib.load(MODEL_PATH)
preprocessor = bundle['preprocessor']
models = bundle['models']
print('Model loaded successfully.')

app = FastAPI(
    title='Seattle Permit Predictor API',
    description='Quantile regression + SDCI permit history',
    version='1.0.0'
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'https://florianaewing.github.io',
        'https://florianaewing.github.io/CSB425-City-of-Seattle-Permit-Predictor',
        'https://florianaewing.github.io/CSB425-City-of-Seattle-Permit-Predictor/',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'http://localhost:3000',
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

class PredictRequest(BaseModel):
    permittypedesc: str
    permitclass: str
    zone_family: str
    review_complexity_max: Optional[str] = 'Unknown'
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    housingunitsadded: Optional[float] = None
    app_year: Optional[int] = None
    app_month: Optional[int] = None
    comment_n_distinct_cycles: Optional[float] = None
    comment_n_rows: Optional[float] = None

class TimelineEstimate(BaseModel):
    days: int
    months: float
    label: str

class PredictResponse(BaseModel):
    optimistic: TimelineEstimate
    typical: TimelineEstimate
    pessimistic: TimelineEstimate

class SDCIReportRequest(BaseModel):
    address: str

def format_timeline(days: float) -> TimelineEstimate:
    months = days / 30.44
    return TimelineEstimate(
        days=int(round(days)),
        months=round(months, 1),
        label=f'{months:.1f} months ({int(round(days))} days)'
    )

@app.get('/')
def root():
    return {
        'status': 'online',
        'endpoints': ['/predict', '/sdci-report', '/health']
    }

@app.get('/health')
def health():
    return {'status': 'healthy', 'timestamp': datetime.datetime.now().isoformat()}

@app.post('/predict', response_model=PredictResponse)
def predict(req: PredictRequest):
    try:
        now = datetime.datetime.now()
        row = pd.DataFrame([{
            'permittypedesc': req.permittypedesc,
            'permitclass': req.permitclass,
            'zone_family': req.zone_family,
            'review_complexity_max': req.review_complexity_max or 'Unknown',
            'latitude': req.latitude if req.latitude is not None else np.nan,
            'longitude': req.longitude if req.longitude is not None else np.nan,
            'log_housingunitsadded': np.log1p(req.housingunitsadded) if req.housingunitsadded is not None else np.nan,
            'app_year': req.app_year if req.app_year is not None else now.year,
            'app_month': req.app_month if req.app_month is not None else now.month,
            'comment_n_distinct_cycles': req.comment_n_distinct_cycles if req.comment_n_distinct_cycles is not None else np.nan,
            'comment_n_rows': req.comment_n_rows if req.comment_n_rows is not None else np.nan,
        }])
        X_row = preprocessor.transform(row)
        results = {}
        for name, model in models.items():
            pred_log = model.predict(X_row)[0]
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

@app.post('/sdci-report')
async def sdci_report(req: SDCIReportRequest):
    """Fetch SDCI permit history for an address"""
    try:
        report = SDCIScraper.search_address(req.address)
        return SDCIScraper.format_report(report)
    except Exception as e:
        return {
            'success': False,
            'address': req.address,
            'error': f'Server error: {str(e)}'
        }
