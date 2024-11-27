import re

def get_function_definition(function_name, file_name):
    """
    Retrieve the full text of a function definition from a Python file.

    Args:
        file_path (str): Path to the Python file.
        function_name (str): Name of the function to retrieve.

    Returns:
        str: The function definition as a string, or None if not found.
    """
    file_path=f"mathgenerator/mathgenerator/{file_name}.py"
    with open(file_path, 'r') as file:
        content = file.read()

    print(f"file_path: {file_path}")
    print(f"function_name: {function_name}")
    print(f"file_name: {file_name}")
    # print(f"content: {content}")
    # Regular expression to match the function definition
    pattern = rf"def {function_name}\(.*?\):.*?(?=\ndef|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    print(f"match: {match}")

    if match:
        return match.group().strip()
    else:
        return None

