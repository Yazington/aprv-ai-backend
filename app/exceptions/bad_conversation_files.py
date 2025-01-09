class DesignOrGuidelineNotFoundError(Exception):
    # This exception is raised when a design or guideline associated with a conversation is not found.
    def __init__(self, conversation_id: str, message="Converation design or guideline doesn't exist."):
        # Initialize the exception with a message and the conversation ID.
        self.message = message
        self.conversation_id = conversation_id
        super().__init__(self.message)

    def __str__(self):
        # Return a string representation of the error, including the message and conversation ID.
        return f"DesignOrGuidelineNotFoundError: {self.message} file_id: {self.conversation_id}"


class FileNotFoundError(Exception):
    # This exception is raised when a file with a specific ID is not found.
    def __init__(self, file_id: str, message="File not found."):
        # Initialize the exception with a message and the file ID.
        self.message = message
        self.file_id = file_id
        super().__init__(self.message)

    def __str__(self):
        # Return a string representation of the error, including the message and file ID.
        return f"FileNotFoundError: {self.message} file_id: {self.file_id}"
