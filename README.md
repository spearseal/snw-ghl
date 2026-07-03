# GoHighLevel + Snowflake Integration with HIPAA Compliance

A secure, HIPAA-compliant integration that extracts data from GoHighLevel (GHL) and loads it into Snowflake data warehouse, plus a full-stack query app (FastAPI + Chonkie backend, Next.js UI) that lets you ask free-text questions across both data sources.

## Features

- **Data Extraction**: Retrieve contacts, conversations, and opportunities from GoHighLevel
- **Data Loading**: Load data into Snowflake with automatic schema creation
- **HIPAA Compliance**: 
  - AES-256 encryption for PHI (Protected Health Information)
  - Audit logging for all data access and operations
  - Data integrity verification using SHA-256 hashing
  - Access controls and authentication
  - Secure transmission (HTTPS/TLS)
- **Batch Processing**: Configurable batch sizes for efficient data transfer
- **Error Handling**: Retry logic and comprehensive error logging
- **Monitoring**: Detailed audit trails for compliance reporting
- **Free-Text Query App**: Ask questions in plain English over GHL + Snowflake data
  - Chunking via [Chonkie](https://github.com/chonkie-inc/chonkie) `RecursiveChunker`
  - BM25 ranked retrieval over indexed chunks
  - PHI masking (emails, phone numbers, SSNs) in query results
  - Next.js UI with query input and output section

## Architecture

```
GoHighLevel API → GHL Client → Encryption → Snowflake Loader → Snowflake
                      ↓                  ↓
                 Audit Log         Audit Log

Query flow:
GHL API ──┐
          ├─→ Query Engine (Chonkie chunking + BM25) ─→ FastAPI (/api/query)
Snowflake ┘        ↓                                        ↓
  (decrypted   Audit Log                             Next.js UI (port 3000)
   PHI reads)                                        query box + output section
```

### Key files

- `api.py` — FastAPI backend (`/api/query`, `/api/index/refresh`, `/api/sync`, `/api/health`)
- `query_engine.py` — Chonkie chunking + BM25 retrieval + PHI masking
- `snowflake_reader.py` — read-only Snowflake access with PHI decryption
- `frontend/` — Next.js 15 + Tailwind query console

## HIPAA Compliance Features

This integration implements the following HIPAA Security Rule safeguards:

### Administrative Safeguards
- **Audit Controls**: All data access and modifications are logged
- **Security Management Process**: Configuration-based security settings
- **Training**: Documentation for proper usage

### Physical Safeguards
- **Data Backup**: Snowflake provides built-in data replication and backup

### Technical Safeguards
- **Access Control**: Unique credentials for GHL and Snowflake
- **Audit Controls**: Comprehensive logging of all operations
- **Integrity Controls**: SHA-256 hashing for data verification
- **Transmission Security**: HTTPS/TLS for all API calls
- **Encryption**: AES-256 encryption for PHI at rest

## Installation

1. Clone the repository:
```bash
cd /Users/pragnyak/CascadeProjects/ghl-snowflake-hipaa-integration
```

2. Install backend dependencies (Python 3.12 recommended):
```bash
python3.12 -m venv venv
./venv/bin/pip install -r requirements.txt
```

2b. Install frontend dependencies:
```bash
cd frontend && npm install
```

3. Copy the example environment file:
```bash
cp .env.example .env
```

4. Configure your environment variables in `.env`:
```bash
# GoHighLevel Configuration
GHL_API_KEY=your_ghl_api_key_here
GHL_API_BASE_URL=https://services.leadconnectorhq.com
GHL_LOCATION_ID=your_location_id_here

# Snowflake Configuration
SNOWFLAKE_ACCOUNT=your_account_here
SNOWFLAKE_USER=your_username_here
SNOWFLAKE_PASSWORD=your_password_here
SNOWFLAKE_WAREHOUSE=your_warehouse_here
SNOWFLAKE_DATABASE=your_database_here
SNOWFLAKE_SCHEMA=your_schema_here
SNOWFLAKE_ROLE=your_role_here

# Security Configuration
ENCRYPTION_KEY=your_32_byte_encryption_key_here
LOG_LEVEL=INFO
AUDIT_LOG_ENABLED=true
AUDIT_LOG_PATH=./logs/audit.log

# Data Sync Configuration
SYNC_INTERVAL_MINUTES=60
BATCH_SIZE=100
MAX_RETRIES=3
```

## Configuration

### GoHighLevel Setup

1. **Get API Key**:
   - For private integrations: Generate a Private Integration Token in GHL settings
   - For public apps: Set up OAuth 2.0 flow (not implemented in this version)

2. **Location ID**: Optional, specify if you want to filter by location

### Snowflake Setup

1. **Create Database and Schema**:
```sql
CREATE DATABASE IF NOT EXISTS ghl_integration;
CREATE SCHEMA IF NOT EXISTS ghl_integration.public;
```

2. **Grant Permissions**:
```sql
GRANT USAGE ON DATABASE ghl_integration TO ROLE your_role;
GRANT USAGE ON SCHEMA ghl_integration.public TO ROLE your_role;
GRANT CREATE TABLE ON SCHEMA ghl_integration.public TO ROLE your_role;
```

3. **Configure Warehouse**: Ensure your warehouse has sufficient resources

### Security Setup

1. **Generate Encryption Key**: Create a 32-character key for AES-256 encryption
```python
import secrets
key = secrets.token_urlsafe(32)[:32]
print(key)
```

2. **Enable Audit Logging**: Set `AUDIT_LOG_ENABLED=true` in `.env`

## Deploy to Railway (POC)

Create a Railway project with **two services** from this repo:

1. **Backend service** — root directory: `/` (uses `railway.json`)
   - Variables: `GHL_API_KEY`, `GHL_LOCATION_ID`, `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`, `ENCRYPTION_KEY` (32 chars), `JWT_SECRET`, `FRONTEND_ORIGIN` (frontend public URL), `DATA_DIR=/data`, `AUDIT_LOG_PATH=/data/audit.log`
   - Attach a **volume** mounted at `/data` (persists users, connections, audit log)
2. **Frontend service** — root directory: `/frontend` (uses `frontend/railway.json`)
   - Variables: `BACKEND_URL=http://<backend-service>.railway.internal:8080` (private networking) or the backend public URL

Note: Railway's Hobby/Pro plans are **not** covered by a HIPAA BAA. Use synthetic data for the POC, or contact Railway for their BAA add-on before handling real PHI.

## Usage

### Run the Query App

Start the backend API (port 8000):
```bash
./venv/bin/uvicorn api:app --port 8000
```

Start the frontend (port 3000):
```bash
cd frontend && npm run dev
```

Open http://localhost:3000, click **Refresh Index** to pull data from GHL and Snowflake, then type a question and press **Query**. Results appear in the output section with PHI masked by default.

### Full Sync

Run a complete sync of all data from GHL to Snowflake:

```bash
python main.py --mode full
```

### Incremental Sync

Run incremental sync (placeholder for future enhancement):

```bash
python main.py --mode incremental --last-sync "2024-01-01T00:00:00Z"
```

### Data Integrity Verification

Verify data integrity between GHL and Snowflake:

```bash
python main.py --mode verify
```

## Data Schema

### Contacts Table (`ghl_contacts`)

- All GHL contact fields (flattened from nested structures)
- PHI fields (email, phone, name, address) are encrypted
- `_sync_timestamp`: When the record was synced
- `_data_hash`: SHA-256 hash for integrity verification

### Conversations Table (`ghl_conversations`)

- All GHL conversation fields
- PHI fields (message body, sender) are encrypted
- `_sync_timestamp`: When the record was synced
- `_data_hash`: SHA-256 hash for integrity verification

### Opportunities Table (`ghl_opportunities`)

- All GHL opportunity/deal fields
- PHI fields (title, description) are encrypted
- `_sync_timestamp`: When the record was synced
- `_data_hash`: SHA-256 hash for integrity verification

## Audit Logs

Audit logs are stored in the configured location (default: `./logs/audit.log`).

Each log entry includes:
- Timestamp
- Event type (e.g., `ghl_api_access`, `snowflake_data_load`, `encryption`)
- Event details (JSON format)

Example log entry:
```json
{
  "timestamp": "2024-01-01T12:00:00.000000",
  "event_type": "ghl_data_retrieval",
  "details": {
    "entity": "contacts",
    "count": 100,
    "timestamp": "2024-01-01T12:00:00.000000"
  }
}
```

## Security Best Practices

1. **Environment Variables**: Never commit `.env` file to version control
2. **Encryption Key**: Store encryption key securely (e.g., AWS Secrets Manager, HashiCorp Vault)
3. **Access Control**: Use principle of least privilege for Snowflake roles
4. **Network Security**: Ensure all connections use HTTPS/TLS
5. **Regular Audits**: Review audit logs regularly for suspicious activity
6. **Key Rotation**: Rotate encryption keys periodically (requires data re-encryption)
7. **Backup**: Implement regular backup procedures for audit logs

## Troubleshooting

### Connection Issues

**GHL API Connection Failed**:
- Verify API key is correct
- Check API key has necessary permissions
- Ensure network can reach `services.leadconnectorhq.com`

**Snowflake Connection Failed**:
- Verify account, user, and password are correct
- Check warehouse and database exist
- Ensure user has necessary permissions
- Verify network allows Snowflake connections

### Data Loading Issues

**Table Creation Failed**:
- Check user has CREATE TABLE permissions
- Verify schema exists
- Check warehouse is running and has resources

**Data Load Failed**:
- Check batch size is not too large
- Verify data types are compatible
- Review error logs for specific issues

### Encryption Issues

**Encryption Key Error**:
- Ensure encryption key is exactly 32 characters
- Verify key is not corrupted in `.env` file

**Decryption Failed**:
- Ensure same encryption key is used for all operations
- Check data was encrypted before attempting decryption

## Business Associate Agreement (BAA)

This software is designed to be HIPAA-compliant, but you must:
1. Sign a BAA with Snowflake (they offer this)
2. Ensure GoHighLevel has a BAA with your organization
3. Implement appropriate security measures in your environment
4. Conduct regular security assessments
5. Train staff on HIPAA compliance

## Future Enhancements

- [ ] OAuth 2.0 authentication for GHL
- [ ] Incremental sync with timestamp-based filtering
- [ ] Data transformation and mapping configuration
- [ ] Real-time sync via webhooks
- [ ] Data quality checks and validation
- [ ] Automated key rotation
- [ ] Multi-region support
- [ ] Performance monitoring and alerting

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review audit logs for error details
3. Verify configuration in `.env`
4. Check GHL and Snowflake documentation

## License

This integration is provided as-is for use in HIPAA-compliant environments. Ensure proper security measures and BAAs are in place.

## Disclaimer

This software is designed to support HIPAA compliance but does not guarantee compliance. Organizations are responsible for implementing appropriate security measures, conducting risk assessments, and ensuring all regulatory requirements are met.
