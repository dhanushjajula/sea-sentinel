# Sea Sentinel 2.0 — AI-Powered Automated Underwater Marine Debris & Anomaly Detection System

**Organisation:** Ministry of Earth Sciences (MoES) — National Institute of Ocean Technology (NIOT)  
**Problem Statement ID:** SIH26057  
**Category:** Software | **Theme:** Renewable / Sustainable Energy & Blue Economy (SDG 14: Life Below Water)

---

## 1. System Architecture Flow

```text
User / AUV Telemetry
         │
         ▼
[Frontend UI Dashboard] (Dual Waterfall, GIS Leaflet Map, Inspection Tables)
         │  HTTP REST
         ▼
[FastAPI Backend Router Aggregator] (/api/v2/...)
         │
         ▼
[AI / ML Processing Core]
 ├── Sonar Preprocessing (Lee Speckle Filter + CLAHE Contrast Boost)
 ├── YOLO Detection (Fast Candidate Proposal Bounding Boxes)
 └── U-Net Semantic Segmentation (Pixel-Level Geometric Masks)
         │
         ▼
[Feature Processing Modules]
 ├── Geolocation Engine (Case A: Affine GeoTransform | Case B: Slant Range Navigation Math)
 ├── Debris Risk Priority Engine (Hazard Scoring & Solidity Analysis)
 ├── Natural vs. Man-Made Classifier (Autoencoder Anomaly Detection & Rock Cluster Filter)
 ├── Duplicate Detection (Multi-Frame Trajectory Correlation & Deduplication)
 ├── Debris Density Engine (Spatial Concentration Index & Heatmaps)
 └── Sonar Quality Evaluator (Speckle Index, ENL Gain & SNR Metrics)
         │
         ▼
[Database Persistence & Reporting] (SQLite Audit Log, GeoJSON, CSV & Visual Overlays)
         │
         ▼
[Interactive Dashboard Viewers]
```

---

## 2. Modular Project Directory Structure

```text
sea-sentinel/
├── frontend/                                   # Client-Side Application
│   ├── index.html                              # Main UI Dashboard Entry Point
│   ├── dashboard/                              # Main Dashboard Page & Subcomponents
│   │   ├── components/
│   │   ├── pages/
│   │   └── services/
│   ├── authentication/                         # User Auth & Session UI
│   ├── debris-detection/                       # YOLO Detection Table & Inspectors
│   ├── sonar-image-processing/                 # Denoising & CLAHE Controls
│   ├── geolocation/                            # Leaflet GIS Map Component
│   ├── debris-risk-scoring/                    # Risk Badge & Priority Views
│   ├── natural-manmade-classification/         # Anomaly & Rock Field Classifier UI
│   ├── duplicate-detection/                    # Multi-Frame Track Views
│   ├── debris-density/                         # Spatial Density Heatmap
│   ├── sonar-quality/                          # Quality Scoring & SNR Indicator
│   ├── visualization/                          # Dual Waterfall & Composite Renderers
│   └── shared/                                 # Shared Assets, Styles & API Client
│       ├── assets/
│       ├── css/
│       ├── js/
│       └── utils/
│
├── backend/                                    # Server-Side Application
│   ├── app/                                    # FastAPI App Entry Point
│   │   └── main.py
│   ├── api/                                    # Central API Router Aggregator
│   │   ├── routes.py
│   │   └── middleware.py
│   ├── authentication/                         # Auth Services & API Security
│   ├── debris-detection/                       # YOLO Object Detection Engine
│   ├── sonar-image-processing/                 # Speckle Filter & Radiometric CLAHE
│   ├── geolocation/                            # WGS84 Transformation & Nav Math
│   ├── debris-risk-scoring/                    # Priority Scoring & Morphometrics
│   ├── natural-manmade-classification/         # Autoencoder & DBSCAN Rock Filter
│   ├── duplicate-detection/                    # Multi-Frame Trajectory Correlator
│   ├── debris-density/                         # Spatial Density Estimator
│   ├── sonar-quality/                          # Speckle Index & Quality Evaluator
│   ├── visualization/                          # Overlay Generator & Waterfall Slices
│   ├── models/                                 # Neural Network Architectures
│   │   ├── unet_models.py                      (Attention U-Net)
│   │   └── autoencoder_models.py               (CNN Autoencoder)
│   ├── database/                               # SQLite DB & Audit Logging
│   │   ├── connection.py
│   │   └── audit_logger.py
│   └── shared/                                 # Shared Configs, Types & Utils
│       ├── config/
│       ├── types/
│       └── utils/
│
├── notebooks/                                  # ML Research & Training Notebooks
│   ├── eda/                                    # Comprehensive Exploratory Data Analysis
│   │   └── project_eda_deep_dive.ipynb
│   ├── yolo/                                   # Complete 26-Stage YOLO Workflow
│   │   ├── data-preparation/
│   │   ├── preprocessing/
│   │   ├── training/
│   │   ├── validation/
│   │   ├── testing/
│   │   └── evaluation/
│   ├── unet/                                   # Complete 24-Stage U-Net Workflow
│   │   ├── data-preparation/
│   │   ├── preprocessing/
│   │   ├── training/
│   │   ├── validation/
│   │   ├── testing/
│   │   └── evaluation/
│   ├── project-analysis/                       # Scientific Ablation & Benchmarks
│   └── experiments/                            # Model Checkpoint Logs
│
├── logs/                                       # Multi-Stream Centralized Logging
│   ├── frontend/
│   ├── backend/
│   ├── model-training/
│   ├── model-predictions/
│   └── errors/
│
├── data/                                       # Separated Dataset Repository
│   ├── raw/
│   ├── processed/
│   ├── yolo/
│   ├── unet/
│   └── samples/
│
├── models/                                     # Trained Checkpoint Weights
│   ├── yolo/                                   (best.pt, last.pt, yolo11n.pt)
│   ├── unet/                                   (attention_unet_best.pt)
│   └── autoencoder/                            (baseline_autoencoder.pt)
│
├── configs/                                    # System & Pipeline YAML Configs
│   ├── pipeline_config.yaml
│   ├── system_config.yaml
│   ├── preprocessing_config.yaml
│   ├── yolo_config.yaml
│   ├── unet_config.yaml
│   ├── anomaly_config.yaml
│   └── geospatial_config.yaml
│
├── tests/                                      # Full Test Suite
├── scripts/                                    # Operational & Execution CLI Scripts
├── reload_servers.bat                          # One-Click Full Stack Launcher (Windows)
├── reload_servers.ps1                          # PowerShell Server Manager
├── requirements.txt                            # Python Package Dependencies
└── README.md                                   # Project Documentation
```

