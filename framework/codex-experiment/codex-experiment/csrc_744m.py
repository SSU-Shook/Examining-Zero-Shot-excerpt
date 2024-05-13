import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained("moyix/csrc_774m")
device = torch.device("cuda")

model.to(device)
tokenizer = AutoTokenizer.from_pretrained("moyix/csrc_774m")

#CSRC_MAX_TOKENS = 1024

def create(
    prompt, max_tokens, temperature, top_p, n, stop, batch=16
):
    
    prompt_toks = tokenizer.encode(prompt, return_tensors="pt")

    responses = []

    while len(responses) < n:
        if temperature<0.00001:
            temperature=0.00001

        outputs = model.generate(
            input_ids=prompt_toks.to(device), 
            max_length=prompt_toks.shape[-1]+max_tokens,
            do_sample=True, 
            # Make this explicit so we don't get a warning
            pad_token_id=tokenizer.eos_token_id,
            top_k=0,
            top_p=top_p,
            temperature=temperature,
            num_return_sequences=min(batch,n-len(responses)),
            output_scores=True,
            return_dict_in_generate=True, 
        )

        # let's compute log-probabilities and give a confidence score too
        gen_sequences = outputs.sequences[:, prompt_toks.shape[-1]:]
        # tuple to tensor
        logits = torch.stack(outputs.scores,dim=1)
        # pick out only the logits for the generated token indices
        gen_logits = logits.gather(2, gen_sequences.unsqueeze(-1)).squeeze(-1)
        # Normalize the logits
        logprobs = gen_logits - logits.logsumexp(2) 
        confidences = logprobs.mean(1)
        logprobs = logprobs.cpu().tolist()
        confidences = confidences.cpu().tolist()

        for (output,logprob,conf) in zip(outputs.sequences,logprobs,confidences):
            response = {}
            tokens = output.tolist()
            response_text = tokenizer.decode(tokens)
            prompt_text, response_text = response_text[:len(prompt)], response_text[len(prompt):]
            prompt_tokens, response_toks = tokens[:len(prompt_toks[0])], tokens[len(prompt_toks[0]):]
            #remove everything after <|endoftext|> in response
            response_text = response_text[:response_text.find("<|endoftext|>")]
            response['prompt'] = prompt_text
            response['prompt_tokens'] = prompt_tokens
            response['gen'] = response_text
            response['gen_tokens'] = response_toks
            response['confidence'] = conf
            response['log_probs'] = logprob
            responses.append(response)

    return responses

if __name__ == "__main__":
    import sys
    import time
    n = 1
    prompt = "#include <stdio.h>\n\nint main(int argc, char **argv) {"
    st = time.time()
    resp = create(prompt, 128, 0.3, 1.0, n, None, batch=int(sys.argv[1]))
    ed = time.time()
    tokgen = 128*n
    elapsed = ed-st
    # print(f"Generated {tokgen} tokens in {elapsed:.2f}s, {tokgen/elapsed:.2f} toks/s")
    print(json.dumps(resp, indent=2))
