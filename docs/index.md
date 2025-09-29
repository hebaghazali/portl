# Portl Documentation

## Overview

Portl is a developer-first CLI tool for moving data across databases, CSVs, and Google Sheets.
Instead of writing one-off SQL or Python scripts for every migration, Portl gives you an interactive wizard and YAML job configs you can re-run, share, and version-control.

## Installation

```bash
pip install portl
```

## Usage

### Starting a new migration

```bash
portl init
```

### Running a migration

```bash
portl run path/to/job.yaml
```

### Dry run mode

```bash
portl run path/to/job.yaml --dry-run
```

## Configuration

See the [configuration guide](configuration.md) for details on YAML job configuration.

## Examples

Check out the [examples directory](../examples/) for sample configurations.
