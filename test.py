import openai

openai.api_key = "your-api-key"

prompt = """Bạn sẽ đóng vai một chuyên gia toán học và sử dụng function được cung cấp để giải quyết bài toán sau. Hãy trả về kết quả với định dạng cụ thể:
- Lời giải chi tiết phải nằm trong cặp thẻ: <solution></solution>.
- Đáp số cuối cùng phải nằm trong cặp thẻ: <result></result>.

### Function được cung cấp:
{function_definition}

### Bài toán:
"{question}"

Hãy giải bài toán này bằng cách sử dụng function trên và trả về đúng định dạng yêu cầu. Không thêm thông tin ngoài các thẻ <solution> và <result>."""

def classify_or_solve(question, topics):
    # Bước 1: Phân loại topic
    classify_prompt = f"""
    Dựa trên danh sách các topic sau: {topics}.
    Hãy xác định topic phù hợp nhất với câu hỏi: "{question}".
    Nếu không rõ, hãy trả lời rằng "NO" và giải bài toán luôn.
    """
    classify_response = openai.ChatCompletion.create(
        model="gpt-4", messages=[{"role": "user", "content": classify_prompt}]
    )
    classification = classify_response["choices"][0]["message"]["content"]

    # Kiểm tra kết quả phân loại
    if "Không chắc chắn" in classification or "không biết" in classification.lower():
        # Bước 2: Giải bài toán
        solve_prompt = f"""
        Dựa trên câu hỏi: "{question}", hãy giải bài toán này và cung cấp câu trả lời chi tiết.
        """
        solve_response = openai.ChatCompletion.create(
            model="gpt-4", messages=[{"role": "user", "content": solve_prompt}]
        )
        return {
            "action": "solved",
            "result": solve_response["choices"][0]["message"]["content"],
        }
    else:
        
        return {"action": "classified", "topic": classification}


# Danh sách các topic
topics = ["calculus", "geometry", "algebra", "statistics", "misc"]

# Câu hỏi cần xử lý
question = "What is the derivative of x^2 + 3x?"

# Gọi hàm xử lý
response = classify_or_solve(question, topics)

# Kiểm tra kết quả
if response["action"] == "classified":
    print(f"Topic được phân loại: {response['topic']}")
elif response["action"] == "solved":
    print(f"Kết quả giải bài toán: {response['result']}")
