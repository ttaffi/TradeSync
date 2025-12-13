
## [0.3.1] - 2025-12-13

### Fixed
- **Window Dragging**: Resolved an issue where the application window could not be dragged from the top. Implemented a specific drag area (~1cm) at the top of the window for standard behavior.
- **Traffic Lights**: Updated minimize/maximize/close buttons to prevent interference with window dragging.


The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2025-12-12

### Added
- **Frameless Window Design**: Implemented a modern, title-bar-less interface for a cleaner look. Traffic light controls now float seamlessly on the app background.
- **Factory Reset**: precise "Danger Zone" in settings allows users to fully reset configuration and credentials to a fresh state.
- **Unified Settings UI**: Improved "Output File Name" input with a visual fixed `.csv` suffix for better user clarity.
- **Default Sanitization**: Ensured that the application ships with completely empty/neutral configuration defaults, preventing dev-data leaks.
- **UI UX Polish**: Fixed fullscreen artifacts (grey bar) and refined traffic light controls for a native-like experience.

## [0.2.0] - 2025-12-12

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
