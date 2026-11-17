import importlib
import sys
from types import ModuleType

import pandas as pd
import shutil

from pathlib import Path

LOCAL = 'local'
PLATFORMS = [LOCAL]

DEFAULT_ARGS = {
    'output': Path('output'),
    'n_runs': 1,
    'platform': LOCAL
}

class InvalidPlatformException(Exception): pass

class InvalidInputDirectory(Exception): pass

def run_sim(sim, output_dir: Path, verbose: bool = False):
    # execute
    sim.run()

    # generate/write results
    if verbose:
        print(f"Writing results to {output_dir}")

    prevalence = sim.results.hiv.prevalence[:]  # convert result to numpy.ndarray

    output_file = Path(output_dir, 'prevalence.csv')
    pd.DataFrame(prevalence).to_csv(output_file)


def load_frame(frame_path: Path, verbose: bool = False) -> ModuleType:
    """
        Loads a project frame/directory by path
        Args:
            frame_path: Path of frame (directory) to load

        Returns:
            the loaded model frame (module)
        """
    resolved_path = frame_path.resolve()
    parent_dir = str(resolved_path.parent)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    if verbose:
        print(f"Loading frame: {frame_path} ...")
    try:
        frame = importlib.import_module(resolved_path.name)
    except ModuleNotFoundError as e:
        e.msg = f'Valid frame not found at path: {frame_path}'
        raise e
    return frame


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument('-f', '--frame', dest='frame', type=str, required=True, help=f'Frame to run (Required).')

    default = DEFAULT_ARGS['n_runs']
    parser.add_argument('-n', '--n-runs', dest='n_runs', type=int, default=default,
                        help=f'Number of stochastic simulation variations to run (Default: {default}).')

    default = DEFAULT_ARGS['output']
    parser.add_argument('-o', '--output', dest='output_dir', type=str, default=default,
                        help=f'Output directory for simulation results (Default: {default}).')

    default = DEFAULT_ARGS['platform']
    platforms = ', '.join(PLATFORMS)
    parser.add_argument('-p', '--platform', dest='platform', type=str, default=default,
                        help=f'Execution platform for simulation(s) (Available: {platforms}) (Default: {default}).')

    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        help='Print more information during processing (Default: False).')

    args = parser.parse_args()
    args.output_dir = Path(args.output_dir).absolute()
    args.frame = Path(args.frame).absolute()
    args.frame = load_frame(args.frame, verbose=args.verbose)
    return args


def generate_seeds(n, base_seed):
    if n < 1:
        raise ValueError(f"Number of seeds must be greater than 0, not {n} .")

    rand_seeds = [i for i in range(n)]

    # keep the specified run number in the base config for the first simulation, esp. in case no extra runs specified
    if base_seed in rand_seeds:
        rand_seeds.remove(base_seed)
        rand_seeds.insert(0, base_seed)
    else:
        rand_seeds[0] = base_seed  # overwriting any generated seed in index 0
    return rand_seeds


def _clean_directory(output_dir: Path):
    # ensure output_dir exists and destroy all contents without removing the directory itself
    for item in output_dir.iterdir():
        if item.is_dir() and not item.is_symlink():
            shutil.rmtree(item)
        else:
            item.unlink()

def run_local(project, rand_seeds: list[int], output_dir: Path, verbose: bool = False):
    # Simple, serial execution of each stochastic variant locally. Each variant gets a different random seed and a
    # different output subdirectory

    # ensure we have a clean root output directory to contain the individual simulation results
    output_dir.mkdir(parents=True, exist_ok=True)
    _clean_directory(output_dir=output_dir)

    for i, rand_seed in enumerate(rand_seeds):
        sim = project.make_sim(seed=rand_seed)

        # ensure we have a clean output directory for this specific sim
        sim_output_dir = Path(output_dir, f"seed-{rand_seed}")
        sim_output_dir.mkdir(parents=True)

        run_sim(sim=sim, output_dir=sim_output_dir, verbose=verbose)


def orchestrate(project: ModuleType, n_seeds: int, output_dir: Path, platform: str, dry_run: bool = False,
                verbose: bool = False):
    if n_seeds < 1:
        raise ValueError(f"number of runs must be greater than 0, not {n_seeds} .")

    if platform not in PLATFORMS:
        platforms_str = ", ".join(PLATFORMS)
        raise InvalidPlatformException(f'Unknown platform: {platform}. Available: {platforms_str}')

    if dry_run:
        return

    # if more than one stochastic variation was requested, we need separate config/outputs for each.
    rand_seeds = generate_seeds(n=n_seeds, base_seed=project.BASE_SEED)

    # build and execute
    if platform == LOCAL:
        run_local(project=project, rand_seeds=rand_seeds, output_dir=output_dir, verbose=verbose)


if __name__ == '__main__':
    # parse input arguments and load the provided config
    args = parse_args()

    orchestrate(project=args.frame, output_dir=args.output_dir, n_seeds=args.n_runs, platform=args.platform,
                verbose=args.verbose)
