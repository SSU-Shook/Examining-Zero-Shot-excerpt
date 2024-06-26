import sys
import math
import os
import json
import subprocess
from transformers import GPT2TokenizerFast
from string import Template
import fcntl
import time

# Shut up the warning
os.environ['TOKENIZERS_PARALLELISM'] = 'true'

FASTDATA = '/media/hammond/Seagate Expansion Drive/polycoder'
BASEDIR = FASTDATA #os.path.join(FASTDATA, 'CodeLMs')
INDIR  = os.path.join(BASEDIR, 'conf')
OUTDIR = os.path.join(BASEDIR, 'out')
os.makedirs(INDIR, exist_ok=True)
os.makedirs(OUTDIR, exist_ok=True)
DOCKER_IMG = 'moyix/polycoder:base'
VOCAB_FILE = os.path.join(BASEDIR, 'polycoder_wrap/data/code-vocab.json')
MERGE_FILE = os.path.join(BASEDIR, 'polycoder_wrap/data/code-merges.txt')
NUM_GPUS = 1
GPU_LIST = []

tok = GPT2TokenizerFast(VOCAB_FILE, MERGE_FILE)

MAX_TOKENS = 2048

def detect_gpus():
    """
    Returns the number of GPUs available on the system.
    """
    try:
        nvidia_smi = subprocess.check_output(['nvidia-smi', '--query-gpu=gpu_name', '--format=csv,noheader'])
        return len(nvidia_smi.splitlines())
    except subprocess.CalledProcessError:
        return -1

def trim_prompt(prompt, n):
    """
    Trim a prompt to fit within the PolyCoder prompt length limit.
    Trims whole lines at a time.
    prompt: a string
    n: the number of tokens we want to generate

    Returns: a trimmed prompt such that len(tokenize(prompt)) + n <= MAX_TOKENS
    """
    tokens = tok.encode(prompt)
    if len(tokens) + n <= MAX_TOKENS: return prompt
    tokens = tokens[-(MAX_TOKENS-n+1):]
    token_strs = [tok.decode([t]) for t in tokens]
    try:
        first_nl = next(i for i in range(len(token_strs)) if '\n' in token_strs[i])
    except StopIteration:
        # No newlines in prompt, and the prompt is too big
        raise ValueError(f"Prompt cannot be trimmed to fit within {MAX_TOKENS} tokens")
    
    # Potential concern: if the last token containing a newline had trailing characters
    # after the newline, we might accidentally lop off those characters. But I checked
    # that for the PolyCoder tokenizer all the tokens with newlines have no trailing
    # characters.
    trimmed_prompt = ''.join(token_strs[first_nl+1:])
    return trimmed_prompt

# How to invoke Docker
DOCKER_CMD = [
    'nvidia-docker', 'run',
    '--privileged', '--rm',
    '--shm-size=1g',
    '--ulimit', 'memlock=-1',
    '--mount', f'type=bind,src={BASEDIR}/checkpoints-2-7B,dst=/gpt-neox/checkpoints',
    # NB: want host and container paths to be the same to avoid
    # having to translate between them
    '-v', f'{FASTDATA}:{FASTDATA}',
    DOCKER_IMG,
]

CONTAINER_CMD = [
    './deepy.py',
    'generate.py',
    '${config}',
    'checkpoints/configs/local_setup.yml',
    'checkpoints/configs/2-7B.yml'
]

def template_cmd(cmd, **kwargs):
    return [Template(c).safe_substitute(**kwargs) for c in cmd]

# Atomic counter for naming files
def get_counter():
    cfname = os.path.join(BASEDIR, 'counter.txt')
    try:
        counter_file = open(cfname, 'r+')
        fcntl.flock(counter_file, fcntl.LOCK_EX)
        try:
            counter = int(counter_file.read())
        except ValueError as ve:
            print(ve)
            counter = 0 
    except FileNotFoundError:
        counter_file = open(cfname, 'w+')
        counter = 0
 
    counter_file.seek(0)
    counter_file.write(str(counter+1))
    fcntl.flock(counter_file, fcntl.LOCK_UN)
    counter_file.close()
    return counter

