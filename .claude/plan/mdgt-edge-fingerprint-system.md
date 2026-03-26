# MDGT Edge Fingerprint Verification System - Implementation Plan

## Overview

Build a complete Fingerprint Verification 1:N system deployed on Jetson Nano, with:
- Web UI (React, port 3000) for enrollment, verification, model management
- FastAPI backend with full REST API
- MDGTv2 deep learning pipeline (ONNX/TensorRT inference)
- FAISS-based 1:N identification
- CLI for headless operation
- Async processing with profiling

## Current State Analysis

### What Exists
| Component | Status | Files |
|-----------|--------|-------|
| Core models | Basic (User, Fingerprint, MatchResult) | `core/models.py` |
| Interfaces | MatchingEngine + ImageProcessor ABCs | `core/interfaces.py` |
| Device matching | Working (hardware sensor matching) | `core/services/matching_engine.py` |
| ONNX matching | Placeholder (no MDGTv2 pipeline) | `core/services/matching_engine.py:98-259` |
| Database | Simple schema (users + fingerprints) | `data/database.py`, `data/repositories/` |
| PyQt6 UI | LiveView, Database, AI tabs | `ui/widgets/` |
| Web backend | SSH remote control + fingerprint scripts | `web/backend/` |
| Web frontend | SSH terminal + connection panel only | `web/frontend/` |

### Critical Gaps (vs. DOCX Spec)
1. **No MDGTv2 inference pipeline** (preprocessing, minutiae extraction, graph construction, embedding)
2. **No FAISS index** for 1:N identification
3. **No TensorRT/ONNX optimization pipeline**
4. **Simplified DB schema** - missing: employee_id, department, role, encrypted embeddings, verification_logs, devices, system_config
5. **No encryption** for biometric data at rest
6. **Minimal web UI** - only SSH terminal, no fingerprint management screens
7. **No CLI** for headless operation
8. **No profiling/async infrastructure**

---

## Implementation Phases

### Phase 1: Database & Data Layer Upgrade
**Goal**: Align database schema with DOCX spec (Section 5)

#### 1.1 Upgrade Database Schema
- **File**: `data/database.py` - Expand `_init_schema()` with full DDL from spec
- New tables: `verification_logs`, `devices`, `system_config`
- Expand `users` table: add `employee_id`, `full_name`, `department`, `role`, `is_active`
- Expand `fingerprints` table: add `finger_index`, `embedding_enc`, `minutiae_enc`, `quality_score` (NFIQ2), `image_hash`, `is_active`
- Add migration strategy (detect old schema, migrate data)

#### 1.2 Update Domain Models
- **File**: `core/models.py`
- Update `User` dataclass: add employee_id, full_name, department, role, is_active
- Update `Fingerprint` dataclass: add finger_index, embedding (encrypted), minutiae (encrypted)
- New models: `VerificationLog`, `Device`, `SystemConfig`, `Embedding`

#### 1.3 Update Repositories
- **Files**: `data/repositories/user_repository.py`, `data/repositories/fingerprint_repository.py`
- New: `data/repositories/log_repository.py`
- New: `data/repositories/device_repository.py`
- New: `data/repositories/config_repository.py`
- Update all CRUD operations for new schema

#### 1.4 Encryption Module
- **New file**: `core/services/crypto_service.py`
- Fernet (AES-128-CBC) encryption for embeddings and minutiae at rest
- Key derivation from device-bound secret
- Encrypt/decrypt helpers for BLOB fields

---

### Phase 2: MDGTv2 Inference Pipeline
**Goal**: Implement full AI pipeline from sensor image to 256-dim embedding

#### 2.1 Image Preprocessing Module
- **New file**: `core/pipeline/preprocessing.py`
- CLAHE adaptive histogram equalization
- Gabor filter bank for ridge enhancement
- Orientation field estimation
- Segmentation mask + thinning
- Input: raw 192x192 grayscale → Output: clean binary ridge image

#### 2.2 Minutiae Extraction Module
- **New file**: `core/pipeline/minutiae_extractor.py`
- Wrapper for FingerNet (PyTorch model) or vendor SDK
- Output: list of (x, y, theta, type, quality) tuples
- False minutiae filtering
- Minimum minutiae count validation (12 per spec)

