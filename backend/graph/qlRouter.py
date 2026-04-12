from fastapi import Request
from strawberry.fastapi import GraphQLRouter
from strawberry.http import GraphQLHTTPResponse
from strawberry.types import ExecutionResult

class CustomGraphQLRouter(GraphQLRouter):
    
    async def process_result(
        self, request: Request, result: ExecutionResult
    ) -> GraphQLHTTPResponse:
        
        data: GraphQLHTTPResponse = {"data": result.data}

        if result.errors:
            formatted_errors = []
            
            for err in result.errors:
                err_dict = err.formatted
                err_dict.pop("locations", None)
                err_dict.pop("path", None)
                
                formatted_errors.append(err_dict)
                
            data["errors"] = formatted_errors

        return data