# Production Observability Guide — Vehicle Insurance MLOps

## 1. What Observability Means

In modern distributed cloud-native MLOps architectures, **monitoring** asks: *"Is the system working?"* (typically via threshold alerts and uptime pings). **Observability** asks: *"Why is the system behaving this way from its external outputs?"*

Observability is built upon three telemetry pillars plus health semantics:
- **Metrics**: High-frequency numerical aggregations (*"How much / how often?"*) — request count, error rates, latencies, resource consumption.
- **Logs**: Discrete event streams with rich contextual metadata (*"What happened at that specific millisecond?"*) — stack traces, model prediction results, training pipeline triggers.
- **Traces**: Distributed lifecycle of requests across microservices (*"Where was time spent?"*).
- **Health Probes**: Immediate lifecycle status (*"Is the container alive and should it receive traffic?"*).

---

## 2. Why the Vehicle Insurance Project Needs Observability

This project serves real-time machine learning predictions and batch model retraining in production on AWS EKS with MongoDB Atlas and S3 model registries:

1. **Prediction Latency & Availability**: Users interacting with the vehicle insurance web portal need sub-second predictions. Observability exposes P50, P95, and P99 latency percentiles to catch model inference degradations.
2. **Crash & Restart Prevention**: Machine learning inference and data preprocessing libraries (pandas, scikit-learn, dill) can consume substantial memory. Observability provides visibility into memory working sets before Out-Of-Memory (OOM) killer events occur.
3. **Training Failure Detection**: Retraining jobs triggered via `/train` run in the background. Automated metrics detect if data ingestion, validation, transformation, or S3 pusher fails.
4. **Third-Party Integrations**: Unmonitored network failures with MongoDB Atlas or S3 bucket permission errors (`AccessDenied`) cause silent user-facing errors if not measured through counters.

---

## 3. Architecture Overview

```text
                                  USERS / CLIENTS
                                         │
                                         ▼
                                AWS Load Balancer
                                         │
                                         ▼
                             Kubernetes Service (:80)
                                         │
                         ┌───────────────┴───────────────┐
                         ▼                               ▼
                 Pod 1 (:5000)                   Pod 2 (:5000)
             [vehicle-insurance]             [vehicle-insurance]
                 │        │                      │        │
                 │        ▼                      │        ▼
                 │    FastAPI App                │    FastAPI App
                 │   /     |    \                │   /     |    \
                 │ Pred  Train Health            │ Pred  Train Health
                 │   │     │                     │   │     │
                 │   │     ▼                     │   │     ▼
                 │   │  MongoDB                  │   │  MongoDB
                 │   ▼                           │   ▼
                 │ Model (S3)                    │ Model (S3)
                 │                               │
                 └───────────────┬───────────────┘
                                 │
           ┌─────────────────────┼─────────────────────┐
           ▼                                           ▼
   AWS CloudWatch / OTel                       Prometheus Scraper
 (amazon-cloudwatch-observability)             (k8s/observability)
           │                                           │
  ┌────────┴────────┐                         ┌────────┴────────┐
  ▼                 ▼                         ▼                 ▼
Logs (CW)      Container Insights          Prometheus TSDB     AMP Workspace
(App, Host,    (Node/Pod CPU, Mem,        (Scrapes /metrics) (Remote-Write)
DataPlane)     Restarts)                              │
  │                 │                                 ▼
  └────────┬────────┘                              Grafana
           ▼                             (Production Dashboards)
  CloudWatch Dashboard                                │
 (Infrastructure & Logs)                              ▼
                                                    Alerts
                                          (Error rates, Latencies, OOM)
```

---

## 4. Telemetry Component Roles

### A. Amazon CloudWatch & AWS OTel Add-on
- **Add-on**: `amazon-cloudwatch-observability` deployed as DaemonSets in `amazon-cloudwatch` namespace.
- **Role**: Collects kernel-level node metrics, container metrics (CPU utilization %, memory working set %, pod restarts), and streams container stdout/stderr logs into CloudWatch Log Groups.
- **Log Group**: `/aws/containerinsights/my-eks-cluster/application`.

### B. Prometheus (`/metrics`)
- **Role**: Scrapes application-level metrics exposed on `GET /metrics` every 15 seconds.
- **Custom Metrics**: Prediction throughput, prediction errors, inference latency histograms, model training pipeline runs, MongoDB error counters.
- **Storage**: Prometheus TSDB inside EKS with optional remote-write to Amazon Managed Service for Prometheus (AMP workspace `ws-900da2bf-84b6-4070-ac1a-fd3a37449ccc`).

### C. Grafana
- **Role**: Visualization layer for application and business metrics.
- **Provisioned Dashboard**: `Vehicle Insurance — Production Observability` loaded automatically from config maps.

---

## 5. Application Metrics Reference

