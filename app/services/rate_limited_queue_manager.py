import asyncio
from time import monotonic


class RateLimitedQueueManager:
    def __init__(self, rate_limit_rpm: int, max_tokens: int):
        self.rate_limit_rpm = rate_limit_rpm
        self.max_tokens = max_tokens
        self.queue = asyncio.Queue()
        self.last_checked = monotonic()
        self.available_tokens = max_tokens

    async def process_requests(self):
        while True:
            now = monotonic()
            elapsed = now - self.last_checked

            # Regenerate tokens based on elapsed time
            regen_rate = self.rate_limit_rpm / 60.0  # RPM to tokens per second
            self.available_tokens = min(self.max_tokens, self.available_tokens + regen_rate * elapsed)
            self.last_checked = now

            # Process requests from the queue if tokens are available
            if not self.queue.empty() and self.available_tokens >= 1:
                request = await self.queue.get()

                # Execute the request
                await request()

                # Deduct the tokens for the processed request
                self.available_tokens -= 1

            # Sleep for a short period to prevent busy waiting
            await asyncio.sleep(0.1)

    async def add_request(self, request_callable):
        await self.queue.put(request_callable)
