#include "config_loader.h"

#include <cstdlib>
#include <fstream>
#include <limits>
#include <sstream>
#include <string>

bool ConfigLoader::load_from_file(
    const std::string& path,
    AppConfig& config,
    std::string& error) const
{
    AppConfig parsed_config;

    bool has_host = false;
    bool has_port = false;
    bool has_debug = false;

    if (!load_file_values(
            path,
            parsed_config,
            has_host,
            has_port,
            has_debug,
            error)) {
        return false;
    }

    if (!has_host) {
        error = "missing host";
        return false;
    }

    if (!has_port) {
        error = "missing port";
        return false;
    }

    if (!has_debug) {
        error = "missing debug";
        return false;
    }

    config = parsed_config;

    error.clear();
    return true;
}

bool ConfigLoader::load(
    const std::string& path,
    AppConfig& config,
    std::string& error) const
{
    AppConfig merged_config;

    merged_config.host = "127.0.0.1";
    merged_config.port = 8080;
    merged_config.debug = false;

    AppConfig file_config;

    bool has_host = false;
    bool has_port = false;
    bool has_debug = false;

    if (!load_file_values(
            path,
            file_config,
            has_host,
            has_port,
            has_debug,
            error)) {
        return false;
    }

    if (has_host) {
        merged_config.host = file_config.host;
    }

    if (has_port) {
        merged_config.port = file_config.port;
    }

    if (has_debug) {
        merged_config.debug = file_config.debug;
    }

    const char* env_host = std::getenv("APP_HOST");

    if (env_host != nullptr) {
        if (*env_host == '\0') {
            error = "host must not be empty";
            return false;
        }

        merged_config.host = env_host;
    }

    const char* env_port = std::getenv("APP_PORT");

    if (env_port != nullptr) {
        if (!parse_port(env_port, merged_config.port, error)) {
            return false;
        }
    }

    const char* env_debug = std::getenv("APP_DEBUG");

    if (env_debug != nullptr) {
        if (!parse_bool(env_debug, merged_config.debug, error)) {
            return false;
        }
    }

    config = merged_config;

    error.clear();
    return true;
}

bool ConfigLoader::load_file_values(
    const std::string& path,
    AppConfig& config,
    bool& has_host,
    bool& has_port,
    bool& has_debug,
    std::string& error) const
{
    std::ifstream input(path);

    if (!input.is_open()) {
        error = "failed to open config file";
        return false;
    }

    AppConfig parsed_config;

    has_host = false;
    has_port = false;
    has_debug = false;

    std::string line;

    while (std::getline(input, line)) {
        if (line.empty()) {
            continue;
        }

        std::string key;
        std::string value;

        if (!parse_line(line, key, value, error)) {
            return false;
        }

        if (key == "host") {
            if (value.empty()) {
                error = "host must not be empty";
                return false;
            }

            parsed_config.host = value;
            has_host = true;
        }
        else if (key == "port") {
            if (!parse_port(value, parsed_config.port, error)) {
                return false;
            }

            has_port = true;
        }
        else if (key == "debug") {
            if (!parse_bool(value, parsed_config.debug, error)) {
                return false;
            }

            has_debug = true;
        }
        else {
            error = "unknown config key";
            return false;
        }
    }

    config = parsed_config;

    return true;
}

bool ConfigLoader::parse_line(
    const std::string& line,
    std::string& key,
    std::string& value,
    std::string& error) const
{
    const std::size_t separator = line.find('=');

    if (separator == std::string::npos) {
        error = "invalid config line";
        return false;
    }

    key = line.substr(0, separator);
    value = line.substr(separator + 1);

    if (key.empty()) {
        error = "config key must not be empty";
        return false;
    }

    return true;
}

bool ConfigLoader::parse_port(
    const std::string& value,
    uint16_t& port,
    std::string& error) const
{
    if (value.empty()) {
        error = "invalid port";
        return false;
    }

    std::istringstream stream(value);

    unsigned long parsed = 0;
    char extra = '\0';

    if (!(stream >> parsed) || (stream >> extra)) {
        error = "invalid port";
        return false;
    }

    if (parsed == 0 ||
        parsed > std::numeric_limits<uint16_t>::max()) {
        error = "invalid port";
        return false;
    }

    port = static_cast<uint16_t>(parsed);

    return true;
}

bool ConfigLoader::parse_bool(
    const std::string& value,
    bool& result,
    std::string& error) const
{
    if (value == "true") {
        result = true;
        return true;
    }

    if (value == "false") {
        result = false;
        return true;
    }

    error = "invalid boolean";
    return false;
}