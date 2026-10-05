#pragma once

#include <cstdint>
#include <string>

struct AppConfig {
    std::string host;
    uint16_t port = 0;
    bool debug = false;
};

class ConfigLoader {
public:
    bool load_from_file(
        const std::string& path,
        AppConfig& config,
        std::string& error) const;

    bool load(
        const std::string& path,
        AppConfig& config,
        std::string& error) const;

private:
    bool load_file_values(
        const std::string& path,
        AppConfig& config,
        bool& has_host,
        bool& has_port,
        bool& has_debug,
        std::string& error) const;

    bool parse_line(
        const std::string& line,
        std::string& key,
        std::string& value,
        std::string& error) const;

    bool parse_port(
        const std::string& value,
        uint16_t& port,
        std::string& error) const;

    bool parse_bool(
        const std::string& value,
        bool& result,
        std::string& error) const;
};