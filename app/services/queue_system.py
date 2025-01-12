from redis import Redis
from rq import Queue
from tenacity import retry, stop_after_attempt, wait_fixed

# Initialize Redis connection for task queue management
# Using Redis as the backend for RQ (Redis Queue) system
redis_conn = Redis(host="localhost", port=6379)

# Create a named queue for OpenAI tasks
# This queue will handle all OpenAI API related tasks
task_queue = Queue("openai_tasks", connection=redis_conn)

# Rate limits configuration based on OpenAI API limits
# These values should match your OpenAI API tier limits
LIMITS = {
    "tokens_per_minute": 4000000,  # Maximum tokens per minute
    "requests_per_minute": 5000,  # Maximum requests per minute
}

# Lock expiry time for Redis locks (in seconds)
# Prevents race conditions when multiple workers access shared resources
LOCK_EXPIRY = 60  # in seconds


# Retry decorator for API calls with exponential backoff
# Handles temporary failures and rate limits by retrying failed calls
@retry(wait=wait_fixed(12), stop=stop_after_attempt(6))  # Wait 12 seconds between retries, max 6 attempts
def execute_api_call(func, *args, **kwargs):
    """
    Wrapper function for executing API calls with retry logic
    Args:
        func: The API function to execute
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function
    """
    # Implement rate-limit check logic here if not using RQ-middleware
    func(*args, **kwargs)


def queue_openai_task(func, *args, **kwargs):
    """
    Enqueues an OpenAI task for asynchronous processing
    Args:
        func: The function to execute asynchronously
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function
    """
    task_queue.enqueue(execute_api_call, func, *args, **kwargs)
