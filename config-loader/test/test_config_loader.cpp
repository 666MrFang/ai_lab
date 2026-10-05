#include "config_loader.h"

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>

namespace {

const char* TEST_CONFIG_FILE = "test_config.tmp";

void write_config(const std::string& content)
{
    std::ofstream output(TEST_CONFIG_FILE);
    output << content;
}

void remove_config()
{
    std::remove(TEST_CONFIG_FILE);
}

void set_env(const char* name, const char* value)
{
#ifdef _WIN32
    _putenv_s(name, value);
#else
    setenv(name, value, 1);
#endif
}

void clear_env()
{
#ifdef _WIN32
    _putenv_s("APP_HOST", "");
    _putenv_s("APP_PORT", "");
    _putenv_s("APP_DEBUG", "");
#else
    unsetenv("APP_HOST");
    unsetenv("APP_PORT");
    unsetenv("APP_DEBUG");
#endif
}

void test_valid_config()
{
    write_config(
        "host=127.0.0.1\n"
        "port=8080\n"
        "debug=true\n");

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(loader.load_from_file(TEST_CONFIG_FILE, config, error));

    assert(config.host == "127.0.0.1");
    assert(config.port == 8080);
    assert(config.debug);
    assert(error.empty());

    remove_config();
}

void test_missing_host()
{
    write_config(
        "port=8080\n"
        "debug=true\n");

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(!loader.load_from_file(TEST_CONFIG_FILE, config, error));
    assert(error == "missing host");

    remove_config();
}

void test_missing_port()
{
    write_config(
        "host=127.0.0.1\n"
        "debug=true\n");

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(!loader.load_from_file(TEST_CONFIG_FILE, config, error));
    assert(error == "missing port");

    remove_config();
}

void test_missing_debug()
{
    write_config(
        "host=127.0.0.1\n"
        "port=8080\n");

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(!loader.load_from_file(TEST_CONFIG_FILE, config, error));
    assert(error == "missing debug");

    remove_config();
}

void test_invalid_port()
{
    write_config(
        "host=127.0.0.1\n"
        "port=70000\n"
        "debug=false\n");

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(!loader.load_from_file(TEST_CONFIG_FILE, config, error));
    assert(error == "invalid port");

    remove_config();
}

void test_invalid_boolean()
{
    write_config(
        "host=127.0.0.1\n"
        "port=8080\n"
        "debug=yes\n");

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(!loader.load_from_file(TEST_CONFIG_FILE, config, error));
    assert(error == "invalid boolean");

    remove_config();
}

void test_unknown_key()
{
    write_config(
        "host=127.0.0.1\n"
        "port=8080\n"
        "debug=false\n"
        "threads=4\n");

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(!loader.load_from_file(TEST_CONFIG_FILE, config, error));
    assert(error == "unknown config key");

    remove_config();
}

void test_invalid_line()
{
    write_config(
        "host=127.0.0.1\n"
        "port=8080\n"
        "debug\n");

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(!loader.load_from_file(TEST_CONFIG_FILE, config, error));
    assert(error == "invalid config line");

    remove_config();
}

void test_file_not_found()
{
    remove_config();

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(!loader.load_from_file(TEST_CONFIG_FILE, config, error));
    assert(error == "failed to open config file");
}

void test_load_default_values()
{
    clear_env();
    write_config("");

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(loader.load(TEST_CONFIG_FILE, config, error));

    assert(config.host == "127.0.0.1");
    assert(config.port == 8080);
    assert(!config.debug);
    assert(error.empty());

    remove_config();
}

void test_load_partial_file()
{
    clear_env();
    write_config("port=9000\n");

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(loader.load(TEST_CONFIG_FILE, config, error));

    assert(config.host == "127.0.0.1");
    assert(config.port == 9000);
    assert(!config.debug);

    remove_config();
}

void test_load_env_overrides_file()
{
    clear_env();

    write_config(
        "host=10.0.0.1\n"
        "port=1000\n"
        "debug=false\n");

    set_env("APP_HOST", "192.168.0.1");
    set_env("APP_PORT", "2000");
    set_env("APP_DEBUG", "true");

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(loader.load(TEST_CONFIG_FILE, config, error));

    assert(config.host == "192.168.0.1");
    assert(config.port == 2000);
    assert(config.debug);

    clear_env();
    remove_config();
}

void test_load_env_partial_override()
{
    clear_env();

    write_config(
        "host=10.0.0.1\n"
        "port=1000\n"
        "debug=false\n");

    set_env("APP_PORT", "2000");

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(loader.load(TEST_CONFIG_FILE, config, error));

    assert(config.host == "10.0.0.1");
    assert(config.port == 2000);
    assert(!config.debug);

    clear_env();
    remove_config();
}

void test_load_invalid_env_port()
{
    clear_env();

    write_config(
        "host=10.0.0.1\n"
        "port=1000\n"
        "debug=false\n");

    set_env("APP_PORT", "70000");

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(!loader.load(TEST_CONFIG_FILE, config, error));
    assert(error == "invalid port");

    clear_env();
    remove_config();
}

void test_load_invalid_env_bool()
{
    clear_env();

    write_config(
        "host=10.0.0.1\n"
        "port=1000\n"
        "debug=false\n");

    set_env("APP_DEBUG", "yes");

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(!loader.load(TEST_CONFIG_FILE, config, error));
    assert(error == "invalid boolean");

    clear_env();
    remove_config();
}

void test_load_invalid_file()
{
    clear_env();

    write_config(
        "host=10.0.0.1\n"
        "port=1000\n"
        "debug=false\n"
        "threads=4\n");

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(!loader.load(TEST_CONFIG_FILE, config, error));
    assert(error == "unknown config key");

    remove_config();
}

void test_load_missing_file()
{
    clear_env();
    remove_config();

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(!loader.load(TEST_CONFIG_FILE, config, error));
    assert(error == "failed to open config file");
}

void test_load_compat_existing_file()
{
    clear_env();

    write_config(
        "host=127.0.0.1\n"
        "port=8080\n"
        "debug=true\n");

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(loader.load(TEST_CONFIG_FILE, config, error));

    assert(config.host == "127.0.0.1");
    assert(config.port == 8080);
    assert(config.debug);

    remove_config();
}

#ifndef _WIN32
void test_load_empty_env_host()
{
    clear_env();

    write_config(
        "host=10.0.0.1\n"
        "port=1000\n"
        "debug=false\n");

    set_env("APP_HOST", "");

    ConfigLoader loader;
    AppConfig config;
    std::string error;

    assert(!loader.load(TEST_CONFIG_FILE, config, error));
    assert(error == "host must not be empty");

    clear_env();
    remove_config();
}
#endif

} // namespace

int main()
{
    test_valid_config();
    test_missing_host();
    test_missing_port();
    test_missing_debug();
    test_invalid_port();
    test_invalid_boolean();
    test_unknown_key();
    test_invalid_line();
    test_file_not_found();
    test_load_default_values();
    test_load_partial_file();
    test_load_env_overrides_file();
    test_load_env_partial_override();
    test_load_invalid_env_port();
    test_load_invalid_env_bool();
    test_load_invalid_file();
    test_load_missing_file();
    test_load_compat_existing_file();
#ifndef _WIN32
    test_load_empty_env_host();
#endif

    std::cout << "All tests passed.\n";
    return 0;
}