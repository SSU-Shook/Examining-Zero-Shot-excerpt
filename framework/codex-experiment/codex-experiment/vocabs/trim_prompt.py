import os

os.environ['TOKENIZERS_PARALLELISM'] = 'true' #silence parallelism warning

from transformers import GPT2TokenizerFast

gpt2_csrc_tokenizer = GPT2TokenizerFast(
    os.path.join('.', 'vocabs', 'gpt2_csrc', 'code-vocab.json'),
    os.path.join('.', 'vocabs', 'gpt2_csrc', 'code-merges.txt'),
)
gpt2_csrc_default_max_tokens =  512
gpt2_csrc_absolute_max_tokens = 768

codex_tokenizer = GPT2TokenizerFast(
    os.path.join('.', 'vocabs', 'codex', 'code-vocab.json'),
    os.path.join('.', 'vocabs', 'codex', 'code-merges.txt'),
)
codex_default_max_tokens = 1024
cushman_codex_absolute_max_tokens = 2048
davinci_codex_absolute_max_tokens = 4096

polycoder_tokenizer = GPT2TokenizerFast(
    os.path.join('.', 'vocabs', 'polycoder', 'code-vocab.json'),
    os.path.join('.', 'vocabs', 'polycoder', 'code-merges.txt'),
)
polycoder_default_max_tokens = 512
polycoder_absolute_max_tokens = 2048

ai21_default_max_tokens = 512
ai21_absolute_max_tokens = 2048

def trim_prompt_no_engine(prompt_text, n, max_tokens):
    if(n > max_tokens):
        raise ValueError("Requested prompt is too long")

    while True:
        request_tokens = float(n + float(len(prompt_text)/3.25) + prompt_text.count('\n'))              
        if (request_tokens > max_tokens):
            prompt_text_lines = prompt_text.split("\n")
            language_key = prompt_text_lines[0]
            non_cut_lines = prompt_text_lines[2:] #cut out second line of prompt text
            if(len(prompt_text_lines)<=3): #if less than 3 lines remain
                raise ValueError("Requested prompt cannot be trimmed")

            prompt_text = language_key + "\n" + "\n".join(non_cut_lines)
        else:
            break
    return (prompt_text, request_tokens + 2)

def prompt_to_token_strs(prompt_text, engine):
    if engine == "davinci-codex" or engine == "cushman-codex" or engine == "code-davinci-002":
        tok = codex_tokenizer
    elif engine == 'polycoder':
        tok = polycoder_tokenizer
    elif engine == "gpt2_csrc":
        tok = gpt2_csrc_tokenizer
    else:
        raise ValueError("Unknown engine: {}".format(engine))

    tokens = tok.encode(prompt_text)
    tokens_strs = [tok.decode([t]) for t in tokens]
    return tokens_strs
    
def trim_prompt(prompt, n, engine, max_tokens=None):
    # compute the max_tokens
    if max_tokens is None:
        if engine == "davinci-codex":
            max_tokens = davinci_codex_absolute_max_tokens
        elif engine == 'code-davinci-002':
            max_tokens = davinci_codex_absolute_max_tokens
        elif engine == "cushman-codex":
            max_tokens = cushman_codex_absolute_max_tokens
        elif engine == 'polycoder':
            max_tokens = polycoder_absolute_max_tokens
        elif engine == "gpt2_csrc":
            max_tokens = gpt2_csrc_absolute_max_tokens
        elif engine == "j1-jumbo" or engine == "j1-large":
            max_tokens = ai21_absolute_max_tokens
        else:
            raise ValueError("Unknown engine: {}".format(engine))
    
    # if ai21 use non-engine
    if engine == "j1-jumbo" or engine == "j1-large":
        return trim_prompt_no_engine(prompt, n, ai21_absolute_max_tokens)

    if(n > max_tokens):
        raise ValueError("Requested prompt is too long")

    prompt_text_lines = prompt.split("\n")
    language_key = prompt_text_lines[0]

    request_token_strs = prompt_to_token_strs(prompt, engine) 

    if (n + len(request_token_strs) > max_tokens):
        # remove enough tokens to make it fit
        min_remove = n + len(request_token_strs) - max_tokens
        request_token_strs = request_token_strs[min_remove:]

        # remove additional request_token_strs until a newline is found
        while('\n' not in request_token_strs[0]):
            request_token_strs = request_token_strs[1:]
            if len(request_token_strs) == 0:
                raise ValueError("Requested prompt cannot be trimmed")

        trimmed_prompt = language_key + "\n" + "".join(request_token_strs)
    else:
        trimmed_prompt = prompt
    return (trimmed_prompt, len(request_token_strs) + 2)
