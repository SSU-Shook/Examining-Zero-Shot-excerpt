import os
import re

from numpy import e
import numpy as np
import config
import json

def get_all_scenario_config_roots(search_dir):
    all_scenario_config_roots = []

    for root, dirs, files in os.walk(search_dir):
        if "__pycache__" in root:
            continue
        if config.CODEX_RESPONSES_DIRNAME_SUFFIX in root:
            continue
        if '.ignore' in root:
            continue

        #check if there is a file is called SCENARIO_CONFIG_FILENAME
        if config.SCENARIO_CONFIG_FILENAME in files:
            all_scenario_config_roots.append(root)

    return all_scenario_config_roots

def get_all_scenario_iterative_fix_instruction_roots(search_dir):
    get_all_scenario_iterative_fix_instruction_roots = []

    for root, dirs, files in os.walk(search_dir):
        if "__pycache__" in root:
            continue
        if config.CODEX_RESPONSES_DIRNAME_SUFFIX in root:
            continue
        if '.ignore' in root:
            continue

        #check if there is a file called ITERATIVE_FIX_INSTRUCTIONS_FILENAME
        if config.ITERATIVE_FIX_INSTRUCTIONS_FILENAME in files:
            get_all_scenario_iterative_fix_instruction_roots.append(root)

    return get_all_scenario_iterative_fix_instruction_roots

