import asyncio

async def a():
    print("Hello, World!")
    await asyncio.sleep(1)
    print("Goodbye, World!")
    await asyncio.sleep(2)

async def b():
    print("Hello, World!")
    await asyncio.sleep(1)
    print("Goodbye, World!")

async def main():
    await asyncio.gather(a(), b())

asyncio.run(main())