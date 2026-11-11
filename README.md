# 🚦 PySig

[![PySig CI](https://github.com/ha-mish/PySig/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ha-mish/PySig/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.4.5-c5a3ff.svg)](#)
[![Status](https://img.shields.io/badge/status-pre--release-ffb86b.svg)](#)

**Open-source traffic signal modelling, design and optimisation in Python.**

Welcome to **PySig**, a signal design and optimisation tool for analysing the performance of signalised intersections and multi-intersection networks.

PySig emulates aspects of **SCATS-style traffic signal operation** using intersection geometry, signal control parameters and vehicle flows. It provides a Python-based, machine-readable approach to testing traffic signal designs and is intended primarily to support the planning and assessment of intersection design changes.

## 🚦 What PySig does

PySig provides a lane-based analytical modelling framework with support for:

- signalised intersection modelling
- lane-based queue and delay calculations
- multiple movements sharing a physical lane
- short lanes and finite lane storage
- fixed origin-destination demand
- route and lane assignment
- signal phase and cycle-time optimisation
- coordinated multi-intersection networks
- controller offsets and network progression
- direct and RR67-style saturation-flow estimation
- machine-readable YAML inputs
- detailed JSON and CSV outputs
- automated testing with pytest

PySig is designed around Australian traffic conventions, including **left-hand traffic, km/h, metres and PCU-based traffic flows**.

## 🚦 Project status

> **PySig is currently pre-release software.**

The model has undergone only limited validation of its calculated outputs. **Version 1.0.0 is intended to be the first release validated against established industry modelling standards and reference models.**

Until that point, PySig outputs should be treated as experimental and independently checked before being relied upon for design, operational, investment or policy decisions.

Significant parts of the PySig codebase and documentation have been developed with assistance from **large language model (LLM) tools**, with limited independent review. Users should therefore exercise appropriate caution and review the implementation, assumptions and outputs for their intended application.

## 🟢 Why PySig?

PySig aims to provide an open-source alternative for quickly and efficiently investigating traffic signal designs.

The project is being developed around several principles:

- **Transparent:** model assumptions and calculations should be inspectable.
- **Machine readable:** model configuration uses YAML and results are available in JSON and CSV.
- **Reproducible:** models can be stored, versioned and tested alongside the code.
- **Lightweight:** the core model is intended to run in a relatively restricted Python environment.
- **Extensible:** the object-based architecture is intended to support increasingly complex intersections and networks.
- **Open source:** model logic can be reviewed, tested and improved by users.

## 🚦 Quick start

Clone or download the repository and install the basic dependencies:

```bash
conda install pyyaml pytest

## PySig 0.4.5 calculation engines

Version 0.4.5 retains the established time-sliced shared-lane simulation and
introduces an initial event-driven analytical engine. Existing YAML files
default to `simulation`.

```yaml
calculation:
  method: analytical
```

The initial analytical scope is deliberately limited to fixed-time,
independent-lane intersection calculations. Network links and shared-lane
analytical interactions raise explicit capability errors. See
`MIGRATION_0.4.5.md` and the user manual before use.
