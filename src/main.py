from fastapi import FastAPI
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from google import genai

if not load_dotenv():
    print("Cannot load .env file")
    raise SystemExit


app = FastAPI()
client = genai.Client()

@app.get("/")
def root():
    return {"Hello": "There"}


class ApiOutput(BaseModel):
    confidence: int = Field(description="Confidence on whether the text is a likely scam or not")


interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Examine the below data and return whether it is likely to be a scam",
    response_format={
        "type": "text",
        "mime_type": "application/json",
        "schema": ApiOutput.model_json_schema()
    }
)

output = ApiOutput.model_validate_json(interaction.output_text)
print(output)
