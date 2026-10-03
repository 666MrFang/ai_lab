# Task Scheduler

A small C++17 task scheduler used for AI coding workflow exercises.

The current implementation schedules tasks in FIFO order.

## Build

```bash
cmake -S . -B build
cmake --build build
ctest --test-dir build