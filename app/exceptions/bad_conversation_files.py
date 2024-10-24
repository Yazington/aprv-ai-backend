class DesignOrGuidelineNotFoundError(Exception):
    def __init__(self, conversation_id: str, message="Converation design or guideline doesn't exist."):
        self.message = message
        self.conversation_id = conversation_id
        super().__init__(self.message)

    def __str__(self):
        return f"DesignOrGuidelineNotFoundError: {self.message} file_id: {self.conversation_id}"


class FileNotFoundError(Exception):
    def __init__(self, file_id: str, message="File not found."):
        self.message = message
        self.file_id = file_id
        super().__init__(self.message)

    def __str__(self):
        return f"FileNotFoundError: {self.message} file_id: {self.file_id}"
