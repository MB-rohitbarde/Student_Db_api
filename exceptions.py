"""Custom exception classes and centralized exception handling for the FastAPI application."""

import logging
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from botocore.exceptions import ClientError, NoCredentialsError, InvalidRegionError
from jose import JWTError
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class APIException(Exception):
    """Base exception class for API-specific errors."""
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(APIException):
    """Raised when input validation fails."""
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message, status.HTTP_400_BAD_REQUEST, {"field": field})


class NotFoundError(APIException):
    """Raised when a requested resource is not found."""
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            f"{resource} not found",
            status.HTTP_404_NOT_FOUND,
            {"resource": resource, "identifier": str(identifier)}
        )


class ConflictError(APIException):
    """Raised when a resource already exists or conflicts with existing data."""
    def __init__(self, message: str, resource: Optional[str] = None):
        super().__init__(message, status.HTTP_409_CONFLICT, {"resource": resource})


class UnauthorizedError(APIException):
    """Raised when authentication or authorization fails."""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(APIException):
    """Raised when user doesn't have permission to perform an action."""
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status.HTTP_403_FORBIDDEN)


class FileTooLargeError(APIException):
    """Raised when uploaded file exceeds size limit."""
    def __init__(self, max_size: int, actual_size: int):
        super().__init__(
            f"File too large. Maximum size: {max_size} bytes, actual size: {actual_size} bytes",
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            {"max_size": max_size, "actual_size": actual_size}
        )


class S3Error(APIException):
    """Raised when S3 operations fail."""
    def __init__(self, message: str, operation: str):
        super().__init__(message, status.HTTP_500_INTERNAL_SERVER_ERROR, {"operation": operation})


class DatabaseError(APIException):
    """Raised when database operations fail."""
    def __init__(self, message: str, operation: str):
        super().__init__(message, status.HTTP_500_INTERNAL_SERVER_ERROR, {"operation": operation})


def create_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI app."""
    
    @app.exception_handler(APIException)
    async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
        """Handle custom API exceptions."""
        logger.error(f"API Exception: {exc.message}", extra={
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method
        })
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.message,
                "status_code": exc.status_code,
                "details": exc.details,
                "path": request.url.path
            }
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Handle FastAPI HTTP exceptions."""
        logger.warning(f"HTTP Exception: {exc.detail}", extra={
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method
        })
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "status_code": exc.status_code,
                "path": request.url.path
            }
        )
    
    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        """Handle SQLAlchemy database exceptions."""
        logger.error(f"Database error: {str(exc)}", extra={
            "path": request.url.path,
            "method": request.method,
            "traceback": traceback.format_exc()
        })
        
        if isinstance(exc, IntegrityError):
            # Handle constraint violations
            error_msg = "Database constraint violation"
            if "UNIQUE constraint failed" in str(exc):
                error_msg = "Resource already exists"
            elif "FOREIGN KEY constraint failed" in str(exc):
                error_msg = "Referenced resource does not exist"
            
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "error": error_msg,
                    "status_code": status.HTTP_409_CONFLICT,
                    "details": {"database_error": str(exc)},
                    "path": request.url.path
                }
            )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Database operation failed",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "details": {"database_error": str(exc)},
                "path": request.url.path
            }
        )
    
    @app.exception_handler(ClientError)
    async def s3_client_error_handler(request: Request, exc: ClientError) -> JSONResponse:
        """Handle AWS S3 client errors."""
        error_code = exc.response.get('Error', {}).get('Code', 'Unknown')
        error_message = exc.response.get('Error', {}).get('Message', str(exc))
        
        logger.error(f"S3 Client Error: {error_code} - {error_message}", extra={
            "path": request.url.path,
            "method": request.method,
            "error_code": error_code
        })
        
        if error_code == 'NoSuchKey':
            status_code = status.HTTP_404_NOT_FOUND
            error_msg = "File not found in storage"
        elif error_code == 'AccessDenied':
            status_code = status.HTTP_403_FORBIDDEN
            error_msg = "Access denied to storage resource"
        elif error_code == 'InvalidBucketName':
            status_code = status.HTTP_400_BAD_REQUEST
            error_msg = "Invalid storage bucket configuration"
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            error_msg = "Storage operation failed"
        
        return JSONResponse(
            status_code=status_code,
            content={
                "error": error_msg,
                "status_code": status_code,
                "details": {
                    "s3_error_code": error_code,
                    "s3_error_message": error_message
                },
                "path": request.url.path
            }
        )
    
    @app.exception_handler(NoCredentialsError)
    async def s3_credentials_error_handler(request: Request, exc: NoCredentialsError) -> JSONResponse:
        """Handle AWS credentials errors."""
        logger.error(f"AWS Credentials Error: {str(exc)}", extra={
            "path": request.url.path,
            "method": request.method
        })
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Storage service not configured properly",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "details": {"credentials_error": str(exc)},
                "path": request.url.path
            }
        )
    
    @app.exception_handler(InvalidRegionError)
    async def s3_region_error_handler(request: Request, exc: InvalidRegionError) -> JSONResponse:
        """Handle AWS region errors."""
        logger.error(f"AWS Region Error: {str(exc)}", extra={
            "path": request.url.path,
            "method": request.method
        })
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Storage service region not configured properly",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "details": {"region_error": str(exc)},
                "path": request.url.path
            }
        )
    
    @app.exception_handler(JWTError)
    async def jwt_error_handler(request: Request, exc: JWTError) -> JSONResponse:
        """Handle JWT token errors."""
        logger.warning(f"JWT Error: {str(exc)}", extra={
            "path": request.url.path,
            "method": request.method
        })
        
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "Invalid or expired token",
                "status_code": status.HTTP_401_UNAUTHORIZED,
                "details": {"jwt_error": str(exc)},
                "path": request.url.path
            }
        )
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Handle ValueError exceptions."""
        logger.warning(f"Value Error: {str(exc)}", extra={
            "path": request.url.path,
            "method": request.method
        })
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Invalid input value",
                "status_code": status.HTTP_400_BAD_REQUEST,
                "details": {"value_error": str(exc)},
                "path": request.url.path
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle all other unhandled exceptions."""
        logger.error(f"Unhandled Exception: {str(exc)}", extra={
            "path": request.url.path,
            "method": request.method,
            "traceback": traceback.format_exc()
        })
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "details": {"exception": str(exc)},
                "path": request.url.path
            }
        )


def safe_db_operation(operation_name: str):
    """Decorator to safely handle database operations with proper exception handling."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except SQLAlchemyError as e:
                logger.error(f"Database error in {operation_name}: {str(e)}")
                raise DatabaseError(f"Database operation failed: {operation_name}", operation_name)
            except Exception as e:
                logger.error(f"Unexpected error in {operation_name}: {str(e)}")
                raise APIException(f"Operation failed: {operation_name}", details={"original_error": str(e)})
        return wrapper
    return decorator
