import time
from rq import Queue
from redis import Redis
from tenacity import retry, stop_after_attempt, wait_fixed

# Connect to Redis server
redis_conn = Redis(host="localhost", port=6379)

# Create a Queue
task_queue = Queue("openai_tasks", connection=redis_conn)

# Rate limits based on your API limits
LIMITS = {
    "tokens_per_minute": 4000000,
    "requests_per_minute": 5000,
}

# Define a lock key in Redis if not using RQ features directly
LOCK_EXPIRY = 60  # in seconds


# Retry logic for processing to ensure jobs run within limits
@retry(wait=wait_fixed(12), stop=stop_after_attempt(6))  # Adjust timings according to allowable
def execute_api_call(func, *args, **kwargs):
    # Implement rate-limit check logic here if not using RQ-middleware
    func(*args, **kwargs)


def queue_openai_task(func, *args, **kwargs):
    task_queue.enqueue(execute_api_call, func, *args, **kwargs)
