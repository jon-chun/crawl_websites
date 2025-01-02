#!/usr/bin/env python3

import json
import getpass
from openai import OpenAI
from collections import Counter

INPUT_JSON_FILENAME = "helixcenter_openai_20241231-141845_cleaned.json"
OUTPUT_NORM_MAP_JSON = INPUT_JSON_FILENAME.replace('_cleaned.json', '_norm_map.json')
OUTPUT_JSON_NORM_FILENAME = INPUT_JSON_FILENAME.replace('_cleaned.json', '_normed.json')
OUTPUT_REPORT_FILENAME = INPUT_JSON_FILENAME.replace('_cleaned.json', '_norm_report.txt')

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
    print(f"\n[DEBUG] Sending {field_name} to OpenAI for normalization...")
    print(f"[DEBUG] Raw values: {', '.join(values)}")
    
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
    
    result = json.loads(response.choices[0].message.content)
    print(f"[DEBUG] Normalization result: {json.dumps(result, indent=2)}\n")
    return result

def update_json_with_normalized_values(data, norm_maps):
    normalized_data = []
    for item in data:
        new_item = item.copy()
        for field, mapping in norm_maps.items():
            if isinstance(item.get(field), list):
                new_item[field] = [mapping.get(val, val) for val in item[field]]
        normalized_data.append(new_item)
    return normalized_data

def generate_normalization_report(norm_maps):
    report = []
    report.append("=== NORMALIZATION REPORT ===\n")
    
    for field, mapping in norm_maps.items():
        report.append(f"\n{field.upper()}\n{'-' * len(field)}\n")
        
        # Group by normalized terms
        normalized_groups = {}
        for original, normalized in mapping.items():
            if normalized not in normalized_groups:
                normalized_groups[normalized] = []
            normalized_groups[normalized].append(original)
        
        for normalized, originals in normalized_groups.items():
            if len(originals) > 1:  # Only show groups where terms were combined
                report.append(f"\nNormalized Term: {normalized}")
                report.append("Original Terms:")
                for term in sorted(originals):
                    report.append(f"  - {term}")
    
    return "\n".join(report)

def main():
    client = setup_openai()
    
    with open(INPUT_JSON_FILENAME, 'r', encoding='utf-8') as f:
        data = json.load(f)

    fields = ['keywords', 'institutions', 'specialities']
    normalization_maps = {}
    total_fields = len(fields)
    
    for idx, field in enumerate(fields, 1):
        print(f"\nProcessing {field}...")
        unique_values = get_unique_values(data, field)
        normalization_maps[field] = normalize_values(client, field, unique_values)
        print(f"Progress: {(idx/total_fields)*100:.1f}% complete")

    # Save normalization maps
    with open(OUTPUT_NORM_MAP_JSON, 'w', encoding='utf-8') as f:
        json.dump(normalization_maps, f, indent=2, ensure_ascii=False)
    print(f"\nNormalization maps saved to {OUTPUT_NORM_MAP_JSON}")

    # Generate and save report
    report = generate_normalization_report(normalization_maps)
    with open(OUTPUT_REPORT_FILENAME, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"Normalization report saved to {OUTPUT_REPORT_FILENAME}")

    # Apply normalizations and save result
    normalized_data = update_json_with_normalized_values(data, normalization_maps)
    with open(OUTPUT_JSON_NORM_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(normalized_data, f, indent=2, ensure_ascii=False)
    print(f"Normalized data saved to {OUTPUT_JSON_NORM_FILENAME}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Process interrupted by user.")
    except Exception as e:
        print(f"\n[ERROR] An error occurred: {str(e)}")