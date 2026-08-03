import asyncio
from patentmind.ingestion.arxiv_client import ArxivClient

async def test():
    client = ArxivClient()
    res = await client.fetch_ai_patents(5)
    print("Found:", len(res))

asyncio.run(test())
