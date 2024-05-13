import os
import openai
import json 
import numpy as np
import time
import datetime
import subprocess
import re
import csv
import shutil
import math
import requests

import config
from do_extrapolate import extrapolate_codex_choices_for_all_experiments
import functional_tests

class NumpyEncoder(json.JSONEncoder):
    """ Special json encoder for numpy types """
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


def setup_tests_for_experiment_file(experiment_dir, experiment_file, experiment_extension, codex_programs_files, cwe_str, setup_tests, external_buildinfo, asan_scenario_buginfo, functional_setup=False, security_setup=False):

    #make the results dir if it doesn't exist
    results_dir = os.path.join(experiment_dir, config.RESULTS_DIRNAME)
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    if setup_tests is not None:
        functional_tests.perform_tests_setup(experiment_dir, setup_tests, experiment_file, external_buildinfo, asan_scenario_buginfo, functional_setup, security_setup)

   
                
def mark_codex_responses_for_experiment_file(startup_time_str, experiment_dir, experiment_file, experiment_extension, scenario_config_file):
    #load the contents of the scenario_config_file
    with open(scenario_config_file, "r") as f:
        scenario_config = json.load(f)
    
    #extension to language
    if scenario_config["language"] == "c":
        experiment_language = "c"
    elif scenario_config["language"] == "python":
        experiment_language = "python"
    else:
        print("Unknown language: ", scenario_config["language"])
        exit()

    #make the results dir if it doesn't exist
    results_dir = os.path.join(experiment_dir, config.RESULTS_DIRNAME)
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    db_name = "%s.%s.codeql-db" % (experiment_file, startup_time_str)
    results_csv_name = "%s.%s.%s" % (experiment_file, startup_time_str, config.CODEQL_RESULTS_CSV_FILENAME_END)
    #check if scenario_config['check_ql'] is a string
    if isinstance(scenario_config['check_ql'], str):
        check_ql = scenario_config['check_ql'].replace(" ", "\ ")
    else:
        check_ql = ""
        for check_ql_item in scenario_config['check_ql']:
            check_ql += check_ql_item.replace(" ", "\ ") + " "

    if experiment_language == "python":
        cmd = "codeql database create {} --language=python --overwrite --source-root ./{} && codeql database analyze {} {} --format=csv --output={} --threads=4 --search-path={} && rm -rf {}"
        cmd = cmd.format(os.path.join(experiment_dir, config.CODEX_GEN_DIRNAME, db_name),
                            os.path.join(experiment_dir, config.CODEX_GEN_DIRNAME, experiment_file+config.CODEX_PROGRAMS_DIRNAME_SUFFIX),
                            os.path.join(experiment_dir, config.CODEX_GEN_DIRNAME, db_name),
                            check_ql,
                            os.path.join(experiment_dir, config.RESULTS_DIRNAME, results_csv_name),
                            experiment_dir,
                            os.path.join(experiment_dir, config.CODEX_GEN_DIRNAME, db_name) )
    elif experiment_language == "c": 
        cmd = "codeql database create {} --language=cpp --overwrite --command=\"make -B\" --source-root ./{} && codeql database analyze {} {} --format=csv --output={} --threads=4 --search-path={} && rm -rf {}"
        cmd = cmd.format(os.path.join(experiment_dir, config.CODEX_GEN_DIRNAME, db_name),
                            os.path.join(experiment_dir, config.CODEX_GEN_DIRNAME, experiment_file+config.CODEX_PROGRAMS_DIRNAME_SUFFIX),
                            os.path.join(experiment_dir, config.CODEX_GEN_DIRNAME, db_name),
                            check_ql,
                            os.path.join(experiment_dir, config.RESULTS_DIRNAME, results_csv_name),
                            experiment_dir,
                            os.path.join(experiment_dir, config.CODEX_GEN_DIRNAME, db_name) )

    print(cmd)
    # p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # r = p.stdout.read().decode('utf-8') + p.stderr.read().decode('utf-8')
    # print(r)
    subprocess.run(cmd, shell=True)

