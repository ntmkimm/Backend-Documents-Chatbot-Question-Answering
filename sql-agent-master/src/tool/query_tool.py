from typing import Annotated

from langchain_core.tools import tool

from database.db import execute_query_safe

@tool
def execute_query_tool(
        query: Annotated[str, "Câu truy vấn SQL cần thực thi"]
    ) -> str:
    """Thực thi một truy vấn SQL"""
    success, result, error = execute_query_safe(query)
    
    if success:
        if len(result) == 0:
            return "Không có kết quả"
        else:
            return str(result)
    else:
        return f"Lỗi khi thực thi truy vấn: {error}"
    
@tool
def finish_query_tool() -> str:
    """Thông báo đã hoàn thành kế hoạch truy vấn"""
    return "Đã hoàn thành kế hoạch truy vấn"