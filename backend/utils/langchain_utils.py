# backend/utils/langchain_utils.py
from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from config import *
import logging
from fastapi import WebSocket
from .db_utils import (
    get_category_name, format_result, is_excluded, execute_search_query,
    get_toc_data, get_chunk_text_for_pages, get_document_id
)

logger = logging.getLogger(__name__)

def get_langchain_client():
    embeddings = AzureOpenAIEmbeddings(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_deployment=AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
        api_version=AZURE_OPENAI_API_VERSION,
    )

    llm = AzureChatOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_deployment=MODEL_GPT4o_DEPLOY_NAME,
        api_version=AZURE_OPENAI_API_VERSION,
        temperature=0.7,
        max_tokens=1024,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        streaming=True
    )

    return embeddings, llm

async def process_websocket_message_langchain(websocket: WebSocket, conn, data, embeddings, llm):
    try:
        question = data["question"]
        category = data.get("category")

        if not category:
            await websocket.send_json({"error": "Category is required"})
            return

        logger.debug(f"Processing question: {question[:50]}... in category: {category}")

        # Generate first AI response
        toc_data = get_toc_data(conn, category)
        first_response = await generate_first_ai_response(llm, toc_data, question, websocket)

        # Parse the first response to get PDF info
        pdf_info = parse_first_response(first_response, category)
        await websocket.send_json({"pdf_info": pdf_info})

        # Process search results
        question_vector = embeddings.embed_query(question)

        excluded_pages = [
            {
                'file_name': pdf['file_name'],
                'start_page': pdf['start_page'],
                'end_page': pdf['end_page']
            } for pdf in pdf_info
        ]

        manual_results, faq_results, manual_texts, faq_texts = await process_search_results(conn, question_vector, category, excluded_pages)

        if not manual_results and not faq_results:
            await websocket.send_json({"warning": "検索結果が見つかりませんでした。"})
        else:
            await websocket.send_json({"manual_results": manual_results})
            await websocket.send_json({"faq_results": faq_results})

        logger.debug(f"Sent search results for question: {question[:50]}... in category: {category}")

        # Generate final AI response
        chunk_texts = [
            get_chunk_text_for_pages(conn, get_document_id(conn, pdf['file_name'], category), pdf['start_page'], pdf['end_page'])
            for pdf in pdf_info
        ]
        if manual_texts or faq_texts or chunk_texts:
            await generate_final_ai_response(llm, chunk_texts, manual_texts, faq_texts, question, websocket)
        else:
            await websocket.send_json({"ai_response_chunk": "申し訳ありませんが、該当する情報が見つかりませんでした。"})
            await websocket.send_json({"ai_response_end": True})
            logger.info("No relevant information found for the query")

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        if websocket.client_state == WebSocket.STATE_CONNECTED:
            await websocket.send_json({"error": "An error occurred while processing your request"})

async def generate_first_ai_response(llm, toc_data, question, websocket: WebSocket):
    system_prompt = f"""
    以下の目次情報を参考に、ユーザーの質問に対して最も関連が高いと考えられる"PDFファイル名", "PDF開始ページ", "PDF終了ページ"を上位2件分を解答例の通りに適切に改行して回答して下さい。
    ただし、上位2件の内容は必ず同じ内容を重複して解答しないようにして下さい。

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

    chat_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{question}")
    ])

    chain = chat_prompt | llm | StrOutputParser()

    response = ""
    async for chunk in chain.astream({"question": question}):
        response += chunk
        await websocket.send_json({"first_ai_response_chunk": chunk})

    await websocket.send_json({"first_ai_response_end": True})
    return response

async def generate_final_ai_response(llm, chunk_texts, manual_texts, faq_texts, question, websocket: WebSocket):
    system_prompt = f"""
    以下の情報を参考に、ユーザーの質問に答えてください。

    参考文書(目次情報)：
    {' '.join(chunk_texts)}

    マニュアル情報:
    {' '.join(manual_texts)}

    FAQ情報:
    {' '.join(faq_texts)}
    """

    chat_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{question}")
    ])

    chain = chat_prompt | llm | StrOutputParser()

    try:
        async for chunk in chain.astream({"question": question}):
            await websocket.send_json({"ai_response_chunk": chunk})
    except Exception as e:
        logger.error(f"Error generating final AI response: {str(e)}")
        await websocket.send_json({"error": f"Error generating final AI response: {str(e)}"})
    finally:
        await websocket.send_json({"ai_response_end": True})

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
