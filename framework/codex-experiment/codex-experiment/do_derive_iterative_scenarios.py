import codex_experiment
import codex_experiment_file_finder as ff
import os
import config
import json
import datetime
import shutil
import re
import argparse

import do_gen_iterative_fix_instructions

def get_vulnerable_function_lines(language, vulnerable_file_contents, start_line_index):
    if language == 'python':
        comment_char = '#'
        detect_function_regex = '^\s*def (.*?)\('
    elif language == 'c':
        comment_char = '//'
        detect_function_regex = """^[a-zA-Z_][a-zA-Z_0-9*\(\)\[\]]*\s*[a-zA-Z_0-9*\(\)\[\]]*\s*[a-zA-Z_0-9*\(\)\[\]]*\s*[a-zA-Z_0-9*\(\)\[\]]+\s+[a-zA-Z_0-9]+\s*\([a-zA-Z0-9*_\s\[\],]*\)(?:\s*{|\s\/\*[\sA-Za-z0-9_.,*#\[\]\\\/;'\"-]+\*\/\s*{)"""
    else:
        raise Exception('unsupported language ' + language)

    #################THIS METHOD WORKS FOR FUNCTION LEVEL#####################

    #
    vulnerable_file_contents_str = ''.join(vulnerable_file_contents)
    vulnerable_file_contents_str = vulnerable_file_contents_str.replace('\r', '')
    #find the end of the function openers using the detect_function_regex
    function_def_boundaries = []
    for match in re.finditer(detect_function_regex, vulnerable_file_contents_str, re.MULTILINE):
        function_def_boundaries.append([match.start(), match.end()])

    #print(function_def_boundaries)

    #we have the end of the function, crop the lines at that point
    ##TODO: COME BACK TO THIS

    #for each function index, determine what line it finishes on by counting the number of newlines before it
    function_def_num_newlines = []
    for function_def_boundary in function_def_boundaries:
        function_def_num_newlines.append(
            [
                vulnerable_file_contents_str.count('\n', 0, function_def_boundary[0]), 
                vulnerable_file_contents_str.count('\n', 0, function_def_boundary[1])
            ]
        )   
    #print(function_def_num_newlines)
    #print(start_line_index)
    closest_newline_index = 0
    closest_newline_value = 0
    for i in range(len(function_def_num_newlines)):
        if function_def_num_newlines[i][1] > start_line_index:
            break
        if function_def_num_newlines[i][1] > closest_newline_value:
            closest_newline_value = function_def_num_newlines[i][1]
            closest_newline_index = i

    vulnerable_function_start_line_num = function_def_num_newlines[closest_newline_index][0]
    vulnerable_function_end_line_num = function_def_num_newlines[closest_newline_index][1]

    print("function starts on line " + str(vulnerable_function_start_line_num))
    #print("function ends on line " + str(vulnerable_function_end_line_num))

    
    ##OLD METHOD

    #get the number of whitespace chars in the first line of the function index
    vulnerable_function_line = vulnerable_file_contents[vulnerable_function_start_line_num]
    vulnerable_function_line_stripped = vulnerable_function_line.lstrip()
    vulnerable_function_whitespace_count = len(vulnerable_function_line) - len(vulnerable_function_line_stripped)

    print("Vulnerable function no. of whitespace chars:", vulnerable_function_whitespace_count)

    #if language == 'python':
    #starting at the end function line number, go forwards until you find a non-comment line that has the same indentation level
    vulnerable_function_end_index = 0
    for i in range(vulnerable_function_end_line_num+1, len(vulnerable_file_contents)):
        line = vulnerable_file_contents[i]
        line_stripped = line.lstrip()
        if len(line_stripped.rstrip()) == 0:
            continue
        if line_stripped[0:len(comment_char)] == comment_char:
            continue

        if len(line) - len(line_stripped) == vulnerable_function_whitespace_count:
            break
        vulnerable_function_end_index = i + 1
        
    #print("Vulnerable function end index:", vulnerable_function_end_index)
    #print("Vulnerable function end line:", vulnerable_file_contents[vulnerable_function_end_index])

    if language == 'c' and vulnerable_file_contents[vulnerable_function_end_index].strip() == '}':
        vulnerable_function_end_index += 1 #we'll include the closing brace in the vulnerable function for C

    #make the prompt lines from 0 to vulnerable_function_index+1 (line after the function)
    vulnerable_file_prepend_lines = vulnerable_file_contents[0:vulnerable_function_start_line_num]

    #IMPORTANT: we assume that the vulnerable function has a newline between function start "{" or ":" and the body
    vulnerable_file_function_def_lines = vulnerable_file_contents[vulnerable_function_start_line_num:vulnerable_function_end_line_num+1]

    #make the vulnerable lines from prompt_line_end_index to start_line_index
    vulnerable_file_function_pre_start_lines = vulnerable_file_contents[vulnerable_function_end_line_num+1:start_line_index]

    #start line onwards
    vulnerable_file_function_start_lines_to_end = vulnerable_file_contents[start_line_index:vulnerable_function_end_index]

    #make the append lines from start_line_index to the end
    vulnerable_file_append_lines = vulnerable_file_contents[vulnerable_function_end_index:]

    #print("The function began on line", vulnerable_function_index)
    return (vulnerable_file_prepend_lines, vulnerable_file_function_def_lines, vulnerable_file_function_pre_start_lines, vulnerable_file_function_start_lines_to_end, vulnerable_file_append_lines)

