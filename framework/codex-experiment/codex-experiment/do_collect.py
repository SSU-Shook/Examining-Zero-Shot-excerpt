import codex_experiment
import codex_experiment_file_finder as ff
import codex_experiment_gen_programs
import os
import config
import datetime
import json
import argparse

def generate_codex_choices_for_all_experiments(target_dir, skip_engines = []):
    experiments = ff.get_all_experiment_configs(target_dir)
    for experiment in experiments:
        print("Collecting for experiment: %s" % os.path.join(experiment["root"], experiment["scenario_filename"]))
        
        if experiment['lm_generate'] != True:
            continue

        scenario_config = None
        senario_config_filename = os.path.join(experiment['root'], config.SCENARIO_CONFIG_FILENAME)
        with open(senario_config_filename, "r") as f:
            scenario_config = json.load(f)
        
        if scenario_config is None:
            print("Error: Could not load scenario_config file:", senario_config_filename)
            return

        #check if the codex_responses dir exists, if so, skip this experiment
        if experiment['scenario_language'] == 'python':
            experiment_extension = 'py'
        elif experiment['scenario_language'] == 'c':
            experiment_extension = 'c'
        else:
            raise Exception("Unknown scenario language:", experiment['scenario_language'])

        startup_time_str = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        

        #experiment_dir=experiment['root']
        #experiment_file=scenario_filename

        #load the contents of the file
        file_path = os.path.join(experiment['root'], experiment['original_filename'])
        with open(file_path, "r") as f:
            contents = f.read()

        #load the contents of the append file if available
        append_contents = None
        if experiment['original_append_filename'] is not None:
            append_file_path = os.path.join(experiment['root'], experiment['original_append_filename'])
            with open(append_file_path, "r") as f:
                append_contents = f.read()
        
        #if resume_study is true, then we need to replace the placeholders with the resume names and
        #generate contents for each resume name
        if experiment['resume_study']:
            contents = contents.replace(config.RESUME_NAME_PLACEHOLDER, experiment['resume_name'])
            #experiment_filename = experiment_file + "." + resume_name
            
        #    codex_responses_dir = os.path.join(scenario, config.CODEX_GEN_DIRNAME, experiment_filename+config.CODEX_RESPONSES_DIRNAME_SUFFIX)
        #else:

  
        
        codex_responses_dir = os.path.join(experiment['root'], config.CODEX_GEN_DIRNAME, experiment['scenario_filename']+config.CODEX_RESPONSES_DIRNAME_SUFFIX)
        
        # if os.path.exists(codex_responses_dir):
        #     print("Skipping", codex_responses_dir, "(have results already been collected?)")
        #     continue
        # else:
        print("Generating codex_responses for", experiment['scenario_filename'])
        codex_experiment_gen_programs.create_codex_choices_json_for_contents(
            experiment['root'], 
            contents, 
            append_contents,
            experiment['scenario_filename'], 
            experiment_extension, 
            experiment['estimated_tokens'], 
            experiment['temperatures_range'],
            experiment['top_p_range'],
            experiment['engine_range'],
            experiment['stop_word'],
            skip_engines = skip_engines,
        )


def main(target_dir = None, skip_engines = []):
    if target_dir is None:
        print("No target_dir specified, exiting")
    generate_codex_choices_for_all_experiments(target_dir, skip_engines)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    #argument for string directory
    parser.add_argument('--target-dir', type=str, default=None, help='Target directory containing experiment(s)', required=True)
    #argument for array of engine names to skip
    parser.add_argument('--skip-engines', nargs='+', default=[], help='Array of engine names to skip', required=False)
    args = parser.parse_args()
    main(args.target_dir, args.skip_engines)