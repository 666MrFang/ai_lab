cmake_minimum_required(VERSION 3.16)

project(packet_parser
    VERSION 1.0.0
    LANGUAGES CXX
)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ------------------------------------------------------------
# Library
# ------------------------------------------------------------

add_library(packet_parser
    src/packet_parser.cpp
    src/ipv4_parser.cpp
)

target_include_directories(packet_parser
    PUBLIC
        ${PROJECT_SOURCE_DIR}/include
)

# ------------------------------------------------------------
# Test executable
# ------------------------------------------------------------

add_executable(test_packet_parser
    test/test_packet_parser.cpp
)

target_link_libraries(test_packet_parser
    PRIVATE
        packet_parser
)

# ------------------------------------------------------------
# Enable CTest
# ------------------------------------------------------------

enable_testing()

add_test(
    NAME packet_parser_test
    COMMAND test_packet_parser
)