def derive_scenario_for_iterative_fix(iterative_fix):
    if iterative_fix['language'] == 'python':
        file_extension = '.py'
        comment_char = '#'
    elif iterative_fix['language'] == 'c':
        file_extension = '.c'
        comment_char = '//'
        assymetric_comment_char_start = '/*'
        assymetric_comment_char_end = '*/'
    else:
        raise Exception('unsupported language ' + iterative_fix['language'])
    #for the iterative fix, we need to
    #1. load the vulnerable file
    #2. isolate and comment out the vulnerable code, and seperate into prompt, vulnerable, append
    #3. derive the language prompt and append it to the prompt
    #4. create the scenario dir and add the necessary files (scenario_prompt.py, scenario_append.py, scenario.json)
    
    possible_prompts = []

    #vulnerabilities = []

    if 'vulnerabilities' in iterative_fix and iterative_fix['vulnerabilities'] is not None: #toy examples
        #first = True
        for vulnerability in iterative_fix['vulnerabilities']:
            # if first == False: #we only run for one vulnerability
            #     break
            # first = False
    
    #   Schema for vulnerability information 
    #         "vulnerabilities": [
    #     {
    #         "name": "Incomplete URL substring sanitization",
    #         "description": "Security checks on the substrings of an unparsed URL are often vulnerable to bypassing.",
    #         "severity": "warning",
    #         "message": "'[[\"example.com\"|\"relative:///scenario.py:12:28:12:40\"]]' may be at an arbitrary position in the sanitized URL.",
    #         "path": "/scenario.py",
    #         "filename": "scenario.py",
    #         "start_line": "12",
    #         "start_column": "8",
    #         "end_line": "12",
    #         "end_column": "41"
    #     }
    # ]
            
            vulnerable_filename_full = os.path.join(iterative_fix['file_dir'], vulnerability['filename'])
            #if not os.path.isfile(vulnerable_filename_full):
            #    print('vulnerable file ' + vulnerable_filename_full + ' does not exist')
            #print(vulnerable_filename_full)
            vulnerable_file_contents = []
            with open(vulnerable_filename_full, 'r') as f:
                vulnerable_file_contents = f.readlines()

            #identify the function of the bad line
            start_line_index = int(vulnerability['start_line']) - 1
            bad_line = vulnerable_file_contents[start_line_index]


            bad_line_whitespace_count = len(bad_line) - len(bad_line.lstrip())
            
            whitespace_chars = bad_line[:bad_line_whitespace_count]

            (vulnerable_file_prepend_lines, vulnerable_file_function_def_lines, vulnerable_file_function_pre_start_lines, vulnerable_file_function_start_lines_to_end, vulnerable_file_append_lines) = get_vulnerable_function_lines(iterative_fix['language'], vulnerable_file_contents, start_line_index)
            #vulnerable_file_prepend_lines - the lines from the vulnerable file leading up to the function definition
            #vulnerable_file_function_def_lines - the function definition lines (e.g. int main(...) {)
            #vulnerable_file_function_pre_start_lines - the lines from the function definition leading up to the start of the vulnerable line 
            #vulnerable_file_function_start_lines_to_end - the lines from the start of the vulnerable line to the end of the function
            #vulnerable_file_append_lines - the lines from the after the function to the end of the vulnerable file

            #get the first word of the vulnerable lines
            first_vulnerable_word = ""
            for i in range(len(vulnerable_file_function_pre_start_lines)):
                split = vulnerable_file_function_pre_start_lines[i].strip().split()
                if len(split) > 0:
                    first_vulnerable_word = split[0]
                    break

            #derive the language prompt and add it to the prompt
            language_prompt_head = whitespace_chars + comment_char + " BUG: " + vulnerability['name'] + "\n" + \
                                whitespace_chars + comment_char + " MESSAGE: " + vulnerability['message'] + "\n"
            language_prompt_foot = "\n" + whitespace_chars + comment_char + " FIXED VERSION:" + "\n" + whitespace_chars + first_vulnerable_word


            possible_prompts.append({
                'name': 'function',
                'filename': vulnerability['filename'],
                'derived_from_filename': vulnerable_filename_full,
                'vulnerable_file_prompt_lines': vulnerable_file_prepend_lines+vulnerable_file_function_def_lines,
                'vulnerable_file_vulnerable_lines': vulnerable_file_function_pre_start_lines + vulnerable_file_function_start_lines_to_end,
                'vulnerable_file_append_lines': vulnerable_file_append_lines,
                'language_prompt_head': language_prompt_head,
                'language_prompt_foot': language_prompt_foot,
                'whitespace_chars': whitespace_chars,
                'assymetrical_comments': False
            })

            possible_prompts.append({
                'name': 'function-noprompt',
                'filename': vulnerability['filename'],
                'derived_from_filename': vulnerable_filename_full,
                'vulnerable_file_prompt_lines': vulnerable_file_prepend_lines+vulnerable_file_function_def_lines,
                'vulnerable_file_vulnerable_lines': [],
                'vulnerable_file_append_lines': vulnerable_file_append_lines,
                'language_prompt_head': "",
                'language_prompt_foot': "",
                'whitespace_chars': whitespace_chars,
                'assymetrical_comments': False
            })

            language_prompt_head = whitespace_chars + comment_char + " BUG: " + vulnerability['name'] + "\n"
            language_prompt_foot = "\n" + whitespace_chars + comment_char + " FIXED:" + "\n"

            possible_prompts.append({
                'name': 'function-nomessage',
                'filename': vulnerability['filename'],
                'derived_from_filename': vulnerable_filename_full,
                'vulnerable_file_prompt_lines': vulnerable_file_prepend_lines+vulnerable_file_function_def_lines,
                'vulnerable_file_vulnerable_lines': vulnerable_file_function_pre_start_lines + vulnerable_file_function_start_lines_to_end,
                'vulnerable_file_append_lines': vulnerable_file_append_lines,
                'language_prompt_head': language_prompt_head,
                'language_prompt_foot': language_prompt_foot + whitespace_chars + first_vulnerable_word,
                'whitespace_chars': whitespace_chars,
                'assymetrical_comments': False
            })

            # alternative prompts
            if iterative_fix['language'] == 'python':
                language_prompt_head = whitespace_chars + "# bugfix: fixed " + vulnerability['name'] + " \n" 
            else:
                language_prompt_head = whitespace_chars + "/* bugfix: fixed " + vulnerability['name'] + " */\n" 

            possible_prompts.append({
                'name': 'simple-prompt-1',
                'filename': vulnerability['filename'],
                'derived_from_filename': vulnerable_filename_full,
                'vulnerable_file_prompt_lines': vulnerable_file_prepend_lines+vulnerable_file_function_def_lines,
                'vulnerable_file_vulnerable_lines': [],
                'vulnerable_file_append_lines': vulnerable_file_append_lines,
                'language_prompt_head': language_prompt_head,
                'language_prompt_foot': "",
                'whitespace_chars': whitespace_chars,
                'assymetrical_comments': False
            })

            if iterative_fix['language'] == 'python':
                language_prompt_head = whitespace_chars + "# fixed " + vulnerability['name'] + " bug \n" 
            else:
                language_prompt_head = whitespace_chars + "/* fixed " + vulnerability['name'] + " bug */\n" 

            possible_prompts.append({
                'name': 'simple-prompt-2',
                'filename': vulnerability['filename'],
                'derived_from_filename': vulnerable_filename_full,
                'vulnerable_file_prompt_lines': vulnerable_file_prepend_lines+vulnerable_file_function_def_lines,
                'vulnerable_file_vulnerable_lines': [],
                'vulnerable_file_append_lines': vulnerable_file_append_lines,
                'language_prompt_head': language_prompt_head,
                'language_prompt_foot': "",
                'whitespace_chars': whitespace_chars,
                'assymetrical_comments': False
            })

            ########METHOD OVER######
    
    elif 'asan_scenario_buginfo' in iterative_fix and iterative_fix['asan_scenario_buginfo'] is not None:
        #convert the asan_scenario_buginfo to a vulnerability
       
        # we will make N scenarios.
        # the first scenario is the "oracle" scenario and is devised from the original patch info
        # the other N-1 scenarios are derived from the ASAN error stack trace


        

        # let us first make the oracle scenario

        repo_path = iterative_fix['asan_scenario_buginfo']["repo_path"]
        asan_buginfo = iterative_fix['asan_scenario_buginfo']
        asan_patchinfo = asan_buginfo["real_patchinfo"]
        asan_stacktrace = asan_buginfo["stacktrace"]
        
        for patch in asan_patchinfo:
            #we will only do the first patch
            patch_filename = patch["filename"]
            patch_lines = patch["edit_lines"]
            break


        #full_patch_filename = os.path.join(repo_path, patch_filename)
        full_patch_filename = os.path.join(iterative_fix['original_dir'], patch_filename)

        vulnerable_file_contents = []
        with open(full_patch_filename, 'r') as f:
            vulnerable_file_contents = f.readlines()

        #get every line from the file that begins with #define
        defines = []
        for line in vulnerable_file_contents:
            if line.startswith('#define'):
                defines.append(line)

        largest_lineno = max(patch_lines) - 1
        smallest_lineno = min(patch_lines) - 1

        #isolate the lines between the smallest and largest line numbers
        
        first_bad_line = vulnerable_file_contents[smallest_lineno]
        first_bad_line_whitespace_count = len(first_bad_line) - len(first_bad_line.lstrip())    
        whitespace_chars = first_bad_line[:first_bad_line_whitespace_count]
        
        #vulnerable_file_prompt_lines = vulnerable_file_contents[0:index_variable_defined_line]
        vulnerable_file_vulnerable_lines = vulnerable_file_contents[smallest_lineno:largest_lineno+1+2] #get the next 2 lines as well to aid in "joining" the generated response to the file
        #vulnerable_file_append_lines = vulnerable_file_contents[error_line_number+1:]
        vulnerable_file_append_lines = []

        print(vulnerable_file_vulnerable_lines)

        #get the first word of the vulnerable lines
        first_vulnerable_word = ""
        for i in range(len(vulnerable_file_vulnerable_lines)):
            split = vulnerable_file_vulnerable_lines[i].strip().split()
            if len(split) > 0:
                first_vulnerable_word = split[0]
                break

        if first_vulnerable_word == '#' or first_vulnerable_word == '//' or first_vulnerable_word == '/*':
            first_vulnerable_word = ""

        #get the function lines
        (pre_function_lines, function_def_lines, pre_start_lines, lines_to_end, post_function_lines) = get_vulnerable_function_lines(iterative_fix['language'], vulnerable_file_contents, smallest_lineno)

        #get the function definition
        prompt_function_ends_at_line_index = len(pre_function_lines) + len(function_def_lines)
        vulnerable_file_prompt_lines = defines + ["\n"] + function_def_lines + pre_start_lines #vulnerable_file_contents[prompt_function_ends_at_line_index:index_variable_defined_line]

        bugname = asan_buginfo["error"].replace('AddressSanitizer: ', '').replace('-', ' ')

        possible_prompts.append({
            'name': 'asan-line2line-oracle-nofunction',
            'filename': patch_filename,
            'derived_from_filename': full_patch_filename,
            'vulnerable_file_prompt_lines': vulnerable_file_prompt_lines,
            'vulnerable_file_vulnerable_lines': [],
            'vulnerable_file_append_lines': vulnerable_file_append_lines,
            'language_prompt_head': "",
            'language_prompt_foot': "",
            'whitespace_chars': whitespace_chars,
            'assymetrical_comments': False
        })

        language_prompt_head = \
            whitespace_chars + comment_char + "BUG: " + bugname
        language_prompt_head += "\n"
        language_prompt_foot = \
            whitespace_chars + comment_char + "FIXED:\n" + \
            whitespace_chars + first_vulnerable_word

        possible_prompts.append({
            'name': 'asan-line2line-oracle-nomessage',
            'filename': patch_filename,
            'derived_from_filename': full_patch_filename,
            'vulnerable_file_prompt_lines': vulnerable_file_prompt_lines,
            'vulnerable_file_vulnerable_lines': vulnerable_file_vulnerable_lines,
            'vulnerable_file_append_lines': vulnerable_file_append_lines,
            'language_prompt_head': language_prompt_head,
            'language_prompt_foot': language_prompt_foot,
            'whitespace_chars': whitespace_chars,
            'assymetrical_comments': False
        })

        language_prompt_head = \
            whitespace_chars + "/* BUG: " + bugname
        language_prompt_head += "\n"
        language_prompt_foot = \
            whitespace_chars + " * " + "FIXED:\n" + \
            whitespace_chars + " */\n" + \
            whitespace_chars + first_vulnerable_word

        possible_prompts.append({
            'name': 'asan-line2line-oracle-nomessage-assymetric',
            'filename': patch_filename,
            'derived_from_filename': full_patch_filename,
            'vulnerable_file_prompt_lines': vulnerable_file_prompt_lines,
            'vulnerable_file_vulnerable_lines': vulnerable_file_vulnerable_lines,
            'vulnerable_file_append_lines': vulnerable_file_append_lines,
            'language_prompt_head': language_prompt_head,
            'language_prompt_foot': language_prompt_foot,
            'whitespace_chars': whitespace_chars,
            'assymetrical_comments': True
        })

        language_prompt_head = \
            whitespace_chars + "/* BUG: " + bugname
        language_prompt_head += "\n"
        language_prompt_foot = \
            whitespace_chars + " * " + "FIXED:\n" + \
            whitespace_chars + " */\n"

        possible_prompts.append({
            'name': 'asan-line2line-oracle-nomessage-notoken-assymetric',
            'filename': patch_filename,
            'derived_from_filename': full_patch_filename,
            'vulnerable_file_prompt_lines': vulnerable_file_prompt_lines,
            'vulnerable_file_vulnerable_lines': vulnerable_file_vulnerable_lines,
            'vulnerable_file_append_lines': vulnerable_file_append_lines,
            'language_prompt_head': language_prompt_head,
            'language_prompt_foot': language_prompt_foot,
            'whitespace_chars': whitespace_chars,
            'assymetrical_comments': True
        })

        language_prompt_head = whitespace_chars + "/* bugfix: fixed " + bugname + " */\n" 

        possible_prompts.append({
            'name': 'asan-line2line-oracle-simple-prompt-1',
            'filename': patch_filename,
            'derived_from_filename': full_patch_filename,
            'vulnerable_file_prompt_lines': vulnerable_file_prompt_lines,
            'vulnerable_file_vulnerable_lines': [],
            'vulnerable_file_append_lines': vulnerable_file_append_lines,
            'language_prompt_head': language_prompt_head,
            'language_prompt_foot': "",
            'whitespace_chars': whitespace_chars,
            'assymetrical_comments': False
        })

        language_prompt_head = whitespace_chars + "/* fixed " + bugname + " bug */\n" 

        possible_prompts.append({
            'name': 'asan-line2line-oracle-simple-prompt-2',
            'filename': patch_filename,
            'derived_from_filename': full_patch_filename,
            'vulnerable_file_prompt_lines': vulnerable_file_prompt_lines,
            'vulnerable_file_vulnerable_lines': [],
            'vulnerable_file_append_lines': vulnerable_file_append_lines,
            'language_prompt_head': language_prompt_head,
            'language_prompt_foot': "",
            'whitespace_chars': whitespace_chars,
            'assymetrical_comments': False
        })


        #identify the function that contains the error
        #(vulnerable_file_prompt_lines, vulnerable_file_vulnerable_lines, vulnerable_file_append_lines) = get_vulnerable_function_lines(iterative_fix['language'], vulnerable_file_contents, start_line_index)


    
    dirs_newly_made = []
    
    for prompt in possible_prompts:

        prompt_name = prompt['name']
        if prompt_name not in iterative_fix['prompts_range']:
            continue

        vulnerable_file_prompt_lines = prompt['vulnerable_file_prompt_lines']
        vulnerable_file_vulnerable_lines = prompt['vulnerable_file_vulnerable_lines']
        vulnerable_file_append_lines = prompt['vulnerable_file_append_lines']
        language_prompt_head = prompt['language_prompt_head']
        language_prompt_foot = prompt['language_prompt_foot']
        whitespace_chars = prompt['whitespace_chars']
        scenario_derived_from_filename = prompt['derived_from_filename']
        
        #make the scenario dirs
        scenario_dirname = prompt['filename']+"."+prompt_name+config.ITERATIVE_FIX_SCENARIO_DIRNAME_SUFFIX
        scenario_dir = os.path.join(iterative_fix['iterative_dir'], scenario_dirname)
        if not os.path.exists(scenario_dir):
            os.makedirs(scenario_dir)
        dirs_newly_made.append(scenario_dirname)

        #stop_word = ""
        # #get the first word from the append lines to act as a stop word
        # for line in vulnerable_file_append_lines:
        #     line_stripped = line.strip()
        #     if len(line_stripped) < 2:
        #         continue
        #     if line_stripped[0] == '#':
        #         line_stripped = line_stripped[1:]
        #     line_stripped_toks = line_stripped.split(' ')
        #     stop_word = line_stripped_toks[0].strip()
        #     if len(stop_word) > 0:
        #         break


        #write the scenario code files
        scenario_prompt_filename = prompt['filename']+".prompt"+file_extension
        scenario_prompt_filename_full = os.path.join(scenario_dir, scenario_prompt_filename)
        scenario_append_filename = prompt['filename']+".append"+file_extension
        scenario_append_filename_full = os.path.join(scenario_dir, scenario_append_filename)


        scenario_json_filename_full = os.path.join(scenario_dir, config.SCENARIO_CONFIG_FILENAME)

        #make the scenario prompt
        with open(scenario_prompt_filename_full, 'w') as f:
            f.writelines(vulnerable_file_prompt_lines)
            f.write(language_prompt_head)
            for line in vulnerable_file_vulnerable_lines:

                # TODO: add option to reproduce only the comments??

                if prompt["assymetrical_comments"]:
                    f.write(whitespace_chars + " * " + line.replace('/*', '//').replace('*/', ''))
                else:
                    f.write(whitespace_chars + comment_char + " " + line)
            f.write(language_prompt_foot)
        
        #make the scenario append
        with open(scenario_append_filename_full, 'w') as f:
            f.writelines(vulnerable_file_append_lines)
        
        #copy the functional test (if it exists)
        # if scenario_functional_filename is not None and scenario_functional_filename != "":
        #     scenario_functional_filename_full = os.path.join(iterative_fix['root_dir'], scenario_functional_filename)
        #     shutil.copy(scenario_functional_filename_full, scenario_dir)
        # else:
        #     scenario_functional_filename = None
        scenario_functional_filename = iterative_fix['functional_test']
        scenario_security_filename = iterative_fix['security_test']
        scenario_setup_tests_filename = iterative_fix['setup_tests']

        if scenario_functional_filename is not None and scenario_functional_filename != "":
            scenario_functional_filename = os.path.join('..','..', scenario_functional_filename)
        if scenario_security_filename is not None and scenario_security_filename != "":
            scenario_security_filename = os.path.join('..','..', scenario_security_filename)
        if scenario_setup_tests_filename is not None and scenario_setup_tests_filename != "":
            scenario_setup_tests_filename = os.path.join('..','..', scenario_setup_tests_filename)
        

        engine_range = iterative_fix['engine_range']
        if engine_range is None or engine_range[0] == config.ENGINE_NAME_MANUAL_AUTHOR:
            engine_range = config.ENGINE_RANGE

        #write the scenario json file
        scenario_json = {
            'prompt_name': prompt_name,
            'language': iterative_fix['language'],
            'scenarios': [scenario_prompt_filename],
            'scenarios_append': [scenario_append_filename],
            'scenarios_derived_from': [scenario_derived_from_filename],
            'cwe': iterative_fix['cwe'],
            'cve': iterative_fix['cve'],
            'check_ql': iterative_fix['check_ql'],
            'temperatures_range': iterative_fix['temperatures_range'],
            'top_p_range': iterative_fix['top_p_range'],
            'engine_range': engine_range,
            "estimated_tokens": iterative_fix['estimated_tokens'],
            "setup_tests": scenario_setup_tests_filename,
            "functional_test": scenario_functional_filename,
            "security_test": scenario_security_filename,
            'asan_scenario_buginfo': iterative_fix['asan_scenario_buginfo'],
            'external_buildinfo': iterative_fix['external_buildinfo'],
            "stop_word": iterative_fix['stop_word'],
            "include_append": iterative_fix['include_append'],
        }
        with open(scenario_json_filename_full, 'w') as f:
            f.write(json.dumps(scenario_json, indent=4))
        #if there is a scenario_json.old file, delete it
        scenario_json_filename_old_full = scenario_json_filename_full + ".old"
        if os.path.exists(scenario_json_filename_old_full):
            os.remove(scenario_json_filename_old_full)

    return dirs_newly_made

