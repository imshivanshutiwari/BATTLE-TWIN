# BATTLE-TWIN

**Live Unreal Engine 5 Digital Twin for Real-Time Battlefield Command and Control with Multi-Agent LangGraph Decision Support**

---

## Overview

BATTLE-TWIN is a full-stack military digital twin system that provides real-time battlefield command and control (C2) capabilities. It combines:

- **Real-time state synchronization** via NATS JetStream
- **Multi-agent AI decision support** via LangGraph (5 specialized agents)
- **Unreal Engine 5 3D visualization** with C++ NATS plugin
- **Real data integration** from OSM, ADS-B, OpenWeatherMap, USGS DEM, Sentinel-2
- **Advanced algorithms**: D* Lite, MCTS COA, Bayesian threat assessment, EKF GPS, Madgwick AHRS
- **22-panel NVG green-on-black C2 dashboard** built with Plotly Dash

---

## Architecture

```
┌─────────────┐    NATS JetStream    ┌──────────────┐
│   Sensors   │ ──────────────────── │ Digital Twin │
│ IMU GPS THR │    battlefield.*     │   State DB   │
└─────────────┘                      └──────┬───────┘
                                            │
                    ┌───────────────────────┤
                    │                       │
             ┌──────▼──────┐        ┌───────▼───────┐
             │  LangGraph  │        │   Dash C2     │
             │  5 Agents   │        │  22 Panels    │
             │ S2/S3/FSO/  │        │  NVG Theme    │
             │ S4/CSS      │        └───────────────┘
             └──────┬──────┘
                    │ NATS
             ┌──────▼──────┐
             │   UE5 3D    │
             │   Plugin    │
             └─────────────┘
```

---

## Quick Start

```bash
cd battle-twin
pip install -r requirements.txt
python main.py  # Starts simulation + dashboard, auto-opens browser
```

### With NATS Server
```bash
docker run -d -p 4222:4222 -p 8222:8222 nats:latest -js
make run
```

---

## Project Structure

| Package | Files | Purpose |
|---|---|---|
| `utils/` | 6 | Seeding, logging, config, MGRS, checkpoints |
| `configs/` | 5 | YAML configurations for all subsystems |
| `data/` | 8 | Real data fetchers (OSM, ADS-B, weather, DEM, Sentinel, CoT) |
| `digital_twin/` | 7 | Canonical state, NATS pub/sub, reconciler, replay |
| `sensors/` | 6 | Madgwick IMU, EKF GPS, thermal, acoustic, aggregator |
| `terrain/` | 6 | DEM processor, slope, LOS/viewshed, cover, route scoring |
| `planning/` | 6 | D* Lite, MCTS COA, Bayesian threat, VRP, MANET |
| `agents/` | 10 | S2 Intel, S3 Maneuver, FSO Fires, S4 Logistics, CSS MEDEVAC, Commander, LangGraph |
| `comms/` | 4 | OLSR MANET sim, link quality, message bus |
| `training/` | 4 | Threat model + terrain classifier training |
| `evaluation/` | 4 | Metrics, evaluation, benchmarks |
| `dashboard/` | 12 | 22-panel NVG Dash app with 5 pages |
| `simulation/` | 3 | Discrete-event engine + runner |
| `ue5_plugin/` | 9 | C++ UE5 plugin (NATS client, TwinState, UnitReplicator) |
| `tests/` | 12 | 30+ pytest tests |
| `.github/` | 2 | CI + lint workflows |

---

## Key Algorithms

| Algorithm | Module | Description |
|---|---|---|
| D* Lite | `planning/dstar_lite.py` | Incremental path planning with dynamic replanning |
| MCTS | `planning/mcts_coa.py` | Monte Carlo Tree Search for COA generation |
| Bayesian Network | `planning/threat_assessor.py` | pgmpy-based threat probability estimation |
| Madgwick AHRS | `sensors/imu_fusion.py` | Quaternion IMU fusion (accel + gyro) |
| Extended Kalman Filter | `sensors/gps_kalman.py` | GPS tracking with spoofing detection |
| VRP | `planning/vrp_logistics.py` | OR-Tools vehicle routing for supply convoys |
| OLSR | `comms/olsr_simulator.py` | MANET mesh routing with MPR selection |

---

## AI Agents (LangGraph)

| Agent | Role | Key Function |
|---|---|---|
| S2 Intel | Threat analysis, enemy situation | `analyze_threats()` |
| S3 Maneuver | Movement orders, COA execution | `plan_maneuver()` |
| FSO Fires | Fire mission planning, CFF | `plan_fires()` |
| S4 Logistics | Supply assessment, convoy planning | `assess_logistics()` |
| CSS MEDEVAC | 9-line MEDEVAC requests | `generate_9line()` |
| Commander | Synthesizes all outputs into decisions | `process()` |

---

## 22 Dashboard Visualizations

1. Tactical Map (MGRS) • 2. Force Status Matrix • 3. Threat Level Gauges
4. NATS Message Flow • 5. Alert Log • 6. Intel Map Overlay
7. Threat Heatmap • 8. Contact Timeline • 9. Pattern of Life
10. Fire Support Map • 11. Fire Mission Timeline • 12. Weather Impact
13. Supply Dashboard • 14. Logistics Route Map • 15. VRP Optimization
16. Agent Execution Trace • 17. COA Spider Chart • 18. MCTS Tree
19. Terrain Analysis • 20. MEDEVAC Map • 21. Sensor Fusion • 22. Sync Status

---

## Testing

```bash
make test           # All tests
make test-sensors   # Sensor module tests
make test-planning  # Planning algorithm tests
```

---

## Environment Variables

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | LLM agents (GPT-4o) |
| `OPENWEATHER_API_KEY` | Weather data |
| `COPERNICUS_USER/PASSWORD` | Sentinel-2 imagery |
| `NATS_TOKEN` | NATS authentication |

---

## License

Proprietary — BATTLE-TWIN Digital Twin System
