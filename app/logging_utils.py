import tracemalloc
import traceback
from functools import wraps
from flask import request
from app import app

# Add environment variable for memory tracking
ENABLE_MEMORY_TRACKING = app.config.get('DISABLE_MEMORY_TRACKING', 'false').lower() != 'true'

def track_memory(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if not ENABLE_MEMORY_TRACKING:
            return await func(*args, **kwargs)
            
        tracemalloc.start()
        try:
            result = await func(*args, **kwargs)
            
            # Memory tracking
            current, peak = tracemalloc.get_traced_memory()
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')
            
            app.logger.info(f"Memory usage for {func.__name__}:")
            app.logger.info(f"Current: {current / 10**6:.1f}MB")
            app.logger.info(f"Peak: {peak / 10**6:.1f}MB")
            app.logger.info("Top 3 memory blocks:")
            for stat in top_stats[:3]:
                app.logger.info(stat)
                
            return result
        finally:
            tracemalloc.stop()
    return wrapper

@app.before_request
def log_request_info():
    app.logger.info(f"Request Origin: {request.headers.get('Origin')}")
    app.logger.info(f"Request Method: {request.method}")
    app.logger.info(f"Request Headers: {dict(request.headers)}")

@app.after_request
def after_request(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, User-Id"
    response.headers["Access-Control-Expose-Headers"] = "Content-Type"
    app.logger.info(f"Final Response Headers: {response.headers}")
    return response