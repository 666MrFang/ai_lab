#pragma once

#include <cstddef>
#include <cstdint>
#include <deque>
#include <string>

struct Task {
    uint32_t id = 0;
    std::string name;
    uint32_t priority = 0;
};

class Scheduler {
public:
    bool submit(const Task& task, std::string& error);

    bool run_next(Task& task, std::string& error);

    std::size_t pending_count() const;

    bool empty() const;

private:
    std::deque<Task> queue_;
};