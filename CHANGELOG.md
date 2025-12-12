# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-12-12

### Added
- **MacOS Desktop App**: Released `TradeSync.app`, a standalone executable for macOS. No Python installation required for end users.
- **Web Frontend**: A dedicated local web interface (running inside the app) for managing syncs, viewing logs, and handling 2FA interactions user-friendliness.
- **Direct API Integration**: Refactored `pytr` integration to use library classes directly, improving reliability and error handling for transaction exports.
- **Resilient Parsing**: Added logic to skip and log individual malformed transaction events instead of failing the entire export.

## [0.1.0] - 2025-12-11

### Added
- Initial release of TradeSync core logic.
- Google Drive integration (download, upload, update, search).
- Trade Republic export automation via `pytr`.
- Smart deduplication logic using row hashing.
- Backup rotation and management.
- Native macOS notifications.
- Configuration system using YAML and .env.
