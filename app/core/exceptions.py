class AppError(Exception):
    """Base application exception."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class EntityNotFoundError(AppError):
    def __init__(self, entity_name: str, identifier: str | int):
        super().__init__(f"{entity_name} with ID '{identifier}' was not found.", status_code=404)


class UnsupportedFormatError(AppError):
    def __init__(self, filename: str, details: str = ""):
        super().__init__(f"File format for '{filename}' is not supported. {details}".strip(), status_code=415)


class ProcessingPipelineError(AppError):
    def __init__(self, stage: str, details: str):
        super().__init__(f"Pipeline failure during stage '{stage}': {details}", status_code=500)


class CoordinateTransformError(AppError):
    def __init__(self, details: str):
        super().__init__(f"Failed to transform coordinates: {details}", status_code=422)


class DimensionParseError(AppError):
    def __init__(self, raw_text: str, reason: str):
        super().__init__(f"Cannot parse dimension string '{raw_text}': {reason}", status_code=422)
