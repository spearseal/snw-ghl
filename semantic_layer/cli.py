#!/usr/bin/env python3
"""CLI for building and deploying the enterprise semantic layer."""
from __future__ import annotations

import argparse
import json
import logging
import sys

from semantic_layer.config import load_semantic_config
from semantic_layer.pipeline import run_pipeline
from semantic_layer.utils import setup_logging


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Build enterprise semantic layer from configured data sources',
    )
    parser.add_argument('--no-profile', action='store_true', help='Skip data profiling')
    parser.add_argument('--passcode', type=str, default=None, help='Snowflake MFA passcode')
    parser.add_argument('--output-json', action='store_true', help='Print JSON metadata to stdout')
    parser.add_argument('--output-yaml', action='store_true', help='Print YAML definition to stdout')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose logging')
    args = parser.parse_args()

    setup_logging()
    if args.verbose:
        logging.getLogger('semantic_layer').setLevel(logging.DEBUG)

    cfg = load_semantic_config()
    print(f'Building semantic layer: {cfg.model_name}')
    print(f'Sources configured: {len(cfg.sources)}')

    try:
        result = run_pipeline(
            config=cfg,
            profile=not args.no_profile,
            passcode=args.passcode,
        )
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1

    print(f'Entities:      {len(result.model.entities)}')
    print(f'Dimensions:    {len(result.model.dimensions)}')
    print(f'Facts:         {len(result.model.facts)}')
    print(f'Measures:      {len(result.model.measures)}')
    print(f'Relationships: {len(result.model.relationships)}')
    print(f'Output:        {cfg.output_dir}')

    if args.output_yaml:
        print('\n--- YAML ---')
        print(result.yaml_definition)
    if args.output_json:
        print('\n--- JSON ---')
        print(json.dumps(result.json_metadata.model_dump(), indent=2))

    return 0


if __name__ == '__main__':
    sys.exit(main())
