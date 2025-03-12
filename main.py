import os
from app import app

# Log environment variables for debugging (excluding sensitive info)
if __name__ == "__main__":
    # Check if FIRECRAWL_API_KEY is set without displaying its value
    firecrawl_key_exists = "FIRECRAWL_API_KEY" in os.environ
    print(f"FIRECRAWL_API_KEY exists in environment: {firecrawl_key_exists}")
    
    # Run the Flask application
    app.run(host="0.0.0.0", port=5000, debug=True)
