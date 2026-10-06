import asyncio
from protocol import RESPparser,serialize

async def test_suite():
    print("starting RESP protocol")
    assert serialize("ok")==b"+ok\r\n"
    assert serialize("10")==b":10\r\n"
        # ---------------------------------------------------------
    assert serialize("OK") == b"+OK\r\n"
    assert serialize(10) == b":10\r\n"
    assert serialize(None) == b"$-1\r\n"
    assert serialize("hello") == b"$5\r\nhello\r\n"
    assert serialize(["SET", "a", "b"]) == b"*3\r\n$3\r\nSET\r\n$1\r\na\r\n$1\r\nb\r\n"
    print("Task 1: Serializer tests passed safely.")

    weird_data = b"$11\r\nhello\r\nworld\r\n"
    reader = asyncio.StreamReader()
    reader.feed_data(weird_data)
    reader.feed_eof()
    
    parser = RESPParser(reader)
    parsed_val = await parser.deserialize()
    assert parsed_val == "hello\r\nworld"
    print("Task 2: Parser handled embedded '\\r\\n' payload smoothly.")

    print("⏳ Testing network splits (simulating packet lag)...")
    split_reader = asyncio.StreamReader()
    parser_split = RESPParser(split_reader)

    
    async def feed_chunks():
        chunks = [
            b"*2\r",          # Split line header mid-way
            b"\n$3\r\nGE",    # Complete header, split bulk payload mid-way
            b"T\r\n$8\r\n",   # Close first bulk, open second bulk length
            b"key\r\n",       # Send partial data that matches a lookalike delimiter
            b"val\r\n"        # Finalize transmission
        ]
        for chunk in chunks:
            await asyncio.sleep(0.2) # Artificial network delay
            split_reader.feed_data(chunk)
        split_reader.feed_eof()

    parse_task = asyncio.create_task(parser_split.deserialize())
    await feed_chunks()
    
    result = await parse_task
    assert result == ["GET", "key\r\nval"]
    print("Task 3: Parser successfully reassembled highly fragmented packets.")

    print(" All RESP protocol engine tests passed!")

if __name__ == "__main__":
    asyncio.run(test_suite())

