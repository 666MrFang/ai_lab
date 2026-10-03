```markdown
# Priority Scheduling Specification

## 1. Overview

The scheduler currently processes tasks in FIFO order.

Add priority scheduling support.

## 2. Task Priority

Each task has a priority.

Higher-priority tasks must be executed before lower-priority tasks.

Tasks with the same priority must preserve their submission order.

## 3. Existing Behavior

Existing callers that do not use priority scheduling must continue to observe
the current FIFO behavior.

## 4. Validation

Task validation behavior must remain unchanged.

Invalid task IDs and empty task names must continue to be rejected.

## 5. API Compatibility

Existing callers should require minimal changes.

## 6. Testing

Add tests for priority scheduling.

Existing tests must continue to pass.