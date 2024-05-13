import codex_experiment
import codex_experiment_file_finder as ff
import os
import config
import json
import datetime
import argparse

def perform_iterative_generation_for_all_experiments(target_dir, force=False):
    experiments = ff.get_all_experiments_scenario_configs_and_results_files(target_dir)
    
    #iterative_fix_instructions = []
    
    for experiment in experiments:
        #make sure it is iterative
        
        if 'iterative' not in experiment:
            continue
        if experiment['iterative'] == False:
            continue

        iterative_dir = os.path.join(experiment['root'], config.ITERATIVE_DIRNAME)
        #check if the iterative_dir exists
        if not os.path.isdir(iterative_dir):
            os.mkdir(iterative_dir)
        elif not force:
            print("Skipping " + experiment['root'] + ", Iterative dir already exists (run with force)")
            continue
        print("Generating iterative instructions for " + experiment['root'])

        codex_programs_dir = os.path.join(experiment['root'], config.CODEX_GEN_DIRNAME, experiment['scenario_filename']+config.CODEX_PROGRAMS_DIRNAME_SUFFIX)

        iterative_fix_instruction = {
            'original_dir': experiment['root'],
            'file_dir': codex_programs_dir,
            'iterative_dir': iterative_dir,
            'external_buildinfo': experiment['external_buildinfo'],
            'setup_tests': experiment['setup_tests'],
            'security_test': experiment['security_test'],
            'functional_test': experiment['functional_test'],
            'root_dir': experiment['root'],
            'language': experiment['scenario_language'],
            'temperatures_range': experiment['temperatures_range'],
            'top_p_range': experiment['top_p_range'],
            'engine_range': experiment['engine_range'],
            'estimated_tokens': experiment['estimated_tokens'],
            'cwe': experiment['cwe'],
            'cve': experiment['cve'],
            'check_ql': experiment['check_ql'],
            'prompts_range': experiment['iterative_prompts_range'],
            'stop_word': experiment['stop_word'],
            'include_append': experiment['include_append'],

            'asan_scenario_buginfo': None,
            'vulnerabilities': None,
        }

        #check if it has asan_scenario_buginfo
        if experiment['asan_scenario_buginfo'] is not None:
            iterative_fix_instruction['asan_scenario_buginfo'] = experiment['asan_scenario_buginfo']

        else:
            #check if the mark_results_filename exists
            if 'mark_results_filename' not in experiment or experiment['mark_results_filename'] is None:
                continue
            mark_results_filename = os.path.join(experiment['root'], config.RESULTS_DIRNAME, experiment['mark_results_filename'])
            if not os.path.isfile(mark_results_filename):
                print("Mark results file not found: " + mark_results_filename)
                continue

            #check if the functional_results_filename exists
            if experiment['functional_results_filename'] is None:
                continue
            functional_results_filename = os.path.join(experiment['root'], config.RESULTS_DIRNAME, experiment['functional_results_filename'])
            if not os.path.isfile(functional_results_filename):
                print("Functional results file not found: " + functional_results_filename)
                continue
        
        
            #load the codex responses
            codeql_scenario_results, mark_unique_affected = codex_experiment.load_and_parse_codeql_results(mark_results_filename)

            #load the functional responses
            functional_scenario_results, functional_unique_pass = codex_experiment.load_and_parse_functional_results(functional_results_filename)

            iterative_fix_instruction['vulnerabilities'] = codeql_scenario_results

        # #for each vulnerability produce the iterative fix instruction
        
        # for vulnerability in codeql_scenario_results:
        #     #ensure that the vulnerability is present in the functional results
        #     vulnerable_filename = vulnerability['filename']
        #     # if vulnerable_filename not in functional_unique_pass:
        #     #     print("Vulnerable filename %s not in functional set, skipping" % vulnerable_filename)
        #     #     continue
            
        #     codex_programs_dir = os.path.join(experiment['root'], config.CODEX_GEN_DIRNAME, experiment['scenario_filename']+config.CODEX_PROGRAMS_DIRNAME_SUFFIX)

        #     iterative_fix_instruction = {
        #         'filename': vulnerable_filename,
        #         'file_dir': codex_programs_dir,
        #         'iterative_dir': iterative_dir,
        #         'external_buildinfo': experiment['external_buildinfo'],
        #         'asan_scenario_buginfo': experiment['asan_buginfo'],
        #         'security_test': experiment['security_test'],
        #         'functional_test': experiment['functional_test'],
        #         'root_dir': experiment['root'],
        #         'language': experiment['scenario_language'],
        #         'temperatures_range': experiment['temperatures_range'],
        #         'top_p_range': experiment['top_p_range'],
        #         'engine_range': experiment['engine_range'],
        #         'estimated_tokens': experiment['estimated_tokens'],
        #         'cwe': experiment['cwe'],
        #         'cve': experiment['cve'],
        #         'check_ql': experiment['check_ql'],
        #         'vulnerability': vulnerability,
        #     }
        #iterative_fix_instructions.append(iterative_fix_instruction)

        #write the iterative fix instructions to a file
        iterative_fix_instructions_filename = os.path.join(iterative_dir, config.ITERATIVE_FIX_INSTRUCTIONS_FILENAME)
        with open(iterative_fix_instructions_filename, 'w') as f:
            f.write(json.dumps(iterative_fix_instruction, indent=4, cls=codex_experiment.NumpyEncoder))




def main(target_dir, force=False):
    perform_iterative_generation_for_all_experiments(target_dir, force)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--target-dir', type=str, default=None, help='Target directory containing experiment(s)', required=True)
    args = parser.parse_args()
    main(args.target_dir, args.force)