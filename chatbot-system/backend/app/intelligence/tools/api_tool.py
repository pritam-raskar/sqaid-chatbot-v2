"""
LangChain tools for REST and SOAP API interactions
"""
from typing import Optional, Type, Any, Dict
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import json
import logging

from app.data_access.adapters.rest_adapter import RESTAdapter
from app.data.soap_adapter import SOAPAdapter

logger = logging.getLogger(__name__)


class RESTAPIInput(BaseModel):
    """Input schema for REST API tool"""
    endpoint: str = Field(..., description="API endpoint path (e.g., /api/cases)")
    method: str = Field("GET", description="HTTP method (GET, POST, PUT, DELETE)")
    params: Optional[str] = Field(None, description="Query parameters as JSON string")
    body: Optional[str] = Field(None, description="Request body as JSON string (for POST/PUT)")


class SOAPAPIInput(BaseModel):
    """Input schema for SOAP API tool"""
    action: str = Field(..., description="SOAP action/operation name")
    parameters: str = Field(..., description="SOAP parameters as JSON string")


class RESTAPITool(BaseTool):
    """
    Generic tool for calling REST API endpoints
    Supports GET, POST, PUT, DELETE methods
    """

    name: str = "call_rest_api"
    description: str = """
    Call any REST API endpoint with flexible parameters.
    Use this when you need to interact with external REST APIs or microservices.

    Examples:
    - "Get data from /api/users endpoint"
    - "POST new record to /api/cases endpoint"
    - "Call /api/reports endpoint with status=completed filter"
    - "Update record via PUT to /api/cases/123"

    Returns: Response data from the API endpoint.
    """
    args_schema: Type[BaseModel] = RESTAPIInput

    # Injected dependencies
    api_adapter: Optional[RESTAdapter] = None
    base_url: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    def _run(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[str] = None,
        body: Optional[str] = None,
        run_manager: Optional[Any] = None
    ) -> str:
        """Synchronous execution"""
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self._arun(endpoint, method, params, body, run_manager)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                self._arun(endpoint, method, params, body, run_manager)
            )

    async def _arun(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[str] = None,
        body: Optional[str] = None,
        run_manager: Optional[Any] = None
    ) -> str:
        """Execute REST API call asynchronously"""
        try:
            # Initialize adapter if not set
            if not self.api_adapter:
                if not self.base_url:
                    return "Error: REST API adapter not configured"
                self.api_adapter = RESTAdapter(base_url=self.base_url)

            # Parse parameters
            query_params = {}
            if params:
                try:
                    query_params = json.loads(params)
                except json.JSONDecodeError:
                    return f"Error: Invalid JSON in params: {params}"

            # Parse body
            request_body = None
            if body:
                try:
                    request_body = json.loads(body)
                except json.JSONDecodeError:
                    return f"Error: Invalid JSON in body: {body}"

            # Execute API call based on method
            method = method.upper()
            response = None

            if method == "GET":
                response = await self.api_adapter.get(endpoint, params=query_params)
            elif method == "POST":
                response = await self.api_adapter.post(endpoint, data=request_body, params=query_params)
            elif method == "PUT":
                response = await self.api_adapter.put(endpoint, data=request_body, params=query_params)
            elif method == "DELETE":
                response = await self.api_adapter.delete(endpoint, params=query_params)
            else:
                return f"Error: Unsupported HTTP method: {method}"

            # Format response
            return self._format_api_response(response, endpoint, method)

        except Exception as e:
            logger.error(f"REST API call failed: {e}")
            return f"Error calling REST API: {str(e)}"

    def _format_api_response(self, response: Any, endpoint: str, method: str) -> str:
        """Format API response for LLM consumption"""
        try:
            if isinstance(response, dict):
                # Pretty print JSON
                formatted = f"API Response from {method} {endpoint}:\n\n"
                formatted += json.dumps(response, indent=2, default=str)
                return formatted
            elif isinstance(response, list):
                formatted = f"API Response from {method} {endpoint}:\n\n"
                formatted += f"Returned {len(response)} items:\n"
                # Show first 5 items
                for i, item in enumerate(response[:5], 1):
                    formatted += f"\n{i}. {json.dumps(item, indent=2, default=str)}\n"
                if len(response) > 5:
                    formatted += f"\n... and {len(response) - 5} more items"
                return formatted
            else:
                return f"API Response: {str(response)}"
        except Exception as e:
            return f"API Response (raw): {str(response)}"


class SOAPAPITool(BaseTool):
    """
    Generic tool for calling SOAP API endpoints
    Supports SOAP 1.1 and 1.2 protocols
    """

    name: str = "call_soap_api"
    description: str = """
    Call SOAP API endpoints with specified actions and parameters.
    Use this when you need to interact with legacy SOAP web services.

    Examples:
    - "Call GetCustomerDetails SOAP action with customerId=12345"
    - "Invoke ProcessPayment SOAP operation"
    - "Query CaseManagement SOAP service for case status"

    Returns: Parsed response from the SOAP service.
    """
    args_schema: Type[BaseModel] = SOAPAPIInput

    # Injected dependencies
    soap_adapter: Optional[SOAPAdapter] = None
    wsdl_url: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    def _run(
        self,
        action: str,
        parameters: str,
        run_manager: Optional[Any] = None
    ) -> str:
        """Synchronous execution"""
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self._arun(action, parameters, run_manager)
                )
                return future.result()
        else:
            return loop.run_until_complete(self._arun(action, parameters, run_manager))

    async def _arun(
        self,
        action: str,
        parameters: str,
        run_manager: Optional[Any] = None
    ) -> str:
        """Execute SOAP API call asynchronously"""
        try:
            # Initialize adapter if not set
            if not self.soap_adapter:
                if not self.wsdl_url:
                    return "Error: SOAP adapter not configured"
                self.soap_adapter = SOAPAdapter(wsdl_url=self.wsdl_url)
                await self.soap_adapter.connect()

            # Parse parameters
            try:
                params_dict = json.loads(parameters)
            except json.JSONDecodeError:
                return f"Error: Invalid JSON in parameters: {parameters}"

            # Call SOAP service
            response = await self.soap_adapter.call_method(action, **params_dict)

            # Format response
            return self._format_soap_response(response, action)

        except Exception as e:
            logger.error(f"SOAP API call failed: {e}")
            return f"Error calling SOAP API: {str(e)}"

    def _format_soap_response(self, response: Any, action: str) -> str:
        """Format SOAP response for LLM consumption"""
        try:
            formatted = f"SOAP Response from {action}:\n\n"

            if isinstance(response, dict):
                formatted += json.dumps(response, indent=2, default=str)
            elif isinstance(response, str):
                # If response is XML string, pretty print it
                if response.startswith("<?xml") or response.startswith("<"):
                    try:
                        import xml.dom.minidom
                        dom = xml.dom.minidom.parseString(response)
                        formatted += dom.toprettyxml(indent="  ")
                    except:
                        formatted += response
                else:
                    formatted += response
            else:
                formatted += str(response)

            return formatted

        except Exception as e:
            return f"SOAP Response (raw): {str(response)}"
