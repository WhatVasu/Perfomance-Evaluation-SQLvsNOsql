class AppException(Exception):
    """Base application exception."""

    pass


class EntityNotFoundError(AppException):
    def __init__(self, entity: str, identifier: str):
        super().__init__(f"{entity} with identifier '{identifier}' not found.")
        self.entity = entity
        self.identifier = identifier


class UserAlreadyExistsError(AppException):
    def __init__(self, email: str):
        super().__init__(f"User with email '{email}' already exists.")
        self.email = email


class EmptyCartError(AppException):
    def __init__(self):
        super().__init__("Cannot checkout an empty shopping cart.")


class InsufficientStockError(AppException):
    def __init__(self, product_id: str, product_name: str, available: int, requested: int):
        super().__init__(
            f"Insufficient stock for product '{product_name}' (ID: {product_id}). "
            f"Available: {available}, requested: {requested}."
        )
        self.product_id = product_id
        self.product_name = product_name
        self.available = available
        self.requested = requested


class ConcurrencyConflictError(AppException):
    def __init__(self, message: str = "Transaction conflicted due to concurrent update"):
        super().__init__(message)