def prepare_cmd(prompt, max_tokens, temperature, top_p, n, gpu_num=0):
    """
    Prepares the codegen command to be run in a Docker container.

    Returns (cmd, outfile)
    """
    counter = get_counter()
    top_k = 0
    # Save the prompt to a file

    filename_pattern = f'PolyCoder_t{temperature:.2f}_p{top_p:.2f}_n{n}_max{max_tokens}.{counter:03d}'
    prompt_file = os.path.join(INDIR, f'Prompt_{filename_pattern}.txt')
    with open(prompt_file, 'w') as f:
        f.write(prompt)
    output_file = os.path.join(OUTDIR, f'Gen_{filename_pattern}.jsonl')
     
    TEXTGEN_CONFIG = {
        # Text gen type: `input-file`, `unconditional` or `interactive`
        "text-gen-type": "input-file",
        
        # Params for all
        "maximum_tokens": max_tokens,
        "temperature": temperature,  # Raise for higher sample-counts.
        "top_p": top_p,
        "top_k": top_k,
        "recompute": False,
        
        # `unconditional`/`input-file`: samples
        "num-samples": n,

        # input/output file
        "sample-input-file": prompt_file,
        "sample-output-file": output_file,

        # DeepSpeed doesn't respect CUDA_VISIBLE_DEVICES, so we need to set this
        "include": f"localhost:{gpu_num}",

        "return_logits": True,

        # Magic: even though we're doing inference, DeepSpeed still checks
        # that train_batch_size == micro_batch_per_gpu * gradient_acc_step * world_size64
        "train_batch_size": 32,
    }

    # Save the config to a file. Extension is YML but it's really JSON
    config_file = os.path.join(INDIR,
        f'Config_{filename_pattern}.yml')
    with open(config_file, 'w') as f:
        json.dump(TEXTGEN_CONFIG, f)

    # Run the container
    cmd = template_cmd(DOCKER_CMD + CONTAINER_CMD,
        config=config_file)
    print('Cmd:', ' '.join(cmd))
    return cmd, output_file

def create(prompt, max_tokens, temperature, top_p, n):
    cmd, output_file = prepare_cmd(prompt, max_tokens, temperature, top_p, n)
    subprocess.run(cmd)

    # Read the output
    results = []
    with open(output_file, 'r') as f:
        for line in f:
            results.append(json.loads(line))
    return results

def prepare_batch(args, gpu_num=0):
    """
    Prepares the codegen command to be run in a Docker container.

    Returns (cmd, outfile)
    """
    # Save the prompt to a file
    glob_counter = get_counter()

    output_files = []
    objs = []
    for prompt, max_tokens, temperature, top_p, top_k, n in args:
        counter = get_counter()
        filename_pattern = f'PolyCoder_t{temperature:.2f}_p{top_p:.2f}_n{n}_max{max_tokens}.{counter:03d}'
        output_file = os.path.join(OUTDIR, f'Gen_{filename_pattern}.jsonl')
        obj = {}
        obj['prompt'] = prompt
        obj['max_tokens'] = max_tokens
        obj['temperature'] = temperature
        obj['top_p'] = top_p
        obj['top_k'] = top_k
        obj['num_samples'] = n
        obj['output_file'] = output_file
        obj['recompute'] = False
        objs.append(obj)
        output_files.append(output_file)
    out_json = os.path.join(INDIR, f'Batch_{glob_counter:03d}.json')
    with open(out_json, 'w') as f:
        json.dump(objs, f)
     
    TEXTGEN_CONFIG = {
        # Text gen type: `input-file`, `unconditional` or `interactive`
        "text-gen-type": "batch",
        "batch-input-file": out_json,
        
        "recompute": False,
        
        "return_logits": True,

        # DeepSpeed doesn't respect CUDA_VISIBLE_DEVICES, so we need to set this
        "include": f"localhost:{gpu_num}",

        # Magic: even though we're doing inference, DeepSpeed still checks
        # that train_batch_size == micro_batch_per_gpu * gradient_acc_step * world_size64
        "train_batch_size": 32,
    }

    # Save the config to a file. Extension is YML but it's really JSON
    config_file = os.path.join(INDIR,
        f'Config_{glob_counter:03d}.yml')
    with open(config_file, 'w') as f:
        json.dump(TEXTGEN_CONFIG, f)

    # Run the container
    cmd = template_cmd(DOCKER_CMD + CONTAINER_CMD,
        config=config_file, gpu_num=gpu_num)
    print('Cmd:', ' '.join(cmd))
    return cmd, output_files

