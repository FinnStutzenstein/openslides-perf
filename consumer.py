import asyncio
import json
import websockets
import traceback
import lz4.frame


class Consumer:
    error = False
    change_id = 0

    def __init__(self, i, token, uri, stats_handler):
        self.i = i
        self.token = token
        self.uri = uri
        self.stats_handler = stats_handler

    async def connect(self, wsuri):
        await self.stats_handler.add_consumer(self)
        headers = {"Cookie": "OpenSlidesSessionID=" + self.token}

        success = False
        while not success:
            try:
                self.connection = await websockets.connect(
                    wsuri,
                    max_size=None,
                    read_limit=2 ** 20,
                    close_timeout=20,
                    extra_headers=headers,
                )
                success = True
            except websockets.exceptions.InvalidStatusCode:
                print("retry: {}".format(self.i))
                await asyncio.sleep(0.1)

    async def recv_task(self):
        try:
            await self._recv_task()
        except Exception as e:
            print(
                "Error in consumer {}: {}\n{}".format(
                    self.i, repr(e), traceback.format_exc()
                )
            )
            self.error = True

    async def _recv_task(self):
        while True:
            message = await self.connection.recv()

            message_length = len(message)
            compressed = False
            if isinstance(message, bytes):
                compressed = True
                decompressed_data = lz4.frame.decompress(message)
                message = decompressed_data.decode("utf-8")

            await self.stats_handler.add_recv(message_length, len(message))

            try:
                data = json.loads(message)
            except Exception:
                pass
            else:
                await self.handle_data(data)

    async def handle_data(self, data):
        if data.get("type") != "autoupdate":
            return

        self.change_id = data["content"]["to_change_id"]
