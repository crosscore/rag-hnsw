# backend/utils/websocket_utils.py
from openai import AzureOpenAI
import logging
from fastapi import WebSocket
from .db_utils import get_category_name, format_result, is_excluded
from config import *

logger = logging.getLogger(__name__)

def get_openai_client():
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION
    )

async def generate_first_ai_response(client, question, toc_data, websocket: WebSocket, category, conn):
    prompt_1st = f"""
    ユーザーの質問に対して、最も関連が高いと考えられる"PDFファイル名", "PDF開始ページ", "PDF終了ページ"を以下の目次情報を参考に、上位2件分を解答例の通りに適切に改行して回答して下さい。
    ただし、上位2件の内容は必ず同じ内容を重複して解答しないようにして下さい。

    ユーザーの質問：
    {question}

    カテゴリに存在する全PDFファイルの目次情報:
    {toc_data}

    解答例：
    PDFファイル名: filename1.pdf
    PDF開始ページ: 10
    PDF終了ページ: 15

    PDFファイル名: filename2.pdf
    PDF開始ページ: 5
    PDF終了ページ: 7
    """

    response = client.chat.completions.create(
        model=MODEL_GPT4o_DEPLOY_NAME,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt_1st}
        ],
        stream=True
    )

    first_response = ""
    try:
        for chunk in response:
            if chunk.choices and len(chunk.choices) > 0:
                if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                    content = chunk.choices[0].delta.content
                    if content:
                        first_response += content
                        await websocket.send_json({"first_ai_response_chunk": content})
            else:
                logger.warning("Received an empty chunk from OpenAI API")
    except Exception as e:
        logger.error(f"Error processing AI response: {str(e)}")
        await websocket.send_json({"error": "Error generating first AI response"})
    finally:
        await websocket.send_json({"first_ai_response_end": True})
        logger.debug(f"Sent streaming first AI response for question: {question[:50]}...")

    return first_response

async def generate_final_ai_response(client, question, chunk_texts, manual_texts, faq_texts, websocket: WebSocket):
    prompt_2nd = f"""
    ユーザーの質問に対して、以下の参考文書を元に回答して下さい。

    ユーザーの質問：
    {question}

    参考文書(目次情報)：
    {' '.join(chunk_texts)}

    参考文書(マニュアル)：
    {' '.join(manual_texts)}

    参考文書(Q&A):
    {' '.join(faq_texts)}
    """

    response = client.chat.completions.create(
        model=MODEL_GPT4o_DEPLOY_NAME,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt_2nd}
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

def parse_first_response(first_response, category):
    pdf_info = []
    lines = first_response.strip().split('\n')
    current_pdf = {}

    category_name = get_category_name(int(category))

    for line in lines:
        if line.startswith("PDFファイル名:"):
            if current_pdf:
                pdf_info.append(current_pdf)
            file_name = line.split(":")[1].strip()
            current_pdf = {
                "file_name": file_name,
                "category": category_name,
                "link_text": f"/manual/{category_name}/{file_name}"
            }
        elif line.startswith("PDF開始ページ:"):
            current_pdf["start_page"] = int(line.split(":")[1].strip())
        elif line.startswith("PDF終了ページ:"):
            current_pdf["end_page"] = int(line.split(":")[1].strip())

    if current_pdf:
        pdf_info.append(current_pdf)

    for pdf in pdf_info:
        pdf["link"] = f"pdf/manual/{pdf['category']}/{pdf['file_name']}?start_page={pdf['start_page']}&end_page={pdf['end_page']}"
        pdf["link_text"] += f", p.{pdf['start_page']}-p.{pdf['end_page']}"

    return pdf_info

async def process_search_results(conn, question_vector, category, excluded_pages):
    manual_results = execute_search_query(conn, question_vector, category, 50, PDF_MANUAL_TABLE)
    faq_results = execute_search_query(conn, question_vector, category, 50, PDF_FAQ_TABLE)

    formatted_manual_results = []
    formatted_faq_results = []
    manual_texts = []
    faq_texts = []

    for result in manual_results:
        formatted_result = format_result(conn, result, category, "manual")
        if not is_excluded(formatted_result, excluded_pages):
            formatted_manual_results.append(formatted_result)
            manual_texts.append(formatted_result['chunk_text'])
            if len(formatted_manual_results) == 4:
                break

    for result in faq_results:
        formatted_result = format_result(conn, result, category, "faq")
        if not is_excluded(formatted_result, excluded_pages):
            formatted_faq_results.append(formatted_result)
            faq_texts.append(formatted_result['chunk_text'])
            if len(formatted_faq_results) == 3:
                break

    return formatted_manual_results, formatted_faq_results, manual_texts, faq_texts
