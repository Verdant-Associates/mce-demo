# Demo Baseline for MCE

This repository provides functions and scripts for running baseline analysis using Python.

## Repository Structure & Usage

* **`uv-venv-setup.ps1`**: A PowerShell script to set up a virtual environment using UV. Run this first to create and configure your local environment and dependencies. The virtual environment will be created within the directory where this repository resides.
* **`requirements.txt`**: Specifies the Python dependencies required by the project (installed during environment setup). You can ignore this.
* **`mce_baseline_functions.py`**: Contains core utility and data processing functions for the MCE baseline calculation workflow. 
* **`mce_run_baseline_function.py`**: The main execution script. Run this file to execute the baseline workflow using the core functions and input data.
* **`demo_data.parquet`**: Sample dataset containing hourly input data used by the execution script for baseline runs.
