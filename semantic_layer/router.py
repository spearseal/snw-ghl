"""FastAPI router for semantic layer endpoints."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user
from semantic_layer.config import (
    SEMANTIC_OUTPUT_DIR,
    load_semantic_config,
    save_semantic_config,
)
from semantic_layer.context import build_semantic_summary
from semantic_layer.models import SourceMetadata

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/semantic', tags=['semantic-layer'])


class BuildRequest(BaseModel):
    profile: bool = True
    snowflake_passcode: Optional[str] = Field(default=None, max_length=10)


class ConfigUpdateRequest(BaseModel):
    model_name: Optional[str] = None
    model_description: Optional[str] = None
    sources: Optional[List[Dict[str, Any]]] = None


@router.get('/sources')
def get_supported_sources(user: str = Depends(get_current_user)) -> Dict[str, Any]:
    """List supported connector types."""
    from semantic_layer.connectors.registry import list_supported_sources as _list
    return {'sources': _list()}


@router.get('/config')
def get_config(user: str = Depends(get_current_user)) -> Dict[str, Any]:
    """Return current semantic layer configuration."""
    cfg = load_semantic_config()
    return cfg.model_dump()


@router.put('/config')
def update_config(
    req: ConfigUpdateRequest,
    user: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update semantic layer configuration."""
    cfg = load_semantic_config()
    if req.model_name:
        cfg.model_name = req.model_name
    if req.model_description:
        cfg.model_description = req.model_description
    if req.sources is not None:
        from semantic_layer.config import SourceConnectorConfig
        cfg.sources = [SourceConnectorConfig.model_validate(s) for s in req.sources]
    save_semantic_config(cfg)
    return cfg.model_dump()


@router.get('/summary')
def get_semantic_summary(user: str = Depends(get_current_user)) -> Dict[str, Any]:
    """Lightweight semantic model summary for Spagent AI UI."""
    return build_semantic_summary()


@router.post('/discover')
def discover_metadata(
    req: BuildRequest = BuildRequest(),
    user: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Discover metadata from all configured sources without full profiling."""
    from semantic_layer.discovery.metadata import discover_all_sources
    from semantic_layer.pipeline import SemanticLayerPipeline

    cfg = load_semantic_config()
    pipeline = SemanticLayerPipeline(cfg)
    sources = discover_all_sources(
        pipeline.config.sources,
        max_tables=pipeline.config.max_tables_per_source,
        passcode=req.snowflake_passcode,
    )
    return {
        'source_count': len(sources),
        'sources': [_source_summary(s) for s in sources],
    }


@router.post('/build')
def build_semantic_layer(
    req: BuildRequest,
    user: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Run the full semantic layer pipeline."""
    from semantic_layer.pipeline import run_pipeline

    try:
        result = run_pipeline(profile=req.profile, passcode=req.snowflake_passcode)
    except Exception as exc:
        logger.error('Semantic layer build failed: %s', exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        'model_name': result.model.name,
        'entities': len(result.model.entities),
        'dimensions': len(result.model.dimensions),
        'facts': len(result.model.facts),
        'measures': len(result.model.measures),
        'relationships': len(result.model.relationships),
        'sources_discovered': len(result.sources_discovered),
        'output_dir': SEMANTIC_OUTPUT_DIR,
        'yaml_file': f'{result.model.name}.yaml',
        'json_file': f'{result.model.name}.json',
    }


@router.get('/model/yaml')
def get_yaml_model(user: str = Depends(get_current_user)) -> Dict[str, str]:
    """Return generated YAML semantic definition."""
    cfg = load_semantic_config()
    path = os.path.join(SEMANTIC_OUTPUT_DIR, f'{cfg.model_name}.yaml')
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail='Semantic model not built yet. POST /api/semantic/build first.')
    with open(path, 'r') as f:
        return {'yaml': f.read(), 'path': path}


@router.get('/model/json')
def get_json_model(user: str = Depends(get_current_user)) -> Dict[str, Any]:
    """Return generated JSON metadata."""
    cfg = load_semantic_config()
    path = os.path.join(SEMANTIC_OUTPUT_DIR, f'{cfg.model_name}.json')
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail='Semantic model not built yet. POST /api/semantic/build first.')
    with open(path, 'r') as f:
        return json.load(f)


def _source_summary(src: SourceMetadata) -> Dict[str, Any]:
    return {
        'name': src.source_name,
        'type': src.source_type.value,
        'database': src.database,
        'schema': src.schema_name,
        'tables': [
            {'name': t.name, 'columns': len(t.columns), 'row_count': t.row_count}
            for t in src.tables
        ],
        'views': [{'name': v.name, 'columns': len(v.columns)} for v in src.views],
    }
