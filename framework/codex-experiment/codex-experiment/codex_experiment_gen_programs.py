import config
import os
import openai
import json
import time
import vocabs.trim_prompt
import requests
import numpy as np

def create_codex_choices_json_for_contents(experiment_dir, experiment_contents, experiment_append_contents, experiment_filename, experiment_extension, estimated_tokens=config.MAX_TOKENS_START_VALUE, temperatures_range = None, top_p_range = None, engine_range = None, stop_word="", skip_engines=[]):
    #language key
    if experiment_extension == "c":
        language_key = "//c"
        stop = ["int main(", "void main(", "%%"]
    elif experiment_extension == "py":
        language_key = "#python"
        stop = ["@app", "@bp"]
    else:
        print("Unknown language extension", experiment_extension)
        exit()

    if stop_word != "":
        stop.append(stop_word)

    # Load the API key from the environment variable 
    openai.api_key = os.getenv("OPENAI_API_KEY")

    #create codex_responses dir in the experiment dir if it does not exist
    codex_responses_dir = os.path.join(experiment_dir, config.CODEX_GEN_DIRNAME, experiment_filename+config.CODEX_RESPONSES_DIRNAME_SUFFIX)
    if not os.path.exists(codex_responses_dir):
        os.makedirs(codex_responses_dir)

    #determine prompt text
    prompt_text = language_key+"\n"+experiment_contents

    #create prompt file in the experiment dir
    prompt_file = os.path.join(codex_responses_dir, config.PROMPT_TEXT_FILENAME)
    with open(prompt_file, "w") as f:
        f.write(prompt_text)

    #create append file if necessary
    if experiment_append_contents is not None and experiment_append_contents != "":
        append_text = experiment_append_contents
        append_file = os.path.join(codex_responses_dir, config.APPEND_TEXT_FILENAME)
        with open(append_file, "w") as f:
            f.write(append_text)

    #range from 0 to 1 with 0.1 step inclusive
    if temperatures_range is None:
        temperatures_range = np.arange(config.TEMPERATURE_ARANGE_MIN, config.TEMPERATURE_ARANGE_MAX, config.TEMPERATURE_ARANGE_STEP)
    if top_p_range is None:
        top_p_range = np.arange(config.TOP_P_ARANGE_MIN, config.TOP_P_ARANGE_MAX, config.TOP_P_ARANGE_STEP)
    if engine_range is None:
        engine_range = config.ENGINE_RANGE
    max_tokens = estimated_tokens

    exists = 0
    not_exists = 0
    #print some data
    for temperature in temperatures_range:
        #for each top_p
        for top_p in top_p_range:
            #for each engine
            for engine in engine_range:
                if engine in skip_engines:
                    continue

                codex_responses_file = os.path.join(codex_responses_dir, "%s.temp-%.2f.top_p-%.2f.gen.json" % (engine, temperature, top_p))
                #check if the codex_responses_file already exists
                if os.path.exists(codex_responses_file):
                    exists += 1
                else:
                    not_exists += 1

    print("\n-->There are %d programs to generate, %d exist, %d to go.\n" % (exists+not_exists, exists, not_exists))
    repeats = 0
    #for each temperature
    AI21_keyID = 0
    AI21_keystr = os.getenv('AI21_API_KEYS')
    AI21_keys = AI21_keystr.split(",") if AI21_keystr else []
    #for each engine
    for engine in engine_range:
        if engine in skip_engines:
            continue
        # get the suggestions for the file
        #reset prompt text
        print("Generating '%s' responses for %s" % (engine, experiment_filename))
        
        prompt_text = language_key+"\n"+experiment_contents

        #determine the final (trimmed) prompt text
        try:
            (prompt_text, req_est_tokens) = vocabs.trim_prompt.trim_prompt(prompt_text, max_tokens, engine) 
        except:
            print("Error trimming prompt text")
            continue

        for temperature in temperatures_range:
            #for each top_p
            for top_p in top_p_range:
            
                skip = False

                codex_responses_file = os.path.join(codex_responses_dir, "%s.temp-%.2f.top_p-%.2f.gen.json" % (engine, temperature, top_p))
                #check if the codex_responses_file already exists
                if os.path.exists(codex_responses_file):
                    #print("Skipping '", codex_responses_file, "' (it already exists)")
                    skip = True
                    #continue
                else:
                    print(codex_responses_file, " does not exist")

                while not skip:
                    try:
                        total_tokens = req_est_tokens * config.NUM_CODEX_RESPONSES_REQUESTED
                        sleep_time = (60/(config.OPENAI_MAX_TOKENS_PER_MINUTE/total_tokens)) + 0.1
                        if config.PERFORM_RATE_LIMITING:
                            print("Requesting %d tokens (%d total), prevent overloading API: waiting for %.2f seconds" % (req_est_tokens, total_tokens, sleep_time))
                            time.sleep(sleep_time)
                        else:
                            print("Requesting %d tokens (%d total)" % (req_est_tokens, total_tokens))
                        
                        print("Attempting responses for folder: %s ,file:%s,temp:%.2f,top_p:%.2f,engine:%s,max_tokens:%d" % (experiment_dir,experiment_filename,temperature, top_p, engine, max_tokens))
                        if engine == "cushman-codex" or engine == "davinci-codex" or engine == "code-davinci-002":
                            response = openai.Completion.create(
                                engine=engine, 
                                prompt=prompt_text, 
                                max_tokens=int(max_tokens),
                                temperature=temperature,
                                top_p=top_p,
                                n=config.NUM_CODEX_RESPONSES_REQUESTED,
                                stop=stop,
                                logprobs=1)
                        
                            
                            print("Codex responses collected.")
                            break
                        elif engine == "j1-jumbo" or engine == "j1-large":
                            ai21_api_key=AI21_keys[AI21_keyID]
                            url = "https://api.ai21.com/studio/v1/"+engine+"/complete"
                            headers = {"Authorization": "Bearer "+ai21_api_key}
                            data = {
                                "prompt": prompt_text, 
                                "numResults": 5, 
                                "maxTokens": 256, 
                                "stopSequences": stop,
                                "topKReturn": top_p,
                                "temperature": temperature
                            }
                            response_raw = requests.post(url, headers=headers, json=data)
                            response = json.loads(response_raw.text)
                            if 'detail' in response:
                                if response['detail'] == 'Quota exceeded.':
                                    print("Quota exceeded for", engine)
                                    if AI21_keyID < len(AI21_keys)-1:
                                        AI21_keyID += 1
                                        print("rotating keys")
                                        continue
                                if 'Request too many tokens' in response['detail']:
                                    print("Request too many tokens for", engine)
                                    if len(prompt_text.split("\n")) > 15:
                                        print("Removing some tokens and trying again")
                                        prompt_text_lines = prompt_text.split("\n")[7:] # remove first 6 lines
                                        prompt_text = language_key + "\n" + "\n".join(prompt_text_lines)
                                        time.sleep(2)
                                        continue
                                skip = True
                                break

                            print("AI21 responses collected.")
                            break
                        elif engine == "gpt2_csrc":
                            import csrc_744m
                            response = csrc_744m.create(
                                prompt_text,
                                max_tokens=max_tokens,
                                temperature=temperature,
                                top_p=top_p,
                                n=config.NUM_CODEX_RESPONSES_REQUESTED,
                                stop=stop
                            )
                            break
                        elif engine == "polycoder":
                            import polycoder
                            response = polycoder.create(
                                prompt_text,
                                max_tokens=max_tokens,
                                temperature=temperature,
                                top_p=top_p,
                                n=config.NUM_CODEX_RESPONSES_REQUESTED,
                                stop=stop
                            )
                            #print(json.dumps(response, indent=2))
                            break
                        else:
                            print("Unknown engine: %s" % engine)
                            break

                    except openai.error.RateLimitError as e:
                        print("Rate limit Exception:", e)
                        print("Waiting 30 seconds and trying again")
                        time.sleep(30)
                        continue
                    except openai.error.InvalidRequestError as e:
                        print("InvalidRequestError Exception:", e)
                        print("Was there a trimming error?")
                        skip=True
                        break
                    except Exception as e:
                        print("Exception:", e)
                        print("Waiting 30 seconds and trying again")
                        time.sleep(30)
                        continue
                
                if not skip:
                    #create codex_responses file in the experiment dir
                    with open(codex_responses_file, "w") as f:
                        f.write(json.dumps(response, indent=4))
                        
                actual_prompt_file = codex_responses_file + config.ACTUAL_PROMPT_FILENAME_SUFFIX
                with open(actual_prompt_file, "w") as f:
                    f.write(prompt_text)
