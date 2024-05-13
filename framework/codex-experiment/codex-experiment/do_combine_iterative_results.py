import codex_experiment
import codex_experiment_file_finder as ff
import json
import config
import os
import numpy as np
import argparse

def combine_iterative_results(target_dir):
    experiments = ff.get_all_experiments_scenario_configs_and_results_files(target_dir)
    #print(json.dumps(experiments, indent=4))

    

    for experiment in experiments:
        best_engine_results = {}
        
        print("Collating iterative results for experiment", experiment['root'], experiment['scenario_filename'])
        if experiment["iterative"] == False:
            continue
        
        # for each child iterative experiment, get the results files
        # and combine them into a single results file
        iterative_children_dir = os.path.join(experiment["root"], config.ITERATIVE_DIRNAME)
        child_experiments = ff.get_all_experiments_collated_results_files(search_dir=iterative_children_dir)
        
        totals_sums = {}
        totals_engines = {}

        for child_experiment in child_experiments:
            #get the prompt name
            prompt_name = child_experiment["prompt_name"]
            if prompt_name not in totals_sums:
                totals_sums[prompt_name] = {}
                totals_engines[prompt_name] = {}

            #get the final results file
            if not 'collated_results_filename' in child_experiment:
                continue
            collated_results_filename_full = os.path.join(child_experiment['root'], config.RESULTS_DIRNAME, child_experiment['collated_results_filename'])
            if not os.path.isfile(collated_results_filename_full):
                continue
            
            # load the results file
            with open(collated_results_filename_full, "r") as f:
                results = json.load(f)
                #for each result, add it to the totals
                for engine,engine_results in results["counts"].items():
                    if engine not in totals_engines[prompt_name]:
                        #totals_engines[prompt_name][engine] = {}

                        #get the heatmap shape
                        results_temperature_range = engine_results["results_temperature_range"]
                        results_top_p_range = engine_results["results_top_p_range"]
                        n_temperatures = len(results_temperature_range)
                        n_top_p = len(results_top_p_range)

                        #make the heatmap shape
                        totals_engines[prompt_name][engine] = {
                            'results_counts': {
                                'total': np.zeros((n_temperatures,n_top_p)),
                                'valid': np.zeros((n_temperatures,n_top_p)),
                                'vulnerable': np.zeros((n_temperatures,n_top_p)),
                                'functional': np.zeros((n_temperatures,n_top_p)),
                                'vulnerable_and_functional': np.zeros((n_temperatures,n_top_p)),
                                'safe_and_functional': np.zeros((n_temperatures,n_top_p)),
                            },
                            'top_suggestion': engine_results["top_suggestion"],
                            'top_safe_and_functional_suggestion': engine_results["top_safe_and_functional_suggestion"],
                            'results_temperature_range': results_temperature_range,
                            'results_top_p_range': results_top_p_range,
                        }

                        # see if this contains a new best result
                        if engine_results["top_safe_and_functional_suggestion"] is not None:
                            if engine not in best_engine_results:
                                best_engine_results[engine] = None
                            if best_engine_results[engine] is None or best_engine_results[engine]["mean_logprobs"] < engine_results["top_safe_and_functional_suggestion"]["mean_logprobs"]:
                                best_engine_results[engine] = engine_results["top_safe_and_functional_suggestion"]
                                best_engine_results[engine]["full_generated_file_name"] = os.path.join(child_experiment['root'], config.CODEX_GEN_DIRNAME, child_experiment['scenario_filename']+config.CODEX_PROGRAMS_DIRNAME_SUFFIX, engine_results["top_safe_and_functional_suggestion"]['file_name'])
                                filename = engine_results["top_safe_and_functional_suggestion"]['file_name']
                                if engine_results["top_safe_and_functional_suggestion"]["duplicate_of"] is not None and engine_results["top_safe_and_functional_suggestion"]["duplicate_of"] != "":
                                    filename = engine_results["top_safe_and_functional_suggestion"]["duplicate_of"]
                                best_engine_results[engine]["diff_command"] = "diff -u --color %s %s" % (os.path.join(experiment['root'], config.CODEX_GEN_DIRNAME, experiment['scenario_filename']+config.CODEX_PROGRAMS_DIRNAME_SUFFIX, experiment['scenario_filename']), os.path.join(child_experiment['root'], config.CODEX_GEN_DIRNAME, child_experiment['scenario_filename']+config.CODEX_PROGRAMS_DIRNAME_SUFFIX, filename))
                                
                    #add the results to the totals
                    for key,value in engine_results["results_counts"].items():
                        # key will now be something like 'total' or 'vulnerable' etc
                        totals_engines[prompt_name][engine]["results_counts"][key] += value

                    # for key,value in engine_results["results_counts"].items():
                    #     if key not in totals_sums[prompt_name]:
                    #         totals_sums[prompt_name][key] = 0
                    #     if key not in totals_engines[prompt_name][engine]:
                    #         totals_engines[prompt_name][engine][key] = 0
                    #     #print(key, value)
                    #     for rows in value:
                    #         for column in rows:
                    #             totals_engines[prompt_name][engine][key] += column
                        
            
        # write the combined results file
        collated_results_filename_full = os.path.join(experiment["root"], config.RESULTS_DIRNAME, experiment["scenario_filename"]+config.ITERATIVE_RESULTS_JSON_FILENAME_END)
        with open(collated_results_filename_full, "w") as f:
            json.dump(totals_engines, f, indent=4, cls=codex_experiment.NumpyEncoder)


        # write the best results file
        best_results_filename_full = os.path.join(experiment["root"], config.RESULTS_DIRNAME, experiment["scenario_filename"]+config.BEST_ITERATIVE_RESULTS_JSON_FILENAME_END)
        with open(best_results_filename_full, "w") as f:
            json.dump(best_engine_results, f, indent=4, cls=codex_experiment.NumpyEncoder)
        
                

def main(target_dir):
    combine_iterative_results(target_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--target-dir', type=str, default=None, help='Target directory containing experiment(s)', required=True)
    args = parser.parse_args()
    main(args.target_dir)