def get_all_experiment_configs(search_dir):
    all_scenario_config_roots = get_all_scenario_config_roots(search_dir = search_dir)
    experiments = []
    for scenario in all_scenario_config_roots:
        scenario_config = None
        senario_config_filename = os.path.join(scenario, config.SCENARIO_CONFIG_FILENAME)
        with open(senario_config_filename, "r") as f:
            scenario_config = json.load(f)
        
        if scenario_config is None:
            print("Error: Could not load scenario_config file:", senario_config_filename)
            return
        
        if 'resume_study' in scenario_config:
            resume_study = scenario_config['resume_study']
        else:
            resume_study = False

        if 'resume_names' in scenario_config:
            resume_names = scenario_config['resume_names']
        else:
            resume_names = []

        if resume_study == True and len(resume_names) > 1:
            for scenario_filename in list(scenario_config['scenarios']):
                #remove the scenario_filename from the list of scenarios
                scenario_config['scenarios'].remove(scenario_filename)

                for name in resume_names:
                    scenario_config['scenarios'].append(scenario_filename + "." + name)

            if 'scenarios_append' in scenario_config:
                for scenario_append_filename in list(scenario_config['scenarios_append']):
                    #remove the scenario_filename from the list of scenarios
                    scenario_config['scenarios_append'].remove(scenario_append_filename)

                    for name in resume_names:
                        scenario_config['scenarios_append'].append(scenario_append_filename + "." + name)

        #for each scenario check if there is a codex_responses dir in the experiment dir
        index = 0
        for scenario_filename in scenario_config['scenarios']:
            
            functional_test = None
            if 'functional_test' in scenario_config:
                functional_test = scenario_config['functional_test']

            iterative = False
            if 'iterative' in scenario_config:
                iterative = scenario_config['iterative']

            cwe_str = ""
            if 'cwe' in scenario_config:
                cwe_str = scenario_config['cwe']

            cve_str = ""
            if 'cve' in scenario_config:
                cve_str = scenario_config['cve']

            if 'temperatures_range' in scenario_config and scenario_config['temperatures_range'] is not None:
                temperatures_range = scenario_config['temperatures_range']
            else:
                temperatures_range = np.arange(config.TEMPERATURE_ARANGE_MIN, config.TEMPERATURE_ARANGE_MAX, config.TEMPERATURE_ARANGE_STEP)

            if 'top_p_range' in scenario_config and scenario_config['top_p_range'] is not None:
                top_p_range = scenario_config['top_p_range']
            else:
                top_p_range = np.arange(config.TOP_P_ARANGE_MIN, config.TOP_P_ARANGE_MAX, config.TOP_P_ARANGE_STEP)

            if 'engine_range' in scenario_config and scenario_config['engine_range'] is not None:
                engine_range = scenario_config['engine_range']
            else:
                engine_range = config.ENGINE_RANGE

            if 'estimated_tokens' in scenario_config:
                estimated_tokens = scenario_config['estimated_tokens']
            else:
                estimated_tokens = config.MAX_TOKENS_START_VALUE

            if 'stop_word' in scenario_config:
                stop_word = scenario_config['stop_word']
            else:
                stop_word = ""

            if 'lm_generate' in scenario_config:
                lm_generate = scenario_config['lm_generate']
            else:
                lm_generate = True

            if resume_study:
                resume_name = scenario_filename.split(".")[-1]
                original_filename = '.'.join(scenario_filename.split(".")[0:-1])
                if 'scenarios_append' in scenario_config:
                    original_append_filename = scenario_config['scenarios_append'][index]
                    original_scenario_append_filename = '.'.join(original_append_filename.split(".")[0:-1])
                else:
                    original_scenario_append_filename = None
                
                if 'scenarios_derived_from' in scenario_config:
                    original_scenario_derived_from_filename = scenario_config['scenarios_derived_from'][index]
                    original_scenario_derived_from_filename = '.'.join(original_scenario_derived_from_filename.split(".")[0:-1])
                else:
                    original_scenario_derived_from_filename = None
            else:
                resume_name = None
                original_filename = scenario_filename

                if 'scenarios_append' in scenario_config:
                    original_scenario_append_filename = scenario_config['scenarios_append'][index]
                else:
                    original_scenario_append_filename = None

                if 'scenarios_derived_from' in scenario_config:
                    original_scenario_derived_from_filename = scenario_config['scenarios_derived_from'][index]
                else:
                    original_scenario_derived_from_filename = None


            if 'check_ql' in scenario_config:
                check_ql = scenario_config['check_ql']
            else:
                check_ql = None

            if 'asan_scenario_buginfo' in scenario_config:
                asan_scenario_buginfo = scenario_config['asan_scenario_buginfo']
            else:
                asan_scenario_buginfo = None

            if 'external_buildinfo' in scenario_config:
                external_buildinfo = scenario_config['external_buildinfo']
            else:
                external_buildinfo = None
            
            if 'security_test' in scenario_config:
                security_test = scenario_config['security_test']
            else:
                security_test = None

            if 'iterative_prompts_range' in scenario_config:
                iterative_prompts_range = scenario_config['iterative_prompts_range']
            else:
                iterative_prompts_range = config.DEFAULT_ITERATIVE_PROMPTS_RANGE

            if 'prompt_name' in scenario_config:
                prompt_name = scenario_config['prompt_name']
            else:
                prompt_name = None

            if 'setup_tests' in scenario_config:
                setup_tests = scenario_config['setup_tests']
            else:
                setup_tests = None

            if 'cwe_rank' in scenario_config:
                cwe_rank = scenario_config['cwe_rank']
            else:
                cwe_rank = 0

            if 'ef' in scenario_config:
                ef = scenario_config['ef']
            else:
                ef = ""

            if 'ef_fixed' in scenario_config:
                ef_fixed = scenario_config['ef_fixed']
            else:
                ef_fixed = None

            if 'include_append' in scenario_config:
                include_append = scenario_config['include_append']
            else:
                include_append = False

            experiment = {
                'root':scenario, 
                'scenario_filename':scenario_filename,
                'original_filename':original_filename,
                'original_append_filename':original_scenario_append_filename,
                'original_scenario_derived_from':original_scenario_derived_from_filename,
                'resume_study': resume_study,
                'resume_name': resume_name,
                'scenario_language': scenario_config['language'],
                'cwe': cwe_str,
                'cve': cve_str,
                'ef': ef,
                'ef_fixed': ef_fixed,
                'cwe_rank': cwe_rank,
                'setup_tests': setup_tests,
                'security_test': security_test,
                'functional_test': functional_test,
                'iterative': iterative,
                'check_ql': check_ql,
                'asan_scenario_buginfo': asan_scenario_buginfo,
                'external_buildinfo': external_buildinfo,
                'lm_generate': lm_generate,
                'temperatures_range': temperatures_range,
                'top_p_range': top_p_range,
                'engine_range': engine_range,
                'estimated_tokens': estimated_tokens,
                'stop_word': stop_word,
                'iterative_prompts_range': iterative_prompts_range,
                'include_append': include_append,
                'prompt_name': prompt_name,
            }
            experiments.append(experiment)
            index += 1
    return experiments

