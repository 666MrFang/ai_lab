#include "scheduler.h"

bool Scheduler::submit(const Task& task, std::string& error)
{
    if (task.id == 0) {
        error = "task id must not be zero";
        return false;
    }

    if (task.name.empty()) {
        error = "task name must not be empty";
        return false;
    }

    queue_.push_back(task);

    error.clear();
    return true;
}

bool Scheduler::run_next(Task& task, std::string& error)
{
    if (queue_.empty()) {
        error = "no pending task";
        return false;
    }

    std::size_t best_index = 0;

    for (std::size_t i = 1; i < queue_.size(); ++i) {
        if (queue_[i].priority < queue_[best_index].priority) {
            best_index = i;
        }
    }

    task = queue_[best_index];

    queue_.erase(
        queue_.begin() +
        static_cast<std::ptrdiff_t>(best_index)
    );

    error.clear();
    return true;
}

std::size_t Scheduler::pending_count() const
{
    return queue_.size();
}

bool Scheduler::empty() const
{
    return queue_.empty();
}