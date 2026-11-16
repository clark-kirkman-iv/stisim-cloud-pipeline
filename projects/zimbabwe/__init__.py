import numpy as np
import pandas as pd
import sciris as sc
import starsim as ss
import stisim as sti

from pathlib import Path


FRAME_DIR = Path(__file__).parent
INPUT_DIR = Path(FRAME_DIR, "input")

BASE_SEED = 420
DEFAULT_PARAMETERS = {
    "rand_seed": BASE_SEED,
    "start": 1990,
    "dur": 5,
    "n_agents": 5000,
    "age_scale": 1000
}

"""
Zimbabwe HIV model with calibrated parameters and UNAIDS comparison data.

This example demonstrates how to build a data-driven HIV simulation:
- Initial prevalence from CSV by risk group/sex/SW status
- Condom use data by partnership type over time
- ART and VMMC coverage from national program data
- Testing interventions with FSW-targeted, general population, and low-CD4 strategies
- UNAIDS estimates attached to sim.data for plot overlay
"""

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


def make_sim(parameters: dict = None, seed: int = None):
    """
    Create a Zimbabwe HIV simulation with calibrated parameters.

    Flat ``**parameters`` are auto-routed via ``sti.route_pars`` — pass any
    network par (e.g. ``debut_f=18``), HIV par (``beta_m2f=0.04``), or sim
    par (``n_agents=5000``) directly, they will override the run_config. User values override the calibrated
    defaults baked into this builder.
    """
    parameters = {} if parameters is None else parameters
    all_parameters = {**DEFAULT_PARAMETERS, **parameters}
    if seed is not None:
        all_parameters['rand_seed'] = seed

    routed = sti.route_pars(all_parameters)
    nw_pars = sc.mergedicts(default_nw_pars, routed.nw)
    hiv_pars = sc.mergedicts(default_hiv_pars, routed.sti)
    for k in (*routed.nw, *routed.sti): all_parameters.pop(k)  # consumed here

    # load input data files
    data_file = Path(INPUT_DIR, 'init_prev_hiv.csv')
    init_prev = pd.read_csv(data_file)

    data_file = Path(INPUT_DIR, 'condom_use.csv')
    condom_data = pd.read_csv(data_file)

    data_file = Path(INPUT_DIR, 'art_coverage.csv')
    art_data = pd.read_csv(data_file).set_index('year')

    data_file = Path(INPUT_DIR, 'vmmc_coverage.csv')
    vmmc_data = pd.read_csv(data_file).set_index('year')

    data_file = Path(INPUT_DIR, 'zimbabwe_hiv_data.csv')
    hiv_data = pd.read_csv(data_file)

    hiv = sti.HIV(init_prev_data=init_prev, **hiv_pars)
    network = sti.StructuredSexual(condom_data=condom_data, **nw_pars)
    art = sti.ART(coverage=art_data)
    vmmc = sti.VMMC(coverage=vmmc_data)

    intvs = make_interventions() + [art, vmmc]
    user_intvs = sc.tolist(all_parameters.pop('interventions', []))

    return sti.Sim(
        demographics='zimbabwe',
        datafolder=INPUT_DIR,  # if datafolder not provided, stisim will attempt to download files from UN WPP
        diseases=[hiv],
        networks=[network, ss.MaternalNet(), ss.BreastfeedingNet()],
        interventions=intvs + user_intvs,
        data=hiv_data,
        **all_parameters
    )