def create_batch(batch):
    part_size = math.ceil(len(batch) / NUM_GPUS)
    output_files = []
    procs = []
    for i in range(0, len(batch), part_size):
        argpart = batch[i:i+part_size]
        gpunum = i // part_size
        gpu = GPU_LIST[gpunum]
        cmd, output_files_part = prepare_batch(argpart, gpu_num=gpu)
        print(f"Launching container for batch generation of {part_size} tasks on GPU {gpu}")
        procs.append(subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        output_files += output_files_part
    for proc in procs:
        proc.wait()
    return output_files

def main(max_tokens, num_samples, top_p, top_k, temperature, prompt_files=[], prompt_text="", num_gpus=None):
    global NUM_GPUS, GPU_LIST
    # A few checks to make sure the model is downloaded
    if not os.path.exists(f"{BASEDIR}/checkpoints-2-7B"):
        print("Hmm, I didn't find the model at {BASEDIR}/checkpoints-2-7B.", file=sys.stderr)
        print("", file=sys.stderr)
        sys.exit(1)

    if num_gpus is None:
        NUM_GPUS = detect_gpus()
        if NUM_GPUS == -1:
            print("WARNING: Couldn't detect the number of GPUs using nvidia-smi.", file=sys.stderr)
            print("Assuming NUM_GPUS = 1, but you can fix this with --num_gpus", file=sys.stderr)
            NUM_GPUS = 1
    else:
        NUM_GPUS = num_gpus

    # Respect CUDA_VISIBLE_DEVICES if given
    env_cudadev = os.environ.get('CUDA_VISIBLE_DEVICES', None)
    if env_cudadev is not None:
        GPU_LIST = [int(d) for d in env_cudadev.split(',')]
        NUM_GPUS = len(GPU_LIST)
    else:
        GPU_LIST = list(range(NUM_GPUS))

    prompts = []
    for f in prompt_files: 
        with open(f, 'r') as fp:
            prompt = fp.read()
            trimmed_prompt = trim_prompt(prompt, max_tokens)
            if prompt != trimmed_prompt:
                print(f"Note: prompt trimmed from {len(prompt.splitlines())} to {len(trimmed_prompt.splitlines())} lines")
                print(f"Saving trimmed prompt to {f}.trimmed")
                open(f + '.trimmed', 'w').write(trimmed_prompt)
            prompts.append((trimmed_prompt, max_tokens, temperature, top_p, top_k, num_samples))
    if prompt_text != "":
        prompts.append((prompt_text, max_tokens, temperature, top_p, top_k, num_samples))
    # j = create(TEST_PROMPT, max_tokens=100, temperature=0.5, top_p=0.0, n=10)
    start = time.time()
    result_files = create_batch(prompts)
    end = time.time()
    taken = end - start
    print("All done, results are in:")
    for pf, res in zip(prompt_files, result_files):
        print(f"  {pf} -> {res}")
    samples_generated = num_samples * len(prompts)
    tokens_generated = samples_generated * max_tokens
    print(f"Took {taken:.2f} seconds to generate {samples_generated} samples, {tokens_generated} tokens")
    print(f"Generated {samples_generated/taken:.2f} samples/second, {tokens_generated/taken:.2f} tokens/second")
    return result_files

if __name__ == "__main__":
    import argparse
    import time
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-m', '--max_tokens', type=int, default=512, help='Max number of tokens to generate')
    parser.add_argument('-n', '--num_samples', type=int, default=10, help='Number of samples to generate per prompt')
    parser.add_argument('-p', '--top_p', type=float, default=0.0, help='Top p')
    parser.add_argument('-k', '--top_k', type=float, default=0.0, help='Top k')
    parser.add_argument('-t', '--temperature', type=float, default=0.5, help='Temperature')
    parser.add_argument('--num_gpus', type=int, default=None, help='Number of GPUs to use (default: autodetect)')
    parser.add_argument('prompt_files', nargs='+', help='Prompt files')
    args = parser.parse_args()

    main(args.max_tokens, args.num_samples, args.top_p, args.top_k, args.temperature, args.prompt_files, args.num_gpus)
