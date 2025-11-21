# BenefitsFlow Metrics Tracking Guide

## Overview

The metrics tracking system is fully contained in the `UI` folder and does not impact other members' code. It tracks:

- **Conversations**: Total conversations and message counts
- **Downloads**: Checklist and calendar downloads with associated programs
- **Performance**: Response times, RAG latency, and errors

## Database Location

- **EC2/Docker**: `/tmp/benefitsflow_metrics.db`
- **Local Development**: Same directory as `metrics.py`

## Automatic Tracking

Metrics are automatically logged when:

1. **Chat messages** are sent (`/chat` endpoint)
   - Logs conversation count
   - Logs response time and RAG latency
   - Logs errors if they occur

2. **Checklist downloads** (`/download/checklist` endpoint)
   - Logs download type and associated programs

3. **Calendar downloads** (`/download/calendar` endpoint)
   - Logs download type and associated programs

## Viewing Statistics

### Via API Endpoint

```bash
# Get last 30 days stats
curl http://localhost:8000/api/admin/stats

# Get last 7 days stats
curl http://localhost:8000/api/admin/stats?days=7
```

Response includes:
- Total conversations and messages
- Downloads by type (checklist/calendar)
- Average response times
- Error counts
- Top 10 most mentioned programs

**Note:** Evaluation scores (accuracy, actionability, simplicity, empathy) are reserved for future implementation by Godsee and Deric. The database schema supports these fields, but they are not currently being tracked.

### Via SQLite Command Line

```bash
# SSH into Instance 1
ssh ec2-user@[INSTANCE-1-IP]

# Connect to database
sqlite3 /tmp/benefitsflow_metrics.db

# Quick queries:
SELECT COUNT(*) as total_conversations 
FROM conversations 
WHERE timestamp >= datetime('now', '-30 days');

SELECT type, COUNT(*) as count 
FROM downloads 
WHERE timestamp >= datetime('now', '-30 days') 
GROUP BY type;

SELECT AVG(response_time_ms) as avg_response_time 
FROM performance 
WHERE timestamp >= datetime('now', '-30 days');
```

## Exporting Reports

### Via API Endpoint

```bash
# Download ZIP file with all CSV exports
curl -O http://localhost:8000/api/admin/export
```

The ZIP file contains:
- `conversations.csv`
- `downloads.csv`
- `performance.csv`

### Via Python Script

```python
from metrics import export_to_csv

# Export to current directory
files = export_to_csv()
print(f"Exported: {files}")

# Export to specific directory
files = export_to_csv(output_dir=Path("/path/to/reports"))
```

## Monthly Report Generation

### Quick Monthly Report (SQLite)

```bash
sqlite3 /tmp/benefitsflow_metrics.db <<EOF
.headers on
.mode csv
.output monthly_report_$(date +%Y%m).csv

SELECT 
    'Conversations' as metric,
    COUNT(*) as total,
    SUM(message_count) as total_messages
FROM conversations 
WHERE timestamp >= datetime('now', '-30 days')

UNION ALL

SELECT 
    'Checklist Downloads' as metric,
    COUNT(*) as total,
    0 as total_messages
FROM downloads 
WHERE timestamp >= datetime('now', '-30 days')
  AND type = 'checklist'

UNION ALL

SELECT 
    'Calendar Downloads' as metric,
    COUNT(*) as total,
    0 as total_messages
FROM downloads 
WHERE timestamp >= datetime('now', '-30 days')
  AND type = 'calendar';

.quit
EOF
```

### Performance Report

```bash
sqlite3 /tmp/benefitsflow_metrics.db <<EOF
.headers on
.mode csv
.output performance_report_$(date +%Y%m).csv

SELECT 
    DATE(timestamp) as date,
    COUNT(*) as requests,
    AVG(response_time_ms) as avg_response_ms,
    AVG(rag_time_ms) as avg_rag_ms,
    COUNT(CASE WHEN error_type IS NOT NULL THEN 1 END) as errors
FROM performance
WHERE timestamp >= datetime('now', '-30 days')
GROUP BY DATE(timestamp)
ORDER BY date DESC;

.quit
EOF
```

## Database Schema

### conversations
- `id`: Primary key
- `timestamp`: ISO format timestamp
- `message_count`: Number of messages in conversation

### downloads
- `id`: Primary key
- `timestamp`: ISO format timestamp
- `type`: 'checklist' or 'calendar'
- `programs`: JSON array of program names

### performance
- `id`: Primary key
- `timestamp`: ISO format timestamp
- `response_time_ms`: Total response time
- `rag_time_ms`: RAG service call time
- `error_type`: Error type if any
- `accuracy`: Evaluation score (0-1) - **RESERVED FOR FUTURE USE** (Godsee/Deric)
- `actionability`: Evaluation score (0-1) - **RESERVED FOR FUTURE USE** (Godsee/Deric)
- `simplicity`: Evaluation score (0-1) - **RESERVED FOR FUTURE USE** (Godsee/Deric)
- `empathy`: Evaluation score (0-1) - **RESERVED FOR FUTURE USE** (Godsee/Deric)

**Note:** Evaluation scores are not currently being tracked. The database schema includes these fields for future implementation by Godsee and Deric. When ready, they can call `log_performance()` with these parameters.

## Maintenance

### Backup Database

```bash
# On EC2 Instance 1
scp ec2-user@[INSTANCE-1-IP]:/tmp/benefitsflow_metrics.db ./backup_$(date +%Y%m%d).db
```

### Cleanup Old Data (Optional)

```sql
-- Delete data older than 90 days
DELETE FROM conversations WHERE timestamp < datetime('now', '-90 days');
DELETE FROM downloads WHERE timestamp < datetime('now', '-90 days');
DELETE FROM performance WHERE timestamp < datetime('now', '-90 days');
```

### Database Size

Typical size: **5-10 MB per month** (negligible cost)

## Integration Notes

- All metrics code is in `UI/metrics.py`
- Integrated into `UI/fastapi_backend.py` only
- Does not modify Deric's RAG service code
- Database auto-initializes on first import
- Errors in logging are caught and printed (won't crash the app)

## Testing

```python
# Test metrics locally
from metrics import (
    log_conversation,
    log_download,
    log_performance,
    get_monthly_stats
)

# Log test data
log_conversation(message_count=5)
log_download('checklist', ['CalFresh', 'Medi-Cal'])
log_performance(response_time_ms=250, rag_time_ms=150)

# View stats
stats = get_monthly_stats(days=1)
print(stats)
```

