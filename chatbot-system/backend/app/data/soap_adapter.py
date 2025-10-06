"""
SOAP API Adapter for legacy web services
"""
from typing import Dict, Any, Optional
import httpx
import logging
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)


class SOAPAdapter:
    """
    Adapter for SOAP web services
    Supports SOAP 1.1 and 1.2 protocols
    """

    def __init__(
        self,
        wsdl_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 30.0,
        soap_version: str = "1.1"
    ):
        """
        Initialize SOAP adapter

        Args:
            wsdl_url: WSDL URL or SOAP endpoint URL
            username: Optional username for authentication
            password: Optional password for authentication
            timeout: Request timeout in seconds
            soap_version: SOAP version ("1.1" or "1.2")
        """
        self.wsdl_url = wsdl_url
        self.endpoint_url = wsdl_url.replace("?wsdl", "").replace("?WSDL", "")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.soap_version = soap_version
        self.client = None

        # SOAP namespaces
        self.soap_11_ns = "http://schemas.xmlsoap.org/soap/envelope/"
        self.soap_12_ns = "http://www.w3.org/2003/05/soap-envelope"
        self.soap_ns = self.soap_11_ns if soap_version == "1.1" else self.soap_12_ns

    async def connect(self) -> bool:
        """
        Initialize connection to SOAP service

        Returns:
            True if connection successful
        """
        try:
            self.client = httpx.AsyncClient(timeout=self.timeout)
            logger.info(f"SOAP adapter initialized for {self.endpoint_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize SOAP adapter: {e}")
            return False

    async def disconnect(self) -> None:
        """Close SOAP connection"""
        if self.client:
            await self.client.aclose()
            self.client = None
            logger.info("SOAP adapter disconnected")

    async def call_method(
        self,
        method_name: str,
        namespace: str = "http://tempuri.org/",
        **parameters
    ) -> Dict[str, Any]:
        """
        Call a SOAP method

        Args:
            method_name: Name of the SOAP operation
            namespace: Target namespace for the operation
            **parameters: Method parameters as keyword arguments

        Returns:
            Parsed response as dictionary
        """
        try:
            # Build SOAP envelope
            soap_envelope = self._build_soap_envelope(method_name, namespace, parameters)

            # Set headers
            headers = self._get_soap_headers(method_name, namespace)

            # Make SOAP request
            response = await self.client.post(
                self.endpoint_url,
                content=soap_envelope,
                headers=headers
            )

            response.raise_for_status()

            # Parse response
            return self._parse_soap_response(response.text)

        except httpx.HTTPStatusError as e:
            logger.error(f"SOAP request failed with status {e.response.status_code}: {e}")
            # Try to parse SOAP fault
            fault = self._parse_soap_fault(e.response.text)
            raise Exception(f"SOAP Fault: {fault}")
        except Exception as e:
            logger.error(f"SOAP method call failed: {e}")
            raise

    def _build_soap_envelope(
        self,
        method_name: str,
        namespace: str,
        parameters: Dict[str, Any]
    ) -> str:
        """
        Build SOAP envelope XML

        Args:
            method_name: SOAP operation name
            namespace: Target namespace
            parameters: Method parameters

        Returns:
            SOAP envelope as XML string
        """
        # Create envelope
        envelope = ET.Element(
            f"{{{self.soap_ns}}}Envelope",
            attrib={
                f"xmlns:soap": self.soap_ns,
                f"xmlns:ns": namespace
            }
        )

        # Create header (for authentication if needed)
        if self.username and self.password:
            header = ET.SubElement(envelope, f"{{{self.soap_ns}}}Header")
            security = ET.SubElement(header, "Security")
            username_token = ET.SubElement(security, "UsernameToken")
            ET.SubElement(username_token, "Username").text = self.username
            ET.SubElement(username_token, "Password").text = self.password

        # Create body
        body = ET.SubElement(envelope, f"{{{self.soap_ns}}}Body")
        method = ET.SubElement(body, f"{{{{ns}}}}{method_name}")

        # Add parameters
        for param_name, param_value in parameters.items():
            param_element = ET.SubElement(method, param_name)
            param_element.text = str(param_value)

        # Convert to string
        return ET.tostring(envelope, encoding="unicode", method="xml")

    def _get_soap_headers(self, method_name: str, namespace: str) -> Dict[str, str]:
        """Get HTTP headers for SOAP request"""
        if self.soap_version == "1.1":
            return {
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": f'"{namespace}{method_name}"'
            }
        else:  # SOAP 1.2
            return {
                "Content-Type": "application/soap+xml; charset=utf-8"
            }

    def _parse_soap_response(self, xml_response: str) -> Dict[str, Any]:
        """
        Parse SOAP response XML to dictionary

        Args:
            xml_response: SOAP response XML string

        Returns:
            Parsed response as dictionary
        """
        try:
            root = ET.fromstring(xml_response)

            # Remove namespace prefixes for easier parsing
            for elem in root.iter():
                if '}' in elem.tag:
                    elem.tag = elem.tag.split('}', 1)[1]

            # Find body
            body = root.find('.//Body')
            if body is None:
                return {"error": "No SOAP Body found in response"}

            # Convert body content to dictionary
            result = self._element_to_dict(body)

            return result

        except ET.ParseError as e:
            logger.error(f"Failed to parse SOAP response: {e}")
            return {"error": f"XML parse error: {str(e)}", "raw_response": xml_response}

    def _parse_soap_fault(self, xml_response: str) -> str:
        """Parse SOAP Fault from response"""
        try:
            root = ET.fromstring(xml_response)

            # Remove namespaces
            for elem in root.iter():
                if '}' in elem.tag:
                    elem.tag = elem.tag.split('}', 1)[1]

            # Find fault
            fault = root.find('.//Fault')
            if fault:
                faultcode = fault.find('.//faultcode')
                faultstring = fault.find('.//faultstring')

                code = faultcode.text if faultcode is not None else "Unknown"
                message = faultstring.text if faultstring is not None else "Unknown error"

                return f"{code}: {message}"

            return "Unknown SOAP Fault"

        except:
            return "Failed to parse SOAP Fault"

    def _element_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        """Convert XML element to dictionary"""
        result = {}

        # Get element text
        if element.text and element.text.strip():
            return element.text.strip()

        # Process children
        for child in element:
            child_data = self._element_to_dict(child)

            # Handle duplicate tags (create list)
            tag = child.tag
            if tag in result:
                if not isinstance(result[tag], list):
                    result[tag] = [result[tag]]
                result[tag].append(child_data)
            else:
                result[tag] = child_data

        # Get attributes
        if element.attrib:
            result.update({f"@{k}": v for k, v in element.attrib.items()})

        return result if result else None

    async def get_operations(self) -> list:
        """
        Get list of available SOAP operations (if WSDL is accessible)

        Returns:
            List of operation names
        """
        try:
            if not self.wsdl_url.endswith("?wsdl") and not self.wsdl_url.endswith("?WSDL"):
                logger.warning("WSDL URL not provided, cannot list operations")
                return []

            response = await self.client.get(self.wsdl_url)
            response.raise_for_status()

            # Parse WSDL
            root = ET.fromstring(response.text)

            # Find operations (simplified - would need full WSDL parser for production)
            operations = []
            for elem in root.iter():
                if 'operation' in elem.tag.lower():
                    name = elem.get('name')
                    if name:
                        operations.append(name)

            return list(set(operations))  # Remove duplicates

        except Exception as e:
            logger.error(f"Failed to get SOAP operations: {e}")
            return []
