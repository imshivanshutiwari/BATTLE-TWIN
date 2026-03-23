# BATTLE-TWIN Makefile
# Commands: make install, make run, make test, make lint, make clean

.PHONY: install run test lint clean docker-nats

# Install all dependencies
install:
	pip install -r requirements.txt

# Run the full system (simulation + dashboard, auto-opens browser)
run:
	python main.py --port 8050

# Run simulation only (no dashboard)
run-sim:
	python -m simulation.sim_runner

# Run dashboard only
run-dash:
	python -m dashboard.app

# Run all tests
test:
	python -m pytest tests/ -v --tb=short

# Run specific test modules
test-utils:
	python -m pytest tests/test_seed.py tests/test_logger.py tests/test_config.py tests/test_mgrs.py -v

test-data:
	python -m pytest tests/test_osm.py tests/test_adsb.py tests/test_weather.py tests/test_dem.py -v

test-twin:
	python -m pytest tests/test_twin_state.py tests/test_nats.py -v

test-sensors:
	python -m pytest tests/test_imu.py tests/test_gps.py tests/test_thermal.py tests/test_acoustic.py -v

test-planning:
	python -m pytest tests/test_dstar.py tests/test_mcts.py tests/test_threat.py tests/test_vrp.py -v

test-agents:
	python -m pytest tests/test_agents.py -v

# Lint
lint:
	python -m flake8 --max-line-length=120 --exclude=ue5_plugin .

# Start NATS server via Docker
docker-nats:
	docker run -d --name nats-battletwin -p 4222:4222 -p 8222:8222 nats:latest -js

# Clean caches and artifacts
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf data/cache/* checkpoints/* logs/* .pytest_cache
