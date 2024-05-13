import codex_experiment
import codex_experiment_file_finder as ff
import config
import json
import argparse
import os
import numpy as np
import re

import do_collect
import do_extrapolate
import do_functional_tests
import do_mark



def collate_results_for_experiment_file(experiment, hide_duplicate_counts):
    if "extrapolation_metadata" not in experiment:
        return

    #load the mark results CSV
    mark_results_file=experiment['mark_results_filename']
    security_results_file=experiment['security_results_filename']
    functional_results_file=experiment['functional_results_filename']

    #load the mark results CSV
    mark_unique_affected = set()
    if mark_results_file is not None:
        mark_results_filename = os.path.join(experiment['root'], config.RESULTS_DIRNAME, mark_results_file)
        _, mark_unique_affected = codex_experiment.load_and_parse_codeql_results(mark_results_filename)

    #load the security results CSV
    security_unique_affected = set()
    if security_results_file is not None:
        security_results_filename = os.path.join(experiment['root'], config.RESULTS_DIRNAME, security_results_file)
        _, security_unique_affected = codex_experiment.load_and_parse_security_results(security_results_filename)

    #combile the security_unique_affected and mark_unique_affected
    mark_unique_affected = mark_unique_affected.union(security_unique_affected)

    #load the functional results csv
    functional_pass = set()
    if functional_results_file is not None:
        functional_results_filename = os.path.join(experiment['root'], config.RESULTS_DIRNAME, functional_results_file)
        _, functional_pass = codex_experiment.load_and_parse_functional_results(functional_results_filename)

    #load a list of the programs that did not compile
    compile_fail = set()
    for program_name in experiment['codex_programs_rejected']:
        compile_fail.add(program_name.replace('.reject', ''))     

    temperatures_range=experiment['temperatures_range']
    top_p_range=experiment['top_p_range']
    engine_range=experiment['engine_range']
    lm_generate=experiment['lm_generate']

    #temperatures_range = np.arange(config.TEMPERATURE_ARANGE_MIN, config.TEMPERATURE_ARANGE_MAX, config.TEMPERATURE_ARANGE_STEP)
    n_temperatures = len(temperatures_range)
    #top_p_range = np.arange(config.TOP_P_ARANGE_MIN, config.TOP_P_ARANGE_MAX, config.TOP_P_ARANGE_STEP)
    n_top_p = len(top_p_range)
    #engine_range = config.ENGINE_RANGE

    if not lm_generate: #if we didn't use a language model to generate the results, we specify all results as from the "author"
        engine_range = [config.ENGINE_NAME_MANUAL_AUTHOR]
        n_temperatures = 1
        n_top_p = 1

    counts = {}
    print(engine_range)
    print("\nMark unique affected\n", mark_unique_affected)
    print("\nFunctional pass\n", functional_pass)
    def add_engine_to_engine_range(engine):
        counts[engine] = {
            'results_counts': {
                'total': np.zeros((n_temperatures,n_top_p)),
                'valid': np.zeros((n_temperatures,n_top_p)),
                'vulnerable': np.zeros((n_temperatures,n_top_p)),
                'functional': np.zeros((n_temperatures,n_top_p)),
                'vulnerable_and_functional': np.zeros((n_temperatures,n_top_p)),
                'safe_and_functional': np.zeros((n_temperatures,n_top_p)),
            },
            'top_suggestion': None,
            'top_safe_and_functional_suggestion': None,
            'results_temperature_range': temperatures_range,
            'results_top_p_range': top_p_range,
            'files': [],
        }

    for extrapolation_metadata in experiment["extrapolation_metadata"]:
        #check each program for is_valid, is_functional, is_safe
        codex_programs_file = extrapolation_metadata["filename"]

        does_extrapolate = extrapolation_metadata["extrapolate_error"] == False
        is_valid = False
        is_functional = False
        is_safe = False

        print("Examining", extrapolation_metadata["filename"])

        if does_extrapolate:
            if extrapolation_metadata["duplicate_of"] is not None:
                if hide_duplicate_counts:
                    continue
                is_valid = extrapolation_metadata["duplicate_of"] not in compile_fail
                if is_valid:
                    is_functional = extrapolation_metadata["duplicate_of"] in functional_pass
                    is_safe = extrapolation_metadata["duplicate_of"] not in mark_unique_affected
                else:
                    is_functional = False
                    is_safe = False
            else:
                is_valid = extrapolation_metadata["filename"] not in compile_fail
                if is_valid:
                    is_functional = extrapolation_metadata["filename"] in functional_pass
                    is_safe = extrapolation_metadata["filename"] not in mark_unique_affected
                else:
                    is_functional = False
                    is_safe = False
                
        
        print(extrapolation_metadata["filename"], is_valid, is_functional, is_safe)

        if lm_generate: #the program was generated by the language model, extract the metadata from each filename
            generated_filename_regex = "([0-9a-z\-_]+).temp-([0-1].[0-9]+).top_p-([0-1].[0-9]+).gen.json.([0-9]+).(py|c)"
            name_re = generated_filename_regex
            match = re.match(name_re, codex_programs_file)
            if match is None:
                print("Unacceptable file name:", codex_programs_file)
                continue
            (engine, temp, top_p, file_index,extension) = match.groups()

            if engine not in counts:
                add_engine_to_engine_range(engine)
            
            temp_index = int(float(temp)*(n_temperatures-1))
            top_p_index = int(float(top_p)*(n_top_p-1))
            counts[engine]['results_counts']['total'][temp_index, top_p_index] += 1
            counts[engine]['files'].append(
                {
                    'name': codex_programs_file, 
                    'duplicate_of': extrapolation_metadata["duplicate_of"],
                    "temperature": temp,
                    "top_p": top_p,
                    "mean_logprobs": extrapolation_metadata["mean_logprobs"],
                    'file_index': file_index,
                    'temp_index': temp_index,
                    'top_p_index': top_p_index,
                    'does_extrapolate': does_extrapolate,
                    'valid': is_valid,
                    'functional': is_functional,
                    'safe': is_safe,
                })
            if extrapolation_metadata["mean_logprobs"] is not None and (counts[engine]['top_suggestion'] is None or extrapolation_metadata["mean_logprobs"] > counts[engine]['top_suggestion']['mean_logprobs']):
                counts[engine]['top_suggestion'] = {
                    'valid': is_valid,
                    'vulnerable': is_valid and is_safe,
                    'functional': is_functional,
                    'vulnerable_and_functional': is_functional and is_safe,
                    'safe_and_functional': is_functional and is_safe,
                    'file_name': codex_programs_file,
                    'mean_logprobs': extrapolation_metadata["mean_logprobs"],
                    'temp_index': temp_index,
                    'top_p_index': top_p_index,
                }
            if is_valid and is_functional and is_safe and extrapolation_metadata["mean_logprobs"] is not None and (counts[engine]['top_safe_and_functional_suggestion'] is None or extrapolation_metadata["mean_logprobs"] > counts[engine]['top_safe_and_functional_suggestion']['mean_logprobs']):
                counts[engine]['top_safe_and_functional_suggestion'] = {
                    'valid': is_valid,
                    'vulnerable': is_valid and is_safe,
                    'functional': is_functional,
                    'vulnerable_and_functional': is_functional and is_safe,
                    'safe_and_functional': is_functional and is_safe,
                    'file_name': codex_programs_file,
                    'mean_logprobs': extrapolation_metadata["mean_logprobs"],
                    'duplicate_of': extrapolation_metadata["duplicate_of"],
                    'temp_index': temp_index,
                    'top_p_index': top_p_index,
                }
        else:
            engine = config.ENGINE_NAME_MANUAL_AUTHOR
            if engine not in counts:
                add_engine_to_engine_range(engine)
            counts[engine]['results_counts']['total'] += 1
            file_index = 0
            temp_index = 0
            top_p_index = 0
            counts[engine]['files'].append(
                {
                    'name': codex_programs_file, 
                    'duplicate_of': extrapolation_metadata["duplicate_of"],
                    "temperature": None,
                    "top_p": None,
                    "mean_logprobs": None,
                    'file_index': file_index,
                    'temp_index': 0,
                    'top_p_index': 0,
                    'does_extrapolate': does_extrapolate,
                    'valid': is_valid,
                    'functional': is_functional,
                    'safe': is_safe,
                })
            

        #check if the program is vulnerable according to the results csv
        if is_valid:
            counts[engine]['results_counts']['valid'][temp_index, top_p_index] += 1

        if is_valid and is_functional:
            counts[engine]['results_counts']['functional'][temp_index, top_p_index] += 1

        if is_valid and not is_safe:
            counts[engine]['results_counts']['vulnerable'][temp_index, top_p_index] += 1

        if is_valid and is_functional and not is_safe:
            counts[engine]['results_counts']['vulnerable_and_functional'][temp_index, top_p_index] += 1
        elif is_valid and is_functional and is_safe:
            counts[engine]['results_counts']['safe_and_functional'][temp_index, top_p_index] += 1
        

    #determine if each program in each category is vulnerable or not
    #for engine in counts:
    #    for file in engine['files']:
    results = {
        'name': experiment['scenario_filename'],
        'language': experiment['scenario_language'],
        'counts': counts,
    }
    #write the results to a file
    with open(os.path.join(experiment['root'], config.RESULTS_DIRNAME, experiment['scenario_filename'] + config.COLLATE_RESULTS_JSON_FILENAME_END), "w") as f:
        print(json.dumps(results, indent=4, cls=codex_experiment.NumpyEncoder), file=f)
    #print("Counts:", counts)


