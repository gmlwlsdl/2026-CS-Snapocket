from graphql import GraphQLError

class UnauthorizedError(GraphQLError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(
            message, 
            extensions={"code": "UNAUTHORIZED"}
        )

class NotFoundError(GraphQLError):
    def __init__(self, message: str = "not_found"):
        super().__init__(
            message, 
            extensions={"code": "NOT_FOUND"}
        )

class BadUserInputError(GraphQLError):
    def __init__(self, message: str = "bad_user_input"):
        super().__init__(
            message, 
            extensions={"code": "BAD_USER_INPUT"}
        )

class InternalServerError(GraphQLError):
    def __init__(self, message: str = "internal_server_error"):
        super().__init__(
            message, 
            extensions={"code": "INTERNAL_SERVER_ERROR"}
        )