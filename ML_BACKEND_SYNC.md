# ML Anomaly Detection — Backend Sync Guide

## Data Flow: Go Backend → Python ML

### Go Backend produces CheckResult records

The Go backend (`api/common/services/monitor_worker.service.go`) executes HTTP checks and stores results in MongoDB:

```
CheckResult {
  monitorId: string
  responseTimeMs: int64
  status: string ("up" or "down")
  statusCode: int
  attempts: int
  error: string (optional)
  checkedAt: datetime
  createdAt: datetime
}
```

**Key field mappings:**
| Go Backend | Python | Type | Notes |
|---|---|---|---|
| `monitorId` | `monitor_id` (query param) | string | Identifies the monitor |
| `responseTimeMs` | Feature input | int64 | Raw HTTP response time |
| `status` | Feature input | string | "up" (success) or "down" (failure) |
| `statusCode` | Feature input | int | HTTP status code (200, 500, etc.) |
| `attempts` | Feature input | int | Number of retry attempts |
| `checkedAt` | Temporal ordering | datetime | When the check ran |

### Python ML Pipeline syncs exactly

**Step 1: Data Loader** (`ml/data_loader.py`)
- Queries MongoDB collection `CheckResult` with field name `monitorId` (camelCase)
- Filters by `checkedAt` >= (now - N days)
- Returns raw dicts with Go backend field names (case-sensitive)

**Step 2: Feature Transformer** (`ml/feature_transformer.py`)
- Extracts 6 features from each check:
  1. **Raw response time** (ms)
  2. **Normalized response time** (z-score using training stats)
  3. **Success flag** (1 if status=="up", else 0)
  4. **Normalized status code** (z-score)
  5. **Failure flag** (1 - success)
  6. **Attempts** (retry count)
- Normalizes using mean/std from training data

**Step 3: Isolation Forest** (`ml/anomaly_model.py`)
- Unsupervised: no labels needed
- Learns what "normal" checks look like (clusters in feature space)
- Flags outliers as anomalies

**Step 4: Inference** (`services/ml_anomaly_detector.py`)
- Loads trained model + transformer from disk
- Takes recent checks from Go backend (via gRPC)
- Scores each check: 0 = normal, 1 = anomalous

---

## Why This Alignment Matters

- **Field names must match Go schema**: `monitorId` not `monitor_id` in Mongo queries
- **Status is a string**: "up" / "down", not boolean True/False
- **ResponseTimeMs is int64**: Python handles this automatically with numpy
- **Attempts field provides robustness signal**: multiple retries → different anomaly profile

If any field name or type changes in Go, update:
1. `ml/data_loader.py` (MongoDB query)
2. `ml/feature_transformer.py` (feature extraction)
3. Retrain models

---

## How to Use

### 1. Train a model (one-time per monitor)
```bash
cd reliability-service
pip install -r requirements.txt

# Train on 14 days of historical data (or fallback to 7, 3, 1 day)
python train_anomaly_model.py "6a2c342367d7434a69e89a63"
```

This creates:
- `ml/models/6a2c342367d7434a69e89a63_anomaly_model.pkl`
- `ml/models/6a2c342367d7434a69e89a63_transformer.pkl`

### 2. Use in insight generation

In `services/insight_generator.py`, replace the old heuristic with:

```python
from services.ml_anomaly_detector import MLAnomalyDetector

def generate_insight(monitor_id: str) -> Insight:
    checks = get_recent_checks(monitor_id)
    
    # Old heuristic:
    # anomaly_detected = detect_anomaly(features)
    
    # New ML:
    ml_detector = MLAnomalyDetector(monitor_id)
    ml_result = ml_detector.predict_anomaly(checks)
    anomaly_detected = ml_result["is_anomaly"]
    anomaly_score = ml_result["anomaly_score"]
    
    # ... rest of insight generation
```

### 3. Retrain periodically (recommended: daily)

```bash
# In a cron job or scheduler:
python train_anomaly_model.py "6a2c342367d7434a69e89a63"
```

This captures new patterns in check behavior.

---

## Troubleshooting

**Model not found?**
```
WARNING: No trained model found for monitor ...
Run: python train_anomaly_model.py <monitor_id>
```
→ Train the model first.

**Insufficient data?**
```
FAILED: Insufficient data. Got 5 checks, need at least 20.
```
→ Wait 1-2 days for more checks, then retry training.

**MongoDB connection error?**
```
ERROR: Failed to load historical data: [connection error]
```
→ Set `MONGO_URI` env var or ensure MongoDB is running.

---

## Architecture Notes

- **Unsupervised learning**: no manual labeling needed; learns from data distribution
- **Isolation Forest**: efficient, scales to ~millions of checks
- **Persistent models**: trained once, loaded from disk (fast inference)
- **Graceful degradation**: works with 1-14 days of data (minimum 20 checks)
- **Backward compatible**: if model missing, inference returns "not anomaly" (no crash)
