'''Exectue set of functions for each epoch
'''
from argparse import ArgumentParser
from collections import namedtuple
from logging import DEBUG, INFO, Formatter, StreamHandler, getLogger
from signal import SIGUSR1, SIGUSR2, signal
from subprocess import PIPE, run
from sys import exit, stdout

from src.analysis import (canonical_coherence_by_ripple_type,
                          coherence_by_ripple_type,
                          decode_ripple_clusterless,
                          detect_epoch_ripples,
                          ripple_triggered_canonical_coherence,
                          ripple_triggered_coherence)
from src.data_processing import (save_ripple_info, get_epoch_lfps,
                                 save_multitaper_parameters,
                                 save_tetrode_pair_info)

sampling_frequency = 1500
Animal = namedtuple('Animal', {'directory', 'short_name'})
animals = {
    'HPa': Animal(directory='HPa_direct', short_name='HPa'),
    'HPb': Animal(directory='HPb_direct', short_name='HPb'),
    'HPc': Animal(directory='HPc_direct', short_name='HPc')
}
ripple_frequency = dict(
    sampling_frequency=sampling_frequency,
    time_window_duration=0.020,
    time_window_step=0.020,
    desired_frequencies=(100, 300),
    time_halfbandwidth_product=1,
    window_of_interest=(-0.420, 0.400)
)
gamma_frequency_highTimeRes = dict(
    sampling_frequency=sampling_frequency,
    time_window_duration=0.050,
    time_window_step=0.050,
    desired_frequencies=(12, 125),
    time_halfbandwidth_product=1,
    window_of_interest=(-0.450, 0.400)
)
gamma_frequency_medFreqRes1 = dict(
    sampling_frequency=sampling_frequency,
    time_window_duration=0.100,
    time_window_step=0.100,
    desired_frequencies=(12, 125),
    time_halfbandwidth_product=1,
    window_of_interest=(-0.500, 0.400)
)
gamma_frequency_medFreqRes2 = dict(
    sampling_frequency=sampling_frequency,
    time_window_duration=0.200,
    time_window_step=0.200,
    desired_frequencies=(12, 125),
    time_halfbandwidth_product=1,
    window_of_interest=(-0.600, 0.400)
)
gamma_frequency_highFreqRes = dict(
    sampling_frequency=sampling_frequency,
    time_window_duration=0.400,
    time_window_step=0.400,
    desired_frequencies=(12, 125),
    time_halfbandwidth_product=1,
    window_of_interest=(-0.800, 0.400)
)
low_frequency_highTimeRes = dict(
    sampling_frequency=sampling_frequency,
    time_window_duration=0.100,
    time_window_step=0.100,
    desired_frequencies=(0, 30),
    time_halfbandwidth_product=1,
    window_of_interest=(-0.500, 0.400)
)
low_frequency_medFreqRes = dict(
    sampling_frequency=sampling_frequency,
    time_window_duration=0.250,
    time_window_step=0.250,
    desired_frequencies=(0, 30),
    time_halfbandwidth_product=1,
    window_of_interest=(-0.750, 0.250)
)
low_frequency_highFreqRes = dict(
    sampling_frequency=sampling_frequency,
    time_window_duration=0.500,
    time_window_step=0.500,
    desired_frequencies=(0, 30),
    time_halfbandwidth_product=1,
    window_of_interest=(-1.00, 0.500)
)
multitaper_parameters = {
    'gamma_frequency_medFreqRes1': gamma_frequency_medFreqRes1,
    'gamma_frequency_medFreqRes2': gamma_frequency_medFreqRes2,
    'gamma_frequency_highTimeRes': gamma_frequency_highTimeRes,
    'gamma_frequency_highFreqRes': gamma_frequency_highFreqRes,
    'low_frequencies_highTimeRes': low_frequency_highTimeRes,
    'low_frequencies_medFreqRes': low_frequency_medFreqRes,
    'low_frequencies_highFreqRes': low_frequency_highFreqRes,
    'ripple_frequencies': ripple_frequency
}
ripple_covariates = ['session_time', 'ripple_trajectory',
                     'ripple_direction']


def estimate_ripple_coherence(epoch_index):
    ripple_times = detect_epoch_ripples(
        epoch_index, animals, sampling_frequency=sampling_frequency)
    lfps, tetrode_info = get_epoch_lfps(epoch_index, animals)
    save_tetrode_pair_info(epoch_index, tetrode_info)

    # Compare before ripple to after ripple
    for parameters_name, parameters in multitaper_parameters.items():
        ripple_triggered_coherence(
            lfps, ripple_times,
            multitaper_parameter_name=parameters_name,
            multitaper_params=parameters)
        ripple_triggered_canonical_coherence(
            lfps, epoch_index, tetrode_info, ripple_times,
            multitaper_parameter_name=parameters_name,
            multitaper_params=parameters)
        save_multitaper_parameters(
            epoch_index, parameters_name, parameters)

    # Compare different types of ripples
    ripple_info = decode_ripple_clusterless(
        epoch_index, animals, ripple_times)[0]
    save_ripple_info(epoch_index, ripple_info)

    for covariate in ripple_covariates:
        for parameters_name, parameters in multitaper_parameters.items():
            coherence_by_ripple_type(
                lfps, ripple_info, covariate,
                multitaper_parameter_name=parameters_name,
                multitaper_params=parameters)
            canonical_coherence_by_ripple_type(
                lfps, epoch_index, tetrode_info, ripple_info, covariate,
                multitaper_parameter_name=parameters_name,
                multitaper_params=parameters)


def get_command_line_arguments():
    parser = ArgumentParser()
    parser.add_argument('Animal', type=str, help='Short name of animal')
    parser.add_argument('Day', type=int, help='Day of recording session')
    parser.add_argument('Epoch', type=int,
                        help='Epoch number of recording session')
    parser.add_argument(
        '-d', '--debug',
        help='More verbose output for debugging',
        action='store_const',
        dest='log_level',
        const=DEBUG,
        default=INFO,
    )
    return parser.parse_args()


def get_logger():
    formatter = Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = StreamHandler(stream=stdout)
    handler.setFormatter(formatter)
    logger = getLogger()
    logger.addHandler(handler)
    return logger


def main():
    args = get_command_line_arguments()
    logger = get_logger()
    logger.setLevel(args.log_level)

    def _signal_handler(signal_code, frame):
        logger.error('***Process killed with signal {signal}***'.format(
            signal=signal_code))
        exit()

    for code in [SIGUSR1, SIGUSR2]:
        signal(code, _signal_handler)

    epoch_index = (args.Animal, args.Day, args.Epoch)
    logger.info(
        'Processing epoch: Animal {0}, Day {1}, Epoch #{2}...'.format(
            *epoch_index))
    git_hash = run(['git', 'rev-parse', 'HEAD'],
                   stdout=PIPE, universal_newlines=True).stdout
    logger.info('Git Hash: {git_hash}'.format(git_hash=git_hash.rstrip()))

    estimate_ripple_coherence(epoch_index)

    logger.info('Finished Processing')

if __name__ == '__main__':
    exit(main())
