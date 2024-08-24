# backend/utils/websocket_utils.py
from fastapi import WebSocket
from openai import AzureOpenAI
from psycopg import sql
import logging
from .db_utils import execute_query, execute_search_query, get_document_id, get_chunk_text_for_pages
from config import *

logger = logging.getLogger(__name__)

def get_openai_client():
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION
    )

def parse_first_response(first_response):
    pdf_info = []
    lines = first_response.strip().split('\n')
    current_pdf = {}

    for line in lines:
        if line.startswith("PDFファイル名:"):
            if current_pdf:
                pdf_info.append(current_pdf)
            current_pdf = {"file_name": line.split(":")[1].strip()}
        elif line.startswith("PDF開始ページ:"):
            current_pdf["start_page"] = int(line.split(":")[1].strip())
        elif line.startswith("PDF終了ページ:"):
            current_pdf["end_page"] = int(line.split(":")[1].strip())

    if current_pdf:
        pdf_info.append(current_pdf)

    return pdf_info

async def process_search_results(conn, question_vector, category, excluded_pages):
    manual_results = execute_search_query(conn, question_vector, category, 50, PDF_MANUAL_TABLE)
    faq_results = execute_search_query(conn, question_vector, category, 50, PDF_FAQ_TABLE)

    formatted_manual_results = []
    formatted_faq_results = []
    manual_texts = []
    faq_texts = []
    unique_manual_pages = set()
    unique_faq_entries = set()

    for result in manual_results:
        formatted_result = format_manual_result(conn, result, category)
        page_key = (formatted_result['file_name'], formatted_result['page'])
        if not is_excluded(formatted_result, excluded_pages) and page_key not in unique_manual_pages:
            formatted_manual_results.append(formatted_result)
            manual_texts.append(formatted_result['chunk_text'])
            unique_manual_pages.add(page_key)
            if len(formatted_manual_results) == 4:
                break

    for result in faq_results:
        formatted_result = format_faq_result(conn, result, category)
        logger.debug(f"Formatted FAQ result: {formatted_result}")
        entry_key = (formatted_result['file_name'], formatted_result['page'], formatted_result['faq_no'])
        if entry_key not in unique_faq_entries:
            formatted_faq_results.append(formatted_result)
            faq_texts.append(formatted_result['chunk_text'])
            unique_faq_entries.add(entry_key)
            if len(formatted_faq_results) == 3:
                break

    formatted_manual_results.sort(key=lambda x: x['distance'])
    formatted_faq_results.sort(key=lambda x: x['distance'])

    logger.info(f"Found {len(formatted_manual_results)} unique manual results and {len(formatted_faq_results)} unique FAQ results")

    return formatted_manual_results, formatted_faq_results, manual_texts, faq_texts

def is_excluded(result, excluded_pages):
    for excluded in excluded_pages:
        if (result['file_name'] == excluded['file_name'] and
            excluded['start_page'] <= result['page'] <= excluded['end_page']):
            return True
    return False

def format_manual_result(conn, result, category):
    document_table_id, chunk_no, document_page, chunk_text, distance = result
    file_path, file_name = get_document_info(conn, document_table_id)
    category_name = next(name for name, value in BUSINESS_CATEGORY_MAPPING.items() if value == category)

    return {
        "file_name": str(file_name),
        "page": int(document_page),
        "chunk_text": str(chunk_text),
        "distance": float(distance),
        "category": category_name,
        "document_type": "manual",
        "link_text": f"/manual/{category_name}/{file_name}, p.{document_page}",
        "link": f"pdf/manual/{category_name}/{file_name}?page={document_page}",
    }

def format_faq_result(conn, result, category):
    document_table_id, document_page, faq_no, chunk_text, distance = result
    file_path, file_name = get_document_info(conn, document_table_id)
    category_name = next(name for name, value in BUSINESS_CATEGORY_MAPPING.items() if value == category)

    return {
        "file_name": str(file_name),
        "page": int(document_page),
        "faq_no": int(faq_no),
        "chunk_text": str(chunk_text),
        "distance": float(distance),
        "category": category_name,
        "document_type": "faq",
        "link_text": f"/faq/{category_name}/{file_name}, p.{document_page}",
        "link": f"pdf/faq/{category_name}/{file_name}?page={document_page}",
    }

def get_document_info(conn, document_table_id):
    doc_info = execute_query(conn, sql.SQL("""
        SELECT file_path, file_name FROM {} WHERE id = %s
    """).format(sql.Identifier(DOCUMENT_TABLE)), (document_table_id,))
    return doc_info[0] if doc_info else (None, None)

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

    pdf_info = parse_first_response(first_response)
    category_name = next((name for name, value in BUSINESS_CATEGORY_MAPPING.items() if value == category), None)
    
    chunk_texts = []
    excluded_pages = []
    for pdf in pdf_info:
        pdf['category'] = category_name
        # ドキュメントIDを取得
        doc_id = get_document_id(conn, pdf['file_name'], category)
        if doc_id:
            chunk_text = get_chunk_text_for_pages(conn, doc_id, pdf['start_page'], pdf['end_page'])
            chunk_texts.append(chunk_text)
        excluded_pages.append({
            'file_name': pdf['file_name'],
            'start_page': pdf['start_page'],
            'end_page': pdf['end_page']
        })
    
    await websocket.send_json({"pdf_info": pdf_info})

    return first_response, pdf_info, chunk_texts, excluded_pages

async def generate_ai_response(client, question, chunk_texts, manual_texts, faq_texts, websocket: WebSocket):
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
