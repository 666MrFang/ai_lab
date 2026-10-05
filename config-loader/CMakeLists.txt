cmake_minimum_required(VERSION 3.16)

project(config_loader LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(config_loader
    src/config_loader.cpp
)

target_include_directories(config_loader
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

add_executable(test_config_loader
    test/test_config_loader.cpp
)

target_link_libraries(test_config_loader
    PRIVATE
        config_loader
)

enable_testing()

add_test(
    NAME config_loader_tests
    COMMAND test_config_loader
)