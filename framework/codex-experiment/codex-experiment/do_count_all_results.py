import codex_experiment
import codex_experiment_file_finder as ff
import json
import config
import os
import numpy as np
import argparse
import csv

def count_all_results(target_dir):
    experiments = ff.get_all_experiments_scenario_configs_and_results_files(target_dir)
    #print(json.dumps(experiments, indent=4))

    results = []
    results_headings = [
        "scenario_filename",    #the name of the scenario
        "experiment_root",      #root directory of the scenario
        "filename",             #generated file name
        "duplicate_of",         #if it is a duplicate, the filename of the original
        "lm_generated",         #was it generated 
        "engine",               #the engine used for generation ('manual' if author)
        "prompt_type_name",     #the prompt used for generation
        "temperature",          #the temperature used in generation
        "top_p",                #the top_p used in generation
        "does_extrapolate",     #true/false if it extrapolates
        "is_valid",             #true/false if it compiles
        "is_functional",        #true/false if it passes the functional test
        "is_safe",              #true/false if it passes the security test (codeql or manual)
    ]            


    for experiment in experiments:
        if "extrapolation_metadata" not in experiment:
            continue

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
            compile_fail.add(program_name)
        
        for extrapolation_metadata in experiment["extrapolation_metadata"]:
            does_extrapolate = (extrapolation_metadata["extrapolate_error"] == False)
            #check each program for is_valid, is_functional, is_safe
            if does_extrapolate:
                if extrapolation_metadata["duplicate_of"] is not None:
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

            result = {
                "scenario_filename": experiment['scenario_filename'],
                "experiment_root": experiment['root'],
                "filename": extrapolation_metadata['filename'],
                "duplicate_of": extrapolation_metadata['duplicate_of'],
                "lm_generated": experiment['lm_generate'],
                "engine": extrapolation_metadata['engine'],
                "prompt_type_name": experiment['prompt_name'],
                "temperature": extrapolation_metadata['temperature'],
                "top_p": extrapolation_metadata['top_p'],
                "does_extrapolate": does_extrapolate,
                "is_valid": is_valid,
                "is_functional": is_functional,
                "is_safe": is_safe,
            }

            results.append(result)
        
    # write the combined results file to a CSV
    results_filename = os.path.join(target_dir, config.FINAL_RESULTS_FILENAME)
    with open(results_filename, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=results_headings)
        writer.writeheader()
        for result in results:
            writer.writerow(result)
    print("Wrote results to {}".format(results_filename))

def main(target_dir):
    count_all_results(target_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--target-dir', type=str, default=None, help='Target directory containing experiment(s)', required=True)
    args = parser.parse_args()
    main(args.target_dir)