import codex_experiment
import codex_experiment_file_finder as ff
import os
import config
import datetime
import argparse

def perform_functional_tests_for_all_experiments(target_dir):
    scenario_configs = ff.get_all_experiments_scenario_configs_and_generated_codex_programs(target_dir)
    #print(experiments_scenario_configs_and_generated_codex_programs)
    for scenario_config in scenario_configs:
        print("Functional tests for experiment: %s" % os.path.join(scenario_config["root"], scenario_config["scenario_filename"]))
        # if scenario_config['iterative'] == False:
        #     continue
        experiment_dir = scenario_config['root']
        experiment_scenario = scenario_config['scenario_filename']

        #make sure it supports functional testing
        functional_test = scenario_config['functional_test']
        if functional_test is None:
            print("Skipping", experiment_dir, experiment_scenario, "(No functional test file provided)")
            continue

        #check if there is any file ending with config.CODEQL_RESULTS_CSV_FILENAME_END, if so, skip
        #check each file in the experiment dir
    
        
        print("Performing functional tests for experiment", scenario_config['root'])
        startup_time_str = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        scenario_extension = scenario_config['scenario_filename'].split('.')[-1]
        
        if scenario_config["setup_tests"] is not None:
            codex_experiment.setup_tests_for_experiment_file(
                experiment_dir=scenario_config['root'],
                experiment_file=scenario_config['scenario_filename'],
                experiment_extension=scenario_extension,
                codex_programs_files=scenario_config['codex_programs'],
                cwe_str=scenario_config['cwe'],
                setup_tests=scenario_config['setup_tests'],
                external_buildinfo=scenario_config['external_buildinfo'],
                asan_scenario_buginfo=scenario_config['asan_scenario_buginfo'],
                functional_setup=True
            )
        
        codex_experiment.perform_functional_tests_for_experiment_file(
            startup_time_str=startup_time_str,
            experiment_dir=scenario_config['root'],
            experiment_file=scenario_config['scenario_filename'],
            experiment_extension=scenario_extension,
            codex_programs_files=scenario_config['codex_programs'],
            cwe_str=scenario_config['cwe'],
            functional_test=functional_test,
            external_buildinfo=scenario_config['external_buildinfo'],
        )


def main(target_dir):
    perform_functional_tests_for_all_experiments(target_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--target-dir', type=str, default=None, help='Target directory containing experiment(s)', required=True)
    args = parser.parse_args()
    main(args.target_dir)