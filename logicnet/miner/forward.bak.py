from logicnet.protocol import LogicSynapse
import openai
import bittensor as bt
import traceback
import re


def solve(
    synapse: LogicSynapse, openai_client: openai.AsyncOpenAI, model: str
) -> LogicSynapse:
    try:
        bt.logging.info(f"Received synapse: {synapse}")
        logic_question: str = synapse.logic_question
        messages = [
            {"role": "user", "content": logic_question},
        ]
        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2048,
            # temperature=0.8,
        )
        synapse.logic_reasoning = response.choices[0].message.content

        messages.extend(
            [
                {"role": "assistant", "content": synapse.logic_reasoning},
                {
                    "role": "user",
                    "content": "Give me the final short answer as a sentence. Don't reasoning anymore, just say the final answer in math latex.",
                },
            ]
        )

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
