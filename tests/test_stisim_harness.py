"""
Tests for the run_stisim.py Zimbabwe model harness script. Ensures input args and minimum required config are valid with
appropriate exceptions thrown in error cases. Verifies seed handling and multi-sim running.
"""

import json
import pytest
import sciris as sc
import tempfile

from pathlib import Path

from run_stisim import (generate_seeds, load_config_file, orchestrate, validate_config,
                        InvalidInputDirectory, InvalidPlatformException, MissingConfigurationEntryException)

@pytest.fixture
def valid_config():
    return {'rand_seed': 420, 'start_year': 1990, 'dur': 1, 'n_agents': 5000}

#
# testing orchestrate input arg error cases
#

@sc.timer()
def test_orchestrate_checks_for_missing_config_entries(valid_config):
    invalid_config = valid_config
    invalid_config.pop('rand_seed')  # now missing required 'rand_seed'
    with pytest.raises(MissingConfigurationEntryException):
        orchestrate(config=invalid_config, input_dir=Path('.'), output_dir=Path('output'), n_seeds=1,
                    platform='local', dry_run=True)

@sc.timer()
def test_orchestrate_allows_extra_config_entries(valid_config):
    valid_config['extra_entry'] = 'should be ok'
    orchestrate(config=valid_config, input_dir=Path('.'), output_dir=Path('output'), n_seeds=1,
                platform='local', dry_run=True)

@sc.timer()
def test_orchestrate_validates_platform(valid_config):
    with pytest.raises(InvalidPlatformException):
        orchestrate(config=valid_config, input_dir=Path('.'), output_dir=Path('output'), n_seeds=1,
                    platform='not_a_platform', dry_run=True)

@sc.timer()
def test_orchestrate_validates_variant_count(valid_config):
    base_args = {'config': valid_config, 'input_dir': Path('.'), 'output_dir': Path('output'), 'platform': 'local',
                 'dry_run': True}

    for n in [-1, 0]:
        with pytest.raises(ValueError):
            orchestrate(**base_args, n_seeds=n)
    for n in [1, 2]:
        orchestrate(**base_args, n_seeds=n)

@sc.timer()
def test_orchestrate_validates_input_dir(valid_config):
    base_args = {'config': valid_config, 'output_dir': Path('output'), 'n_seeds': 1, 'platform': 'local',
                 'dry_run': True}

    # directory does not exist
    with pytest.raises(InvalidInputDirectory):
        orchestrate(**base_args, input_dir=Path('does_not_exist'))

    # exists, but is not a directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_filename = Path(temp_dir, 'data.json')
        with open(temp_filename, 'w') as f:
            json.dump({'some': 'data'}, f)

        with pytest.raises(InvalidInputDirectory):
            orchestrate(**base_args, input_dir=temp_filename)

#
# config and config file loading tests, separate from orchestrate()
#

@sc.timer()
def test_validate_config_extra_entries_ok(valid_config):
    valid_config['extra_entry'] = 'should be ok'
    validate_config(config=valid_config)

    # ensure actual file loading does not skip verification
    with tempfile.TemporaryDirectory() as temp_dir:
        filename = Path(temp_dir, 'config.json')
        with open(filename, 'w') as f:
            json.dump(valid_config, f)
        load_config_file(filename=str(filename))

@sc.timer()
def test_validate_config_missing_required_entry(valid_config):
    invalid_config = valid_config
    invalid_config.pop('rand_seed')  # now missing required 'rand_seed'

    with pytest.raises(MissingConfigurationEntryException):
        validate_config(config=invalid_config)

    # ensure actual file loading verifies as well to ensure quick error reporting
    with tempfile.TemporaryDirectory() as temp_dir:
        filename = Path(temp_dir, 'config.json')
        with open(filename, 'w') as f:
            json.dump(invalid_config, f)
        with pytest.raises(MissingConfigurationEntryException):
            load_config_file(filename=filename)

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
# Multi-sim tests
#

@sc.timer()
def test_two_stochastic_variants_generates_two_separate_results_regression(valid_config):
    # verify the execution harness generates the right number of distinct results, one with the required seed. This is
    # not a data check on the results.
    with tempfile.TemporaryDirectory() as temp_dir:
        output_root = Path(temp_dir, 'output')
        orchestrate(config=valid_config, input_dir=Path('input'), output_dir=output_root, n_seeds=2, platform='local')

        # now verify that there are two output directories, one per simulation (seed) and that one of them used the
        # default specified seed
        expected_seed = valid_config['rand_seed']
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
