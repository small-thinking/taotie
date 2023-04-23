import asyncio

from taotie.message_queue import RedisMessageQueue


async def main():
    redis_url = "localhost"
    port = 6379
    channel_name = "my-redis"
    queue = RedisMessageQueue(
        redis_url=redis_url, port=port, channel_name=channel_name, verbose=True
    )

    await queue.connect()
    await queue.put('{"source": "user", "message": "Hello, world!"}')
    await queue.put('{"source": "user", "message": "Hello, world!2"}')
    await queue.put('{"source": "user", "message": "Hello, world!3"}')
    await queue.put('{"source": "user", "message": "Hello, world!4"}')
    await queue.put('{"source": "user", "message": "Hello, world!5"}')
    await queue.put('{"source": "user", "message": "Hello, world!6"}')
    messages = await queue.get(batch_size=6)
    print(messages)

    await queue.close()


asyncio.run(main())
