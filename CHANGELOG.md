# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-15

### Added
- Initial release of Trade Republic Transaction Exporter
- Interactive setup mode for first-run configuration
- Configuration file (`config.json`) for persistent settings
- Automatic CSV export using `pytr` via `uv`
- Incremental CSV updates (appends only new transactions)
- Automatic backup creation before each update
- Git integration with automatic commit and push
- Robust transaction detection using full row comparison
- Comprehensive error handling and user feedback
- Support for configurable paths, commands, and Git branches
- README documentation with setup and usage instructions
- Configuration example file (`config.example.json`)
- Strict CSV format compliance (semicolon delimiter, UTF-8 encoding)

### Features
- **Setup Mode**: Interactive configuration wizard on first run
- **Incremental Updates**: Preserves existing CSV rows, only appends new transactions
- **Backup System**: Timestamped backups stored in Git-tracked directory
- **Git Automation**: Automatic commit and push of changes
- **Error Handling**: Clear error messages and graceful failure handling
- **Reusability**: Fully configurable for different users and environments
- **CSV Format Compliance**: Strictly respects Trade Republic CSV format specifications
