import logging
import azure.functions as func


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint"""
    logging.info('Health check requested.')
    
    return func.HttpResponse(
        "OK",
        status_code=200
    )
