import asyncio
import logging

from app.workspace.processing import process_pending_documents

logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":
    asyncio.run(process_pending_documents())
