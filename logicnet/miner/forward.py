from logicnet.protocol import LogicSynapse
import openai
import bittensor as bt
import traceback
import re
from helpers.helper import get_function_definition
from logicnet.validator.challenger.math_generator.topics import A as topics

GET_FUNCTION_DEFINITION_TEMPLATE = """Tôi có 1 array gồm topic và subtopic dạng:
{all_topics}

Và 1 câu hỏi: {question}
Câu hỏi trên thuộc topic và subtopic nào, hãy cân nhắc thật kỹ vì có nhiều topic tương tự nhau dễ gây nhầm lẫn, chỉ trả ra kết quả dạng "subtopic, topic", không trả ra gì thêm."""

GET_LOGIC_ANSWER_TEMPLATE = """Hãy giải quyết bài toán sau tuân theo đúng như giải thuật trong function bên dưới. Give me the final short answer as a sentence. Don't reasoning anymore, just say the final answer in math latex:
- Bài toán: {question}
- Function:
```{function_definition}```"""


async def solve(
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
        response = await openai_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2048,
            temperature=0.7,
        )
        topic_and_subtopic = response.choices[0].message.content.split(",")
        subtopic = topic_and_subtopic[0].strip()
        topic = topic_and_subtopic[1].strip()
        function_definition = get_function_definition(subtopic, topic)
        # Get logic_reasoning
        messages = [
            {"role": "user", "content": logic_question},
        ]
        response = await openai_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2048,
            temperature=0.7,
        )
        synapse.logic_reasoning = response.choices[0].message.content

        # Get logic_answer
        if function_definition is not None:
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
            messages.extend(
                [
                    {"role": "assistant", "content": synapse.logic_reasoning},
                    {
                        "role": "user",
                        "content": "Give me the final short answer as a sentence. Don't reasoning anymore, just say the final answer in math latex.",
                    },
                ]
            )

        response = await openai_client.chat.completions.create(
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
