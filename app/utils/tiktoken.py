import tiktoken


def num_tokens_from_messages(messages, model="gpt-4o-mini-2024-07-18"):
    """Return the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using o200k_base encoding.")
        encoding = tiktoken.get_encoding("o200k_base")
    if model in {
        "gpt-3.5-turbo-0125",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
        "gpt-4o-mini-2024-07-18",
        "gpt-4o-2024-08-06",
        "gpt-4o",
    }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif "gpt-3.5-turbo" in model:
        print("Warning: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0125.")
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0125")
    elif "gpt-4o-mini" in model:
        print("Warning: gpt-4o-mini may update over time. Returning num tokens assuming gpt-4o-mini-2024-07-18.")
        return num_tokens_from_messages(messages, model="gpt-4o-mini-2024-07-18")
    elif "gpt-4o" in model:
        print("Warning: gpt-4o and gpt-4o-mini may update over time. Returning num tokens assuming gpt-4o-2024-08-06.")
        return num_tokens_from_messages(messages, model="gpt-4o-2024-08-06")
    elif "gpt-4" in model:
        print("Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
        return num_tokens_from_messages(messages, model="gpt-4-0613")
    else:
        raise NotImplementedError(f"""num_tokens_from_messages() is not implemented for model {model}.""")
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        num_tokens += len(encoding.encode(message))
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


def truncate_all(user_prompt, user_prompt_tokens, history_tokens, history_text):
    total_prompt_tokens = user_prompt_tokens + history_tokens
    tokens_needed = total_prompt_tokens - PROMPT_TOKENS

    if tokens_needed > 0:
        # Truncate history first
        if history_tokens > 0:
            tokens_to_remove = min(tokens_needed, history_tokens)
            history_text = truncate_text(history_text, history_tokens - tokens_to_remove)
            history_tokens = count_tokens(history_text)
            tokens_needed = total_prompt_tokens - (user_prompt_tokens + history_tokens)
        # Truncate user prompt as a last resort
        if tokens_needed > 0:
            tokens_to_remove = min(tokens_needed, user_prompt_tokens - 1)  # Keep at least 1 token
            user_prompt = truncate_text(user_prompt, user_prompt_tokens - tokens_to_remove)
            user_prompt_tokens = count_tokens(user_prompt)
    return user_prompt, history_text


MAX_TOKENS = 128000  # Max tokens for the model's context window
RESPONSE_TOKENS = 16384  # Tokens reserved for the response
PROMPT_TOKENS = MAX_TOKENS - RESPONSE_TOKENS  # Tokens available for the prompt


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))


def truncate_text(text: str, max_tokens: int, model: str = "gpt-3.5-turbo") -> str:
    encoding = tiktoken.encoding_for_model(model)
    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return text
    else:
        truncated_tokens = tokens[-max_tokens:]  # Keep the last tokens
        return encoding.decode(truncated_tokens)
