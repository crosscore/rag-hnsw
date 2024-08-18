# backend/utils/websocket_utils.py
from fastapi import WebSocket
from openai import OpenAI, AzureOpenAI
from psycopg import sql
import logging
from .db_utils import execute_query, execute_search_query
from config import *

logger = logging.getLogger(__name__)

def get_openai_client():
    if ENABLE_OPENAI:
        return OpenAI(api_key=OPENAI_API_KEY)
    else:
        return AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION
        )

async def process_search_results(conn, question_vector, category, top_n):
    manual_results = execute_search_query(conn, question_vector, category, top_n, PDF_MANUAL_TABLE)
    faq_results = execute_search_query(conn, question_vector, category, top_n, PDF_FAQ_TABLE)

    formatted_manual_results = []
    formatted_faq_results = []
    manual_texts = []
    faq_texts = []

    for result in manual_results:
        formatted_result = format_manual_result(conn, result, category)
        formatted_manual_results.append(formatted_result)
        manual_texts.append(formatted_result['chunk_text'])

    for result in faq_results:
        formatted_result = format_faq_result(conn, result, category)
        formatted_faq_results.append(formatted_result)
        faq_texts.append(formatted_result['page_text'])

    formatted_manual_results.sort(key=lambda x: x['distance'])
    formatted_faq_results.sort(key=lambda x: x['distance'])

    return formatted_manual_results[:top_n], formatted_faq_results[:top_n], manual_texts, faq_texts

def format_manual_result(conn, result, category):
    document_table_id, chunk_no, document_page, chunk_text, distance = result
    file_path, file_name = get_document_info(conn, document_table_id)

    return {
        "file_name": str(file_name),
        "page": int(document_page),
        "chunk_text": str(chunk_text),
        "distance": float(distance),
        "category": category,
        "document_type": "manual",
        "link_text": f"/manual/{category}/{file_name}, p.{document_page}",
        "link": f"pdf/manual/{category}/{file_name}?page={document_page}",
    }

def format_faq_result(conn, result, category):
    document_table_id, document_page, faq_no, page_text, distance = result
    file_path, file_name = get_document_info(conn, document_table_id)

    return {
        "file_name": str(file_name),
        "page": int(document_page),
        "page_text": str(page_text),
        "distance": float(distance),
        "category": category,
        "document_type": "faq",
        "link_text": f"/faq/{category}/{file_name}, p.{document_page}",
        "link": f"pdf/faq/{category}/{file_name}?page={document_page}",
    }

def get_document_info(conn, document_table_id):
    doc_info = execute_query(conn, sql.SQL("""
        SELECT file_path, file_name FROM {} WHERE id = %s
    """).format(sql.Identifier(DOCUMENT_TABLE)), (document_table_id,))
    return doc_info[0] if doc_info else (None, None)

async def generate_ai_response(client, question, manual_texts, faq_texts, websocket: WebSocket):
    formatted_prompt = f"""
    ユーザーの質問に対して、参考文書を元に回答して下さい。

    ユーザーの質問：
    {question}

    参考文書(マニュアル)：
    {' '.join(manual_texts)}

    参考文書(Q&A):
    {' '.join(faq_texts)}
    """

    if ENABLE_OPENAI:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=1.00,
            max_tokens=250,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": formatted_prompt}
            ],
            stream=True
        )
    else:
        response = client.chat.completions.create(
            model=MODEL_GPT4o_DEPLOY_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": formatted_prompt}
            ],
            stream=True
        )

    try:
        for chunk in response:
            if chunk.choices and len(chunk.choices) > 0:
                if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                    content = chunk.choices[0].delta.content
                    if content:
                        await websocket.send_json({"ai_response_chunk": content})
            else:
                logger.warning("Received an empty chunk from OpenAI API")
    except Exception as e:
        logger.error(f"Error processing AI response: {str(e)}")
        await websocket.send_json({"error": "Error generating AI response"})
    finally:
        await websocket.send_json({"ai_response_end": True})
        logger.debug(f"Sent streaming AI response for question: {question[:50]}...")