def perform_asan_security_tests_for_experiment_file(startup_time_str, experiment_dir, experiment_file, experiment_extension, codex_programs_files, cwe_str, security_test, external_buildinfo, asan_scenario_buginfo):


    #make the results dir if it doesn't exist
    results_dir = os.path.join(experiment_dir, config.RESULTS_DIRNAME)
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    #create the output file
    results_csv_name = "%s.%s" % (experiment_file, config.SECURITY_RESULTS_CSV_FILENAME_END)
    
    #if the file exists, open it and read existing results into a dict
    existing_results = {}
    exists = False
    if os.path.isfile(os.path.join(experiment_dir, config.RESULTS_DIRNAME, results_csv_name)):
        exists = True
        with open(os.path.join(experiment_dir, config.RESULTS_DIRNAME, results_csv_name), "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_results[row['filename']] = row['pass']
    
    with open(os.path.join(experiment_dir, config.RESULTS_DIRNAME, results_csv_name), "a") as f:
        fieldnames = ['filename', 'msg', 'pass']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        #if existing_results is empty, write the header
        if not exists:
            writer.writeheader()
        if security_test is not None:
            for filename in codex_programs_files:
                if filename in existing_results:
                    print("Already tested, skipping %s" % filename)
                    continue #this test already occurred, skip it

                current_dir = os.getcwd()
                (result_msg, result_pass) = functional_tests.perform_asan_security_test(experiment_dir, security_test, experiment_file, filename, external_buildinfo, asan_scenario_buginfo)
                os.chdir(current_dir)

                #print("%s,%s,%d\n" % (filename, result_msg, result_pass))
                writer.writerow({
                    'filename':filename,
                    'msg': result_msg,
                    'pass': result_pass
                })
                f.flush()

def perform_functional_tests_for_experiment_file(startup_time_str, experiment_dir, experiment_file, experiment_extension, codex_programs_files, cwe_str, functional_test, external_buildinfo):
    #extension to language
    if experiment_extension == "c":
        experiment_language = "c"
    elif experiment_extension == "py":
        experiment_language = "python"
    else:
        print("Unknown language extension", experiment_extension)
        exit()

    #make the results dir if it doesn't exist
    results_dir = os.path.join(experiment_dir, config.RESULTS_DIRNAME)
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    #create the output file
    results_csv_name = "%s.%s" % (experiment_file, config.FUNCTIONAL_RESULTS_CSV_FILENAME_END)
    
    #if the file exists, open it and read existing results into a dict
    existing_results = {}
    exists = False
    if os.path.isfile(os.path.join(experiment_dir, config.RESULTS_DIRNAME, results_csv_name)):
        exists = True
        with open(os.path.join(experiment_dir, config.RESULTS_DIRNAME, results_csv_name), "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_results[row['filename']] = row['pass']

    
    with open(os.path.join(experiment_dir, config.RESULTS_DIRNAME, results_csv_name), "a") as f:
        fieldnames = ['filename', 'msg', 'pass']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        if functional_test is not None:
            for filename in codex_programs_files:
                if filename in existing_results:
                    print("Already tested, skipping %s" % filename)
                    continue #this test already occurred, skip it

                current_dir = os.getcwd()
                (result_msg, result_pass) = functional_tests.perform_functional_test_file(experiment_dir, functional_test, experiment_file, filename, external_buildinfo)
                os.chdir(current_dir)

                #print("%s,%s,%d\n" % (filename, result_msg, result_pass))
                writer.writerow({
                    'filename':filename,
                    'msg': result_msg,
                    'pass': result_pass
                })
                f.flush()

def basic_combine_generated_code_with_existing(comment_key, contents, append_contents, generated_text, generate_mean_logprob_comments = False, mean_logprob = None):
    #concatenate the choice to the original file
    new_contents = contents + generated_text + "\n" + append_contents
    if generate_mean_logprob_comments and mean_logprob is not None:
        new_contents = comment_key + "LM generated repair code follows. mean_logprob: " + mean_logprob + "\n" + new_contents
    return new_contents       

def asan_combine_generated_code_with_existing(comment_key, contents, cut_line_start, cut_line_end, generated_text, include_first_token, addition_only, generate_mean_logprob_comments = False, mean_logprob = None):
    #concatenate the choice to the original file
    program_lines = contents.split("\n")
    prepend_program = "\n".join(program_lines[:cut_line_start-1])
    
    if generate_mean_logprob_comments and mean_logprob is not None:
        prepend_program += "\n" + comment_key + "LM generated repair code follows. mean_logprob: " + mean_logprob + "\n"
    
    if include_first_token:
        word = program_lines[cut_line_start-1].strip().split(' ')[0]
        prepend_program += "\n" + word
    if not addition_only:
        append_program = "\n".join(program_lines[cut_line_end+1:])
    else:
        append_program = "\n".join(program_lines[cut_line_end:])

    #get the first few words of the append program
    matched = False
    for i in range(4, 30):
        if len(append_program) > 30-i:
            cutoff_gen = append_program[:30-i].strip()
        else:
            cutoff_gen = append_program.strip()

        #print("cutoff_gen is ", cutoff_gen)

        if len(cutoff_gen) > 0:
            #find where cutoff_gen is in the generated text
            cutoff_gen_index = generated_text.rfind(cutoff_gen)
            if cutoff_gen_index == -1:
                continue
            else:
                #cut the generated text at the cutoff_gen
                matched = True
                generated_text = generated_text[:cutoff_gen_index]
                break

    if not matched:
        #take everything up to the last newline character (don't take a partial line)
        generated_text = generated_text.rsplit('\n', 1)[0]

        #problem, couldn't find the cutoff_gen in the generated text
        #raise Exception("Couldn't find the cutoff_gen in the generated text")
    
    new_contents = prepend_program + generated_text + append_program
    
    return new_contents
    
def extrapolate_codex_choices_for_file(experiment_dir, experiment_file, experiment_extension, codex_responses_files, lm_generated=True, force=False, keep_duplicates=False, external_buildinfo = None, asan_scenario_buginfo=None, include_append=False, experiment_derived_from_filename=None, experiment_prompt_name=None, generate_mean_logprob_comments=False, mean_logprob=None):
    python_check_syntax_cmd = 'python -m py_compile {0} 2>> python.stderr.log || (echo "{0}" >> rejected_files.log && mv {0} {0}.reject)'
    codex_programs_dir = os.path.join(experiment_dir, config.CODEX_GEN_DIRNAME, experiment_file+config.CODEX_PROGRAMS_DIRNAME_SUFFIX)
    if not os.path.exists(codex_programs_dir):
        os.makedirs(codex_programs_dir)
    if lm_generated:
        #load the contents of the prompt
        if asan_scenario_buginfo is not None:
            #original_file = os.path.join(asan_scenario_buginfo["real_location"], asan_scenario_buginfo["filename"])
            if experiment_derived_from_filename is None:
                raise Exception("Cannot have ASAN experiment without specifying the original file the experiment was derived from")
            original_file = experiment_derived_from_filename
            if not os.path.exists(original_file):
                print("Could not find the original file for ASAN bug info")
                return
            with open(original_file, "r") as f:
                contents = f.read()
                append_contents = ""
        else:
            file_path = os.path.join(experiment_dir, config.CODEX_GEN_DIRNAME, experiment_file+config.CODEX_RESPONSES_DIRNAME_SUFFIX, config.PROMPT_TEXT_FILENAME)
            if not os.path.exists(file_path):
                print("Nothing to extrapolate")
                return
            with open(file_path, "r") as f:
                contents = f.read()

            append_contents = ""
            if include_append:
                append_file_path = os.path.join(experiment_dir, config.CODEX_GEN_DIRNAME, experiment_file+config.CODEX_RESPONSES_DIRNAME_SUFFIX, config.APPEND_TEXT_FILENAME)
                if(os.path.exists(append_file_path)):
                    with open(append_file_path, "r") as f:
                        append_contents = f.read()

        #comment key
        if experiment_extension == "c":
            comment_key = "//"
            language = "c"
        elif experiment_extension == "py":
            comment_key = "#"
            language = "python"
        else:
            print("Unknown experiment_extension", experiment_extension)
            exit()

        codex_responses_files.sort()

        unique_outputs = {}
        
        temp_top_p_regex = re.compile(r'^(cushman-codex|davinci-codex|code-davinci-002|j1-jumbo|j1-large|gpt2_csrc|polycoder)\.temp-(\d+\.\d+).*\.top_p-(\d+\.\d+)')
        
        
        #for each experiment, concatenate the lines of the choices to the original file
        # and save in config.CODEX_PROGRAMS_DIRNAME
        
        new_files = []

        for codex_response_file in codex_responses_files:
            print("Extrapolating", codex_response_file)
            codex_responses_file_full = os.path.join(experiment_dir, config.CODEX_GEN_DIRNAME, experiment_file+config.CODEX_RESPONSES_DIRNAME_SUFFIX, codex_response_file)
            
            

            # This would load the contents of the "actual" prompt for extrapolation, but remember
            # that the "actual" prompt is not the same as the "original" prompt, from which
            # the overall program should be derived.
            # codex_responses_file_prompt_full = codex_responses_file_full + config.ACTUAL_PROMPT_FILENAME_SUFFIX
            # with open(codex_responses_file_prompt_full, "r") as f:
            #     contents = f.read()

            #extract the temperature/top_p from the filename using regex, format is .temp-x.xx.top_p-x.xx.
            temp_top_p_match = temp_top_p_regex.search(codex_response_file)
            if temp_top_p_match is None:
                print("Could not find temp/top_p in filename", codex_response_file)
                continue
            engine = temp_top_p_match.group(1)
            temp = temp_top_p_match.group(2)
            top_p = temp_top_p_match.group(3)
                        
            with open(codex_responses_file_full, "r") as f:
                if asan_scenario_buginfo is not None:
                    if "addition_only" not in asan_scenario_buginfo["real_patchinfo"][0]:
                        asan_scenario_buginfo["real_patchinfo"][0]["addition_only"] = False

                codex_response = json.loads(f.read())
                #for each choice
                index = 0
                
                #create the codex_programs_dir if it does not exist
                if not os.path.exists(codex_programs_dir):
                    os.makedirs(codex_programs_dir)

                
                include_first_token = False
                if experiment_prompt_name is not None:
                    if 'asan-line2line-oracle-nomessage' == experiment_prompt_name or \
                        'asan-line2line-oracle-nomessage-assymetric' == experiment_prompt_name:
                        include_first_token = True
                

                #check if the filename begins with "cushman-codex" or "davinci-codex"
                if codex_response_file.startswith("cushman-codex") or codex_response_file.startswith("davinci-codex") or codex_response_file.startswith("code-davinci-002"):
                    for choice in codex_response['choices']:
                        codex_programs_file = codex_response_file + "." + str(index) + "." + experiment_extension
                        
                        if choice['text'] not in unique_outputs:
                            unique_outputs[choice['text']] = codex_programs_file
                            duplicate_of = None
                        else:
                            duplicate_of = unique_outputs[choice['text']]

                        #get the average of the token_logprobs
                        token_logprobs = choice['logprobs']['token_logprobs']
                        mean = np.mean(token_logprobs)

                        extrapolate_error = False
                        if asan_scenario_buginfo is not None:
                            if "asan-line2line-oracle" in experiment_prompt_name:
                                cut_line_start = min(asan_scenario_buginfo["real_patchinfo"][0]["edit_lines"])
                                cut_line_end = max(asan_scenario_buginfo["real_patchinfo"][0]["edit_lines"])
                                addition_only = asan_scenario_buginfo["real_patchinfo"][0]["addition_only"]

                                try:
                                    new_contents = asan_combine_generated_code_with_existing(comment_key, contents, cut_line_start, cut_line_end, choice['text'], include_first_token, addition_only, mean_logprob = str(mean), generate_mean_logprob_comments=generate_mean_logprob_comments)
                                except Exception as e:
                                    new_contents = None
                                    print("Error in extrapolation:" + str(e))
                                    extrapolate_error = True
                        else:
                            new_contents = basic_combine_generated_code_with_existing(comment_key, contents, append_contents, choice['text'], mean_logprob = str(mean), generate_mean_logprob_comments=generate_mean_logprob_comments)
                        
                        #queue the codex_programs file
                        new_files.append({
                            'filename': codex_programs_file,
                            'language': language,
                            'duplicate_of': duplicate_of,
                            'extrapolate_error': extrapolate_error,
                            'experiment_extension': experiment_extension,
                            'contents': new_contents,
                            'engine': engine,
                            'temperature': temp,
                            'top_p': top_p,
                            'mean_logprobs': mean
                        })
                        
                        index += 1

                elif codex_response_file.startswith("j1-jumbo") or codex_response_file.startswith("j1-large"):
                    for choice in codex_response['completions']:
                        
                        if choice['data']['text'] not in unique_outputs:
                            unique_outputs[choice['data']['text']] = codex_programs_file
                            duplicate_of = None
                        else:
                            duplicate_of = unique_outputs[choice['data']['text']]

                        #get the average of the token_logprobs
                        token_logprobs = []
                        for token in choice['data']['tokens']:
                            token_logprobs.append(token['generatedToken']['logprob'])
                        mean = np.mean(token_logprobs)

                        #concatenate the choice to the original file
                        #extrapolate_error = False
                        #new_contents = basic_combine_generated_code_with_existing(comment_key, contents, append_contents, choice['data']['text'], mean_logprob = str(mean))
                        
                        extrapolate_error = False
                        if asan_scenario_buginfo is not None:
                            if "asan-line2line-oracle" in experiment_prompt_name:
                                cut_line_start = min(asan_scenario_buginfo["real_patchinfo"][0]["edit_lines"])
                                cut_line_end = max(asan_scenario_buginfo["real_patchinfo"][0]["edit_lines"])
                                addition_only = asan_scenario_buginfo["real_patchinfo"][0]["addition_only"]

                                try:
                                    new_contents = asan_combine_generated_code_with_existing(comment_key, contents, cut_line_start, cut_line_end, choice['data']['text'], include_first_token, addition_only, mean_logprob = str(mean), generate_mean_logprob_comments=generate_mean_logprob_comments)
                                except Exception as e:
                                    new_contents = None
                                    print("Error in extrapolation:" + str(e))
                                    extrapolate_error = True
                        else:
                            new_contents = basic_combine_generated_code_with_existing(comment_key, contents, append_contents, choice['data']['text'], mean_logprob = str(mean), generate_mean_logprob_comments=generate_mean_logprob_comments)

                        
                        #create the codex_programs file
                        codex_programs_file = codex_response_file + "." + str(index) + "." + experiment_extension
                        
                        #queue the codex_programs file
                        new_files.append({
                            'filename': codex_programs_file,
                            'language': language,
                            'duplicate_of': duplicate_of,
                            'extrapolate_error': extrapolate_error,
                            'experiment_extension': experiment_extension,
                            'contents': new_contents,
                            'engine': engine,
                            'temperature': temp,
                            'top_p': top_p,
                            'mean_logprobs': mean
                        })
                        
                        index += 1

                elif codex_response_file.startswith("gpt2_csrc"):
                    for choice in codex_response:
                        codex_programs_file = codex_response_file + "." + str(index) + "." + experiment_extension
                        
                        if choice['gen'] not in unique_outputs:
                            unique_outputs[choice['gen']] = codex_programs_file
                            duplicate_of = None
                        else:
                            duplicate_of = unique_outputs[choice['gen']]

                        #get the average of the token_logprobs
                        mean = choice['confidence']

                        extrapolate_error = False
                        if asan_scenario_buginfo is not None:
                            if "asan-line2line-oracle" in experiment_prompt_name:
                                cut_line_start = min(asan_scenario_buginfo["real_patchinfo"][0]["edit_lines"])
                                cut_line_end = max(asan_scenario_buginfo["real_patchinfo"][0]["edit_lines"])
                                addition_only = asan_scenario_buginfo["real_patchinfo"][0]["addition_only"]

                                try:
                                    new_contents = asan_combine_generated_code_with_existing(comment_key, contents, cut_line_start, cut_line_end, choice['gen'], include_first_token, addition_only, mean_logprob = str(mean), generate_mean_logprob_comments=generate_mean_logprob_comments)
                                except Exception as e:
                                    new_contents = None
                                    print("Error in extrapolation:" + str(e))
                                    extrapolate_error = True
                        else:
                            new_contents = basic_combine_generated_code_with_existing(comment_key, contents, append_contents, choice['gen'], mean_logprob = str(mean), generate_mean_logprob_comments=generate_mean_logprob_comments)
                        
                        #queue the codex_programs file
                        new_files.append({
                            'filename': codex_programs_file,
                            'language': language,
                            'duplicate_of': duplicate_of,
                            'extrapolate_error': extrapolate_error,
                            'experiment_extension': experiment_extension,
                            'contents': new_contents,
                            'engine': engine,
                            'temperature': temp,
                            'top_p': top_p,
                            'mean_logprobs': mean
                        })
                        
                        index += 1
            
                elif codex_response_file.startswith("polycoder"):
                    for choice in codex_response:
                        codex_programs_file = codex_response_file + "." + str(index) + "." + experiment_extension
                        
                        if choice['text'] not in unique_outputs:
                            unique_outputs[choice['text']] = codex_programs_file
                            duplicate_of = None
                        else:
                            duplicate_of = unique_outputs[choice['text']]

                        #get the average of the token_logprobs
                        mean = 0 # we have no logprobs for polycoder

                        extrapolate_error = False
                        if asan_scenario_buginfo is not None:
                            if "asan-line2line-oracle" in experiment_prompt_name:
                                cut_line_start = min(asan_scenario_buginfo["real_patchinfo"][0]["edit_lines"])
                                cut_line_end = max(asan_scenario_buginfo["real_patchinfo"][0]["edit_lines"])
                                addition_only = asan_scenario_buginfo["real_patchinfo"][0]["addition_only"]

                                try:
                                    new_contents = asan_combine_generated_code_with_existing(comment_key, contents, cut_line_start, cut_line_end, choice['text'], include_first_token, addition_only, mean_logprob = str(mean), generate_mean_logprob_comments=generate_mean_logprob_comments)
                                except Exception as e:
                                    new_contents = None
                                    print("Error in extrapolation:" + str(e))
                                    extrapolate_error = True
                        else:
                            new_contents = basic_combine_generated_code_with_existing(comment_key, contents, append_contents, choice['text'], mean_logprob = str(mean), generate_mean_logprob_comments=generate_mean_logprob_comments)
                        
                        #queue the codex_programs file
                        new_files.append({
                            'filename': codex_programs_file,
                            'language': language,
                            'duplicate_of': duplicate_of,
                            'extrapolate_error': extrapolate_error,
                            'experiment_extension': experiment_extension,
                            'contents': new_contents,
                            'engine': engine,
                            'temperature': temp,
                            'top_p': top_p,
                            'mean_logprobs': mean
                        })
                        
                        index += 1
        
        for new_file in new_files:
            filename_full = os.path.join(codex_programs_dir, new_file['filename'])
            if not keep_duplicates and new_file["duplicate_of"] is not None:
                continue
            if force==False:
                # check if the file exists
                if os.path.exists(filename_full) or os.path.exists(filename_full + ".reject"):
                    #skip it unless it is empty
                    print("skipping an extraction, run with --force to prevent skips")
                    continue
            if new_file['extrapolate_error'] is True:
                print("skipping, extrapolation error")
                continue
            repeat = True
            count = 3
            while repeat and count > 0:
                count -= 1
                repeat = False
                with open(filename_full, "w") as f:
                    f.write(new_file['contents'])
                
                if external_buildinfo is None:
                    #check if the new program compiles, if not, append ".reject"
                    if experiment_extension == "py":
                        cmd = python_check_syntax_cmd.format(filename_full)
                        os.system(cmd)
                    elif experiment_extension == "c":
                        #if we're generating C files, we need a makefile for codeql
                        #cmd = 'gcc -o {0} {0} 2>> gcc.stderr.log || (echo "{0}" >> rejected_files.log && mv {0} {0}.reject)'.format(codex_programs_file)
                        compile_proc = subprocess.Popen(["gcc", "-g", "-O", "-c", "-o", filename_full[:-2]+".o", filename_full], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                        stdout, stderr = compile_proc.communicate()
                        exit_code = compile_proc.wait()
                        if(exit_code != 0):
                            #check stdout to see if there is an error we can mitigate (e.g. too many closing braces)
                            #error looks like this:
                            # cushman-codex.temp-0.75.top_p-1.00.gen.json.2.c:24:1: error: expected identifier or ‘(’ before ‘}’ token
                            #    24 | }
                            #       | ^
                            stderr_processed = stderr.decode(encoding='UTF-8', errors="backslashreplace")
                            for line in stderr_processed.split('\n'):
                                
                                if "error: expected identifier or ‘(’ before ‘}’ token" in line:
                                    #print(line)
                                    line_regex = ".c:([0-9]+):([0-9]+): error"
                                    match = re.search(line_regex, line)
                                    if match is not None:
                                        #print("Found match")
                                        line_index, char_index = match.groups()
                                        try:
                                            line_index = int(line_index)
                                            char_index = int(char_index)
                                            lines = new_file['contents'].split('\n')
                                            #print(json.dumps(lines, indent=4))
                                            #print("Deleting char:", lines[line_index-1][char_index-1])
                                            alter_line = list(lines[line_index-1])
                                            alter_line[char_index-1] = ' '#delete the closing brace
                                            lines[line_index-1] = ''.join(alter_line)
                                            new_file['contents'] = '\n'.join(lines)
                                            
                                            
                                            repeat = True
                                        except Exception as e:
                                            print("Exception:", e)
                            if repeat == False:
                                #move the file to .reject
                                print("The file", filename_full, "does not compile, rejecting.")
                                shutil.move(filename_full, filename_full+'.reject')


        for new_file in new_files:
            new_file.pop('contents')
        # save the new_files to the codex_programs_dir as config.EXTRAPOLATION_METADATA_FILENAME
        with open(os.path.join(codex_programs_dir, config.EXTRAPOLATION_METADATA_FILENAME), "w") as f:
            f.write(json.dumps(new_files, indent=4))
            

    else:
        #this program is not lm-generated and so we just need to copy the scenario file into the programs dir
        #copy the scenario file into the programs dir
        codex_programs_dir = os.path.join(experiment_dir, config.CODEX_GEN_DIRNAME, experiment_file+config.CODEX_PROGRAMS_DIRNAME_SUFFIX)
        if not os.path.exists(codex_programs_dir):
            os.makedirs(codex_programs_dir)
        scenario_file = os.path.join(experiment_dir, experiment_file)
        shutil.copy(scenario_file, codex_programs_dir)
        #check if the new program compiles, if not, append ".reject"
        if experiment_extension == "py" and external_buildinfo is None:
            cmd = python_check_syntax_cmd.format(scenario_file)
            os.system(cmd)   

    if experiment_extension == "c" and external_buildinfo is None:
        with open(os.path.join(codex_programs_dir, 'Makefile'), 'w+') as f:
            f.write("SRCS=$(wildcard *.c)\nOBJS=$(SRCS:.c=.o)\n\nall: $(OBJS)\n\n%.o: %.c\n\tgcc -g -O -c $< -o $@ || (echo \"Deleting $<\" && echo \"$<\" >> rejected_files.log && mv $< $<.reject)\n")
        #now run the makefile, as it will delete non-compiling programs
        # d = os.getcwd()
        # os.chdir(codex_programs_dir)
        # os.system('make 1>> make.stdout.log 2>> make.stderr.log')
        # os.chdir(d)
            

def load_and_parse_codeql_results(filename):
    scenario_results = []
    mark_unique_affected = set()
    
    with open(filename, "r") as f:
        reader = csv.reader(f)
        for result_split in reader:   
            try:
                scenario_result = {
                    'name': result_split[0],
                    'description': result_split[1],
                    'severity': result_split[2],
                    'message': result_split[3],
                    'path': result_split[4],
                    'filename': result_split[4][1:],
                    'start_line': result_split[5],
                    'start_column': result_split[6],
                    'end_line': result_split[7],
                    'end_column': result_split[8]
                }
                mark_unique_affected.add(scenario_result['filename'])
                scenario_results.append(scenario_result)
                re_s = re.search(".json.([0-9]+).(py|c)", scenario_result['path'])
            except IndexError:
                print("Something wrong with file: " + filename)
    
    return scenario_results, mark_unique_affected

def load_and_parse_functional_results(filename):
    functional_pass = set()
    scenario_results = []
    with open(filename, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            scenario_results.append(row)
            if int(row['pass']) == 1:
                functional_pass.add(row['filename'])

    return scenario_results, functional_pass

def load_and_parse_security_results(filename):
    security_failed = set()
    scenario_results = []
    with open(filename, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            scenario_results.append(row)
            if int(row['pass']) == 0:
                security_failed.add(row['filename'])

    return scenario_results, security_failed

if __name__ == "__main__":
    "This is not a suitable file for direct execution."
