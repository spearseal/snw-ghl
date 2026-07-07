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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
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
from email_followup import (
    EmailSettings,
    SendFollowupRequest,
    load_email_settings,
    save_email_settings,
    send_followup_emails,
)
from insights import compute_insights
from medspa_insights import compute_ceo_tasks, evaluate_compliance
from intake_store import HealthIntakeForm, save_intake
from treatment_insights import compute_plan_for_intake, compute_treatment_plans
from revenue_insights import compute_revenue_growth
from reports import compute_reports, report_to_csv_rows
from search_service import search_datasets
from reactivate_campaign import (
    ReactivateSendRequest,
    ReactivateSettings,
    compute_reactivate_campaign,
    export_all_followup_csv,
    export_manual_followup_csv,
    load_reactivate_settings,
    save_reactivate_settings,
    send_reactivate_emails,
)
from hipaa_compliance import hipaa_manager
from query_engine import QueryEngine, detect_query_sources
from snowflake_agent import SnowflakeAgent
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

DATA_DIR = os.environ.get(
    'DATA_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
)


@app.on_event('startup')
async def startup_event():
    """Ensure writable directories exist on Cloud Run."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, 'semantic_layer'), exist_ok=True)
    log_dir = os.path.dirname(settings.audit_log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    logger.info('App startup complete — data dir: %s', DATA_DIR)


def _register_semantic_router() -> None:
    try:
        from semantic_layer.router import router as semantic_router
        app.include_router(semantic_router)
        logger.info('Semantic layer API registered')
    except Exception as exc:
        logger.error('Semantic layer unavailable (app will run without it): %s', exc)


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
_register_semantic_router()

engine = QueryEngine()

INDEX_TTL_SECONDS = int(os.environ.get('INDEX_TTL_SECONDS', '300'))


def _index_fresh_for_source(source: str) -> bool:
    """True when in-memory chunks for this source are younger than INDEX_TTL_SECONDS."""
    if source not in engine.get_indexed_sources():
        return False
    if not engine.last_indexed or not any(c['source'] == source for c in engine.chunks):
        return False
    try:
        last = datetime.fromisoformat(engine.last_indexed.replace('Z', '+00:00'))
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - last).total_seconds()
        return age < INDEX_TTL_SECONDS
    except (ValueError, TypeError):
        return False


def _sources_needing_refresh(
    connected: Dict[str, bool],
    load_fresh: bool,
    snowflake_passcode: Optional[str],
) -> Dict[str, bool]:
    """Decide per-source whether to re-fetch before query (skip when cache is fresh)."""
    if not load_fresh:
        return {'ghl': False, 'snowflake': False}
    force_sf = bool((snowflake_passcode or '').strip())
    return {
        'ghl': connected.get('ghl', False) and not _index_fresh_for_source('ghl'),
        'snowflake': connected.get('snowflake', False) and (
            force_sf or not _index_fresh_for_source('snowflake')
        ),
    }


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


class SmartQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    limit: int = Field(default=100, ge=1, le=1000)
    top_k: int = Field(default=5, ge=1, le=25)
    mask_phi: bool = True
    load_fresh: bool = True
    limit_per_entity: int = Field(default=500, ge=1, le=5000)
    snowflake_passcode: Optional[str] = Field(default=None, max_length=10)


SOURCE_LABELS = {
    'snowflake': 'Snowflake',
    'ghl': 'GoHighLevel',
}


def _build_combined_answer(
    results_by_source: Dict[str, Dict[str, Any]],
    sources_queried: List[str],
    load_errors: Dict[str, str],
) -> str:
    parts: List[str] = []
    for source in sources_queried:
        label = SOURCE_LABELS.get(source, source)
        block = results_by_source.get(source)
        if block and block.get('answer'):
            parts.append(f'[{label}] {block["answer"]}')
        elif load_errors.get(source):
            parts.append(f'[{label}] Could not query: {load_errors[source]}')

    if parts:
        return ' '.join(parts)

    if load_errors:
        failed = '; '.join(f'{k}: {v}' for k, v in load_errors.items())
        return f'No results from connected sources. {failed}'

    return 'No results found in connected data sources for your question.'


@app.post('/api/smart/query')
def smart_query(req: SmartQueryRequest, user: str = Depends(get_current_user)):
    """
    Unified query across all connected sources.
    Refreshes memory from Snowflake and/or GHL, then returns labeled results per datasource.
    """
    _seed_defaults()
    connected = get_connected_sources()
    load_errors: Dict[str, str] = {}
    load_skipped: Dict[str, str] = {}
    results_by_source: Dict[str, Dict[str, Any]] = {}
    used_cached_index = False

    if not connected['ghl'] and not connected['snowflake']:
        return {
            'answer': (
                'No data sources connected. Go to DB Connectors, test Snowflake '
                'and/or GoHighLevel, then query again.'
            ),
            'connected_sources': connected,
            'indexed_sources': engine.get_indexed_sources(),
            'sources_queried': [],
            'results_by_source': {},
            'load_errors': load_errors,
            'load_skipped': load_skipped,
        }

    if req.load_fresh:
        refresh_plan = _sources_needing_refresh(
            connected, req.load_fresh, req.snowflake_passcode
        )
        if refresh_plan['ghl'] or refresh_plan['snowflake']:
            datasets, fetch_errors, load_skipped = _fetch_datasets(
                include_ghl=refresh_plan['ghl'],
                include_snowflake=refresh_plan['snowflake'],
                snowflake_passcode=req.snowflake_passcode,
                limit_per_entity=req.limit_per_entity,
            )
            load_errors.update(fetch_errors)
            if datasets:
                engine.index_data(datasets, merge=True)
        else:
            used_cached_index = True
            load_skipped = {
                k: 'Using cached in-memory index (refresh skipped)'
                for k, v in connected.items()
                if v and _index_fresh_for_source(k)
            }

    available = [s for s in ('snowflake', 'ghl') if connected.get(s)]
    sources_queried = detect_query_sources(req.question, available)

    # Ensure GHL memory has data before BM25 search (lazy load if cache was skipped).
    if (
        'ghl' in sources_queried
        and connected['ghl']
        and not any(c['source'] == 'ghl' for c in engine.chunks)
    ):
        ghl_data, ghl_errors, _ = _fetch_datasets(
            include_ghl=True,
            include_snowflake=False,
            limit_per_entity=req.limit_per_entity,
        )
        load_errors.update(ghl_errors)
        if ghl_data:
            engine.index_data(ghl_data, merge=True)

    def _run_snowflake() -> None:
        nonlocal load_errors
        if 'snowflake' not in sources_queried or not connected['snowflake']:
            return
        sf_config = dict(get_active_config('snowflake') or {})
        if snowflake_requires_passcode(sf_config) and not (req.snowflake_passcode or '').strip():
            load_errors['snowflake'] = (
                'Snowflake uses password + MFA. Enter a fresh 6-digit code, or switch '
                'to key-pair authentication in DB Connectors.'
            )
            return
        reader = None
        try:
            if req.snowflake_passcode:
                sf_config['passcode'] = req.snowflake_passcode.strip()
            reader = SnowflakeReader(sf_config)
            reader.connect(passcode=req.snowflake_passcode)
            agent = SnowflakeAgent(reader)
            sf_result = agent.query(
                req.question,
                limit=req.limit,
                mask_phi=req.mask_phi,
            )
            results_by_source['snowflake'] = {
                'datasource': SOURCE_LABELS['snowflake'],
                **sf_result,
            }
        except Exception as e:
            logger.error(f"Snowflake smart query failed: {e}")
            msg = str(e)
            if snowflake_requires_passcode(sf_config) and (
                'TOTP' in msg or 'passcode' in msg.lower()
            ):
                msg += (
                    ' — Enter a fresh 6-digit MFA code from your authenticator, '
                    'or switch to key-pair auth.'
                )
            load_errors['snowflake'] = msg
        finally:
            if reader:
                try:
                    reader.disconnect()
                except Exception:
                    pass

    def _run_ghl() -> None:
        nonlocal load_errors
        if 'ghl' not in sources_queried or not connected['ghl']:
            return
        try:
            ghl_result = engine.query(
                req.question,
                top_k=req.top_k,
                mask_phi=req.mask_phi,
                sources=['ghl'],
            )
            results_by_source['ghl'] = {
                'datasource': SOURCE_LABELS['ghl'],
                **ghl_result,
            }
            if load_errors.get('ghl'):
                results_by_source['ghl']['answer'] = (
                    f"{results_by_source['ghl'].get('answer', '')} "
                    f"(Note: {load_errors['ghl']})"
                ).strip()
        except Exception as e:
            logger.error(f"GHL smart query failed: {e}")
            load_errors['ghl'] = str(e)

    query_futures = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        if 'snowflake' in sources_queried and connected['snowflake']:
            query_futures.append(pool.submit(_run_snowflake))
        if 'ghl' in sources_queried and connected['ghl']:
            query_futures.append(pool.submit(_run_ghl))
        for fut in as_completed(query_futures):
            fut.result()

    answer = _build_combined_answer(results_by_source, sources_queried, load_errors)

    hipaa_manager.log_audit_event('smart_query_executed', {
        'query_hash': hipaa_manager.hash_phi(req.question),
        'sources_queried': sources_queried,
        'connected_sources': connected,
        'timestamp': datetime.utcnow().isoformat(),
    })

    try:
        from semantic_layer.context import semantic_model_exists
        semantic_active = semantic_model_exists()
    except Exception:
        semantic_active = False

    return {
        'answer': answer,
        'connected_sources': connected,
        'indexed_sources': engine.get_indexed_sources(),
        'sources_queried': [SOURCE_LABELS.get(s, s) for s in sources_queried],
        'results_by_source': results_by_source,
        'load_errors': load_errors or None,
        'load_skipped': load_skipped or None,
        'used_cached_index': used_cached_index,
        'total_chunks': len(engine.chunks),
        'semantic_model_active': semantic_active,
    }


class AgentQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    limit: int = Field(default=100, ge=1, le=1000)
    mask_phi: bool = True
    snowflake_passcode: Optional[str] = Field(default=None, max_length=10)


def _snowflake_reader_from_active(passcode: Optional[str] = None) -> SnowflakeReader:
    if not datasource_connected('snowflake'):
        raise HTTPException(
            status_code=422,
            detail='Snowflake is not connected. Test the connection in DB Connectors first.',
        )
    sf_config = dict(get_active_config('snowflake') or {})
    if snowflake_requires_passcode(sf_config) and not (passcode or '').strip():
        raise HTTPException(
            status_code=422,
            detail='Enter a fresh Snowflake MFA code or use key-pair authentication.',
        )
    if passcode:
        sf_config['passcode'] = passcode.strip()
    reader = SnowflakeReader(sf_config)
    reader.connect(passcode=passcode)
    return reader


def _fetch_ghl_dataset(limit_per_entity: int) -> tuple[Optional[dict], dict]:
    errors: dict = {}
    if not datasource_connected('ghl'):
        return None, errors
    try:
        ghl = GHLClient(get_active_config('ghl'))
        ghl_data, ghl_entity_errors = ghl.get_all_data()
        for entity, msg in ghl_entity_errors.items():
            errors[f'ghl.{entity}'] = msg
        return {'ghl': ghl_data}, errors
    except Exception as e:
        logger.error(f"GHL fetch failed: {e}")
        errors['ghl'] = str(e)
        return None, errors


def _fetch_snowflake_dataset(
    snowflake_passcode: Optional[str],
    limit_per_entity: int,
) -> tuple[Optional[dict], dict]:
    errors: dict = {}
    if not datasource_connected('snowflake'):
        return None, errors
    sf_config = dict(get_active_config('snowflake') or {})
    if snowflake_passcode:
        sf_config['passcode'] = snowflake_passcode.strip()
    reader = SnowflakeReader(sf_config)
    try:
        reader.connect(passcode=snowflake_passcode)
        snowflake_data, table_errors = reader.fetch_all(limit_per_entity)
        for entity, msg in table_errors.items():
            errors[f'snowflake.{entity}'] = msg
        total_rows = sum(len(rows) for rows in snowflake_data.values())
        if total_rows == 0 and not table_errors:
            custom = (sf_config.get('custom_tables') or '').strip()
            table_list = (
                custom
                if custom
                else ', '.join(SnowflakeReader.GHL_TABLES.values())
            )
            errors['snowflake'] = (
                f'Connected but all tables are empty ({table_list}). '
                'Add rows in Snowflake or set custom_tables on the connection.'
            )
        elif total_rows == 0 and table_errors:
            expected = ', '.join(reader.tables_to_fetch().values())
            errors['snowflake'] = (
                'Connected but could not read tables. Expected in your '
                f'database/schema: {expected}. See snowflake.<table> errors for details.'
            )
        return {'snowflake': snowflake_data}, errors
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
        return None, errors
    finally:
        try:
            reader.disconnect()
        except Exception:
            pass


def _fetch_datasets(
    include_ghl: bool,
    include_snowflake: bool,
    snowflake_passcode: Optional[str] = None,
    limit_per_entity: int = 500,
) -> tuple[dict, dict, dict]:
    """Fetch data from connected sources in parallel into memory-ready datasets."""
    datasets: dict = {}
    errors: dict = {}
    skipped: dict = {}

    if not include_ghl:
        skipped['ghl'] = 'GoHighLevel refresh not requested'
    elif not datasource_connected('ghl'):
        skipped['ghl'] = 'GoHighLevel is not connected'

    if not include_snowflake:
        skipped['snowflake'] = 'Snowflake refresh not requested'
    elif not datasource_connected('snowflake'):
        skipped['snowflake'] = 'Snowflake is not connected'

    futures = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        if include_ghl and datasource_connected('ghl'):
            futures['ghl'] = pool.submit(_fetch_ghl_dataset, limit_per_entity)
        if include_snowflake and datasource_connected('snowflake'):
            futures['snowflake'] = pool.submit(
                _fetch_snowflake_dataset, snowflake_passcode, limit_per_entity
            )
        for key, fut in futures.items():
            partial, partial_errors = fut.result()
            errors.update(partial_errors)
            if partial:
                datasets.update(partial)

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
    available = [s for s in indexed if connected.get(s)]
    search_sources = detect_query_sources(req.question, available or indexed)

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
        elif (
            not result['results']
            and connected.get('snowflake')
            and len(engine.chunks) == 0
        ):
            sf_config = get_active_config('snowflake') or {}
            reader = SnowflakeReader(sf_config)
            expected = ', '.join(reader.tables_to_fetch().values())
            result['answer'] = (
                f'Snowflake is connected but no rows were loaded from: {expected}. '
                'Edit the Snowflake connection and set Tables to query (e.g. testtable), '
                'then Refresh Memory.'
            )
        return result
    except Exception as e:
        logger.error(f"Query failed: {e}")
        hipaa_manager.log_audit_event('query_failed', {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat(),
        })
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/snowflake/schema')
def snowflake_schema(
    snowflake_passcode: Optional[str] = None,
    user: str = Depends(get_current_user),
):
    """Discover all tables and columns in the connected Snowflake database/schema."""
    _seed_defaults()
    reader = _snowflake_reader_from_active(snowflake_passcode)
    try:
        agent = SnowflakeAgent(reader)
        schema = agent.analyze_schema(refresh=True)
        return schema
    finally:
        reader.disconnect()


@app.post('/api/agent/query')
def agent_query(req: AgentQueryRequest, user: str = Depends(get_current_user)):
    """
    Schema-aware agent: analyzes all tables in the configured database/schema,
    generates read-only SQL from your question, and returns live data.
    """
    _seed_defaults()
    reader = _snowflake_reader_from_active(req.snowflake_passcode)
    try:
        agent = SnowflakeAgent(reader)
        return agent.query(
            req.question,
            limit=req.limit,
            mask_phi=req.mask_phi,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Agent query failed: {e}")
        hipaa_manager.log_audit_event('agent_query_failed', {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat(),
        })
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        reader.disconnect()


@app.get('/api/insights')
def get_insights(
    snowflake_passcode: Optional[str] = None,
    limit_per_entity: int = 500,
    inactive_days: int = 90,
    user: str = Depends(get_current_user),
):
    """Marketing KPIs, CEO tasks, and follow-up candidates from connected sources."""
    _seed_defaults()
    connected = get_connected_sources()
    if not connected['ghl'] and not connected['snowflake']:
        return {
            'connected_sources': connected,
            'kpis': [],
            'ceo_tasks': [],
            'followup_candidates': [],
            'message': 'Connect GoHighLevel and/or Snowflake in DB Connectors first.',
        }

    datasets, errors, skipped = _fetch_datasets(
        include_ghl=connected['ghl'],
        include_snowflake=connected['snowflake'],
        snowflake_passcode=snowflake_passcode,
        limit_per_entity=limit_per_entity,
    )
    email_cfg = load_email_settings()
    threshold = email_cfg.get('inactive_days') or inactive_days
    result = compute_insights(datasets, connected, inactive_days=threshold)
    result['ceo_tasks'] = compute_ceo_tasks(datasets, connected, inactive_days=threshold)
    result['errors'] = errors or None
    result['skipped'] = skipped or None
    return result


@app.get('/api/treatment-plans')
def get_treatment_plans(
    snowflake_passcode: Optional[str] = None,
    limit_per_entity: int = 500,
    inactive_days: int = 90,
    limit: int = 50,
    user: str = Depends(get_current_user),
):
    """Patient treatment plans from Snowflake data and health intake forms."""
    _seed_defaults()
    connected = get_connected_sources()

    datasets, errors, skipped = _fetch_datasets(
        include_ghl=connected['ghl'],
        include_snowflake=connected['snowflake'],
        snowflake_passcode=snowflake_passcode,
        limit_per_entity=limit_per_entity,
    )
    result = compute_treatment_plans(
        datasets, connected, inactive_days=inactive_days, limit=limit,
    )
    result['errors'] = errors or None
    result['skipped'] = skipped or None
    return result


@app.post('/api/intake/submit')
def submit_health_intake(
    form: HealthIntakeForm,
    snowflake_passcode: Optional[str] = None,
    limit_per_entity: int = 500,
    user: str = Depends(get_current_user),
):
    """Submit a health intake form and return a generated treatment plan."""
    _seed_defaults()
    try:
        intake = save_intake(form)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    connected = get_connected_sources()
    datasets, errors, skipped = _fetch_datasets(
        include_ghl=connected['ghl'],
        include_snowflake=connected['snowflake'],
        snowflake_passcode=snowflake_passcode,
        limit_per_entity=limit_per_entity,
    )
    plan = compute_plan_for_intake(intake, datasets)
    return {
        'intake_id': intake['id'],
        'submitted_at': intake['submitted_at'],
        'plan': plan,
        'errors': errors or None,
        'skipped': skipped or None,
    }


@app.get('/api/revenue/growth')
def get_revenue_growth(
    snowflake_passcode: Optional[str] = None,
    limit_per_entity: int = 500,
    inactive_days: int = 90,
    months: int = 12,
    user: str = Depends(get_current_user),
):
    """Monthly revenue metrics and decision factors from connected data."""
    _seed_defaults()
    connected = get_connected_sources()
    if not connected['ghl'] and not connected['snowflake']:
        return compute_revenue_growth({}, connected, months=months, inactive_days=inactive_days)

    datasets, errors, skipped = _fetch_datasets(
        include_ghl=connected['ghl'],
        include_snowflake=connected['snowflake'],
        snowflake_passcode=snowflake_passcode,
        limit_per_entity=limit_per_entity,
    )
    email_cfg = load_email_settings()
    threshold = email_cfg.get('inactive_days') or inactive_days
    result = compute_revenue_growth(
        datasets, connected, months=min(max(months, 3), 24), inactive_days=threshold,
    )
    result['errors'] = errors or None
    result['skipped'] = skipped or None
    return result


@app.get('/api/reports')
def get_reports(
    snowflake_passcode: Optional[str] = None,
    limit_per_entity: int = 500,
    inactive_days: int = 90,
    user: str = Depends(get_current_user),
):
    """Aggregated business reports across insights, revenue, retention, and compliance."""
    _seed_defaults()
    connected = get_connected_sources()
    if not connected['ghl'] and not connected['snowflake']:
        return compute_reports({}, connected, inactive_days=inactive_days)

    datasets, errors, skipped = _fetch_datasets(
        include_ghl=connected['ghl'],
        include_snowflake=connected['snowflake'],
        snowflake_passcode=snowflake_passcode,
        limit_per_entity=limit_per_entity,
    )
    email_cfg = load_email_settings()
    threshold = email_cfg.get('inactive_days') or inactive_days
    result = compute_reports(datasets, connected, inactive_days=threshold)
    result['errors'] = errors or None
    result['skipped'] = skipped or None
    hipaa_manager.log_audit_event('reports_generated', {
        'report_count': len(result.get('reports') or []),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })
    return result


@app.get('/api/search')
def global_search(
    q: str = '',
    limit: int = 20,
    offset: int = 0,
    snowflake_passcode: Optional[str] = None,
    limit_per_entity: int = 500,
    user: str = Depends(get_current_user),
):
    """Global search across contacts and opportunities."""
    _seed_defaults()
    connected = get_connected_sources()
    if not q.strip():
        return {'results': [], 'total': 0, 'limit': limit, 'offset': offset, 'query': ''}
    if not connected['ghl'] and not connected['snowflake']:
        return {'results': [], 'total': 0, 'limit': limit, 'offset': offset, 'query': q}

    datasets, errors, _ = _fetch_datasets(
        include_ghl=connected['ghl'],
        include_snowflake=connected['snowflake'],
        snowflake_passcode=snowflake_passcode,
        limit_per_entity=limit_per_entity,
    )
    result = search_datasets(
        datasets, q, limit=min(max(1, limit), 50), offset=max(0, offset),
    )
    result['errors'] = errors or None
    return result


@app.get('/api/reactivate/campaign')
def get_reactivate_campaign(
    snowflake_passcode: Optional[str] = None,
    limit_per_entity: int = 500,
    inactive_days: Optional[int] = None,
    page: int = 1,
    page_size: int = 25,
    q: str = '',
    channel: str = 'all',
    sort: str = '-days_inactive',
    user: str = Depends(get_current_user),
):
    """Identify 90+ day no-show patients for reactivate campaign with discount offers."""
    _seed_defaults()
    connected = get_connected_sources()
    if not connected['ghl'] and not connected['snowflake']:
        settings = load_reactivate_settings()
        return {
            'connected_sources': connected,
            'settings': settings,
            'summary': {'total_candidates': 0, 'email_ready': 0, 'manual_followup': 0},
            'candidates': {'email_ready': [], 'manual_only': [], 'total': 0},
            'message': 'Connect GoHighLevel and/or Snowflake in DB Connectors first.',
        }

    datasets, errors, skipped = _fetch_datasets(
        include_ghl=connected['ghl'],
        include_snowflake=connected['snowflake'],
        snowflake_passcode=snowflake_passcode,
        limit_per_entity=limit_per_entity,
    )
    cfg = load_reactivate_settings()
    threshold = inactive_days if inactive_days is not None else cfg.get('inactive_days', 90)
    result = compute_reactivate_campaign(
        datasets,
        connected,
        inactive_days=threshold,
        mask_phi=True,
        page=max(1, page),
        page_size=min(max(5, page_size), 100),
        q=q,
        channel=channel if channel in ('all', 'email', 'manual') else 'all',
        sort=sort,
    )
    result['errors'] = errors or None
    result['skipped'] = skipped or None
    return result


@app.put('/api/reactivate/settings')
def update_reactivate_settings(
    settings_in: ReactivateSettings,
    user: str = Depends(get_current_user),
):
    return save_reactivate_settings(settings_in.model_dump())


@app.post('/api/reactivate/send')
def send_reactivate_campaign(
    req: ReactivateSendRequest,
    snowflake_passcode: Optional[str] = None,
    limit_per_entity: int = 500,
    user: str = Depends(get_current_user),
):
    """Send discount reactivation emails to selected or all email-ready candidates."""
    _seed_defaults()
    connected = get_connected_sources()
    datasets, errors, _ = _fetch_datasets(
        include_ghl=connected['ghl'],
        include_snowflake=connected['snowflake'],
        snowflake_passcode=snowflake_passcode,
        limit_per_entity=limit_per_entity,
    )
    cfg = load_reactivate_settings()
    campaign = compute_reactivate_campaign(
        datasets, connected, inactive_days=cfg.get('inactive_days', 90), mask_phi=False,
    )
    raw = campaign.get('candidates') or {}
    # Use unmasked source list for sending
    insights_raw = compute_insights(
        datasets, connected,
        inactive_days=cfg.get('inactive_days', 90),
        mask_contacts=False,
    )
    candidates = insights_raw.get('followup_candidates') or []

    ghl_client = None
    provider = (cfg.get('provider') or 'ghl').lower()
    if provider == 'ghl' and connected['ghl']:
        ghl_client = GHLClient(get_active_config('ghl'))

    try:
        result = send_reactivate_emails(
            candidates,
            contact_ids=req.contact_ids,
            send_all=req.send_all,
            dry_run=req.dry_run,
            ghl_client=ghl_client,
        )
        result['email_ready'] = len(raw.get('email_ready') or [])
        result['errors'] = errors or None
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get('/api/reactivate/export')
def export_reactivate_list(
    snowflake_passcode: Optional[str] = None,
    limit_per_entity: int = 500,
    scope: str = 'manual',
    user: str = Depends(get_current_user),
):
    """Export manual follow-up list (or full list) as CSV for staff outreach."""
    _seed_defaults()
    connected = get_connected_sources()
    datasets, _, _ = _fetch_datasets(
        include_ghl=connected['ghl'],
        include_snowflake=connected['snowflake'],
        snowflake_passcode=snowflake_passcode,
        limit_per_entity=limit_per_entity,
    )
    cfg = load_reactivate_settings()
    insights_raw = compute_insights(
        datasets, connected,
        inactive_days=cfg.get('inactive_days', 90),
        mask_contacts=False,
    )
    candidates = insights_raw.get('followup_candidates') or []

    if scope == 'all':
        csv_data = export_all_followup_csv(candidates, cfg)
        filename = 'reactivate-campaign-all.csv'
    else:
        csv_data = export_manual_followup_csv(candidates, cfg)
        filename = 'reactivate-manual-followup.csv'

    hipaa_manager.log_audit_event('reactivate_export', {
        'scope': scope,
        'count': len(candidates),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })

    return PlainTextResponse(
        content=csv_data,
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@app.get('/api/compliance/evaluate')
def compliance_evaluate(
    snowflake_passcode: Optional[str] = None,
    limit_per_entity: int = 500,
    inactive_days: int = 90,
    user: str = Depends(get_current_user),
):
    """Evaluate customer service data and recommend compliance-oriented follow-ups."""
    _seed_defaults()
    connected = get_connected_sources()
    if not connected['ghl'] and not connected['snowflake']:
        return evaluate_compliance({}, connected, inactive_days=inactive_days)

    datasets, errors, skipped = _fetch_datasets(
        include_ghl=connected['ghl'],
        include_snowflake=connected['snowflake'],
        snowflake_passcode=snowflake_passcode,
        limit_per_entity=limit_per_entity,
    )
    email_cfg = load_email_settings()
    threshold = email_cfg.get('inactive_days') or inactive_days
    result = evaluate_compliance(datasets, connected, inactive_days=threshold)
    result['errors'] = errors or None
    result['skipped'] = skipped or None
    hipaa_manager.log_audit_event('compliance_evaluated', {
        'score': result.get('compliance_score'),
        'findings': len(result.get('findings') or []),
        'recommendations': result.get('recommendation_count', 0),
        'timestamp': datetime.utcnow().isoformat(),
    })
    return result


@app.get('/api/email/settings')
def get_email_settings(user: str = Depends(get_current_user)):
    from email_followup import _public_settings
    data = load_email_settings()
    return _public_settings(data)


@app.put('/api/email/settings')
def update_email_settings(settings_in: EmailSettings, user: str = Depends(get_current_user)):
    saved = save_email_settings(settings_in.model_dump())
    return saved


@app.post('/api/email/followup/send')
def send_followup(req: SendFollowupRequest, user: str = Depends(get_current_user)):
    """Send re-engagement emails to 90-day inactive / no-follow-up customers."""
    _seed_defaults()
    connected = get_connected_sources()
    datasets, _, _ = _fetch_datasets(
        include_ghl=connected['ghl'],
        include_snowflake=connected['snowflake'],
        limit_per_entity=500,
    )
    email_cfg = load_email_settings()
    insights = compute_insights(
        datasets,
        connected,
        inactive_days=email_cfg.get('inactive_days', 90),
        mask_contacts=False,
    )
    candidates = insights.get('followup_candidates') or []

    ghl_client = None
    provider = (email_cfg.get('provider') or 'ghl').lower()
    if provider == 'ghl' and connected['ghl']:
        ghl_client = GHLClient(get_active_config('ghl'))

    try:
        return send_followup_emails(
            candidates,
            contact_ids=req.contact_ids,
            send_all=req.send_all,
            dry_run=req.dry_run,
            ghl_client=ghl_client,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post('/api/sync')
def sync(user: str = Depends(get_current_user)):
    """Run the full GHL -> Snowflake sync pipeline"""
    try:
        _seed_defaults()
        ghl = GHLClient(get_active_config('ghl'))
        loader = SnowflakeLoader(get_active_config('snowflake'))
        loader.connect()
        try:
            data, entity_errors = ghl.get_all_data()
            loader.load_all_data(data)
        finally:
            loader.disconnect()
        return {
            'status': 'ok',
            'contacts': len(data['contacts']),
            'conversations': len(data['conversations']),
            'opportunities': len(data['opportunities']),
            'errors': {f'ghl.{k}': v for k, v in entity_errors.items()} or None,
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
