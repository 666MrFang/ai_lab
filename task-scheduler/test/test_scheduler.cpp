#include "scheduler.h"

#include <cassert>
#include <iostream>
#include <string>

void test_fifo_order()
{
    Scheduler scheduler;
    std::string error;

    assert(scheduler.submit({1, "task-a"}, error));
    assert(scheduler.submit({2, "task-b"}, error));
    assert(scheduler.submit({3, "task-c"}, error));

    Task task;

    assert(scheduler.run_next(task, error));
    assert(task.id == 1);

    assert(scheduler.run_next(task, error));
    assert(task.id == 2);

    assert(scheduler.run_next(task, error));
    assert(task.id == 3);

    assert(scheduler.empty());
}

void test_invalid_task_id()
{
    Scheduler scheduler;
    std::string error;

    assert(!scheduler.submit({0, "invalid"}, error));
    assert(error == "task id must not be zero");
    assert(scheduler.empty());
}

void test_empty_task_name()
{
    Scheduler scheduler;
    std::string error;

    assert(!scheduler.submit({1, ""}, error));
    assert(error == "task name must not be empty");
    assert(scheduler.empty());
}

void test_run_empty_scheduler()
{
    Scheduler scheduler;
    std::string error;
    Task task;

    assert(!scheduler.run_next(task, error));
    assert(error == "no pending task");
}

void test_pending_count()
{
    Scheduler scheduler;
    std::string error;

    assert(scheduler.pending_count() == 0);

    assert(scheduler.submit({1, "task-a"}, error));
    assert(scheduler.pending_count() == 1);

    assert(scheduler.submit({2, "task-b"}, error));
    assert(scheduler.pending_count() == 2);

    Task task;
    assert(scheduler.run_next(task, error));

    assert(scheduler.pending_count() == 1);
}

void test_priority_order()
{
    Scheduler scheduler;
    std::string error;

    assert(scheduler.submit({1, "task-a", 5}, error));
    assert(scheduler.submit({2, "task-b", 1}, error));
    assert(scheduler.submit({3, "task-c", 3}, error));

    Task task;

    assert(scheduler.run_next(task, error));
    assert(task.id == 2);

    assert(scheduler.run_next(task, error));
    assert(task.id == 3);

    assert(scheduler.run_next(task, error));
    assert(task.id == 1);

    assert(scheduler.empty());
}

void test_priority_stable_order()
{
    Scheduler scheduler;
    std::string error;

    assert(scheduler.submit({1, "task-a", 1}, error));
    assert(scheduler.submit({2, "task-b", 1}, error));
    assert(scheduler.submit({3, "task-c", 2}, error));
    assert(scheduler.submit({4, "task-d", 1}, error));

    Task task;

    assert(scheduler.run_next(task, error));
    assert(task.id == 1);

    assert(scheduler.run_next(task, error));
    assert(task.id == 2);

    assert(scheduler.run_next(task, error));
    assert(task.id == 4);

    assert(scheduler.run_next(task, error));
    assert(task.id == 3);

    assert(scheduler.empty());
}

void test_default_priority_order()
{
    Scheduler scheduler;
    std::string error;

    assert(scheduler.submit({1, "task-a", 1}, error));
    assert(scheduler.submit({2, "task-b"}, error));

    Task task;

    assert(scheduler.run_next(task, error));
    assert(task.id == 2);

    assert(scheduler.run_next(task, error));
    assert(task.id == 1);

    assert(scheduler.empty());
}

void test_priority_validation_unchanged()
{
    Scheduler scheduler;
    std::string error;

    assert(!scheduler.submit({0, "invalid", 1}, error));
    assert(error == "task id must not be zero");

    assert(!scheduler.submit({1, "", 1}, error));
    assert(error == "task name must not be empty");

    assert(scheduler.empty());
}

int main()
{
    test_fifo_order();
    test_invalid_task_id();
    test_empty_task_name();
    test_run_empty_scheduler();
    test_pending_count();
    test_priority_order();
    test_priority_stable_order();
    test_default_priority_order();
    test_priority_validation_unchanged();

    std::cout << "All tests passed.\n";
    return 0;
}