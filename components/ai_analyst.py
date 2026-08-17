"""AI Analyst chat tab."""

import streamlit as st

from utils.llm_agent import (
    LLMServiceError,
    chat_response,
    groq_is_configured,
    prepare_portfolio_context,
)
from utils.market_data import recent_performance

RECENT_TERMS = ("today", "recent", "month", "week", "movement", "moving", "down", "up", "performed")


def render(transactions, holdings, metrics, portfolio_result, xirr) -> None:
    st.subheader("AI analyst")
    if transactions is None or holdings is None or metrics is None:
        st.info("Upload a valid transaction CSV in the Data Upload tab first.")
        return
    if not groq_is_configured():
        st.warning("Set GROQ_API_KEY in .env or your environment to use chat.")
        return
    st.caption("Answers use your calculated portfolio data. They are analytical observations, not financial advice.")
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    question = st.chat_input("Ask about your portfolio or trading history")
    if not question:
        return
    st.session_state.chat_messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    recent = None
    if any(term in question.lower() for term in RECENT_TERMS):
        with st.spinner("Retrieving recent prices before analysis…"):
            recent = recent_performance(tuple(holdings["ticker"]), "1mo")
    context = prepare_portfolio_context(
        transactions, holdings, metrics, portfolio_result.realized_sales, xirr, recent
    )
    with st.chat_message("assistant"):
        try:
            with st.spinner("Analyzing your portfolio…"):
                answer = chat_response(context, st.session_state.chat_messages)
            st.markdown(answer)
        except LLMServiceError as exc:
            answer = str(exc)
            st.error(answer)
    st.session_state.chat_messages.append({"role": "assistant", "content": answer})
