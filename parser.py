import asyncio

class RESPParser:
    def __init__(self, reader: asyncio.StreamReader):
        self.reader = reader

    async def read_line(self) -> bytes:
        """Reads bytes until it encounters \\r\\n and strips it."""
        line = await self.reader.readuntil(b'\r\n')
        return line[:-2]  

    async def parse(self):
        """Parses the next complete RESP object from the stream."""
        # 1. Read the very first byte to determine the type
        prefix = await self.reader.readexactly(1)
        
        # Handle Simple String (+)
        if prefix == b'+':
            line = await self.read_line()
            return line.decode('utf-8')
            
        # Handle Error (-)
        elif prefix == b'-':
            line = await self.read_line()
            return Exception(line.decode('utf-8'))
            
        # Handle Integer (:)
        elif prefix == b':':
            line = await self.read_line()
            return int(line)
            
        # Handle Bulk String ($)
        elif prefix == b'$':
            length_bytes = await self.read_line()
            length = int(length_bytes)
            
            # Check for Null Bulk String ($-1\r\n)
            if length == -1:
                return None
                
            # CRITICAL: Read EXACTLY the number of bytes specified
            data = await self.reader.readexactly(length)
            
            # Consume the trailing \r\n that follows the data
            await self.reader.readexactly(2) 
            
            return data.decode('utf-8')
            
        # Handle Array (*)
        elif prefix == b'*':
            length_bytes = await self.read_line()
            count = int(length_bytes)
            
            if count == -1:
                return None
                
            # Recursively parse each element inside the array
            array_result = []
            for _ in range(count):
                item = await self.parse()
                array_result.append(item)
            return array_result
            
        else:
            raise ValueError(self.reader, f"Unknown RESP prefix: {prefix}")
