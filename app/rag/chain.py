from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableBranch, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory

def format_docs(docs):
    formatted = []
    for doc in docs:
        page = doc.metadata.get("source_page", "Unknown")
        formatted.append(f"[Page {page}] {doc.page_content}")
    return "\n\n".join(formatted)

def build_conversational_rag_chain(
    *,
    groq_api_key: str,
    model_name: str,
    temperature: float,
    hybrid_retriever,
    get_session_history,
):
    llm = ChatGroq(
        groq_api_key=groq_api_key,
        model_name=model_name,
        temperature=temperature,
    )

    contextualize_q_system_prompt = """Given a chat history and the latest user question 
which might reference context in the chat history, formulate a standalone question 
which can be understood without the chat history. Do NOT answer the question, 
just reformulate it if needed and otherwise return it as is."""

    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
        ]
    )

    condense_question_chain = contextualize_q_prompt | llm | StrOutputParser()

    history_aware_retriever = RunnableBranch(
        (lambda x: bool(x.get("chat_history")), condense_question_chain | hybrid_retriever),
        (lambda x: x["input"]) | hybrid_retriever,
    )

    qa_system_prompt = """You are an assistant for question-answering tasks. 
Use the following pieces of retrieved context to answer the question. 
If you don't know the answer, just say that you don't know. 
Use three sentences maximum and keep the answer concise.

{context}"""

    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", qa_system_prompt),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
        ]
    )

    rag_chain = (
        RunnablePassthrough.assign(context=history_aware_retriever | format_docs)
        | qa_prompt
        | llm
        | StrOutputParser()
    )

    return RunnableWithMessageHistory(
        rag_chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )