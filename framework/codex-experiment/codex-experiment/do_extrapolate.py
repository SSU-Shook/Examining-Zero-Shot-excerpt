import codex_experiment
import codex_experiment_file_finder as ff
import argparse
import os
import config
import shutil
import json

def extrapolate_codex_choices_for_all_experiments(target_dir, force=False, keep_duplicates=False, generate_mean_logprob_comments=False):
    experiment_generated = ff.get_all_experiment_codex_generated_responses(target_dir)
    #print(experiment_generated)
    for experiment in experiment_generated:
        print("Extrapolating experiment: %s" % os.path.join(experiment["root"], experiment["scenario_filename"]))
        scenario_config = None
        senario_config_filename = os.path.join(experiment['root'], config.SCENARIO_CONFIG_FILENAME)
        with open(senario_config_filename, "r") as f:
            scenario_config = json.load(f)
        
        if scenario_config is None:
            print("Error: Could not load scenario_config file:", senario_config_filename)
            return

        #for scenario_filename in scenario_config["scenarios"]:
        scenario_filename = experiment['scenario_filename']

        if scenario_config["language"] == "python":
            scenario_extension = "py"
        elif scenario_config["language"] == "c":
            scenario_extension = "c"
        else:
            raise "Error: Unknown language:" + scenario_config["language"]

        codex_programs_dir = os.path.join(experiment['root'], config.CODEX_GEN_DIRNAME, scenario_filename+config.CODEX_PROGRAMS_DIRNAME_SUFFIX)

        if experiment['lm_generate'] == True:
            #check if the codex_programs dir exists, if so, skip this experiment
            if os.path.exists(codex_programs_dir):
                if force:
                    #delete the directory and its contents
                    shutil.rmtree(codex_programs_dir)
            #         pass
            #     else:
            #         print("Skipping", codex_programs_dir, "(have files already been extrapolated? Use '--force' to overwrite all)")
            #         continue
            # else:
            print("Extrapolating codex choices for experiment", os.path.join(experiment['root'], " file: ", scenario_filename))

            
            codex_experiment.extrapolate_codex_choices_for_file(
                experiment_dir=experiment['root'], 
                experiment_file=scenario_filename, 
                experiment_extension=scenario_extension, 
                codex_responses_files=experiment['codex_responses'],
                lm_generated=True,
                force=force,
                keep_duplicates=keep_duplicates,
                external_buildinfo=experiment['external_buildinfo'],
                asan_scenario_buginfo=experiment['asan_scenario_buginfo'],
                experiment_derived_from_filename=experiment['original_scenario_derived_from'],
                experiment_prompt_name=experiment['prompt_name'],
                include_append=experiment['include_append'],
                generate_mean_logprob_comments=generate_mean_logprob_comments
            )
        else:
            #if the lm_generate is false then we don't need to extrapolate language model choices
            #instead we can just copy scenario.py into the codex_programs dir
            codex_experiment.extrapolate_codex_choices_for_file(
                experiment_dir=experiment['root'], 
                experiment_file=scenario_filename, 
                experiment_extension=scenario_extension, 
                codex_responses_files=[],
                lm_generated=False,
                force=force,
                keep_duplicates=keep_duplicates,
                external_buildinfo=experiment['external_buildinfo'],
                asan_scenario_buginfo=experiment['asan_scenario_buginfo'],
                include_append=experiment['include_append'],
                generate_mean_logprob_comments=generate_mean_logprob_comments
            )


def main(target_dir, force=False, keep_duplicates=False, generate_mean_logprob_comments=False):
    #check force flag from command line argument
    extrapolate_codex_choices_for_all_experiments(target_dir, force, keep_duplicates, generate_mean_logprob_comments)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--keep-duplicates', action='store_true')
    parser.add_argument('--generate-mean-logprob-comments', action='store_true')
    parser.add_argument('--target-dir', type=str, default=None, help='Target directory containing experiment(s)', required=True)
    args = parser.parse_args()
    main(args.target_dir, args.force, args.keep_duplicates, args.generate_mean_logprob_comments)