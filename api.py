"""
FastAPI backend for the GHL + Snowflake HIPAA query app.

Endpoints:
- GET  /api/health          - health check
- POST /api/index/refresh   - pull data from GHL and Snowflake, rebuild index
- POST /api/query           - free-text question over the indexed data
- POST /api/sync            - run the GHL -> Snowflake sync pipeline
"""
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from auth import get_current_user
from auth import router as auth_router
from config import settings
from connections import router as connections_router
from ghl_client import GHLClient
from hipaa_compliance import hipaa_manager
from query_engine import QueryEngine
from snowflake_loader import SnowflakeLoader
from snowflake_reader import SnowflakeReader

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title='GHL + Snowflake HIPAA Query API',
    version='1.0.0',
)

FRONTEND_ORIGIN = os.environ.get('FRONTEND_ORIGIN', 'http://localhost:3000')

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(auth_router)
app.include_router(connections_router)

engine = QueryEngine()


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=25)
    mask_phi: bool = True


class RefreshRequest(BaseModel):
    include_ghl: bool = True
    include_snowflake: bool = True
    limit_per_entity: int = Field(default=500, ge=1, le=5000)


@app.get('/api/health')
def health():
    return {
        'status': 'ok',
        'indexed_chunks': len(engine.chunks),
        'last_indexed': engine.last_indexed,
        'timestamp': datetime.utcnow().isoformat(),
    }


@app.post('/api/index/refresh')
def refresh_index(req: RefreshRequest, user: str = Depends(get_current_user)):
    """Fetch data from GHL and/or Snowflake and rebuild the query index"""
    datasets = {}
    errors = {}

    if req.include_ghl:
        try:
            ghl = GHLClient()
            datasets['ghl'] = ghl.get_all_data()
        except Exception as e:
            logger.error(f"GHL fetch failed: {e}")
            errors['ghl'] = str(e)

    if req.include_snowflake:
        reader = SnowflakeReader()
        try:
            reader.connect()
            datasets['snowflake'] = reader.fetch_all(req.limit_per_entity)
        except Exception as e:
            logger.error(f"Snowflake fetch failed: {e}")
            errors['snowflake'] = str(e)
        finally:
            try:
                reader.disconnect()
            except Exception:
                pass

    if not datasets:
        raise HTTPException(
            status_code=502,
            detail={'message': 'No data sources available', 'errors': errors},
        )

    engine.index_data(datasets)

    counts = {
        source: {entity: len(records) for entity, records in entities.items()}
        for source, entities in datasets.items()
    }

    return {
        'status': 'ok',
        'indexed_chunks': len(engine.chunks),
        'last_indexed': engine.last_indexed,
        'record_counts': counts,
        'errors': errors,
    }


@app.post('/api/query')
def query(req: QueryRequest, user: str = Depends(get_current_user)):
    """Answer a free-text question over the indexed GHL + Snowflake data"""
    try:
        return engine.query(req.question, top_k=req.top_k, mask_phi=req.mask_phi)
    except Exception as e:
        logger.error(f"Query failed: {e}")
        hipaa_manager.log_audit_event('query_failed', {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat(),
        })
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/sync')
def sync(user: str = Depends(get_current_user)):
    """Run the full GHL -> Snowflake sync pipeline"""
    try:
        ghl = GHLClient()
        loader = SnowflakeLoader()
        loader.connect()
        try:
            data = ghl.get_all_data()
            loader.load_all_data(data)
        finally:
            loader.disconnect()
        return {
            'status': 'ok',
            'contacts': len(data['contacts']),
            'conversations': len(data['conversations']),
            'opportunities': len(data['opportunities']),
        }
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('api:app', host='0.0.0.0', port=int(os.environ.get('PORT', 8000)), reload=True)
