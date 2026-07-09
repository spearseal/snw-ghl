"""
Pydantic models for the enterprise semantic layer.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    SNOWFLAKE = 'snowflake'
    BIGQUERY = 'bigquery'
    POSTGRESQL = 'postgresql'
    SQLSERVER = 'sqlserver'
    MYSQL = 'mysql'
    REST_API = 'rest_api'
    GHL = 'ghl'


class ColumnSemantic(str, Enum):
    ID = 'id'
    FOREIGN_KEY = 'foreign_key'
    EMAIL = 'email'
    PHONE = 'phone'
    DATE = 'date'
    DATETIME = 'datetime'
    CURRENCY = 'currency'
    STATUS = 'status'
    NAME = 'name'
    ADDRESS = 'address'
    BOOLEAN = 'boolean'
    CATEGORY = 'category'
    MEASURE = 'measure'
    TEXT = 'text'
    UNKNOWN = 'unknown'


class RelationshipType(str, Enum):
    ONE_TO_ONE = 'one_to_one'
    ONE_TO_MANY = 'one_to_many'
    MANY_TO_MANY = 'many_to_many'
    LOOKUP = 'lookup'


class EntityType(str, Enum):
    DIMENSION = 'dimension'
    FACT = 'fact'
    BRIDGE = 'bridge'
    LOOKUP = 'lookup'


# --- Metadata ---


class ColumnMetadata(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    comment: str = ''
    is_primary_key: bool = False
    is_foreign_key: bool = False
    ordinal_position: int = 0


class ConstraintMetadata(BaseModel):
    name: str
    constraint_type: Literal['PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE', 'CHECK']
    columns: List[str] = Field(default_factory=list)
    referenced_table: Optional[str] = None
    referenced_columns: List[str] = Field(default_factory=list)


class TableMetadata(BaseModel):
    name: str
    schema_name: str = ''
    database_name: str = ''
    table_type: Literal['BASE TABLE', 'VIEW'] = 'BASE TABLE'
    row_count: Optional[int] = None
    comment: str = ''
    columns: List[ColumnMetadata] = Field(default_factory=list)
    constraints: List[ConstraintMetadata] = Field(default_factory=list)


class SourceMetadata(BaseModel):
    source_type: SourceType
    source_name: str
    database: str = ''
    schema_name: str = ''
    tables: List[TableMetadata] = Field(default_factory=list)
    views: List[TableMetadata] = Field(default_factory=list)


# --- Profiling ---


class ColumnProfile(BaseModel):
    column_name: str
    table_name: str
    null_pct: float = 0.0
    distinct_count: Optional[int] = None
    min_value: Optional[str] = None
    max_value: Optional[str] = None
    sample_values: List[str] = Field(default_factory=list)
    cardinality: Literal['low', 'medium', 'high', 'unique'] = 'medium'
    inferred_semantic: ColumnSemantic = ColumnSemantic.UNKNOWN
    confidence: float = 0.0


class TableProfile(BaseModel):
    table_name: str
    row_count: Optional[int] = None
    columns: List[ColumnProfile] = Field(default_factory=list)


# --- Relationships ---


class InferredRelationship(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    relationship_type: RelationshipType
    confidence: float = Field(ge=0.0, le=1.0)
    inference_method: str = 'naming_convention'


# --- Semantic model ---


class BusinessEntity(BaseModel):
    name: str
    business_name: str
    description: str = ''
    source_table: str
    entity_type: EntityType
    primary_key: List[str] = Field(default_factory=list)
    synonyms: List[str] = Field(default_factory=list)


class Dimension(BaseModel):
    name: str
    business_name: str
    description: str = ''
    source_table: str
    source_column: str
    data_type: str = ''
    semantic: ColumnSemantic = ColumnSemantic.UNKNOWN
    is_conformed: bool = False
    synonyms: List[str] = Field(default_factory=list)


class Fact(BaseModel):
    name: str
    business_name: str
    description: str = ''
    source_table: str
    grain: List[str] = Field(default_factory=list)
    dimensions: List[str] = Field(default_factory=list)
    measures: List[str] = Field(default_factory=list)


class Measure(BaseModel):
    name: str
    business_name: str
    description: str = ''
    expression: str
    aggregation: Literal['sum', 'count', 'count_distinct', 'avg', 'min', 'max'] = 'sum'
    source_table: str = ''
    source_column: str = ''
    format: str = ''


class Hierarchy(BaseModel):
    name: str
    dimension: str
    levels: List[str] = Field(default_factory=list)


class SemanticRelationship(BaseModel):
    name: str
    from_entity: str
    to_entity: str
    from_column: str
    to_column: str
    relationship_type: RelationshipType
    confidence: float = 1.0


class SemanticModel(BaseModel):
    name: str
    description: str = ''
    version: str = '1.0.0'
    sources: List[str] = Field(default_factory=list)
    entities: List[BusinessEntity] = Field(default_factory=list)
    dimensions: List[Dimension] = Field(default_factory=list)
    facts: List[Fact] = Field(default_factory=list)
    measures: List[Measure] = Field(default_factory=list)
    hierarchies: List[Hierarchy] = Field(default_factory=list)
    relationships: List[SemanticRelationship] = Field(default_factory=list)


class LineageEntry(BaseModel):
    semantic_object: str
    object_type: str
    source_type: str
    source_name: str
    source_table: str
    source_column: str = ''


class SemanticMetadataDocument(BaseModel):
    """Full JSON metadata output schema."""
    source: Dict[str, Any] = Field(default_factory=dict)
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[Dict[str, Any]] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    dimensions: List[Dict[str, Any]] = Field(default_factory=list)
    facts: List[Dict[str, Any]] = Field(default_factory=list)
    measures: List[Dict[str, Any]] = Field(default_factory=list)
    lineage: List[Dict[str, Any]] = Field(default_factory=list)


class PipelineResult(BaseModel):
    model: SemanticModel
    yaml_definition: str
    json_metadata: SemanticMetadataDocument
    sources_discovered: List[SourceMetadata] = Field(default_factory=list)
    profiles: List[TableProfile] = Field(default_factory=list)
    inferred_relationships: List[InferredRelationship] = Field(default_factory=list)
    discovery_errors: Dict[str, str] = Field(default_factory=dict)
