import boto3
import pandas as pd

REGION = "us-west-2"

# Check models available for on-demand inference
# control_client = boto3.client("bedrock", region_name=REGION)
# on_demand_list = control_client.list_foundation_models(
#     byInferenceType="ON_DEMAND"
# )
# for model in on_demand_list["modelSummaries"]:
#     print(model["modelId"], model.get("inferenceTypesSupported"))

# List of selected on-demand inference models
MODELS = [
    # "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "meta.llama3-1-70b-instruct-v1:0",
    "openai.gpt-oss-120b-1:0",
    "mistral.mistral-7b-instruct-v0:2"
]

system_instructions = (
    "You are a concise, helpful social worker assistant providing assistance to users who have lost their job in California at a 5th-grade reading level."
)

user_prompts = [
    "Which government programs or benefits am I currently eligible for?",
    "How do I apply for benefits and what documents do I need?",
    "Are there deadlines or waiting periods I should know about for applying or maintaining eligibility?",
    "Can you explain how unemployment insurance works and how to maximize what I can receive?",
    "If I've done freelance or contract work, does that affect my unemployment eligibility or benefit amount?",
    "What options are available if I need help with rent, utilities, or food?",
    "Am I eligible for Medicaid or other healthcare assistance?",
    "Can I receive multiple types of assistance at the same time?",
    "If I start earning money again, what should I do?",
    "Are there programs that I could qualify for to help me get another job?"
]

# Create Bedrock client once
client = boto3.client("bedrock-runtime", region_name=REGION)

# Initialize results list
results = []

# Loop through questions by model
model_num = 1
for MODEL_ID in MODELS:
    print("Working on", MODEL_ID)
    for user_prompt in user_prompts:
        combined_prompt = f"{system_instructions}\n\n{user_prompt}"
        messages = [{"role": "user", "content": [{"text": combined_prompt}]}]

        response = client.converse(
            modelId=MODEL_ID,
            messages=messages,
            inferenceConfig={
                "maxTokens": 512,
                "temperature": 0.3,
                "topP": 0.9
            }
        )

        model_answer = "".join(
            part.get("text", "") for part in response["output"]["message"]["content"]
        )

        # Append a row to the results list
        results.append({
            "model_num": model_num,
            "model_id": MODEL_ID,
            "user_prompt": user_prompt,
            "model_answer": model_answer
        })

    model_num += 1

# Convert list of dicts to DataFrame
df = pd.DataFrame(results)

# Save to CSV
output_path = "baseline_model_responses.csv"
df.to_csv(output_path, index=False)
print(f"✅ Saved results to {output_path}")
