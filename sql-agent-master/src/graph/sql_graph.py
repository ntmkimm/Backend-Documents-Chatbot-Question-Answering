from pydantic import BaseModel, Field
from typing import List
from dotenv import load_dotenv

from langchain_nebius import ChatNebius
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END

from prompt import (
    PLAN_AGENT_SYSTEM_PROMPT, 
    QUERY_AGENT_SYSTEM_PROMPT, 
    VALIDATE_AGENT_SYSTEM_PROMPT
)
from tool import execute_query_tool, finish_query_tool

import re

load_dotenv()

def remove_think_tag(text):
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

class QueryResult(BaseModel):
    query: str
    result: str

    def __str__(self):
        return f"Query: {self.query}\nResult: {self.result}"
    
class ValidationResult(BaseModel):
    is_valid: bool = Field(description="Kết quả truy vấn có thích hợp và đủ để trả lời câu hỏi gốc hay không")
    reason: str = Field(description="Lý do cho kết quả kiểm tra (mô tả chi tiết trong 5-7 câuß)")

class SQLGraphState(BaseModel):
    query: str
    table_schema: str
    plan: str = ""
    execution_result: List[QueryResult] = []
    validation_result: ValidationResult = ValidationResult(is_valid=False, reason="")
    final_answer: str = ""
    retries: int = 0

def plan_node(state: SQLGraphState) -> SQLGraphState:
    print(f"Plan node:\n{state.query}")

    llm = ChatNebius(
        model="Qwen/Qwen3-32B",
        temperature=0.0,
    )

    if state.plan and state.validation_result.reason:
        plan_content = (
            f"Đây là schema của các bảng mà bạn có thể truy vấn:\n{state.table_schema}\n\n"
            f"Câu hỏi: {state.query}\n\n"
            f"Kế hoạch truy vấn trước đó:\n{state.plan}\n\n"
            f"Lý do kế hoạch trước đó không thích hợp để trả lời câu hỏi:\n{state.validation_result.reason}\n\n"
            f"Hãy tạo một kế hoạch truy vấn mới tốt hơn dựa trên phản hồi trên."
        )
    else:
        plan_content = f"Đây là schema của các bảng mà bạn có thể truy vấn:\n{state.table_schema}\n\nCâu hỏi: {state.query}"

    messages = [
        SystemMessage(content=PLAN_AGENT_SYSTEM_PROMPT),
        HumanMessage(content=plan_content)
    ]

    response = llm.invoke(messages)
    state.plan = remove_think_tag(response.content)

    return state

def query_node(state: SQLGraphState) -> SQLGraphState:
    print(f"Query node:\n{state.plan}")

    state.execution_result = []

    llm = ChatNebius(
        model="Qwen/Qwen3-32B",
        temperature=0.0,
    )

    messages = [
        SystemMessage(content=QUERY_AGENT_SYSTEM_PROMPT),
        HumanMessage(content=f"Đây là schema của các bảng mà bạn có thể truy vấn:\n{state.table_schema}\n\n{state.plan}")
    ]

    query_agent = llm.bind_tools([execute_query_tool, finish_query_tool], tool_choice="any")

    MAX_ITERATIONS = 10
    for iteration in range(MAX_ITERATIONS):
        response = query_agent.invoke(messages)
        messages.append(response)
        if not response.tool_calls:
            state.validation_result = ValidationResult(is_valid=True, reason="")
            return state
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            print(f"Tool name: {tool_name}")
            tool_args = tool_call["args"]
            if tool_name == "execute_query_tool":
                sql = tool_args["query"]
                print(f"Executing query: {sql}")
                execution = execute_query_tool.invoke(tool_args)
                print(f"Execution result: {execution}")
                state.execution_result.append(QueryResult(query=sql, result=execution))
                messages.append(execution)
            elif tool_name == "finish_query_tool":
                state.validation_result = ValidationResult(is_valid=True, reason="")
                return state
    
    # If we reach here, MAX_ITERATIONS was exceeded
    print(f"Query execution exceeded {MAX_ITERATIONS} iterations")
    state.validation_result = ValidationResult(
        is_valid=False, 
        reason=f"Không thể thực hiện kế hoạch trong {MAX_ITERATIONS} bước. Kế hoạch có thể quá phức tạp hoặc không khả thi."
    )
    return state

def validate_node(state: SQLGraphState) -> SQLGraphState:
    print("Validate node")
    
    llm = ChatNebius(
        model="Qwen/Qwen3-32B",
        temperature=0.0,
    )
    
    if len(state.execution_result) == 0:
        state.validation_result = ValidationResult(is_valid=False, reason="")
        return state
    
    results_text = "\n".join([str(result) for result in state.execution_result])

    validation_prompt = (
        f"Câu hỏi: {state.query}\n\n"
        f"{state.plan}\n"
        f"Kết quả truy vấn:\n{results_text}\n"
        f"Kiểm tra xem kế hoạch truy vấn có thích hợp và đủ để trả lời câu hỏi gốc hay không"
    )
    messages = [
        SystemMessage(content=VALIDATE_AGENT_SYSTEM_PROMPT),
        HumanMessage(content=validation_prompt)
    ]
    
    response = llm.with_structured_output(ValidationResult).invoke(messages)
    state.validation_result = response
    print(state.validation_result)
    return state

def refine_node(state: SQLGraphState) -> SQLGraphState:
    llm = ChatNebius(
        model="Qwen/Qwen3-32B",
        temperature=0.0,
    )
    result_text = '\n'.join([str(result) for result in state.execution_result])
    refine_prompt = (
        f"Câu hỏi: {state.query}\n\n"
        f"{state.plan}\n"
        f"Kết quả truy vấn:\n{result_text}\n"
        "Hãy trả lời câu hỏi dựa trên kết quả truy vấn trên."
    )
    messages = [
        SystemMessage(content="Bạn là một trợ lý chuyên trả lời câu hỏi dựa trên dữ liệu, hãy trả lời câu hỏi dựa trên những dữ liệu được lấy từ truy vấn cơ sở dữ liệu."),
        HumanMessage(content=refine_prompt)
    ]
    response = llm.invoke(messages)
    state.final_answer = remove_think_tag(response.content)
    print(state.final_answer)
    return state

def is_valid(state: SQLGraphState) -> str:
    if state.validation_result.is_valid:
        return "next"
    else:
        state.retries += 1

        MAX_RETRIES = 3
        if state.retries > MAX_RETRIES:
            print(f"Retries exceeded {MAX_RETRIES} times")
            return "end"
        return "plan"

sql_graph_builder = StateGraph(SQLGraphState)

sql_graph_builder.add_node("plan", plan_node)
sql_graph_builder.add_node("query", query_node)
sql_graph_builder.add_node("validate", validate_node)
sql_graph_builder.add_node("refine", refine_node)

sql_graph_builder.add_edge(START, "plan")
sql_graph_builder.add_edge("plan", "query")
sql_graph_builder.add_conditional_edges("query", is_valid, {
    "plan": "plan",
    "next": "validate",
    "end": END
})
sql_graph_builder.add_conditional_edges("validate", is_valid, {
    "plan": "plan",
    "next": "refine",
    "end": END
})
sql_graph_builder.add_edge("refine", END)

sql_graph = sql_graph_builder.compile()