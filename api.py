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
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from auth import get_current_user
from auth import router as auth_router
from config import settings
from connections import (
    datasource_connected,
    get_active_config,
    get_connected_sources,
    snowflake_requires_passcode,
    _seed_defaults,
)
from connections import router as connections_router
from ghl_client import GHLClient
from hipaa_compliance import hipaa_manager
from query_engine import QueryEngine, detect_query_sources
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


# Determine allowed CORS origin from environment.
# GCP deployments set FRONTEND_ORIGIN; fall back to localhost for dev.
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
    load_fresh: bool = True
    limit_per_entity: int = Field(default=500, ge=1, le=5000)
    snowflake_passcode: Optional[str] = Field(default=None, max_length=10)


class RefreshRequest(BaseModel):
    include_ghl: Optional[bool] = None
    include_snowflake: Optional[bool] = None
    limit_per_entity: int = Field(default=500, ge=1, le=5000)
    snowflake_passcode: Optional[str] = Field(default=None, max_length=10)


def _fetch_datasets(
    include_ghl: bool,
    include_snowflake: bool,
    snowflake_passcode: Optional[str] = None,
    limit_per_entity: int = 500,
) -> tuple[dict, dict, dict]:
    """Fetch data from independent connected sources into memory-ready datasets."""
    datasets: dict = {}
    errors: dict = {}
    skipped: dict = {}

    if include_ghl:
        if not datasource_connected('ghl'):
            skipped['ghl'] = 'GoHighLevel is not connected'
        else:
            try:
                ghl = GHLClient(get_active_config('ghl'))
                datasets['ghl'] = ghl.get_all_data()
            except Exception as e:
                logger.error(f"GHL fetch failed: {e}")
                errors['ghl'] = str(e)

    if include_snowflake:
        if not datasource_connected('snowflake'):
            skipped['snowflake'] = 'Snowflake is not connected'
        else:
            sf_config = dict(get_active_config('snowflake') or {})
            if snowflake_passcode:
                sf_config['passcode'] = snowflake_passcode.strip()
            reader = SnowflakeReader(sf_config)
            try:
                reader.connect(passcode=snowflake_passcode)
                datasets['snowflake'] = reader.fetch_all(limit_per_entity)
            except Exception as e:
                logger.error(f"Snowflake fetch failed: {e}")
                msg = str(e)
                if snowflake_requires_passcode(sf_config) and (
                    'TOTP' in msg or 'passcode' in msg.lower()
                ):
                    msg += (
                        ' — Enter a fresh 6-digit MFA code from your authenticator '
                        '(codes expire every ~30 seconds), or switch to key-pair auth.'
                    )
                errors['snowflake'] = msg
            finally:
                try:
                    reader.disconnect()
                except Exception:
                    pass

    return datasets, errors, skipped


@app.get('/api/health')
def health():
    connected = get_connected_sources()
    source_chunks = {
        source: sum(1 for c in engine.chunks if c['source'] == source)
        for source in ('snowflake', 'ghl')
    }
    return {
        'status': 'ok',
        'indexed_chunks': len(engine.chunks),
        'last_indexed': engine.last_indexed,
        'connected_sources': connected,
        'indexed_sources': engine.get_indexed_sources(),
        'source_chunks': source_chunks,
        'record_counts': engine.record_counts,
        'snowflake_requires_passcode': (
            connected['snowflake'] and snowflake_requires_passcode()
        ),
        'timestamp': datetime.utcnow().isoformat(),
    }


@app.post('/api/index/refresh')
def refresh_index(req: RefreshRequest, user: str = Depends(get_current_user)):
    """Fetch data from connected GHL and/or Snowflake sources and rebuild the in-memory index"""
    _seed_defaults()
    connected = get_connected_sources()
    include_ghl = req.include_ghl if req.include_ghl is not None else connected['ghl']
    include_snowflake = (
        req.include_snowflake if req.include_snowflake is not None else connected['snowflake']
    )

    datasets, errors, skipped = _fetch_datasets(
        include_ghl=include_ghl,
        include_snowflake=include_snowflake,
        snowflake_passcode=req.snowflake_passcode,
        limit_per_entity=req.limit_per_entity,
    )

    if not datasets:
        raise HTTPException(
            status_code=502,
            detail={
                'message': 'No data sources available',
                'errors': errors,
                'skipped': skipped,
                'connected_sources': connected,
                'hint': (
                    'Connect Snowflake and/or GoHighLevel in DB Connectors first. '
                    'For password auth, enter a fresh TOTP code. For GCP, use key-pair '
                    'auth (SNOWFLAKE_PRIVATE_KEY) to avoid MFA on every query.'
                ),
            },
        )

    engine.index_data(datasets, merge=True)

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
        'skipped': skipped,
        'indexed_sources': engine.get_indexed_sources(),
    }


@app.post('/api/query')
def query(req: QueryRequest, user: str = Depends(get_current_user)):
    """Load data from connected sources into memory, then answer a natural-language question"""
    _seed_defaults()
    connected = get_connected_sources()
    load_errors: dict = {}
    load_skipped: dict = {}

    if not connected['ghl'] and not connected['snowflake']:
        return {
            'answer': (
                'No data sources connected. Go to DB Connectors, test your Snowflake '
                'and/or GoHighLevel connection, then ask a question here.'
            ),
            'results': [],
            'total_chunks': len(engine.chunks),
            'connected_sources': connected,
            'indexed_sources': engine.get_indexed_sources(),
            'load_errors': load_errors,
        }

    if req.load_fresh:
        sf_config = get_active_config('snowflake') or {}
        if (
            connected['snowflake']
            and snowflake_requires_passcode(sf_config)
            and not (req.snowflake_passcode or '').strip()
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    'Snowflake uses password + MFA. Enter a fresh 6-digit code, or switch '
                    'the connection to key-pair authentication in DB Connectors.'
                ),
            )

        datasets, load_errors, load_skipped = _fetch_datasets(
            include_ghl=connected['ghl'],
            include_snowflake=connected['snowflake'],
            snowflake_passcode=req.snowflake_passcode,
            limit_per_entity=req.limit_per_entity,
        )
        if datasets:
            engine.index_data(datasets, merge=True)

    indexed = engine.get_indexed_sources()
    search_sources = detect_query_sources(req.question, indexed)

    try:
        result = engine.query(
            req.question,
            top_k=req.top_k,
            mask_phi=req.mask_phi,
            sources=search_sources,
        )
        result['connected_sources'] = connected
        result['load_errors'] = load_errors
        result['load_skipped'] = load_skipped
        if load_errors and result['results']:
            result['answer'] += ' (Some sources failed to load; showing available data.)'
        elif load_errors and not result['results']:
            failed = '; '.join(f'{k}: {v}' for k, v in load_errors.items())
            result['answer'] = f'Could not load data into memory. {failed}'
        return result
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
        _seed_defaults()
        ghl = GHLClient(get_active_config('ghl'))
        loader = SnowflakeLoader(get_active_config('snowflake'))
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


# Serve the exported Next.js frontend (single-service deploy).
# Built via: cd frontend && NEXT_OUTPUT=export npm run build
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'out')
if os.path.isdir(FRONTEND_DIR):
    app.mount('/', StaticFiles(directory=FRONTEND_DIR, html=True), name='frontend')
else:
    logger.warning(
        'Frontend build directory not found at %s — static files will not be served. '
        'Run the build script to compile the Next.js frontend.',
        FRONTEND_DIR,
    )


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('api:app', host='0.0.0.0', port=int(os.environ.get('PORT', 8000)), reload=True)