---

## 3. Quick Start & Execution

### Prerequisites
* Python 3.10+
* CUDA-compatible GPU (optional, automatic CPU fallback included)

### 1. Installation
```powershell
pip install -r requirements.txt
```

### 2. Launching Full-Stack Application
```powershell
.\reload_servers.ps1
```
* **Frontend Web Dashboard:** `http://localhost:3000`
* **FastAPI Backend OpenAPI Docs:** `http://localhost:8000/docs`

### 3. Running Test Suite
```powershell
pytest tests/
```

### 4. Running the Complete Standalone Pipeline Script
```powershell
python scripts/run_pipeline.py --input test_fixtures/test_document.png
```

---

## 4. Key Machine Learning Benchmarks

| Component | Model / Method | Primary Metric | Result |
|---|---|---|---|
| **Candidate Detection** | Ultralytics YOLOv11 | $\text{mAP}@0.5$ / Precision | **0.9100 / 0.8900** |
| **Region Segmentation** | Attention U-Net (PyTorch) | Dice Coefficient / IoU | **0.8742 / 0.7815** |
| **Speckle Denoising** | Adaptive Lee Filter ($Cu=0.22$) | ENL Gain | **$1.28\times$ Gain** |
| **Anomaly Filtering** | 3-Sigma Autoencoder ($T=0.094$) | False Positive Reduction | **$94.5\%$ Suppressed** |
| **End-to-End Latency** | Parallel PyTorch + ONNX | Full Swath Inference | **~26 ms (~38 FPS)** |

---

## 5. API Endpoints Overview

| Endpoint | Method | Description |
|---|---|---|
| `/health` | `GET` | System health check and GPU diagnostics |
| `/analyze` | `POST` | Full end-to-end parallel AI agent survey analysis |
| `/api/v2/debris-detection/detect` | `POST` | Standalone YOLO candidate debris detection |
| `/api/v2/sonar-processing/enhance` | `POST` | Standalone Lee Speckle + CLAHE enhancement |
| `/api/v2/geolocation/tag` | `POST` | WGS84 coordinate calculation |
| `/api/v2/debris-risk/score` | `POST` | Hazard and risk priority scoring |
| `/api/v2/duplicate-detection/track`| `POST` | Multi-frame target tracking and deduplication |
| `/api/v2/sonar-quality/evaluate` | `POST` | Backscatter and speckle quality assessment |
| `/audit/recent` | `GET` | Historical SQLite survey inspection audits |
