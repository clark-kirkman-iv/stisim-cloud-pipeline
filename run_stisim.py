import numpy as np
import pandas as pd
import sciris as sc
import shutil
import starsim as ss
import stisim as sti

from pathlib import Path

LOCAL = 'local'
PLATFORMS = [LOCAL]

DEFAULT_ARGS = {
    'input': Path('input'),
    'output': Path('output'),
    'n_runs': 1,
    'platform': LOCAL
}

class InvalidPlatformException(Exception): pass

class InvalidInputDirectory(Exception): pass

class MissingConfigurationEntryException(Exception): pass

#
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# Original stisim Zimbabwe example model in here.

"""
Zimbabwe HIV model with calibrated parameters and UNAIDS comparison data.

This example demonstrates how to build a data-driven HIV simulation:
- Initial prevalence from CSV by risk group/sex/SW status
- Condom use data by partnership type over time
- ART and VMMC coverage from national program data
- Testing interventions with FSW-targeted, general population, and low-CD4 strategies
- UNAIDS estimates attached to sim.data for plot overlay
"""

# TODO: make_interventions, make_sim, and all their defaults (here) should be in a separate file, e.g. zimbabwe.py,
#   which is essentially a standard module for loading/using with this harness.

# Sim settings
default_sim_pars = dict(start=1990, age_scale=1000)

# Calibrated parameters
default_hiv_pars = dict(
    beta_m2f=0.035,
    eff_condom=0.95,
    rel_init_prev=1.0,
)
default_nw_pars = dict(
    prop_f0=0.79,
    prop_m0=0.83,
    f1_conc=0.16,
    m1_conc=0.11,
    p_pair_form=0.58,
)

def make_interventions():
    """
    Create Zimbabwe-specific HIV testing interventions.

    Returns FSW-targeted testing, general population testing, low-CD4 testing,
    and PrEP. ART and VMMC are created separately from coverage data.
    """
    scaleup_years = np.arange(1990, 2021)
    years = np.arange(1990, 2041)
    n_scaleup = len(scaleup_years)
    n_future = len(years) - n_scaleup

    fsw_prob = np.concatenate([np.linspace(0, 0.75, n_scaleup), np.linspace(0.75, 0.85, n_future)])
    gp_prob = np.concatenate([np.linspace(0, 0.5, n_scaleup), np.linspace(0.5, 0.6, n_future)])
    low_cd4_prob = np.concatenate([np.linspace(0, 0.85, n_scaleup), np.linspace(0.85, 0.95, n_future)])

    def fsw_eligibility(sim):
        return sim.networks.structuredsexual.fsw & ~sim.diseases.hiv.diagnosed & ~sim.diseases.hiv.on_art

    def other_eligibility(sim):
        return ~sim.networks.structuredsexual.fsw & ~sim.diseases.hiv.diagnosed & ~sim.diseases.hiv.on_art

    def low_cd4_eligibility(sim):
        return (sim.diseases.hiv.cd4 < 200) & ~sim.diseases.hiv.diagnosed

    fsw_testing = sti.HIVTest(years=years, test_prob_data=fsw_prob, name='fsw_testing', eligibility=fsw_eligibility)
    other_testing = sti.HIVTest(years=years, test_prob_data=gp_prob, name='other_testing', eligibility=other_eligibility)
    low_cd4_testing = sti.HIVTest(years=years, test_prob_data=low_cd4_prob, name='low_cd4_testing', eligibility=low_cd4_eligibility)
    prep = sti.Prep()

    return [fsw_testing, other_testing, low_cd4_testing, prep]


def make_sim(input_dir: Path, **kwargs):
    """
    Create a Zimbabwe HIV simulation with calibrated parameters.

    Flat ``**kwargs`` are auto-routed via ``sti.route_pars`` — pass any
    network par (e.g. ``debut_f=18``), HIV par (``beta_m2f=0.04``), or sim
    par (``n_agents=5000``) directly. User values override the calibrated
    defaults baked into this builder.
    """
    routed = sti.route_pars(kwargs)
    nw_pars  = sc.mergedicts(default_nw_pars,  routed.nw)
    hiv_pars = sc.mergedicts(default_hiv_pars, routed.sti)
    for k in (*routed.nw, *routed.sti): kwargs.pop(k)  # consumed here

    # load input data files
    data_file = Path(input_dir, 'init_prev_hiv.csv')
    init_prev   = pd.read_csv(data_file)

    data_file = Path(input_dir, 'condom_use.csv')
    condom_data = pd.read_csv(data_file)

    data_file = Path(input_dir, 'art_coverage.csv')
    art_data    = pd.read_csv(data_file).set_index('year')

    data_file = Path(input_dir, 'vmmc_coverage.csv')
    vmmc_data   = pd.read_csv(data_file).set_index('year')

    data_file = Path(input_dir, 'zimbabwe_hiv_data.csv')
    hiv_data    = pd.read_csv(data_file)

    hiv     = sti.HIV(init_prev_data=init_prev, **hiv_pars)
    network = sti.StructuredSexual(condom_data=condom_data, **nw_pars)
    art     = sti.ART(coverage=art_data)
    vmmc    = sti.VMMC(coverage=vmmc_data)

    intvs      = make_interventions() + [art, vmmc]
    user_intvs = sc.tolist(kwargs.pop('interventions', []))
    sim_pars   = sc.mergedicts(default_sim_pars, kwargs.pop('sim_pars', None))

    return sti.Sim(
        demographics='zimbabwe',
        datafolder=input_dir,  # TODO: why the heck is this needed? Is it used at all??
        diseases=[hiv],
        networks=[network, ss.MaternalNet(), ss.BreastfeedingNet()],
        interventions=intvs + user_intvs,
        sim_pars=sim_pars,
        data=hiv_data,
        **kwargs
    )

