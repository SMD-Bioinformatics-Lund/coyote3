# Logging System Documentation

## Purpose

The logging system in Coyote3 provides centralized, structured, and environment-aware logging across all application components. It ensures that logs are written consistently, rotated daily, and categorized by source and severity.

## Directory Structure

Logs are stored under a base directory based on the active environment (e.g., `logs/dev/`, `logs/prod/`). The directory structure is date-based and includes specific subdirectories for component-level logs.


```
logs/
└── <env>/
├── <YYYY>/
│ └── <MM>/
│ └── <DD>/
│ ├── <YYYY-MM-DD>.info.log
│ ├── <YYYY-MM-DD>.error.log
│ ├── <YYYY-MM-DD>.debug.log
├── audit/
│ └── <YYYY-MM-DD>.audit.log
├── flask/
│ └── <YYYY-MM-DD>.flask.log
├── werkzeug/
│ └── <YYYY-MM-DD>.werkzeug.log
└── gunicorn/
└── <YYYY-MM-DD>.gunicorn.log
```  


Each log file contains logs for a specific purpose, written in UTC and encoded as UTF-8.

## Loggers

The system defines separate loggers for major categories:

- `coyote`: Main application logic (includes info, error, debug levels)
- `audit`: Application-specific audit actions and metadata
- `flask`: Internal Flask messages
- `werkzeug`: HTTP request logs from the development server
- `gunicorn`: Logs from Gunicorn in production

All loggers are explicitly initialized and use non-propagating loggers with individual file handlers.

## Rotation

The system uses a subclass of `TimedRotatingFileHandler`:

- Log files rotate daily at midnight UTC.
- Each log file is named using the current date.
- Rotation automatically creates the next day's file and folder structure.
- Old files are not deleted by default, unless explicitly configured.

## Fault Tolerance

If a log directory or file is deleted while the application is running:

- The next write operation will recreate the necessary directory and file.
- Log rollover does not crash on missing paths; it reconstructs them.
- This behavior is built into the custom handler subclass.

## Encoding and Time

- All logs use UTF-8 encoding.
- Timestamps are in UTC to ensure cross-environment consistency.

## Log Format

Each log line follows a standardized format:  
```
[YYYY-MM-DD HH:MM:SS +ZZZZ] [PID] [logger_name] [LEVEL] [client_ip] [host:port] [username] message
```

This format is consistent across all log files for easier parsing and searching.

## Queue Handling

The system currently uses direct log writes with multiple handlers per logger. Queue-based handlers are not used, as logging categories are explicitly separated via distinct loggers. This provides:

- Clear ownership of logs by logger name
- Isolation of output files per log type
- No risk of handler duplication or write contention

## Manual Testing

To test log creation and rotation:

1. Trigger a log write using one of the application loggers.
2. Confirm the file is created at the expected path for the current UTC date.
3. To manually trigger rotation (for testing):

```python
for handler in logger.handlers:
    if hasattr(handler, "doRollover"):
        handler.doRollover()
```  

## Monitoring and Maintenance  
- Log files are created only when a log event occurs.
- Logs can be tailed or archived using standard tools.
- Retention and cleanup policies (if needed) should be implemented via external scripts or cron jobs.  

## Summary
The Coyote3 logging system is:
- Organized: Clean file and directory layout
- Robust: Recovers from missing directories or files
- Isolated: Component logs are clearly separated
- Consistent: UTC-based daily rotation, uniform formatting
- Maintainable: Easy to extend or integrate with log aggregators  

This logging foundation ensures auditability, traceability, and operational transparency across all application layers.