#### 2.3 Graph Construction Module
- **New file**: `core/pipeline/graph_builder.py`
- Build 5-dim feature matrix (N x 5): x, y, cos(theta), sin(theta), type_norm
- Compute pairwise relational features (N x N x 7)
- Dynamic k-NN graph construction (k=16)
- Relational positional encoding (RPE)

#### 2.4 MDGTv2 Inference Engine
- **New file**: `core/pipeline/mdgtv2_engine.py`
- Abstract base: `InferenceBackend` (ONNX, TensorRT)
- ONNX Runtime backend: load .onnx model, run inference
- TensorRT backend: load .engine file, FP16 inference
- Output: L2-normalized 256-dim embedding vector
- Async inference support with `asyncio`

#### 2.5 FAISS Index Manager
- **New file**: `core/pipeline/faiss_index.py`
- FlatIP (brute-force) for galleries < 5,000
- IVFFlat for larger galleries (nlist=sqrt(N), nprobe=8)
- Incremental add on enrollment
- Full rebuild on deletion
- ID mapping: FAISS internal ID <-> fingerprints.id
- Load from encrypted embeddings on startup

#### 2.6 Unified Pipeline Orchestrator
- **New file**: `core/pipeline/pipeline.py`
- Chains: Preprocessing -> Minutiae -> Graph -> MDGTv2 -> Embedding
- Async execution with profiling decorators
- Configurable thresholds from system_config table
- Pipeline profiling: time each stage, total latency

---

### Phase 3: Matching Engine Upgrade
**Goal**: Replace placeholder ONNX engine with real MDGTv2 pipeline

#### 3.1 MDGTv2 Matching Engine
- **Update**: `core/services/matching_engine.py`
- New `MDGTv2MatchingEngine(MatchingEngine)` class
- Uses pipeline orchestrator for embedding extraction
- Uses FAISS for 1:N search (identify)
- Cosine similarity for 1:1 verification (verify)
- Configurable thresholds (verify: 0.55, identify: 0.50)
- Add `EngineType.MDGTV2` to enum

#### 3.2 TensorRT Conversion Tool
- **New file**: `tools/convert_trt.py`
- ONNX -> TensorRT engine conversion
- FP16 precision option
- Dynamic axes support for variable minutiae count
- Profile: measure latency on target hardware

---

### Phase 4: Web Backend API (FastAPI)
**Goal**: Full REST API per DOCX Section 11, plus model management

#### 4.1 Restructure Backend for Dual Mode
- Backend runs **locally on Jetson** (not just SSH remote)
- Keep SSH mode as fallback for remote development
- **New file**: `web/backend/services/local_fingerprint_service.py`
  - Direct import of `core/` modules when running on Jetson
  - No SSH overhead, native sensor access

#### 4.2 User Management API
- **Update**: `web/backend/routers/fingerprint.py` -> split into multiple routers
- **New**: `web/backend/routers/users.py`
  - `POST /api/v1/enroll` - Full enrollment flow (user details + fingerprint capture + embedding)
  - `GET /api/v1/users` - List users (paginated, filterable)
  - `GET /api/v1/users/{id}` - User detail with enrolled fingers
  - `PUT /api/v1/users/{id}` - Update user details
  - `DELETE /api/v1/users/{id}` - Deactivate user + cascade templates

#### 4.3 Verification API
- **New**: `web/backend/routers/verification.py`
  - `POST /api/v1/verify` - 1:1 verification (probe image + user_id)
  - `POST /api/v1/identify` - 1:N identification (probe image -> top-K candidates)
  - WebSocket `/ws/verify` - Real-time verification stream

#### 4.4 Model Management API
- **New**: `web/backend/routers/models.py`
  - `GET /api/v1/models` - List available models (ONNX, TensorRT engines)
  - `POST /api/v1/models/upload` - Upload new model weights (.onnx, .pth, .engine)
  - `POST /api/v1/models/{id}/activate` - Set active model for inference
  - `POST /api/v1/models/{id}/convert` - Trigger ONNX -> TensorRT conversion
  - `GET /api/v1/models/{id}/profile` - Get profiling data (latency, memory)
  - `DELETE /api/v1/models/{id}` - Remove model file

