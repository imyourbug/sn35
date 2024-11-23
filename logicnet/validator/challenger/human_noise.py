import random


def get_condition():
    profiles = [
        "math enthusiast",
        "math student",
        "research mathematician",
        "math teacher",
        "theoretical physicist",
        "engineer",
        "student",
        "teacher",
        "researcher",
        "physicist",
        "scientist",
        "mathematician",
        "data scientist",
        "math tutor",
        "math hobbyist",
        "data analyst",
        "data engineer",
        "data enthusiast",
        "data student",
        "data teacher",
        "data researcher",
    ]

    mood = [
        "curious",
        "puzzled",
        "eager",
        "analytical",
        "determined",
        "excited",
    ]

    tone = [
        "inquisitive",
        "thoughtful",
        "meticulous",
        "enthusiastic",
        "serious",
        "playful",
    ]

    return {
        "profile": random.choice(profiles),
        "mood": random.choice(mood),
        "tone": random.choice(tone),
    }

def multiply_int_to_22_matrix(max_matrix_val=10, max_res=100):
    r"""Multiply Integer to 2x2 Matrix

    | Ex. Problem | Ex. Solution |
    | --- | --- |
    | $5 * \begin{bmatrix} 1 & 0 \\\ 2 & 9 \end{bmatrix} =$ | $\begin{bmatrix} 5 & 0 \\\ 10 & 45 \end{bmatrix}$ |
    """
    a = random.randint(0, max_matrix_val)
    b = random.randint(0, max_matrix_val)
    c = random.randint(0, max_matrix_val)
    d = random.randint(0, max_matrix_val)

    constant = random.randint(0, int(max_res / max(a, b, c, d)))

    a1 = a * constant
    b1 = b * constant
    c1 = c * constant
    d1 = d * constant
    lst = [[a, b], [c, d]]
    lst1 = [[a1, b1], [c1, d1]]

    problem = f'${constant} * {bmatrix(lst)} =$'
    solution = f'${bmatrix(lst1)}$'
    return problem, solution