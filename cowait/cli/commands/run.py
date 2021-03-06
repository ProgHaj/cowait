import sys
import json
import getpass
from cowait.tasks import TaskDefinition
from cowait.engine.errors import TaskCreationError, ProviderError
from cowait.utils import parse_task_image_name
from cowait.tasks.messages import TASK_INIT, TASK_STATUS, TASK_FAIL, TASK_RETURN, TASK_LOG
from ..config import CowaitConfig
from ..context import CowaitContext
from ..utils import ExitTrap
from ..logger import Logger
from .build import build as build_cmd
from sty import fg, rs


def run(
    config: CowaitConfig,
    task: str,
    name: str = None,
    inputs: dict = {},
    env: dict = {},
    ports: dict = {},
    routes: dict = {},
    build: bool = False,
    upstream: str = None,
    detach: bool = False,
    cpu: str = None,
    cpu_limit: str = None,
    memory: str = None,
    memory_limit: str = None,
    raw: bool = False,
    quiet: bool = False,
):
    logger = RunLogger(raw, quiet)
    try:
        context = CowaitContext.open()
        cluster = config.get_cluster()

        # figure out image name
        remote_image = True
        image, task = parse_task_image_name(task, None)
        if image is None:
            if build:
                build_cmd(quiet=quiet or raw)
            image = context.image
            remote_image = False

        volumes = context.get('volumes', {})
        if not isinstance(volumes, dict):
            raise TaskCreationError('Invalid volume configuration')
        if not remote_image:
            volumes['/var/task'] = {
                'bind': {
                    'src': context.root_path,
                    'mode': 'rw',
                },
            }

        # default to agent as upstream
        agent = cluster.find_agent()

        # create task definition
        taskdef = TaskDefinition(
            id=name,
            name=task,
            image=image,
            inputs=inputs,
            env={
                **context.environment,
                **env,
            },
            ports=ports,
            routes=routes,
            parent=None,  # root task
            upstream=context.coalesce('upstream', upstream, agent),
            owner=getpass.getuser(),
            volumes=volumes,
            cpu=context.override('cpu', cpu),
            cpu_limit=context.override('cpu_limit', cpu_limit),
            memory=context.override('memory', memory),
            memory_limit=context.override('memory_limit', memory_limit),
            storage=context.get('storage', {}),
        )

        # print execution info
        logger.print_info(taskdef, config.default_cluster)

        # submit task to cluster
        task = cluster.spawn(taskdef)

        if detach:
            logger.header('detached')
            return

        def destroy(*args):
            logger.header('interrupt')
            cluster.destroy(task.id)
            sys.exit(1)

        with ExitTrap(destroy):
            # capture & print logs
            logs = cluster.logs(task)
            logger.header('task output')
            for msg in logs:
                logger.handle(msg)

        logger.header()

    except ProviderError as e:
        print('Provider error:', str(e))
        logger.print_exception(f'Provider Error: {e}')

    except TaskCreationError as e:
        logger.print_exception(f'Error creating task: {e}')


class RunLogger(Logger):
    def __init__(self, raw: bool = False, quiet: bool = False, time: bool = True):
        super().__init__(quiet, time)
        self.raw = raw
        self.idlen = 0

    @property
    def newline_indent(self):
        return self.idlen + 4 + super().newline_indent

    def handle(self, msg):
        if 'type' not in msg:
            return
        type = msg['type']

        if self.quiet:
            # only top level return value
            if type == TASK_RETURN and msg['id'] == self.id:
                print(json.dumps(msg['result']))
            return
        elif self.raw:
            print(json.dumps(msg))
        else:
            if type == TASK_INIT:
                self.on_init(**msg)
            elif type == TASK_RETURN:
                self.on_return(**msg)
            elif type == TASK_FAIL:
                self.on_fail(**msg)
            elif type == TASK_STATUS:
                pass
            elif type == TASK_LOG:
                self.on_log(**msg)

    def header(self, title: str = None):
        if self.raw:
            return
        super().header(title)

    def print_info(self, taskdef, cluster_name):
        self.id = taskdef.id

        self.header('task')
        self.println('   task:      ', self.json(taskdef.id))
        self.println('   cluster:   ', self.json(cluster_name))
        if taskdef.upstream:
            self.println('   upstream:  ', self.json(taskdef.upstream))
        self.println('   image:     ', self.json(taskdef.image))
        if len(taskdef.inputs) > 0:
            self.println('   inputs:    ', self.json(taskdef.inputs))
        if len(taskdef.volumes) > 0:
            self.println('   volumes:   ', self.json(taskdef.volumes))
        if len(taskdef.storage) > 0:
            self.println('   storage:   ', ', '.join(taskdef.storage.keys()))
        if taskdef.cpu or taskdef.cpu_limit:
            self.println(f'   cpu:        {taskdef.cpu}/{taskdef.cpu_limit}')
        if taskdef.memory or taskdef.memory_limit:
            self.println(f'   memory:     {taskdef.memory}/{taskdef.memory_limit}')

    def print(self, *args):
        if self.raw:
            return
        super().print(*args)

    def print_id(self, id, short=True, pad=True):
        color = fg(hash(id) % 214 + 17)
        if short and '-' in id:
            id = id[:id.find('-')]
            self.idlen = max(self.idlen, len(id))
        self.print(color + id.ljust(self.idlen if pad else 0) + rs.all)

    def on_init(self, task: dict, version: str, **msg):
        self.print_time()
        self.print_id(task['id'])
        self.print(
            f' {fg.yellow}*{rs.all} started with',
            self.json(task['inputs'], indent=2),
        )
        if task['parent'] is not None:
            self.print(' by [')
            self.print_id(task['parent'], pad=False)
            self.println(']')
        else:
            self.println()

    def on_status(self, id, status, **msg):
        self.print_time()
        self.print_id(id)
        self.println(f'{fg.yellow} ~ {status}{rs.all}')

    def on_fail(self, id, error, **msg):
        self.print_time()
        self.print_id(id)
        self.println(f'{fg.red} ! {rs.all}ERROR: {error}')

    def on_return(self, id, result, **msg):
        self.print_time()
        self.print_id(id)
        self.println(f'{fg.green} ={rs.all} returned', self.json(result, indent=2))

    def on_log(self, id, file, data, **msg):
        self.print_time()
        self.print_id(id)
        self.println('  ', data)