def get_all_experiment_codex_generated_responses(search_dir):
    experiments_configs = get_all_experiment_configs(search_dir = search_dir)
    experiments = []
    for experiment in experiments_configs:
        codex_responses_dir = os.path.join(experiment['root'], config.CODEX_GEN_DIRNAME, experiment['scenario_filename']+config.CODEX_RESPONSES_DIRNAME_SUFFIX)
        
        #if not os.path.exists(codex_responses_dir):
        #    continue

        experiment['codex_responses'] = []
        #for each json file in the codex_responses dir
        if os.path.exists(codex_responses_dir):
            for file in os.listdir(codex_responses_dir):
                if file.endswith(config.JSON_EXTENSION) and ".mod.json" not in file:   
                    experiment['codex_responses'].append(file)

        experiments.append(experiment)

    return experiments

def get_all_experiments_scenario_configs_and_generated_codex_programs(search_dir):
    experiments = get_all_experiment_codex_generated_responses(search_dir = search_dir)
    for experiment in experiments:
        
        experiment['codex_programs'] = []
        experiment['codex_programs_rejected'] = []
        
        codex_programs_dir = os.path.join(experiment['root'], config.CODEX_GEN_DIRNAME, experiment['scenario_filename']+config.CODEX_PROGRAMS_DIRNAME_SUFFIX)
        if os.path.exists(codex_programs_dir):
            if os.path.exists(os.path.join(codex_programs_dir, config.EXTRAPOLATION_METADATA_FILENAME)):
                experiment['extrapolation_metadata'] = json.load(open(os.path.join(codex_programs_dir, config.EXTRAPOLATION_METADATA_FILENAME)))

            for file in os.listdir(codex_programs_dir):
                if experiment['scenario_language'] == 'python':
                    if "__pycache__" in file:
                        continue
                    if file.endswith(".py"):
                        experiment['codex_programs'].append(file)
                    if file.endswith(".py.reject"):
                        experiment['codex_programs_rejected'].append(file)
                elif experiment['scenario_language'] == 'c':
                    if file.endswith(".c"):
                        experiment['codex_programs'].append(file)
                    if file.endswith(".c.reject"):
                        experiment['codex_programs_rejected'].append(file)

    #sort experiments['codex_programs'] alphabetically
    for experiment in experiments:
        experiment['codex_programs'].sort()

    return experiments

def get_all_experiments_scenario_configs_and_results_files(search_dir):
    experiments = get_all_experiments_scenario_configs_and_generated_codex_programs(search_dir = search_dir)
    for experiment in experiments:

        scenario_filename = experiment['scenario_filename']
        # #check if the codex_programs dir also exists
        # codex_programs_dir = os.path.join(experiment['root'], config.CODEX_GEN_DIRNAME, scenario_filename+config.CODEX_PROGRAMS_DIRNAME_SUFFIX)
        # if not os.path.exists(codex_programs_dir):
        #     continue

        #check if a generated csv file exists
        mark_results_filename = None
        functional_results_filename = None
        security_results_filename = None

        #get all files in directory
        results_dir = os.path.join(experiment['root'], config.RESULTS_DIRNAME)
        if os.path.exists(results_dir):
            files = os.listdir(os.path.join(experiment['root'], config.RESULTS_DIRNAME))
            #sort the files
            files.sort()
        else:
            files = []
    
        for file in files:
            if scenario_filename in file and file.endswith(config.CODEQL_RESULTS_CSV_FILENAME_END):
                mark_results_filename = file
            if scenario_filename in file and file.endswith(config.FUNCTIONAL_RESULTS_CSV_FILENAME_END):
                functional_results_filename = file
            if scenario_filename in file and file.endswith(config.SECURITY_RESULTS_CSV_FILENAME_END):
                security_results_filename = file

        experiment['mark_results_filename'] = mark_results_filename
        experiment['functional_results_filename'] = functional_results_filename
        experiment['security_results_filename'] = security_results_filename
    return experiments

def get_all_experiments_collated_results_files(search_dir):
    experiments = get_all_experiments_scenario_configs_and_results_files(search_dir=search_dir)
    for experiment in experiments:
        #check if there is a results.json file in the experiment dir
        #get all files in directory
        files = os.listdir(os.path.join(experiment['root'], config.RESULTS_DIRNAME))
        #sort the files
        files.sort()

        for file in files:
            if experiment['scenario_filename'] in file and file.endswith(config.COLLATE_RESULTS_JSON_FILENAME_END):
                experiment['collated_results_filename'] = file
                
            if experiment['scenario_filename'] in file and file.endswith(config.ITERATIVE_RESULTS_JSON_FILENAME_END):
                experiment['iterative_collated_results_filename'] = file
                

    return experiments

if __name__ == "__main__":
    print("Do not run this file directly")