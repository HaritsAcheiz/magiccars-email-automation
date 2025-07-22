import azure.functions as func
import logging
from openai import AzureOpenAI
import os
import json

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="helloworld", methods=["GET"])
def http_get(req: func.HttpRequest) -> func.HttpResponse:
    name = req.params.get("name", "World")

    logging.info(f"Processing GET request. Name: {name}")

    return func.HttpResponse(f"Hello, {name}!")


@app.route(route="replyemail", methods=["POST"])
def http_post(req: func.HttpRequest) -> func.HttpResponse:
    try:
        openai_client = AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version="2024-02-01"
        )
        logging.info("Azure OpenAI client initialized successfully.")
    except KeyError as e:
        logging.error(f"Missing environment variable: {e}. Please ensure AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT are set.")
        openai_client = None
        return func.HttpResponse(f"Missing environment variable: {e}. Please ensure AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT are set.")
    except Exception as e:
        logging.error(f"Error initializing Azure OpenAI client: {e}")
        openai_client = None
        return func.HttpResponse(f"Error initializing Azure OpenAI client: {e}")

    logging.info('Python HTTP trigger function processed a request.')

    if openai_client is None:
        return func.HttpResponse(
            "Azure OpenAI client not initialized. Please check environment variables and function logs.",
            status_code=500
        )

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            "Please pass a JSON body in the request.",
            status_code=400
        )
    except Exception as e:
        logging.error(f"Error parsing request body: {e}")
        return func.HttpResponse(
            f"Error processing request. Ensure valid JSON is provided.",
            status_code=400
        )

    original_email_subject = req_body.get('subject')
    original_email_body = req_body.get('body')
    sender_name = req_body.get('sender_name')
    recipient_name = req_body.get('recipient_name')
    sender_email = req_body.get('sender_email')

    if not all([original_email_subject, original_email_body, sender_name]):
        return func.HttpResponse(
            "Please provide 'subject', 'body', and 'sender_name' in the request body.",
            status_code=400
        )

    try:
        prompt_messages = [
            {"role": "system", "content": "You are a helpful assistant that drafts professional email replies. Be concise and polite."},
            {"role": "user", "content": f"The following is an email from {sender_name} (email: {sender_email}) with the subject '{original_email_subject}' and body:\n\n---\n{original_email_body}\n---\n\nDraft a concise and polite reply. Start the reply with 'Dear {sender_name},'"},
        ]

        if recipient_name:
            prompt_messages[1]["content"] += f"\n\nSign off as {recipient_name}."

        logging.info(f"Sending prompt to Azure OpenAI: {prompt_messages}")

        response = openai_client.chat.completions.create(
            model=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
            messages=prompt_messages,
            temperature=0.7,
            max_tokens=250,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
            stop=None
        )

        reply_content = response.choices[0].message.content.strip()
        logging.info(f"Generated reply: {reply_content}")

        reply_subject = f"Re: {original_email_subject}"

        return_payload = {
            "reply_subject": reply_subject,
            "reply_body": reply_content
        }

        return func.HttpResponse(
            json.dumps(return_payload),
            mimetype="application/json",
            status_code=200
        )

    except Exception as e:
        logging.error(f"Error generating reply: {e}")
        return func.HttpResponse(
            f"An error occurred while generating the reply: {e}",
            status_code=500
        )
