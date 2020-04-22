import os
import asyncio
from pipeline.tasks import Task, rpc


class ShellTask(Task):
    async def run(self, command, **inputs):
        # run shell command
        self.process = await asyncio.create_subprocess_shell(
            command,
            stderr=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            env=os.environ,  # inherit environment
        )

        # setup stream readers
        stream_log_to_node(self.process.stdout, self.node, 'stdout')
        stream_log_to_node(self.process.stderr, self.node, 'stderr')

        # wait for process to finish
        result = await self.process.wait()

        return {
            'code': result,
        }

    @rpc
    async def stop(self):
        print('stopping shell process')
        self.process.kill()

        return await super().stop()


def stream_log_to_node(stream, node, name):
    async def logger():
        while True:
            line = await stream.readline()
            if line == b'':
                return

            print(line.decode('utf-8'), end='')

    asyncio.create_task(logger())
