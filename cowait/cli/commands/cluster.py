from ..config import CowaitConfig


ADDABLE_PROVIDERS = ['api']


def cluster_get(config: CowaitConfig, name: str) -> None:
    if name not in config.clusters:
        print('Unknown cluster', name)
        return 1

    args = config.get(['clusters', name])
    print(name)
    if name == config.default_cluster:
        print('    default')
    for key, value in args.items():
        print(f'    {key}: {value}')


def cluster_ls(config: CowaitConfig) -> None:
    for name in config.clusters:
        cluster_get(config, name)
        print()


def cluster_add(config: CowaitConfig, name: str, type: str, **options) -> None:
    if name in config.clusters:
        print(f'Error: Cluster {name} already exists')
        return 1

    if type not in ADDABLE_PROVIDERS:
        print(f'Error: Cant add cluster of type {type}')
        return 1

    config.set(['clusters', name], {
        'type': type,
        **options,
    })
    config.write()

    # dump added cluster
    cluster_get(config, name)


def cluster_rm(config: CowaitConfig, name: str) -> None:
    if name not in config.clusters:
        print(f'Error: Cluster {name} does not exist')
        return 1

    if name == config.default_cluster:
        print(f'Error: Cant remove the default cluster')
        return 1

    if name == 'docker':
        print('Error: Cant remove the docker provider')
        return 1

    if name == 'kubernetes':
        print('Error: Cant remove the kubernetes provider')
        return 1

    config.delete(['clusters', name])
    config.write()


def cluster_default(config: CowaitConfig) -> None:
    print(config.default_cluster)


def cluster_set_default(config: CowaitConfig, name: str) -> None:
    if name not in config.clusters:
        print(f'Error: Cluster {name} does not exist')
        return 1

    config.set('default_cluster', name)
    config.write()