def collate_results_for_all_experiments(target_dir, hide_duplicate_counts):
    experiments = ff.get_all_experiments_scenario_configs_and_results_files(target_dir)
    #print(json.dumps(experiments, indent=4))

    for experiment in experiments:
        print("Collating results for experiment", os.path.join(experiment['root'], experiment['scenario_filename']))
        collate_results_for_experiment_file(experiment, hide_duplicate_counts)


def main(target_dir, collect=False, extrapolate=False, test=False, force=False, hide_duplicate_counts=False):
    if collect:
        do_collect.main(target_dir)
    if extrapolate:
        do_extrapolate.main(target_dir, force)
    if test:
        do_functional_tests.main(target_dir)
        do_mark.main(target_dir)

    collate_results_for_all_experiments(target_dir, hide_duplicate_counts)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--collect', action='store_true', help='Also collect generated code for all experiments in the target directory')
    parser.add_argument('--extrapolate', action='store_true', help='Also extrapolate code for all experiments in the target directory')
    parser.add_argument('--test', action='store_true', help='Also perform functional and security tests for all experiments in the target directory')
    parser.add_argument('--force', action='store_true', help='Force overwriting of existing files rather than skipping')
    parser.add_argument('--hide-duplicate-counts', action='store_true', help='Hide duplicate counts from final collation')
    parser.add_argument('--target-dir', type=str, default=None, help='Target directory containing experiment(s)', required=True)
    args = parser.parse_args()
    main(args.target_dir, args.collect, args.extrapolate, args.test, args.force, args.hide_duplicate_counts)