#### 4.5 System & Monitoring API
- **New**: `web/backend/routers/system.py`
  - `GET /api/v1/health` - System health (CPU/GPU temp, memory, sensor, gallery size)
  - `GET /api/v1/logs` - Verification logs (paginated, filterable)
  - `GET /api/v1/config` - System configuration
  - `PUT /api/v1/config` - Update configuration
  - `POST /api/v1/backup` - Trigger database backup
  - `GET /api/v1/stats` - Dashboard stats (enrolled count, today's verifications, acceptance rate, avg latency)

#### 4.6 Async & Profiling Infrastructure
- **New**: `web/backend/middleware/profiling.py`
  - Request timing middleware
  - Endpoint profiling decorator
- **New**: `web/backend/services/profiler.py`
  - Pipeline stage profiling (preprocessing, minutiae, inference, FAISS)
  - Model benchmark utility (batch inference timing)
  - Memory usage tracking (tegrastats integration on Jetson)

---

### Phase 5: Web Frontend (React + Vite, Port 3000)
**Goal**: Full-featured web UI with 5 main screens

#### 5.1 Project Setup & Layout
- **Update**: `web/frontend/package.json` - Add dependencies:
  - `react-router-dom` (routing)
  - `@tanstack/react-query` (data fetching)
  - `tailwindcss` (styling)
  - `lucide-react` (icons)
  - `recharts` (charts for dashboard)
  - `react-hot-toast` (notifications)
- **New**: `web/frontend/src/layouts/MainLayout.tsx` - Navigation sidebar + content area
- **New**: `web/frontend/src/services/api.ts` - API client for all endpoints

#### 5.2 Verification Screen (Home)
- **New**: `web/frontend/src/pages/VerificationPage.tsx`
- Large fingerprint capture area with real-time preview
- ACCEPT/REJECT visual feedback (green/red animation)
- Matched user info display (name, photo, employee ID)
- Verification mode toggle: 1:1 vs 1:N
- WebSocket-based live stream

#### 5.3 Enrollment Wizard
- **New**: `web/frontend/src/pages/EnrollmentPage.tsx`
- Multi-step wizard:
  1. Enter employee ID + user details
  2. Select fingers to enroll (finger position diagram)
  3. Capture fingerprints (3 captures per finger, quality selection)
  4. Quality validation feedback
  5. Confirmation + save
- Progress bar, quality indicators, finger position guide

#### 5.4 Admin Dashboard
- **New**: `web/frontend/src/pages/DashboardPage.tsx`
- Stats cards: total enrolled, today's verifications, acceptance rate, avg latency
- Charts: verification trend (7 days), hourly distribution
- Recent verification log table with filtering
- Quick action buttons: enroll, manage users, settings

#### 5.5 User Management
- **New**: `web/frontend/src/pages/UsersPage.tsx`
- Searchable/filterable user list (table or card view)
- User detail panel: enrolled fingers, enrollment date, verification history
- Actions: edit details, re-enroll fingers, deactivate, delete
- Bulk operations support

#### 5.6 Model Management
- **New**: `web/frontend/src/pages/ModelsPage.tsx`
- List active/available models with metadata (size, format, latency)
- Upload new model files (drag & drop)
- Trigger ONNX -> TensorRT conversion with progress
- Profile model (run benchmark, show latency chart)
- Switch active model

#### 5.7 Settings Page
- **New**: `web/frontend/src/pages/SettingsPage.tsx`
- Verification threshold sliders (verify: 0.3-0.9, identify: 0.3-0.9)
- Sensor configuration
- Language selector (Vietnamese / English)
- Database backup/restore
- System info (device, firmware, uptime)

#### 5.8 Shared Components
- `components/FingerprintCanvas/` - Fingerprint image display with quality overlay
- `components/StatusBadge/` - Connection/sensor status indicator
- `components/DataTable/` - Reusable sortable/filterable table
- `components/StatsCard/` - Dashboard stat card
- `components/FingerDiagram/` - Hand diagram for finger selection

---

### Phase 6: CLI Interface
**Goal**: Headless operation for scripting and automation

#### 6.1 CLI Application
- **New file**: `cli/main.py` (using `click` or `argparse`)
- Commands:
  - `mdgt enroll --employee-id E001 --name "John Doe"` - Interactive enrollment
  - `mdgt verify --user-id 1` - 1:1 verification
  - `mdgt identify` - 1:N identification
  - `mdgt users list` - List enrolled users
  - `mdgt users delete <id>` - Delete user
  - `mdgt model list` - List available models
  - `mdgt model activate <path>` - Set active model
  - `mdgt model convert --input model.onnx --output model.engine --fp16`
  - `mdgt model profile <path>` - Benchmark model
  - `mdgt status` - System health check
  - `mdgt db backup` - Database backup
  - `mdgt db restore <file>` - Database restore

---

### Phase 7: TensorRT & ONNX Optimization
**Goal**: Production-ready model deployment on Jetson Nano

#### 7.1 ONNX Optimization
- **New file**: `core/pipeline/onnx_optimizer.py`
- Fold constants, eliminate dead code, fuse BatchNorm
- Validate with onnx.checker
- Dynamic axes for variable minutiae count

#### 7.2 TensorRT Conversion
- **New file**: `core/pipeline/trt_converter.py`
- FP16 precision (Maxwell supports FP16)
- Profile latency: target < 50ms on 10W mode
- Fallback to ONNX Runtime with CUDA EP if TRT fails

#### 7.3 Profiling Framework
- **New file**: `core/pipeline/profiler.py`
- Decorator-based stage profiling
- Report: per-stage latency, total E2E latency, memory usage
- Export to JSON/CSV for analysis
- Integration with tegrastats for GPU metrics

---

## Architecture Diagram

```
                    +------------------+
                    |   Web Frontend   |
                    |  React + Vite    |
                    |   (port 3000)    |
                    +--------+---------+
                             |
                    +--------+---------+
                    |   FastAPI Backend |
                    |   (port 8000)    |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
     +--------+-----+ +-----+------+ +-----+------+
     | User/Verify  | |   Model    | |  System    |
     | Endpoints    | | Management | | Monitoring |
     +--------------+ +-----+------+ +-----+------+
                             |              |
                    +--------+---------+    |
                    | Pipeline Engine  |    |
                    | (Async + Profile)|    |
                    +--------+---------+    |
                             |              |
     +----------+----------+-+---------+    |
     |          |          |           |    |
  +--+--+  +---+---+  +---+---+ +-----+--+ |
  |Prepr|  |Minutia|  |Graph  | |MDGTv2  | |
  |ocess|  |Extract|  |Build  | |Inference| |
  +-----+  +-------+  +-------+ +----+---+ |
                                      |     |
                              +-------+--+  |
                              | FAISS    |  |
                              | Index    |  |
                              +----------+  |
                                            |
     +--------------------------------------+
     |         Data Layer                   |
     | SQLite + Crypto + Repositories       |
     +--------------------------------------+
     |         Sensor Layer                 |
     | USB Fingerprint Reader (0483:5720)   |
     +--------------------------------------+
```

## Tech Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Backend | Python 3.8+ / FastAPI | JetPack native, async, auto-docs |
| Frontend | React 18 + TypeScript + Vite | Modern, fast HMR, type-safe |
| UI Framework | TailwindCSS | Utility-first, responsive, small bundle |
| Database | SQLite 3 | Zero-config, embedded, ACID |
| ANN Search | FAISS (faiss-cpu) | Fast cosine similarity, IVFFlat |
| DL Inference | ONNX Runtime + TensorRT | Portable + Jetson-optimized |
| Encryption | cryptography (Fernet) | AES-128 at rest |
| CLI | click | Clean CLI framework |

## File Structure (New/Modified)

```
fingersensor/
+-- core/
|   +-- models.py                    # UPDATE: expanded models
|   +-- interfaces.py                # UPDATE: add InferenceBackend ABC
|   +-- pipeline/                    # NEW: entire directory
|   |   +-- __init__.py
|   |   +-- preprocessing.py         # Image enhancement
|   |   +-- minutiae_extractor.py    # Minutiae extraction
|   |   +-- graph_builder.py         # Dynamic k-NN graph
|   |   +-- mdgtv2_engine.py         # ONNX/TRT inference
|   |   +-- faiss_index.py           # FAISS index manager
|   |   +-- pipeline.py              # Orchestrator
|   |   +-- profiler.py              # Stage profiling
|   |   +-- onnx_optimizer.py        # ONNX graph optimization
|   |   +-- trt_converter.py         # TensorRT conversion
|   +-- services/
|       +-- matching_engine.py       # UPDATE: add MDGTv2MatchingEngine
|       +-- crypto_service.py        # NEW: encryption
|       +-- database_service.py      # UPDATE: new operations
+-- data/
|   +-- database.py                  # UPDATE: expanded schema
|   +-- repositories/
|       +-- user_repository.py       # UPDATE
|       +-- fingerprint_repository.py# UPDATE
|       +-- log_repository.py        # NEW
|       +-- device_repository.py     # NEW
|       +-- config_repository.py     # NEW
+-- web/
|   +-- backend/
|   |   +-- main.py                  # UPDATE: add new routers
|   |   +-- routers/
|   |   |   +-- users.py             # NEW
|   |   |   +-- verification.py      # NEW
|   |   |   +-- models.py            # NEW
|   |   |   +-- system.py            # NEW
|   |   +-- services/
|   |   |   +-- local_fingerprint_service.py  # NEW
|   |   |   +-- profiler.py          # NEW
|   |   +-- middleware/
|   |       +-- profiling.py         # NEW
|   +-- frontend/
|       +-- src/
|           +-- pages/               # NEW: all pages
|           |   +-- VerificationPage.tsx
|           |   +-- EnrollmentPage.tsx
|           |   +-- DashboardPage.tsx
|           |   +-- UsersPage.tsx
|           |   +-- ModelsPage.tsx
|           |   +-- SettingsPage.tsx
|           +-- layouts/
|           |   +-- MainLayout.tsx    # NEW
|           +-- components/           # NEW: shared components
|           |   +-- FingerprintCanvas/
|           |   +-- StatusBadge/
|           |   +-- DataTable/
|           |   +-- StatsCard/
|           |   +-- FingerDiagram/
|           +-- services/
|               +-- api.ts           # UPDATE: full API client
+-- cli/                             # NEW: entire directory
|   +-- __init__.py
|   +-- main.py
+-- tools/                           # NEW
|   +-- convert_trt.py
|   +-- init_db.py
|   +-- benchmark.py
+-- models/                          # NEW: model storage
|   +-- README.md
+-- config/                          # NEW
    +-- default.yaml
    +-- device.yaml
```

## Priority Order

1. **Phase 1** (Database) - Foundation for everything else
2. **Phase 4** (Web Backend API) - Enables frontend development
3. **Phase 5** (Web Frontend) - User-facing interface
4. **Phase 2** (MDGTv2 Pipeline) - Core AI inference
5. **Phase 3** (Matching Engine Upgrade) - Connect pipeline to matching
6. **Phase 7** (TensorRT Optimization) - Production performance
7. **Phase 6** (CLI) - Automation support

## Key Constraints

- **Jetson Nano 4GB RAM** - Memory budget: < 2.5GB for entire app
- **USB sensor (VID:0483 PID:5720)** - Requires custom SDK driver on Jetson
- **TensorRT FP16** - Maxwell GPU, 128 CUDA cores
- **Offline-capable** - No cloud dependency for core operations
- **Sub-500ms E2E** - Capture + preprocessing + inference + FAISS < 500ms

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| MDGTv2 model not available yet | Use ONNX placeholder, mock embeddings for development |
| TensorRT conversion fails for dynamic graph ops | Fallback to ONNX Runtime with CUDA EP |
| FAISS memory on 4GB Jetson | Use FlatIP for <5K, IVFFlat with careful nlist |
| Sensor SDK requires specific Jetson libs | Keep SSH remote mode as development fallback |
| Web UI performance on low-power Jetson | Serve pre-built static files, minimize JS bundle |
