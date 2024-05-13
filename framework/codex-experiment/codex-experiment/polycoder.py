from numpy import poly
import polycoder_wrap.polycoder
import json

def create(
    prompt, max_tokens, temperature, top_p, n, stop
):
    
    outputs = polycoder_wrap.polycoder.main( 
        prompt_text = prompt,
        max_tokens=max_tokens, 
        top_k=0,
        top_p=top_p,
        temperature=temperature,
        num_samples = n)

    responses = []
    for output in outputs:
        #load the contents of the file
        filepath = output
        with open(filepath, "r") as f:
            contents = f.read()
        for content in contents.split("\n"): #it is json lines format
            if content != "":
                responses.append(json.loads(content))
    return responses
