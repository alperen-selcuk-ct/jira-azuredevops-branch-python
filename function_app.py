import azure.functions as func
import logging

# Flex Consumption için Function App instance
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="test", methods=["GET"])
def test_function(req: func.HttpRequest) -> func.HttpResponse:
    """Simple test function"""
    logging.info('Test function called')
    return func.HttpResponse("Hello from Azure Functions!", status_code=200)

@app.route(route="healthcheck", methods=["GET"])
def healthcheck(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint"""
    logging.info('Health check requested.')
    return func.HttpResponse("OK", status_code=200)