All metrics follow Prometheus naming conventions prefixed with `vehicle_insurance_`:

| Metric Name | Type | Labels | Description |
| :--- | :--- | :--- | :--- |
| `vehicle_insurance_prediction_requests_total` | Counter | `status` (`success`, `failure`) | Total prediction requests received |
| `vehicle_insurance_prediction_errors_total` | Counter | `error_type` | Total prediction failures categorized by exception type |
| `vehicle_insurance_prediction_latency_seconds` | Histogram | `le` (buckets: 0.01s - 10s) | Time spent processing inference |
| `vehicle_insurance_training_runs_total` | Counter | `status` (`started`, `completed`, `failed`) | Model training pipeline executions |
| `vehicle_insurance_training_failures_total` | Counter | `stage` (`pipeline`) | Failures during model retraining |
| `vehicle_insurance_mongodb_errors_total` | Counter | `operation` (`connection`, `query`) | Failures encountered communicating with MongoDB |
| `vehicle_insurance_http_requests_total` | Counter | `method`, `endpoint`, `status_code` | HTTP requests received across endpoints |
| `vehicle_insurance_http_request_duration_seconds`| Histogram | `method`, `endpoint`, `le` | HTTP request latencies across endpoints |

> [!IMPORTANT]
> **No High-Cardinality Labels**: Metric labels exclude user IDs, form field values, raw customer data, and timestamps. Using dynamic values as labels creates cardinality explosions that degrade TSDB memory.

---

## 6. Kubernetes Health Probes & Resource Limits

