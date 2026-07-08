"""
Enterprise semantic layer pipeline.

Orchestrates: discover → profile → infer relationships → build model → output YAML/JSON.
"""
from __future__ import annotations

import json
import logging
import os
from typing import List, Optional

from semantic_layer.config import SemanticLayerConfig, load_semantic_config, resolve_semantic_config
from semantic_layer.connectors.registry import create_connector
from semantic_layer.discovery.metadata import discover_all_sources
from semantic_layer.models import PipelineResult, SourceMetadata, TableProfile
from semantic_layer.output.json_generator import generate_json_metadata
from semantic_layer.output.yaml_generator import generate_yaml
from semantic_layer.relationships.inferrer import infer_relationships
from semantic_layer.semantics.model_builder import build_semantic_model
from semantic_layer.utils import setup_logging

logger = setup_logging()


class SemanticLayerPipeline:
    """Production semantic layer build pipeline."""

    def __init__(self, config: Optional[SemanticLayerConfig] = None):
        self.config = config or resolve_semantic_config()

    def run(
        self,
        profile: bool = True,
        passcode: Optional[str] = None,
    ) -> PipelineResult:
        """Execute the full semantic layer pipeline."""
        logger.info('Starting semantic layer pipeline: %s', self.config.model_name)

        if not self.config.sources:
            raise RuntimeError(
                'No data sources configured. Connect Snowflake or GoHighLevel '
                'in DB Connectors and test the connection first.'
            )

        # 1. Discover metadata
        sources, discovery_errors = discover_all_sources(
            self.config.sources,
            max_tables=self.config.max_tables_per_source,
            passcode=passcode,
        )
        if not sources:
            if discovery_errors:
                detail = '; '.join(f'{k}: {v}' for k, v in discovery_errors.items())
                raise RuntimeError(
                    f'Could not discover any sources. {detail}'
                )
            raise RuntimeError(
                'No sources discovered. Connect and test Snowflake or GoHighLevel in DB Connectors.'
            )

        # 2. Profile tables
        profiles: List[TableProfile] = []
        if profile:
            profiles = self._profile_all(sources, passcode=passcode)

        # 3. Infer relationships
        relationships = infer_relationships(
            sources,
            min_confidence=self.config.min_relationship_confidence,
        )
        logger.info('Inferred %d relationships', len(relationships))

        # 4. Build semantic model
        model = build_semantic_model(
            name=self.config.model_name,
            description=self.config.model_description,
            sources=sources,
            profiles=profiles,
            relationships=relationships,
        )
        logger.info(
            'Built model: %d entities, %d dimensions, %d facts, %d measures',
            len(model.entities), len(model.dimensions), len(model.facts), len(model.measures),
        )

        # 5. Generate outputs
        yaml_def = generate_yaml(model)
        json_meta = generate_json_metadata(model, sources, profiles, relationships)

        result = PipelineResult(
            model=model,
            yaml_definition=yaml_def,
            json_metadata=json_meta,
            sources_discovered=sources,
            profiles=profiles,
            inferred_relationships=relationships,
        )

        self._write_outputs(result)
        return result

    def _profile_all(
        self,
        sources: List[SourceMetadata],
        passcode: Optional[str] = None,
    ) -> List[TableProfile]:
        profiles: List[TableProfile] = []
        source_configs = {s.name: s for s in self.config.sources}

        for src_meta in sources:
            src_cfg = source_configs.get(src_meta.source_name)
            if not src_cfg:
                continue
            connector = create_connector(src_cfg)
            try:
                connect_kwargs = {}
                if passcode:
                    connect_kwargs['passcode'] = passcode
                connector.connect(**connect_kwargs)
                tables = src_meta.tables
                if src_cfg.profile_tables:
                    tables = [t for t in tables if t.name in src_cfg.profile_tables]

                sample_size = src_cfg.profile_sample_size or self.config.profile_sample_size
                for table in tables:
                    try:
                        prof = connector.profile_table(table, sample_size=sample_size)
                        profiles.append(prof)
                        logger.debug('Profiled %s (%d columns)', table.name, len(prof.columns))
                    except Exception as exc:
                        logger.warning('Profiling failed for %s: %s', table.name, exc)
            finally:
                connector.disconnect()

        return profiles

    def _write_outputs(self, result: PipelineResult) -> None:
        out_dir = self.config.output_dir
        os.makedirs(out_dir, exist_ok=True)

        yaml_path = os.path.join(out_dir, f'{self.config.model_name}.yaml')
        json_path = os.path.join(out_dir, f'{self.config.model_name}.json')

        with open(yaml_path, 'w') as f:
            f.write(result.yaml_definition)
        with open(json_path, 'w') as f:
            json.dump(result.json_metadata.model_dump(), f, indent=2)

        logger.info('Wrote semantic layer outputs to %s', out_dir)


def run_pipeline(
    config: Optional[SemanticLayerConfig] = None,
    profile: bool = True,
    passcode: Optional[str] = None,
) -> PipelineResult:
    """Convenience entry point."""
    return SemanticLayerPipeline(config).run(profile=profile, passcode=passcode)
