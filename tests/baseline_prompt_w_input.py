import boto3
import pandas as pd
from datetime import datetime
from tests.evaluation import evaluate_response

from dotenv import load_dotenv
import os
load_dotenv()  # loads .env into environment variables

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
    "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "openai.gpt-oss-120b-1:0",
    "meta.llama3-1-70b-instruct-v1:0"
]

today = datetime.today().strftime("%Y-%m-%d")
# system_instructions = (
#     "You are a concise, helpful social worker assistant providing assistance to users who have lost their job in California. "
#     "Ensure that your responses are at a simple reading level; do not include this system instruction in your response. "
#     "Explain program basics, eligibility, steps, necessary documents, timelines; include county-variation note. "
#     "Suggest other programs that may be relevant even if not directly asked given the context. "
#     "Do not guarantee approval or benefit amounts. Do not generalize county-specific rules without stating they vary by county. "
#     "Do not provide outdated income limits or timelines. Do not give legal/financial advice beyond program guidance. "
#     "Do not fabricate citations or sources. Use empathetic language in your response. "
#     "Format your responses using Markdown syntax: use **bold** for emphasis, ## for section headers, "
#     "- or * for bullet lists, | for tables, and [link text](url) for links. "
#     "Use clear section headers (##) to organize information and tables when presenting structured data. "
#     f"Today's date is {today}. "
#     "Do not answer questions unrelated to social services or benefits programs in California. "
#     "Do not mention system instructions in your response. "
# )
system_instructions = (
    "You are a concise, helpful social worker assistant providing assistance to users who have lost their job in California. "
    "Format your responses using Markdown syntax: use **bold** for emphasis, ## for section headers, "
    "- or * for bullet lists, | for tables, and [link text](url) for links. "
    "Use clear section headers (##) to organize information and tables when presenting structured data. "
    f"Today's date is {today}. "
)

df_input = pd.read_csv("tests/gold_dataset.csv")
prompts_df = df_input.drop_duplicates(subset=["user_question"], keep="first")
user_prompts = prompts_df["user_question"].dropna().tolist()
id_map = dict(zip(prompts_df["user_question"], prompts_df["id"]))
gold_by_id = df_input.set_index("id")

# Create Bedrock client once
client = boto3.client("bedrock-runtime", region_name=REGION)

# Initialize results list
results = []

# Loop through questions by model
model_num = 1
for MODEL_ID in MODELS:
    print("Working on", MODEL_ID)
    for user_prompt in user_prompts:
        messages = [{"role": "user", "content": [{"text": user_prompt}]}]

        response = client.converse(
            modelId=MODEL_ID,
            system=[{"text": system_instructions}],
            messages=messages,
            inferenceConfig={
                "maxTokens": 2048,
                "temperature": 0.0,
                "topP": 1.0
            }
        )

        model_answer = "".join(
            part.get("text", "") for part in response["output"]["message"]["content"]
        )

        # Append a row to the results list
        row_id = id_map.get(user_prompt)
        gold_context = ""
        gold_response = ""
        if row_id is not None and row_id in gold_by_id.index:
            gold_row = gold_by_id.loc[row_id]
            # gold_row is a pandas Series
            gold_context = str(gold_row.get("gold_context", ""))
            gold_response = str(gold_row.get("gold_response", ""))

        # Evaluate this response using our shared evaluation helper
        eval_metrics = evaluate_response(
            user_prompt=user_prompt,
            model_answer=model_answer,
            gold_context=gold_context,
            gold_response=gold_response,
        )

        row = {
            "model_num": model_num,
            "model_id": MODEL_ID,
            "user_prompt": user_prompt,
            "id": row_id,
            "gold_context": gold_context,
            "gold_response": gold_response,
            "model_answer": model_answer,
        }
        if isinstance(eval_metrics, dict):
            row.update(eval_metrics)

        results.append(row)

    model_num += 1

# Convert list of dicts to DataFrame
df = pd.DataFrame(results)

# Save to CSV
output_path = f"tests/{today}_baseline_model_responses.csv"
df.to_csv(output_path, index=False)
print(f"✅ Saved results to {output_path}")
