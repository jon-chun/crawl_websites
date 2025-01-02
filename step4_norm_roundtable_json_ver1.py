#!/usr/bin/env python3

import json
import getpass
from openai import OpenAI
from collections import Counter

INPUT_JSON_FILENAME = "helixcenter_openai_20241231-141845_cleaned.json"
OUTPUT_JSON_NORM_FILENAME = INPUT_JSON_FILENAME.replace('_cleaned.json', '_normed.json')

def setup_openai():
    api_key = getpass.getpass("Enter your OpenAI API key: ")
    return OpenAI(api_key=api_key)

def get_unique_values(data, field):
    values = set()
    for item in data:
        if isinstance(item.get(field), list):
            values.update(item[field])
    return sorted(list(values))

def normalize_values(client, field_name, values):
    prompt = f"""Here are unique {field_name} from academic roundtable discussions:
{', '.join(values)}

Please normalize these terms by:
1. Combining very similar concepts
2. Using the most universal/standard phrasing
3. Return ONLY a JSON mapping of original terms to normalized terms

Example format:
{{"original_term": "normalized_term"}}"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a data standardization assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    
    return json.loads(response.choices[0].message.content)

def update_json_with_normalized_values(data, mapping, field):
    for item in data:
        if isinstance(item.get(field), list):
            item[field] = [mapping.get(val, val) for val in item[field]]
    return data

def main():
    client = setup_openai()
    
    with open(INPUT_JSON_FILENAME, 'r', encoding='utf-8') as f:
        data = json.load(f)

    fields = ['keywords', 'institutions', 'specialities']
    
    for field in fields:
        print(f"\nProcessing {field}...")
        unique_values = get_unique_values(data, field)
        normalized_mapping = normalize_values(client, field, unique_values)
        data = update_json_with_normalized_values(data, normalized_mapping, field)

    with open(OUTPUT_JSON_NORM_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\nNormalized data saved to {OUTPUT_JSON_NORM_FILENAME}")

if __name__ == "__main__":
    main()