def derive_iterative_scenarios_for_root(iterative_root):
    #load the iterative fixes file
    iterative_fixes_filename = os.path.join(iterative_root, config.ITERATIVE_FIX_INSTRUCTIONS_FILENAME)
    
    with open(iterative_fixes_filename, 'r') as f:
        iterative_fix = json.load(f)
    
    dirs_newly_made = []
    #for iterative_fix in iterative_fixes:
    dirs_newly_made += derive_scenario_for_iterative_fix(iterative_fix)

    #get a list of all dirs in iterative_fix['iterative_dir'] which contain a scenario.json file
    #print("=======\n\n")
    #print(dirs_newly_made)
    dirs_in_iterative_dir = []
    for dirname in os.listdir(iterative_fix['iterative_dir']):
        if os.path.isdir(os.path.join(iterative_fix['iterative_dir'], dirname)):
            if os.path.exists(os.path.join(iterative_fix['iterative_dir'], dirname, config.SCENARIO_CONFIG_FILENAME)):
                dirs_in_iterative_dir.append(dirname)
    #print("======\n")
    #print(dirs_in_iterative_dir)
    #print("\n")
    #for each of those dirs, if they are not newly made then rename the scenario.json to scenario.json.old
    for d in dirs_in_iterative_dir:
        #print("Searching for ", d)
        if d not in dirs_newly_made:
            #print("NO GOOD:", d)
            scenario_json_filename_full = os.path.join(iterative_fix['iterative_dir'], d, config.SCENARIO_CONFIG_FILENAME)
            scenario_json_filename_old_full = scenario_json_filename_full + ".old"
            shutil.move(scenario_json_filename_full, scenario_json_filename_old_full)
        #else:
            #print("GOOD:", d)
    
    #make an "old" dir
    old_dir = os.path.join(iterative_fix['iterative_dir'], "old")
    if not os.path.exists(old_dir):
        os.makedirs(old_dir)

    #move all the dirs containing a scenario.json.old file to the old dir
    for d in os.listdir(iterative_fix['iterative_dir']):
        scenario_dir = os.path.join(iterative_fix['iterative_dir'], d)
        scenario_json_filename_old_full = os.path.join(scenario_dir, config.SCENARIO_CONFIG_FILENAME + ".old")
        if os.path.exists(scenario_json_filename_old_full):
            shutil.move(scenario_dir, os.path.join(old_dir, d))


    #for each of the dirs_in_iterative_dir

def derive_iterative_scenarios_for_all_experiments(target_dir):
    iterative_roots = ff.get_all_scenario_iterative_fix_instruction_roots(target_dir)
    print(iterative_roots)
    for iterative_root in iterative_roots:
        derive_iterative_scenarios_for_root(iterative_root)


def main(target_dir, gen, force):
    if gen:
        do_gen_iterative_fix_instructions.main(target_dir, force)
    derive_iterative_scenarios_for_all_experiments(target_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gen", action='store_true', help="Also run generation script")
    parser.add_argument("--force", action='store_true')
    parser.add_argument('--target-dir', type=str, default=None, help='Target directory containing experiment(s)', required=True)
    args = parser.parse_args()
    main(args.target_dir, args.gen, args.force)