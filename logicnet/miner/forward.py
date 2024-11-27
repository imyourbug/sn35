from logicnet.protocol import LogicSynapse
import openai
import bittensor as bt
import traceback
import re
from helpers.helper import get_function_definition
from logicnet.validator.challenger.math_generator.topics import A as topics
from logicnet.validator.challenger.math_generator.topics import (
    TOPICS,
    NEED_TO_GET_FUNCTION_TOPICS,
)

GET_FUNCTION_DEFINITION_TEMPLATE = """Tôi có 1 array dạng (subtopic, topic):
TOPICS = {all_topics}

Và 1 câu hỏi: {question}
Câu hỏi trên thuộc topic và subtopic nào, giá trị trả ra phải trong array trên, trả ra vị trí phần tử tương ứng của mảng TOPICS và đưa vào trong thẻ <result></result> (ví dụ <result>TOPICS[1]</result>), không trả ra gì thêm. Nếu không rõ, hãy trả lời rằng 'NO'."""

GET_LOGIC_ANSWER_TEMPLATE = """Hãy giải quyết bài toán sau tuân theo đúng như giải thuật trong function bên dưới. Give me the final short answer as a sentence. Don't reasoning anymore, just say the final answer in math latex:
- Bài toán: {question}
- Function:
```{function_definition}```"""


def solve(
    synapse: LogicSynapse, openai_client: openai.AsyncOpenAI, model: str
) -> LogicSynapse:
    try:
        bt.logging.info(f"Received synapse: {synapse}")
        logic_question: str = synapse.logic_question

        # Get the function definition
        messages = [
            {
                "role": "user",
                "content": GET_FUNCTION_DEFINITION_TEMPLATE.format(
                    all_topics=topics,
                    question=logic_question,
                ),
            },
        ]
        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2048,
            temperature=0.7,
        )
        answer = response.choices[0].message.content
        function_definition = None
        if "NO" not in answer:
            index = int(re.search(r'\[([0-9]+)\]', answer).group(1))
            if index < len(TOPICS):
                topic_and_subtopic = TOPICS[index]
                print(f"topic_and_subtopic: {topic_and_subtopic}")
                # Extracted values
                subtopic = topic_and_subtopic["subtopic"]
                topic = topic_and_subtopic["topic"]
                print(f"subtopic: {subtopic}")
                print(f"topic: {topic}")
                if (subtopic, topic) in NEED_TO_GET_FUNCTION_TOPICS:
                    try:
                        function_definition = get_function_definition(subtopic, topic)
                    except Exception as e:
                        print(f"Exception: {e}")

        # Get logic_reasoning
        messages = [
            {"role": "user", "content": logic_question},
        ]
        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2048,
            temperature=0.7,
        )
        synapse.logic_reasoning = response.choices[0].message.content

        # Get logic_answer
        if function_definition is not None:
            print(f"Got function_definition: {function_definition}")
            messages = [
                {
                    "role": "user",
                    "content": GET_LOGIC_ANSWER_TEMPLATE.format(
                        function_definition=function_definition,
                        question=logic_question,
                    ),
                },
            ]
        else:
            print(f"Cannot get function_definition: {function_definition}")
            messages.extend(
                [
                    {"role": "assistant", "content": synapse.logic_reasoning},
                    {
                        "role": "user",
                        "content": "Give me the final short answer as a sentence. Don't reasoning anymore, just say the final answer in math latex.",
                    },
                ]
            )

        print(f"messages: {messages}")
        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=512,
            temperature=0.7,
        )
        synapse.logic_answer = response.choices[0].message.content

        bt.logging.info(f"Logic answer: {synapse.logic_answer}")
        bt.logging.info(f"Logic reasoning: {synapse.logic_reasoning}")
        return synapse
    except Exception as e:
        bt.logging.error(f"Error in forward: {e}")
        traceback.print_exc()


def extract_code_block(text):
    # Define the regular expression pattern for code blocks
    pattern = r"```python(.*?)```"

    # Find all matches of the pattern in the text
    matches = re.findall(pattern, text, re.DOTALL)

    return matches
