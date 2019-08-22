import asyncio
from collections import defaultdict
import time


class StatsHandler:
    stats = []
    stats_by_time = defaultdict(list)
    recv = 0
    consumers = []

    async def add_consumer(self, consumer):
        self.consumers.append(consumer)

    async def task(self):
        while True:
            await asyncio.sleep(1)
            await self.clear_by_time()

            # Throughput
            kb_per_sec = self.recv / 1024
            self.recv = 0
            print(
                "Throughput: {:.2f} kB/s ({:.2f} kbit/s)".format(
                    kb_per_sec, kb_per_sec * 8
                )
            )

            # Consumer stats
            ok = 0
            error = 0
            for consumer in self.consumers:
                if consumer.error:
                    error += 1
                else:
                    ok += 1
            print("Consumers: {} OK, {} errors".format(ok, error))

            # Change ids
            change_ids = defaultdict(lambda: 0)
            for consumer in self.consumers:
                change_ids[consumer.change_id] += 1
            keys = sorted(list(change_ids.keys()), reverse=True)
            print("Change ids")
            for key in keys:
                print("  {}: {}".format(key, change_ids[key]))

            # Message len stats
            await self.print_stats(self.stats, "All")
            stats_by_time = []
            for value in self.stats_by_time.values():
                stats_by_time.extend(value)
            await self.print_stats(stats_by_time, "Last 10 secs")
            print("")

    async def print_stats(self, list_of_stats, msg):
        N = len(list_of_stats)
        if N == 0:
            return
        ratios = [s.ratio for s in list_of_stats]
        mean = sum(ratios) / N
        std = sum((l - mean) ** 2 for l in ratios)
        recv = int(sum(s.message_len for s in list_of_stats) / 1024)
        recv_de = int(sum(s.decompressed_len for s in list_of_stats) / 1024)
        print("# {}".format(msg))
        print(
            "received {} messages; {} kB ({} kB decompressed)".format(N, recv, recv_de)
        )
        print("ratio: mean={:.2f} std={:.2f}".format(mean, std))

    async def clear_by_time(self):
        t = int(time.time()) - 10
        for key in [k for k in self.stats_by_time.keys()]:
            if int(key) < t:
                del self.stats_by_time[key]

    async def add_recv(self, message_len, decompressed_len):
        t = int(time.time())
        stats = Stats(message_len, decompressed_len)
        self.recv += message_len
        self.stats.append(stats)
        self.stats_by_time[t].append(stats)


class Stats:
    def __init__(self, message_len, decompressed_len):
        self.message_len = message_len
        self.decompressed_len = decompressed_len
        self.ratio = float(decompressed_len) / message_len