# End original stisim Zimbabwe example model
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#


def run_sim(config: dict, input_dir: Path, output_dir: Path, verbose: bool = False):
    # first, configure the simulation
    seed = config['rand_seed']
    start = config['start_year']
    duration = config['dur']
    n_agents = config['n_agents']

    # ensure we have a clean output directory for use later
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    sim = make_sim(input_dir=input_dir, rand_seed=seed, n_agents=n_agents, start=start, dur=duration)

    # execute
    sim.run()

    # generate/write results
    if verbose:
        print(f"Writing results to {output_dir}")

    results = sim.results
    prevalence = sim.results.hiv.prevalence[:]  # TODO: why the "[:]" ???

    output_file = Path(output_dir, 'prevalence.csv')
    pd.DataFrame(prevalence).to_csv(output_file)
    # prevalence.to_csv(output_file)

    # TODO: route output to where the config file indicates


def load_config_file(filename):
    import json
    with open(filename, 'r') as f:
        config = json.load(f)
    validate_config(config=config)
    return config


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--config', dest='config_file', type=str, required=True,
                        help='JSON configuration file for the simulation (Required).')

    default = DEFAULT_ARGS['n_runs']
    parser.add_argument('-n', '--n-runs', dest='n_runs', type=int, default=default,
                        help=f'Number of stochastic simulation variations to run (Default: {default}).')

    default = DEFAULT_ARGS['input']
    parser.add_argument('-i', '--input', dest='input_dir', type=str, default=default,
                        help=f'Directory containing simulation input data files (Default: {default}).')

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
    args.config_file = Path(args.config_file).absolute()
    args.output_dir = Path(args.output_dir).absolute()
    args.input_dir = Path(args.input_dir).absolute()

    args.config = load_config_file(filename=args.config_file)
    return args


def validate_config(config: dict):
    required_entries = ['rand_seed', 'start_year', 'dur', 'n_agents']
    missing_entries = [entry for entry in required_entries if entry not in config]
    if len(missing_entries) > 0:
        missing_str = ", ".join(missing_entries)
        raise MissingConfigurationEntryException(f"Config is missing one or more required entries: {missing_str}")


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


def run_local(config: dict, rand_seeds: list[int], input_dir: Path, output_dir: Path, verbose: bool = False):
    # Simple, serial execution of each stochastic variant locally. Each variant gets a different random seed and a
    # different output directory

    # ensure we have a clean root output directory to contain the individual simulation results
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    for i, rand_seed in enumerate(rand_seeds):
        config['rand_seed'] = rand_seed
        sim_output_dir = Path(output_dir, f"seed-{rand_seed}")
        run_sim(config=config, input_dir=input_dir, output_dir=sim_output_dir, verbose=verbose)


def orchestrate(config: dict, input_dir: Path, output_dir: Path, n_seeds: int, platform: str, dry_run: bool = False,
                verbose: bool = False):
    # first, validate arguments whether they come from CLI or programmatic call
    # report noisy, descriptive configuration errors now
    validate_config(config=config)

    if n_seeds < 1:
        raise ValueError(f"number of runs must be greater than 0, not {n_seeds} .")

    if not (input_dir.exists() and input_dir.is_dir()):
        raise InvalidInputDirectory(f"Input directory does not exist or is not a directory: {input_dir}")

    if platform not in PLATFORMS:
        platforms_str = ", ".join(PLATFORMS)
        raise InvalidPlatformException(f'Unknown platform: {platform}. Available: {platforms_str}')

    if dry_run:
        return

    # if more than one stochastic variation was requested, we need separate config/outputs for each.
    rand_seeds = generate_seeds(n=n_seeds, base_seed=config['rand_seed'])

    # build and execute
    if platform == LOCAL:
        run_local(config=config, rand_seeds=rand_seeds, input_dir=input_dir, output_dir=output_dir,
                  verbose=verbose)


if __name__ == '__main__':
    # parse input arguments and load the provided config
    args = parse_args()

    orchestrate(config=args.config, input_dir=args.input_dir, output_dir=args.output_dir, n_seeds=args.n_runs,
                platform=args.platform, verbose=args.verbose)
