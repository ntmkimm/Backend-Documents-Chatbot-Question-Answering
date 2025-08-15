from graph import sql_graph
from prompt import (
    HR_EMPLOYEE_SCHEMA,
    COMPANY_SCHEMA,
    FIFA_WC_2022_SCHEMA,
    LAPTOP_PRICES_SCHEMA,
    YOUTUBE_INFLUENCERS_SCHEMA
)
from typing import List, Dict, Any

def run_sql_graph_questions(questions: List[str], schema: str) -> List[Dict[str, Any]]:
    """
    Run SQL graph for a list of questions with a given schema.
    
    Args:
        questions: List of questions to process
        schema: Database schema to use for queries
        
    Returns:
        List of dictionaries containing results for each question
    """
    results = []
    
    for i, question in enumerate(questions, 1):
        print(f"\n{'='*50}")
        print(f"Question {i}: {question}")
        print(f"{'='*50}")
        
        try:
            result = sql_graph.invoke({
                "query": question,
                "table_schema": schema
            })
            
            question_result = {
                "question_number": i,
                "question": question,
                "final_answer": result["final_answer"],
                "plan": result["plan"],
                "execution_results": result["execution_result"],
                "validation_result": result["validation_result"],
                "retries": result["retries"]
            }
            
            results.append(question_result)
            
            print(f"\nFinal Answer for Question {i}:")
            print(result["final_answer"])
            print("\n" + "-"*50)
            
        except Exception as e:
            error_result = {
                "question_number": i,
                "question": question,
                "error": str(e),
                "final_answer": "",
                "plan": "",
                "execution_results": [],
                "validation_result": None,
                "retries": 0
            }
            results.append(error_result)
            
            print(f"\nError processing Question {i}: {str(e)}")
            print("\n" + "-"*50)
    
    return results

def main():
    # Company questions
    company_questions = [
        "Số lượng đơn hàng nhiều nhất mà một nhà cung cấp từng có là bao nhiêu?",
        "Sản phẩm có thời gian giao trung bình lâu nhất thuộc nhà sản xuất nào?",
        "Phương thức vận chuyển nào được sử dụng nhiều nhất?",
        "Nhà cung cấp nào có nhiều đơn hàng bị trễ nhất?",
        "Ước tính khối lượng của đơn hàng lớn nhất dựa trên phí vận chuyển và phương thức vận chuyển?",
        "Nhà cung cấp nào có tổng giá trị đơn hàng cao nhất đối với các sản phẩm có thời gian giao hàng trung bình lớn hơn 30 ngày và đã giao đủ hàng?"
    ]
    
    print("Processing Company Questions:")
    company_results = run_sql_graph_questions(company_questions, COMPANY_SCHEMA)
    
    # Print summary of results
    print("\n" + "="*80)
    print("SUMMARY OF RESULTS:")
    print("="*80)
    for result in company_results:
        print(f"\nQuestion {result['question_number']}: {result['question']}")
        if 'error' in result and result['error']:
            print(f"Error: {result['error']}")
        else:
            print(f"Answer: {result['final_answer']}")

if __name__ == "__main__":
    main()