"""
Zimbabwe HIV model with calibrated parameters and UNAIDS comparison data.

This example demonstrates how to build a data-driven HIV simulation:
- Initial prevalence from CSV by risk group/sex/SW status
- Condom use data by partnership type over time
- ART and VMMC coverage from national program data
- Testing interventions with FSW-targeted, general population, and low-CD4 strategies
- UNAIDS estimates attached to sim.data for plot overlay
"""
import os
import shutil
from os.path import exists
from pathlib import Path

import numpy as np
import pandas as pd
import sciris as sc
import starsim as ss
import stisim as sti

DEFAULT_ARGS = {
    'input': Path('input'),
    'output': Path('output')
}

class MissingConfigurationException(Exception): pass

#
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
#

# TODO: make_interventions, make_sim, and all their defaults (here) should be in a separate file, e.g. zimbabwe.py,
#   which is essentially a standard module for loading/using with this harness.

# Sim settings
default_sim_pars = dict(start=1990, stop=2025, age_scale=1000)

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
#
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#


def run_sim(config: dict, input_dir: Path = DEFAULT_ARGS['input'], output_dir: Path = DEFAULT_ARGS['output'],
            verbose: bool = False):
    # first, configure the simulation
    seed = config['rand_seed']
    start = config['start_year']
    duration = config['duration']
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


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--config', dest='config_file', type=str, required=True,
                        help='JSON configuration file for the simulation (Required).')

    default = DEFAULT_ARGS['input']
    parser.add_argument('-i', '--input', dest='input_dir', type=str, default=default,
                        help=f'Directory containing simulation input data files (Default: {default}).')

    default = DEFAULT_ARGS['output']
    parser.add_argument('-o', '--output', dest='output_dir', type=str, default=default,
                        help=f'Output directory for simulation results (Default: {default}).')

    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        help='Print more information during processing (Default: False).')

    args = parser.parse_args()
    args.config_file = Path(args.config_file).absolute()
    args.output_dir = Path(args.output_dir).absolute()
    return args


def verify_config(config: dict):
    required_entries = ['rand_seed', 'start_year', 'duration', 'n_agents']
    missing_entries = [entry for entry in config if entry not in required_entries]
    if len(missing_entries) > 0:
        missing_entries_str = ", ".join(missing_entries)
        raise MissingConfigurationException(f"Config is missing one or more required entries: {missing_entries_str}")


def load_config_file(filename):
    import json
    with open(filename, 'r') as f:
        config = json.load(f)

    # report noisy, descriptive configuration errors now
    verify_config(config=config)
    return config


if __name__ == '__main__':
    # parse input arguments and load the provided config
    args = parse_args()
    config = load_config_file(filename=args.config_file)

    # build and execute
    run_sim(config=config, input_dir=args.input_dir, output_dir=args.output_dir, verbose=args.verbose)
