# Configuration Override Specification

## 1. Overview

The application currently loads configuration from a configuration file.

Add support for environment-variable overrides and default configuration
values.

## 2. Configuration Values

The application configuration contains:

- host
- port
- debug

Configuration values may come from:

- default values
- the configuration file
- environment variables

Environment variables use the following names:

- APP_HOST
- APP_PORT
- APP_DEBUG

## 3. Override Behavior

Environment-variable values override values loaded from the configuration
file.

Values explicitly provided by the user should take precedence over default
values.

## 4. Missing Configuration

A configuration file may omit values that can be supplied by defaults or
environment variables.

## 5. Validation

Values from environment variables must follow the same validation rules as
values from the configuration file.

Invalid explicitly provided values must not silently fall back to another
source.

## 6. Compatibility

Existing valid configuration files must continue to load successfully.

Existing validation behavior should remain unchanged unless required by the
new configuration-source behavior.

## 7. API

Existing callers should require minimal changes.

## 8. Testing

Add tests for:

- default values
- environment-variable overrides
- invalid environment-variable values
- compatibility with existing configuration files

Existing tests should continue to pass where their expectations remain valid.