Configured in [`deployment.yaml`](file:///d:/mlops/vehicleInsuranceDomain/deployment.yaml):

### Readiness Probe
- **Path**: `GET /ready` on port 5000.
- **Purpose**: Tells Kubernetes: *"Should traffic from the LoadBalancer be routed to this pod?"*
- **Settings**: `initialDelaySeconds: 10`, `periodSeconds: 5`, `failureThreshold: 2`.
- **Behavior**: If the application is initializing or overwhelmed, Kubernetes isolates the pod from traffic without killing the process.

### Liveness Probe
- **Path**: `GET /health` on port 5000.
- **Purpose**: Tells Kubernetes: *"Is the container process deadlocked or dead? Should Kubernetes restart it?"*
- **Settings**: `initialDelaySeconds: 15`, `periodSeconds: 10`, `failureThreshold: 3`.
- **Behavior**: If 3 consecutive checks fail, kubelet restarts the container.

### Resource Requests & Limits
```yaml
resources:
  requests:
    cpu: "250m"
    memory: "512Mi"
  limits:
    cpu: "1000m"
    memory: "1536Mi"
```
- **Rationale**: Python with scikit-learn, pandas, and FastAPI requires ~300Mi under baseline load. Setting requests to `512Mi` guarantees worker node capacity. A `1536Mi` limit prevents memory leaks from crashing the entire EC2 node.

---

## 7. Useful PromQL Queries

### Prediction Request Throughput
```promql
sum(rate(vehicle_insurance_prediction_requests_total[5m])) by (status)
```

### Prediction Error Rate (%)
```promql
sum(rate(vehicle_insurance_prediction_errors_total[5m])) / (sum(rate(vehicle_insurance_prediction_requests_total[5m])) + 0.001) * 100
```

### P50, P95, and P99 Prediction Latency
```promql
# P50 (Median)
histogram_quantile(0.50, sum(rate(vehicle_insurance_prediction_latency_seconds_bucket[5m])) by (le))

# P95
histogram_quantile(0.95, sum(rate(vehicle_insurance_prediction_latency_seconds_bucket[5m])) by (le))

# P99
histogram_quantile(0.99, sum(rate(vehicle_insurance_prediction_latency_seconds_bucket[5m])) by (le))
```

### Model Training Runs in the Last 24 Hours
```promql
sum(increase(vehicle_insurance_training_runs_total{status="completed"}[24h]))
```

### MongoDB Failure Rate
```promql
sum(rate(vehicle_insurance_mongodb_errors_total[5m])) by (operation)
```

---

## 8. Alerting Rules

Defined in [`k8s/observability/alerts.yaml`](file:///d:/mlops/vehicleInsuranceDomain/k8s/observability/alerts.yaml):

1. **`VehicleInsurancePodUnavailable`**: Triggers if 0 pods report `UP` status for > 2 minutes (Severity: `critical`).
2. **`HighPredictionErrorRate`**: Triggers if prediction failures exceed 5% of requests for > 5 minutes (Severity: `warning`).
3. **`HighPredictionLatency`**: Triggers if P95 prediction latency exceeds 1.0 second for > 5 minutes (Severity: `warning`).
4. **`MongoDBErrorSpike`**: Triggers if database errors occur at > 0.1/sec for > 2 minutes (Severity: `critical`).
5. **`ModelTrainingFailed`**: Triggers if a training pipeline run fails within 1 hour (Severity: `warning`).
6. **`HighContainerMemoryUsage`**: Triggers if container working set exceeds 85% of memory limit (> 1.3 GiB) for > 5 minutes (Severity: `warning`).

---

## 9. Verification & Operational Commands

### Local Verification
```powershell
# Run the test suite (10/10 tests covering health, metrics, prediction counters)
.\venv\Scripts\python.exe -m pytest -v

# Run app locally
.\venv\Scripts\python.exe app.py

# Query health & metrics
Invoke-RestMethod -Uri http://localhost:5000/health
Invoke-RestMethod -Uri http://localhost:5000/ready
(Invoke-WebRequest -Uri http://localhost:5000/metrics).Content
```

### Kubernetes Verification
```powershell
# Check Application pods in default namespace
kubectl get pods -n default -l app=vehicle-insurance

# Check Observability pods (Prometheus & Grafana)
kubectl get pods -n observability

# Check CloudWatch & OpenTelemetry daemonsets
kubectl get pods -n amazon-cloudwatch

# Access Grafana Dashboard locally via Port-Forward
kubectl port-forward svc/grafana 3000:3000 -n observability
# Open http://localhost:3000 (pre-loaded dashboard: Vehicle Insurance — Production Observability)

# Access Prometheus UI locally via Port-Forward
kubectl port-forward svc/prometheus 9090:9090 -n observability
# Open http://localhost:9090
```

### AWS CloudWatch Verification
```powershell
# Verify CloudWatch Observability Add-on is ACTIVE
aws eks describe-addon --cluster-name my-eks-cluster --addon-name amazon-cloudwatch-observability --region us-east-1 --query "addon.status"

# Inspect application log groups
aws logs describe-log-groups --log-group-name-prefix /aws/containerinsights/my-eks-cluster --region us-east-1

# View live application logs
aws logs tail /aws/containerinsights/my-eks-cluster/application --follow --region us-east-1
```

---

## 10. Troubleshooting Guide

| Symptom | Likely Cause | Diagnostic Command | Remediation |
| :--- | :--- | :--- | :--- |
| **Pod status `Pending`** | Worker nodes are cordoned or insufficient CPU/RAM | `kubectl describe pod <pod_name>` | Run `kubectl uncordon <node_name>` or adjust resource requests. |
| **Pod in `CrashLoopBackOff`** | Liveness probe failing or missing env var | `kubectl logs <pod_name> --previous` | Check if port 5000 is open and `MONGODB_URL` is set in deployment. |
| **`GET /metrics` returns 404** | Old Docker image running without instrumentation | `kubectl exec -it <pod_name> -- curl localhost:5000/metrics` | Trigger GitHub Actions CI/CD to push latest image to EKS. |
| **CloudWatch add-on degraded / no logs** | Worker node role lacks CloudWatch permissions | `aws iam list-attached-role-policies --role-name <node_role>` | Attach `arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy` to node role. |
| **Grafana shows empty panels** | Prometheus has not scraped targets yet | `kubectl logs -n observability -l app=prometheus` | Ensure pod annotations `prometheus.io/scrape: "true"` are present. |
| **High prediction latency** | CPU throttling or heavy memory contention | `kubectl top pod -l app=vehicle-insurance` | Increase container CPU limit in `deployment.yaml`. |

---

## 11. Security & IAM Best Practices

- **Zero Hardcoded Secrets**: Secrets such as `MONGODB_URL` are passed via Kubernetes environment variables / Secret manifests, never hardcoded in source code or committed to Git.
- **Least Privilege IAM**:
  - `GitHubActions-VehicleInsurance`: Scoped to ECR push, EKS describe/access, and deployment rollout. It does **not** possess broad administrative CloudWatch/S3 write privileges.
  - `NodeInstanceRole`: Equipped with `CloudWatchAgentServerPolicy`, `AWSXrayWriteOnlyAccess`, and scoped S3 bucket access.
- **Log Sanitation**: Stack traces and error messages filter out connection strings, passwords, and AWS session tokens before logging to stdout.

---

## 12. Future Advanced ML Observability (Planned Roadmap)

While infrastructure and application telemetry is now in production, the following advanced ML monitoring capabilities are planned:
- **Feature & Data Drift**: Measuring drift between training baseline distribution and incoming inference features using **Evidently AI** or **Great Expectations**.
- **Model Concept Drift**: Tracking changes in true conversion labels vs predicted probability over weekly cohorts.
- **Automated Retraining Trigger**: Publishing an alert to an AWS SNS topic or invoking an Airflow/GitHub Actions workflow when prediction drift exceeds a Wasserstein distance threshold of 0.15.
