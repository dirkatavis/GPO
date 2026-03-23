# Dual-Axis Logging System Requirements

## Overview
This document defines requirements for a dual-axis logging system that combines **Criticality** (importance) and **Verbosity** (detail level) to provide flexible log filtering and output control.

## 1. Core Architecture Requirements

### 1.1 Dual-Axis Design
- **MUST** support two independent filtering axes:
  - **Criticality Axis**: Determines importance level (critical, major, minor, common)
  - **Verbosity Axis**: Determines detail level (low, medium, high, maximum)
- **MUST** filter messages based on BOTH axes simultaneously
- **MUST** only log messages that meet BOTH threshold criteria

### 1.2 Filtering Logic
- **MUST** use threshold-based filtering where:
  - Message criticality >= configured criticality threshold AND
  - Message verbosity <= configured verbosity threshold
- **MUST** support runtime threshold configuration changes

## 2. Criticality Levels

### 2.1 Criticality Hierarchy (lowest to highest priority)
1. **COMMON** (`comm`) - Routine operations, normal flow
2. **MINOR** (`min`) - Warnings, non-critical issues  
3. **MAJOR** (`maj`) - Errors, significant problems
4. **CRITICAL** (`crit`) - Critical failures, system-breaking issues

### 2.2 Criticality Requirements
- **MUST** support string-based criticality specification (`"comm"`, `"min"`, `"maj"`, `"crit"`)
- **MUST** convert to numeric values internally for efficient comparison
- **MUST** default to COMMON level for invalid inputs
- **MUST** support case-insensitive criticality strings

## 3. Verbosity Levels

### 3.1 Verbosity Hierarchy (lowest to highest detail)
1. **LOW** (`low`) - Essential information only
2. **MEDIUM** (`med`) - Standard detail level
3. **HIGH** (`high`) - Enhanced detail with additional context
4. **MAXIMUM** (`max`) - Full technical detail and debugging info

### 3.2 Verbosity Requirements
- **MUST** support string-based verbosity specification (`"low"`, `"med"`, `"high"`, `"max"`)
- **MUST** convert to numeric values internally for efficient comparison
- **MUST** default to MEDIUM level for invalid inputs
- **MUST** support case-insensitive verbosity strings

## 4. Message Structure Requirements

### 4.1 Core Message Parameters
- **MUST** accept the following parameters:
  - `criticality` - Required string indicating message importance
  - `verbosity` - Required string indicating message detail level
  - `headline` - Required string with primary message content
  - `stage` - Required string identifying context/source component
  - `reason` - Optional string with specific cause/reason information
  - `technical` - Optional string with technical details

### 4.2 Progressive Detail Display
- **MUST** always display headline and stage information
- **MUST** include reason information for HIGH and MAXIMUM verbosity
- **MUST** include technical information only for MAXIMUM verbosity
- **MUST** format detailed information consistently: `headline - Reason: reason | Tech: technical`

## 5. Configuration Requirements

### 5.1 Threshold Configuration
- **MUST** support configuration file-based threshold setting
- **MUST** support environment variable overrides
- **MUST** provide reasonable startup defaults:
  - Criticality: COMMON (log all levels)
  - Verbosity: MAXIMUM (show all detail during startup)

### 5.2 Runtime Configuration
- **MUST** allow runtime threshold adjustments without restart
- **MUST** validate configuration values and reject invalid settings
- **SHOULD** provide configuration validation feedback

## 6. Backward Compatibility Requirements

### 6.1 Legacy Function Support
- **MUST** provide backward-compatible wrappers for existing logging functions:
  - `LogError()` -> maps to major/low
  - `LogWarn()` -> maps to minor/low  
  - `LogInfo()` -> maps to common/low
  - `LogDebug()` -> maps to common/high
  - `LogTrace()` -> maps to common/max

### 6.2 Migration Support
- **MUST** support existing numeric log level mappings
- **SHOULD** provide clear migration path from single-axis to dual-axis

## 7. Convenience Function Requirements

### 7.1 Criticality-Based Shortcuts
- **MUST** provide convenience functions for each criticality level:
  - `LogCritical(headline, stage, reason, technical)`
  - `LogMajor(headline, stage, reason, technical)`  
  - `LogMinor(headline, stage, reason, technical)`
  - `LogCommon(headline, stage, reason, technical)`

### 7.2 Default Verbosity Behavior
- **MUST** default convenience functions to LOW verbosity
- **MUST** allow explicit verbosity specification via main LogEvent function

## 8. Output Format Requirements

### 8.1 Log Entry Format
- **MUST** include timestamp in readable format
- **MUST** include criticality/verbosity indicators: `[crit/verb]`
- **MUST** include source/stage information: `[stage]`
- **MUST** truncate source field to 16 characters for consistency
- **MUST** follow format: `HH:MM:SS[crit/verb][source]message`

### 8.2 File Output Requirements
- **MUST** append to existing log files
- **MUST** create log files and directories as needed
- **MUST** handle file access errors gracefully
- **SHOULD** support log rotation and size management

## 9. Performance Requirements

### 9.1 Filtering Efficiency
- **MUST** perform threshold checks before message formatting
- **MUST** use numeric comparison for threshold evaluation
- **MUST** avoid unnecessary string processing for filtered-out messages

### 9.2 Startup Performance
- **MUST** initialize logging system early in application startup
- **MUST** support logging during initialization phase
- **SHOULD** minimize startup overhead from logging configuration

## 10. Error Handling Requirements

### 10.1 Graceful Degradation
- **MUST** continue operation if log file writing fails
- **MUST** handle invalid criticality/verbosity values gracefully
- **MUST** provide error recovery for file system issues
- **SHOULD** provide fallback logging mechanisms

### 10.2 Error Reporting
- **MUST** avoid recursive logging errors
- **SHOULD** report configuration errors to alternative output
- **SHOULD** provide diagnostic information for troubleshooting

## 11. Testing Requirements

### 11.1 Threshold Testing
- **MUST** verify correct filtering at all threshold combinations
- **MUST** test boundary conditions for each axis
- **MUST** validate message format at each verbosity level

### 11.2 Integration Testing
- **MUST** test backward compatibility functions
- **MUST** test configuration loading and validation
- **MUST** test error handling scenarios

## Example Usage Patterns

```vbscript
' Basic dual-axis logging
Call LogEvent("maj", "low", "Connection failed", "DatabaseManager", "Timeout after 30s", "SQLException: Connection timeout")

' High verbosity for debugging
Call LogEvent("comm", "max", "Processing item", "DataProcessor", "Item ID: 12345", "Memory usage: 45MB, CPU: 12%")

' Convenience functions  
Call LogMajor("Critical system failure", "SystemCore", "Out of memory", "Available: 0MB, Required: 100MB")
Call LogInfo("Processing started", "MainLoop")

' Backward compatibility
Call LogError("Database connection failed", "DataAccess")
```

## Implementation Notes

- The dual-axis approach allows fine-grained control over what gets logged
- Criticality threshold controls WHAT types of events are important enough to log
- Verbosity threshold controls HOW MUCH detail to include in logged events  
- Both axes must pass their respective thresholds for a message to be logged
- This design supports both production (low verbosity) and debugging (high verbosity) scenarios
- Configuration can be adjusted at runtime to change logging behavior without restart