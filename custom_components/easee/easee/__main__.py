import asyncio
import logging
from .session import EaseeSession, Chargers, Charger, ChargerConfig, ChargerState


logging.basicConfig(
    format="%(asctime)-15s %(name)-5s %(levelname)-8s %(message)s", level=logging.INFO
)

_LOGGER = logging.getLogger(__name__)


async def main():
    session = EaseeSession("+460761386397", "hobbe1234")
    await session.connect()
    chrs = Chargers(session)
    chargers = await chrs.get()
    await session.close()


if __name__ == "__main__":
    import time

    s = time.perf_counter()
    asyncio.run(main())
    elapsed = time.perf_counter() - s
    print(f"{__file__} executed in {elapsed:0.2f} seconds.")
