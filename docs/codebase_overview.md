# Codebase Overview

Welcome to Portl! This document walks you through the repository layout, the main building blocks in the source code, and pointers for what to explore next. Pair this guide with the existing README and docs when you begin making changes.

## Repository Structure

Portl follows the standard modern Python layout:

- `src/portl/` contains the installable package and all runtime code.
- `tests/` holds automated tests that exercise the CLI surface.
- `docs/` contains user-facing documentation; the new developer docs live here too.
- `examples/` provides sample configuration files you can try while developing features.
- Top-level helper files such as `README.md` and the Docker scripts describe goals and usage patterns for the CLI.
- `docs/development/` contains project planning, PR documentation, and development status files.

## CLI Entry Point

The CLI is implemented with [Typer](https://typer.tiangolo.com/). The root command group and shared configuration live in `src/portl/cli.py`.

Key things to note:

- A `ConsoleUI` instance is created once and reused so that rich-formatted output is consistent across commands.
- The `portl` Typer application registers the `init` and `run` subcommands and exposes global options such as `--version` that are handled via callbacks.
- Each subcommand delegates to a dedicated handler class (`InitCommandHandler` and `RunCommandHandler`) to keep the CLI wiring thin and business logic testable.

## Command Handlers

Command handlers live in `src/portl/commands/` and encapsulate the behavior behind each CLI entry point.

- `InitCommandHandler` is responsible for the onboarding wizard. Today it shows the welcome banner, advertises upcoming features, and eventually will orchestrate interactive question flows. Even in non-interactive mode it reports that the functionality is not yet available, which helps keep the CLI responsive while the feature is under construction.
- `RunCommandHandler` owns the migration execution command. It prompts the user to create a template when no job file is supplied, validates the provided YAML, surfaces warnings, and eventually calls into the job runner. When the execution engine is ready, this is the place where dry-run versus live-mode behavior will branch.

Because the handlers are stateful classes, they can comfortably pull in dependencies such as services and the console UI once per invocation and keep the CLI functions declarative.

## Services Layer

Supporting utilities live under `src/portl/services/`.

- `TemplateService` reads the built-in template YAML (found at `src/portl/template.yaml`) and can write it to disk for the user. It also exposes helper metadata such as the default template name.
- `JobRunner` provides validation for YAML job files and will eventually execute migrations. For now it verifies the file exists, returns warnings if extensions look suspicious, and offers a configuration object (`JobRunnerConfig`) that bundles CLI options so the runner and UI stay in sync.

These classes are deliberately lightweight and keep I/O logic separate from the CLI handlers. As you implement additional data connectors or parsing logic, this is where most new code will land.

## Console UI Helpers

The CLI surfaces rich text through `ConsoleUI` (`src/portl/ui/console.py`). It wraps `rich.Console` to standardize banners, warnings, and confirmations. The handlers rely on this layer to present wizard steps, template creation messages, and execution summaries, which keeps printing logic out of the services.

## Configuration Templates

The default YAML template bundled with the package lives at `src/portl/template.yaml`. It covers source/destination types, conflict strategies, batch processing, optional schema mapping, transformations, and hooks. When the user asks for help from the CLI, the template service copies this file so they have a ready-made starting point.

## Documentation and Tests

- `docs/index.md` and `docs/configuration.md` explain how to install Portl, run commands, and structure job files. Keeping feature docs up to date here helps users and developers stay aligned.
- `tests/test_cli.py` currently includes smoke tests for the CLI options. They assert on expected output strings, so remember to update them whenever you reword banners or change the version string.

## Roadmap and Next Steps

The `docs/development/TODO.md` file outlines the long-term roadmap. Near-term tasks for new contributors include:

1. Flesh out the `portl init` wizard questions and YAML generation experience.
2. Implement the YAML parsing and validation pipeline that feeds the job runner.
3. Begin wiring source/destination connectors for real databases and CSV/Sheets integrations.
4. Expand the automated tests to cover the new question flows and migration execution logic as it becomes available.

As you work through these features, keep the separation between CLI presentation, services, and future execution engines in mind. This layered architecture will make it easier to add new connectors, enhance validation, and introduce cloud integrations without rewriting the UI layer.
