import asyncio
import aiohttp
import argparse
import sys
from stats import StatsHandler
from consumer import Consumer

class Main():
    def __init__(self, host, user, password, N, secure):
        self.host = host
        self.user = user
        self.password = password
        self.N = N
        self.secure = secure
        print(host, user, password, N, secure)

    async def run(self):
        url = "https://" if self.secure else "http://"
        url += self.host + "/apps/users/login/"
        wsuri = "wss://" if self.secure else "ws://"
        wsuri += self.host + "/ws/?autoupdate=1"

        stats_handler = StatsHandler()
        token = await self.login(url)
        print("got token:", token)

        consumers = [Consumer(i, token, wsuri, stats_handler) for i in range(self.N)]
        for consumer in consumers:
            await consumer.connect(wsuri)
        futures = [consumer.recv_task() for consumer in consumers]

        print("OK!")

        futures.append(stats_handler.task())
        await asyncio.gather(*futures)

    async def login(self, url):
        data = {
            "username": self.user,
            "password": self.password,
        }
        async with aiohttp.ClientSession() as session:
            response = await session.post(url, json=data)
            return response.cookies["OpenSlidesSessionID"].value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="WS-Receiver"
    )
    parser.add_argument(
            "-i", help="Instance (url/Host)", default="localhost:8000"
    )
    parser.add_argument("-u", help="User", default="admin")
    parser.add_argument("-p", help="Password", default="admin")
    parser.add_argument("-N", help="No. of connections", default="10")
    parser.add_argument('-s', help="secure connection", action='store_true')
    args = parser.parse_args()
    try:
        N = int(args.N)
    except ValueError:
        logging.critical("N must be an integer")
        sys.exit(1)
    loop = asyncio.get_event_loop()
    main = Main(args.i, args.u, args.p, N, args.s)
    try:
        loop.run_until_complete(main.run())
    except KeyboardInterrupt:
        print("bye")
