cmake_minimum_required(VERSION 3.16)

project(task_scheduler LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(task_scheduler
    src/scheduler.cpp
)

target_include_directories(task_scheduler
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

add_executable(test_scheduler
    test/test_scheduler.cpp
)

target_link_libraries(test_scheduler
    PRIVATE
        task_scheduler
)

enable_testing()

add_test(
    NAME task_scheduler_tests
    COMMAND test_scheduler
)