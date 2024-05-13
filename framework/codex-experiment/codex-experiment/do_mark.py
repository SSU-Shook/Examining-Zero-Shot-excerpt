import codex_experiment
import codex_experiment_file_finder as ff
import os
import config
import datetime
import json
import argparse

def mark_codex_responses_for_all_experiments(target_dir):
    scenarios = ff.get_all_experiments_scenario_configs_and_generated_codex_programs(target_dir)
    
    for scenario in scenarios:
        print("Security/codeql tests for experiment: %s" % os.path.join(scenario["root"], scenario["scenario_filename"]))
        # if scenario['iterative'] == False:
        #     continue
        scenario_config = None
        senario_config_filename = os.path.join(scenario['root'], config.SCENARIO_CONFIG_FILENAME)
        with open(senario_config_filename, "r") as f:
            scenario_config = json.load(f)
        
        if scenario_config is None:
            print("Error: Could not load scenario_config file:", senario_config_filename)
            return

        #for scenario_filename in scenario_config["scenarios"]:
        scenario_filename = scenario["scenario_filename"]
        
        #check if there is any file ending with config.CODEQL_RESULTS_CSV_FILENAME_END, if so, skip
        #check each file in the experiment dir
        experiment_dir = scenario['root']
        skip = False
        results_dir = os.path.join(experiment_dir, config.RESULTS_DIRNAME)
        
        print("Marking codex responses for experiment", scenario['root'], "scenario", scenario_filename)
        startup_time_str = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        if scenario_config["language"] == "python":
            scenario_extension = "py"
        elif scenario_config["language"] == "c":
            scenario_extension = "c"
        else:
            print("Error: Unknown language:", scenario_config["language"])
            return

        if "setup_tests" in scenario_config and scenario_config["setup_tests"] is not None:
            codex_experiment.setup_tests_for_experiment_file(
                experiment_dir=scenario['root'],
                experiment_file=scenario['scenario_filename'],
                experiment_extension=scenario_extension,
                codex_programs_files=scenario['codex_programs'],
                cwe_str=scenario['cwe'],
                setup_tests=scenario['setup_tests'],
                external_buildinfo=scenario['external_buildinfo'],
                asan_scenario_buginfo=scenario_config['asan_scenario_buginfo'],
                security_setup=True
            )

        if 'asan_scenario_buginfo' not in scenario_config or scenario_config['asan_scenario_buginfo'] is None:
            #check if results dir exists
            if os.path.exists(results_dir):
                for file in os.listdir(os.path.join(experiment_dir, config.RESULTS_DIRNAME)):
                    if scenario_filename in file and file.endswith(config.CODEQL_RESULTS_CSV_FILENAME_END):
                        print("Skipping", experiment_dir, "(the file", file, "already exists - have results already been collected?)")
                        skip = True
                        break
                    if scenario_filename in file and file.endswith(config.SECURITY_RESULTS_CSV_FILENAME_END):
                        print("Skipping", experiment_dir, "(the file", file, "already exists - have results already been collected?)")
                        skip = True
                        break
            if skip:
                continue
            codex_experiment.mark_codex_responses_for_experiment_file(
                startup_time_str=startup_time_str,
                experiment_dir=scenario['root'],
                experiment_file=scenario_filename,
                experiment_extension=scenario_extension,
                scenario_config_file=senario_config_filename,
            )
        else:
            codex_experiment.perform_asan_security_tests_for_experiment_file(
                startup_time_str=startup_time_str,
                experiment_dir=scenario['root'],
                experiment_file=scenario['scenario_filename'],
                experiment_extension=scenario_extension,
                codex_programs_files=scenario['codex_programs'],
                cwe_str=scenario['cwe'],
                security_test=scenario['security_test'],
                external_buildinfo=scenario['external_buildinfo'],
                asan_scenario_buginfo=scenario_config['asan_scenario_buginfo'],
            )

def main(target_dir):
    mark_codex_responses_for_all_experiments(target_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--target-dir', type=str, default=None, help='Target directory containing experiment(s)', required=True)
    args = parser.parse_args()
    main(args.target_dir)