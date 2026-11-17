"""
Tests for the run_stisim.py Zimbabwe model harness script. Ensures input args and frame are valid with
appropriate exceptions thrown in error cases. Verifies seed handling and multi-sim running.
"""
import pandas as pd
import pytest
import sciris as sc

from pathlib import Path

from run_stisim import generate_seeds, load_frame, orchestrate, InvalidPlatformException

REPO_ROOT = Path(__file__).resolve().parent.parent
ZIMBABWE_FRAME_PATH = Path(REPO_ROOT, "examples", "zimbabwe")

@pytest.fixture
def valid_frame():
    return load_frame(frame_path=ZIMBABWE_FRAME_PATH)

#
# testing orchestrate input arg error cases
#

@sc.timer()
def test_orchestrate_validates_platform(valid_frame):
    with pytest.raises(InvalidPlatformException):
        orchestrate(project=valid_frame, output_dir=Path('output'), n_seeds=1, platform='not_a_platform', dry_run=True)

@sc.timer()
def test_orchestrate_validates_variant_count(valid_frame):
    base_args = {'project': valid_frame, 'output_dir': Path('output'), 'platform': 'local', 'dry_run': True}

    for n in [-1, 0]:
        with pytest.raises(ValueError):
            orchestrate(**base_args, n_seeds=n)
    for n in [1, 2]:
        orchestrate(**base_args, n_seeds=n)

#
# stochastic seed generation testing
#

@sc.timer()
def test_validate_positive_seed_count():
    for n in [-1, 0]:
        with pytest.raises(ValueError):
            generate_seeds(n=n, base_seed=10)
    for n in [1, 2]:
        generate_seeds(n=n, base_seed=10)

@sc.timer()
def test_base_seed_is_always_the_first_seed():
    base_seed = 10
    for n in [1, 2]:
        seeds = generate_seeds(n=n, base_seed=base_seed)
        assert seeds[0] == base_seed

@sc.timer()
def test_right_number_of_seeds_are_made():
    for n in [1, 2]:
        seeds = generate_seeds(n=n, base_seed=10)
        assert len(seeds) == n

@sc.timer()
def test_seeds_are_unique():
    seeds = generate_seeds(n=1000, base_seed=1)
    assert len(seeds) == len(set(seeds))

#
# Frame loading tests
#

@sc.timer()
def test_load_frame_valid_example():
    frame = load_frame(frame_path=ZIMBABWE_FRAME_PATH)
    assert hasattr(frame, "BASE_SEED")
    assert callable(getattr(frame, "make_sim", None))


@sc.timer()
def test_load_frame_missing_path_raises(tmp_path):
    missing_path = Path(tmp_path, "does_not_exist")
    with pytest.raises(ModuleNotFoundError):
        load_frame(frame_path=missing_path)


@sc.timer()
def test_load_frame_arbitrary_external_directory(tmp_path):
    # ensures we load_frame() can properly handle pathing outside the repository root (arbitrary project workspaces)
    external_frame = Path(tmp_path, "external_study")
    external_frame.mkdir()
    Path(external_frame, "__init__.py").write_text(
        "BASE_SEED = 123\n"
        "def make_sim(seed=0):\n"
        "    return {'seed': seed}\n"
    )

    frame = load_frame(frame_path=external_frame)
    assert frame.BASE_SEED == 123
    assert frame.make_sim(seed=7) == {"seed": 7}

#
# Multi-sim tests
#

@sc.timer()
def test_two_stochastic_variants_generates_two_separate_results_regression(valid_frame, tmp_path):
    # verify the execution harness generates the right number of distinct results, one with the required seed. This is
    # not a data check on the results.
    expected_seed = valid_frame.BASE_SEED

    # adding some stale data representing. Ensuring all final results in output/ are NEW results.
    output_root = Path(tmp_path, 'output')
    output_root.mkdir(parents=True)

    stale_file = Path(output_root, 'stale.txt')
    stale_file.write_text('leftover data')

    sim_output_dir = Path(output_root, f'seed-{expected_seed}')
    sim_output_dir.mkdir(parents=True)

    csv_filename = Path(sim_output_dir, 'prevalence.csv')
    stale_prevalence = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
    stale_prevalence.to_csv(csv_filename)

    orchestrate(project=valid_frame, output_dir=output_root, n_seeds=2, platform='local')

    assert output_root.is_dir()
    assert not stale_file.exists()
    fresh_prevalence = pd.read_csv(csv_filename)
    assert not fresh_prevalence.equals(stale_prevalence)

    # now verify that there are two output directories, one per simulation (seed) and that one of them used the
    # default specified seed
    expected_seed_dir = f"seed-{expected_seed}"
    items = list(output_root.glob('*'))

    assert len(items) == 2  # two items
    for item in items:
        assert item.is_dir()  # each is a directory
    directory_names = [item.name for item in items]
    assert expected_seed_dir in directory_names  # the required base seed was used and has an output dir

    for directory in items:
        # ensure prevalence.csv exists and is the only output file
        per_sim_items = list(directory.glob('*'))
        assert len(per_sim_items) == 1
        item = per_sim_items[0]
        assert item.is_file()  # it is a file
        assert item.name == "prevalence.csv"  # it is prevalence data
