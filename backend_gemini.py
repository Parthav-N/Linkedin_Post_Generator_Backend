from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
import google.generativeai as genai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Set up Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyBBhAh0HIqQFThiS19ia6-HaC0_0hB0Ghc")
genai.configure(api_key=GEMINI_API_KEY)

# Model configuration
MODEL_NAME = "models/gemini-1.5-pro"  # You can also use "models/gemini-pro"
TEMPERATURE = 0.7
MAX_TOKENS = 1024

def generate_post(context):
    """Generate a LinkedIn post using Gemini."""
    try:
        logger.info("Generating LinkedIn post...")
        prompt = f"""
        Based on the following context, generate a professional LinkedIn post.
        The post should be engaging, include relevant hashtags, and follow LinkedIn best practices.
        
        USER CONTEXT:
        {context}
        
        LINKEDIN POST:
        """
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=TEMPERATURE,
                max_output_tokens=MAX_TOKENS
            )
        )
        logger.info("Post generated successfully")
        return response.text
    except Exception as e:
        logger.exception(f"Error generating LinkedIn post: {e}")
        return f"Error generating LinkedIn post: {str(e)}"

def regenerate_post(context):
    """Generate a completely new LinkedIn post."""
    try:
        logger.info("Regenerating LinkedIn post...")
        prompt = f"""
        Based on the following context, generate a NEW professional LinkedIn post.
        This should be completely different from any previous generation.
        The post should be engaging, include relevant hashtags, and follow LinkedIn best practices.
        
        USER CONTEXT:
        {context}
        
        NEW LINKEDIN POST:
        """
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=TEMPERATURE + 0.2,
                max_output_tokens=MAX_TOKENS
            )
        )
        logger.info("Post regenerated successfully")
        return response.text
    except Exception as e:
        logger.exception(f"Error regenerating LinkedIn post: {e}")
        return f"Error regenerating LinkedIn post: {str(e)}"

def modify_post(post, action):
    """Modify an existing LinkedIn post (reduce or elaborate)."""
    try:
        logger.info(f"Modifying LinkedIn post with action: {action}")

        if action == "reduce":
            prompt = f"""
            Make this LinkedIn post more concise while preserving the key message.
            Aim for about half the original length.
            
            ORIGINAL POST:
            {post}
            
            SHORTER LINKEDIN POST:
            """
        elif action == "elaborate":
            prompt = f"""
            Expand this LinkedIn post with more details, examples, or insights.
            Make it more compelling and detailed while maintaining professionalism.
            
            ORIGINAL POST:
            {post}
            
            EXPANDED LINKEDIN POST:
            """
        else:
            return f"Invalid action: {action}"

        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=TEMPERATURE,
                max_output_tokens=MAX_TOKENS
            )
        )
        logger.info("Post modified successfully")
        return response.text
    except Exception as e:
        logger.exception(f"Error modifying LinkedIn post: {e}")
        return f"Error modifying LinkedIn post: {str(e)}"

@app.route('/', methods=['GET'])
def root():
    """Root endpoint with API status."""
    print("Home page accessed - API is running!")
    return jsonify({
        "status": "API is running",
        "model": MODEL_NAME,
        "endpoints": [
            "/",
            "/health",
            "/generate_post",
            "/regenerate_post",
            "/modify_post"
        ]
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({"status": "ok"})

@app.route('/generate_post', methods=['POST'])
def generate_post_endpoint():
    """Generate a LinkedIn post based on the provided context."""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    data = request.get_json()
    if 'context' not in data:
        return jsonify({"error": "Missing 'context' field"}), 400

    logger.info(f"Generating LinkedIn post for context: {data['context'][:50]}...")
    generated_text = generate_post(data['context'])

    if isinstance(generated_text, str) and generated_text.startswith("Error"):
        return jsonify({"error": generated_text}), 500

    return jsonify({"post": generated_text.strip()})

@app.route('/regenerate_post', methods=['POST'])
def regenerate_post_endpoint():
    """Generate a new LinkedIn post with a different approach."""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    if 'context' not in data:
        return jsonify({"error": "Missing 'context' field"}), 400

    logger.info(f"Regenerating LinkedIn post for context: {data['context'][:50]}...")
    generated_text = regenerate_post(data['context'])

    if isinstance(generated_text, str) and generated_text.startswith("Error"):
        return jsonify({"error": generated_text}), 500

    return jsonify({"post": generated_text.strip()})

@app.route('/modify_post', methods=['POST'])
def modify_post_endpoint():
    """Modify the existing post according to the action (reduce or elaborate)."""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    required_fields = ['context', 'current_post', 'action']
    missing_fields = [field for field in required_fields if field not in data]

    if missing_fields:
        return jsonify({"error": f"Missing fields: {', '.join(missing_fields)}"}), 400

    if data['action'] not in ["reduce", "elaborate"]:
        return jsonify({"error": "Invalid action. Use 'reduce' or 'elaborate'."}), 400

    logger.info(f"Modifying LinkedIn post with action: {data['action']}")
    modified_text = modify_post(data['current_post'], data['action'])

    if isinstance(modified_text, str) and modified_text.startswith("Error"):
        return jsonify({"error": modified_text}), 500

    return jsonify({"post": modified_text.strip()})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port)
    print("✅ Server deployed successfully and running on port", port)

server = app 
