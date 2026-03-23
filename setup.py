"""
BATTLE-TWIN: Live Unreal Engine 5 Digital Twin for
Real-Time Battlefield Command and Control
with Multi-Agent LangGraph Decision Support.

Setup configuration for pip install.
"""

from setuptools import setup, find_packages
from pathlib import Path

README = Path("README.md")
long_description = README.read_text(encoding="utf-8") if README.exists() else ""

setup(
    name="battle-twin",
    version="1.0.0",
    description=(
        "Live UE5 Digital Twin for Real-Time Battlefield "
        "Command and Control with Multi-Agent LangGraph Decision Support"
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="BATTLE-TWIN Team",
    python_requires=">=3.11",
    packages=find_packages(exclude=["tests*", "notebooks*"]),
    install_requires=[
        "torch>=2.3.0",
        "langchain>=0.1.20",
        "langgraph>=0.0.55",
        "langchain-openai>=0.1.6",
        "nats-py>=2.6.0",
        "dash>=2.17.0",
        "dash-leaflet>=1.0.15",
        "plotly>=5.22.0",
        "numpy>=1.26.4",
        "scipy>=1.13.0",
        "pandas>=2.2.2",
        "geopandas>=0.14.4",
        "shapely>=2.0.4",
        "pyproj>=3.6.1",
        "requests>=2.31.0",
        "aiohttp>=3.9.5",
        "wandb>=0.16.6",
        "pyyaml>=6.0.1",
        "python-dotenv>=1.0.1",
        "tqdm>=4.66.4",
        "rasterio>=1.3.10",
        "folium>=0.16.0",
        "networkx>=3.3",
        "pgmpy>=0.1.25",
        "ortools>=9.10.4067",
        "ahrs>=0.3.1",
        "overpy>=0.7",
        "sentinelsat>=1.2.1",
    ],
    extras_require={
        "dev": [
            "pytest>=8.2.0",
            "black>=24.4.2",
            "flake8>=7.0.0",
            "jupyter>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "battle-twin=dashboard.app:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Scientific/Engineering :: GIS",
    ],
)
