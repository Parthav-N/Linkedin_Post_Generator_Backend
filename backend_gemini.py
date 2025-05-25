from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
import google.generativeai as genai
import sys

# Configure logging to stdout for Render
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Get Gemini API key from environment variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable is not set")
    # Don't set a default API key here for security reasons

# Configure Gemini API if key is available
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("Gemini API configured successfully")
    except Exception as e:
        logger.error(f"Failed to configure Gemini API: {e}")

# Firebase initialization with enhanced debugging
db = None
firebase_connection_method = "none"

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    from datetime import datetime
    
    logger.info("=== FIREBASE DEBUG INFO ===")
    
    # Debug: Print environment variables (safely)
    firebase_env_vars = [
        "FIREBASE_PROJECT_ID",
        "FIREBASE_PRIVATE_KEY", 
        "FIREBASE_CLIENT_EMAIL",
        "FIREBASE_PRIVATE_KEY_ID",
        "FIREBASE_CLIENT_ID"
    ]
    
    for var in firebase_env_vars:
        value = os.getenv(var)
        if value:
            if var == "FIREBASE_PRIVATE_KEY":
                logger.info(f"{var}: Present (length: {len(value)}, starts with: {value[:50]}...)")
            else:
                logger.info(f"{var}: {value}")
        else:
            logger.warning(f"{var}: NOT SET")
    
    # Try to initialize Firebase if not already initialized
    if not firebase_admin._apps:
        cred = None
        
        # Method 1: Try JSON file (for development)
        json_file_paths = [
            "firebase-credentials.json",
            "./firebase-credentials.json", 
            "../firebase-credentials.json"
        ]
        
        logger.info("Checking for JSON files...")
        for json_path in json_file_paths:
            logger.info(f"Checking: {json_path} - Exists: {os.path.exists(json_path)}")
            if os.path.exists(json_path):
                try:
                    cred = credentials.Certificate(json_path)
                    firebase_connection_method = f"JSON file: {json_path}"
                    logger.info(f"SUCCESS: Using Firebase credentials from {json_path}")
                    break
                except Exception as e:
                    logger.error(f"FAILED to load {json_path}: {e}")
                    continue
        
        # Method 2: Try environment variables (for production)
        if not cred:
            logger.info("JSON file not found, trying environment variables...")
            
            required_env_vars = [
                "FIREBASE_PROJECT_ID",
                "FIREBASE_PRIVATE_KEY", 
                "FIREBASE_CLIENT_EMAIL"
            ]
            
            missing_vars = [var for var in required_env_vars if not os.getenv(var)]
            if missing_vars:
                logger.error(f"Missing required environment variables: {missing_vars}")
            else:
                logger.info("All required environment variables are present, creating Firebase config...")
                
                try:
                    # Clean up private key formatting
                    private_key = os.getenv("FIREBASE_PRIVATE_KEY")
                    logger.info(f"Original private key length: {len(private_key) if private_key else 0}")
                    
                    if private_key:
                        # Handle different private key formats
                        private_key = private_key.replace('\\n', '\n')
                        logger.info(f"After \\n replacement: {len(private_key)}")
                        
                        if not private_key.startswith('-----BEGIN PRIVATE KEY-----'):
                            private_key = f"-----BEGIN PRIVATE KEY-----\n{private_key}\n-----END PRIVATE KEY-----\n"
                            logger.info("Added BEGIN/END markers to private key")
                        else:
                            logger.info("Private key already has proper format")
                    
                    firebase_config = {
                        "type": os.getenv("FIREBASE_TYPE", "service_account"),
                        "project_id": os.getenv("FIREBASE_PROJECT_ID"),
                        "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
                        "private_key": private_key,
                        "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
                        "client_id": os.getenv("FIREBASE_CLIENT_ID"),
                        "auth_uri": os.getenv("FIREBASE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
                        "token_uri": os.getenv("FIREBASE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
                        "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL", "https://www.googleapis.com/oauth2/v1/certs")
                    }
                    
                    # Remove None values and log config (safely)
                    firebase_config = {k: v for k, v in firebase_config.items() if v is not None}
                    
                    # Log config safely (without private key)
                    safe_config = {k: v for k, v in firebase_config.items() if k != "private_key"}
                    safe_config["private_key"] = f"<PRESENT - {len(firebase_config.get('private_key', ''))} chars>"
                    logger.info(f"Firebase config created: {safe_config}")
                    
                    cred = credentials.Certificate(firebase_config)
                    firebase_connection_method = "Environment variables"
                    logger.info("SUCCESS: Firebase credentials created from environment variables")
                    
                except Exception as e:
                    logger.error(f"FAILED to create credentials from environment variables: {e}")
                    logger.error(f"Error type: {type(e).__name__}")
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
        
        if cred:
            logger.info("Attempting to initialize Firebase app...")
            try:
                firebase_admin.initialize_app(cred)
                db = firestore.client()
                logger.info(f"SUCCESS: Firebase initialized via {firebase_connection_method}")
                
                # Test connection with more detailed logging
                logger.info("Testing Firebase connection...")
                test_ref = db.collection('sundai_projects').limit(1)
                test_docs = list(test_ref.stream())
                logger.info(f"SUCCESS: Firebase connection verified - found {len(test_docs)} test documents in sundai_projects collection")
                
                # Try to get a sample document to verify read permissions
                if test_docs:
                    sample_doc = test_docs[0]
                    sample_data = sample_doc.to_dict()
                    logger.info(f"Sample document ID: {sample_doc.id}")
                    logger.info(f"Sample document keys: {list(sample_data.keys()) if sample_data else 'No data'}")
                
            except Exception as e:
                logger.error(f"Firebase connection test failed: {e}")
                logger.error(f"Error type: {type(e).__name__}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
                logger.warning("Firebase initialized but connection test failed - check collection name and permissions")
        else:
            logger.error("FAILED: No Firebase credentials could be loaded")
            logger.info("Firebase Setup: Add firebase-credentials.json or set Firebase environment variables")

except ImportError as e:
    logger.error(f"Firebase Admin SDK not installed: {e}")
    logger.info("Install with: pip install firebase-admin")
except Exception as e:
    logger.error(f"Error initializing Firebase: {e}")
    logger.error(f"Error type: {type(e).__name__}")
    import traceback
    logger.error(f"Full traceback: {traceback.format_exc()}")

logger.info("=== END FIREBASE DEBUG INFO ===")
logger.info(f"Final Firebase status: db={'Connected' if db else 'Not connected'}")
logger.info(f"Final connection method: {firebase_connection_method}")

# Model configuration
MODEL_NAME = "models/gemini-1.5-pro"
TEMPERATURE = 0.7
MAX_TOKENS = 1024

def generate_post(context):
    """Generate a LinkedIn post using Gemini."""
    try:
        if not GEMINI_API_KEY:
            return "Error: Gemini API key is not configured"
            
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
        if not GEMINI_API_KEY:
            return "Error: Gemini API key is not configured"
            
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
        if not GEMINI_API_KEY:
            return "Error: Gemini API key is not configured"
            
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

def generate_comment(post_text, post_author, refinement="", current_comment=""):
    """Generate a LinkedIn comment using Gemini."""
    try:
        if not GEMINI_API_KEY:
            return "Error: Gemini API key is not configured"
        
        logger.info("Generating LinkedIn comment...")
        
        # Build prompt based on inputs
        prompt = f"""Post author: "{post_author}"
Post content: "{post_text}" """

        if current_comment and current_comment.strip():
            prompt += f"\nCurrent comment: {current_comment}"
            
        if refinement and refinement.strip():
            prompt += f"\nRefinement instructions: {refinement}"
            
        if current_comment and current_comment.strip():
            prompt += """\n\nRefine the current comment based on refinement instructions, keeping it as a congratulatory comment for this LinkedIn post. Only output the final comment — do not include options, explanations, formatting, or any extra text."""
        else:
            prompt += """\n\nWrite a single, concise, professional congratulatory comment for this LinkedIn post. Only output the final comment — do not include options, explanations, formatting, or any extra text. Include author's name in the comment."""
            
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=TEMPERATURE,
                max_output_tokens=MAX_TOKENS
            )
        )
        logger.info("Comment generated successfully")
        return response.text
    except Exception as e:
        logger.exception(f"Error generating LinkedIn comment: {e}")
        return f"Error generating LinkedIn comment: {str(e)}"

def generate_project_post(project_data):
    """Generate a LinkedIn post for a specific project."""
    try:
        if not GEMINI_API_KEY:
            return "Error: Gemini API key is not configured"
        
        logger.info("Generating project LinkedIn post...")
        
        # Extract project information
        title = project_data.get('title', '')
        description = project_data.get('description', '')
        team_lead = project_data.get('team_lead', '')
        team_members = project_data.get('team_members', [])
        demo_url = project_data.get('demo_url', '')
        github_url = project_data.get('github_url', '')
        blog_url = project_data.get('blog_url', '')
        tags = project_data.get('tags', [])
        
        # Build team information
        team_info = []
        if team_lead:
            team_info.append(f"Team Lead: {team_lead}")
        if team_members and len(team_members) > 0:
            if len(team_members) == 1:
                team_info.append(f"Team Member: {team_members[0]}")
            else:
                team_info.append(f"Team Members: {', '.join(team_members)}")
        
        team_text = ' | '.join(team_info) if team_info else 'Individual project'
        
        # Build links information
        links_info = []
        if demo_url:
            links_info.append(f"🚀 Demo: {demo_url}")
        if github_url:
            links_info.append(f"💻 GitHub: {github_url}")
        if blog_url:
            links_info.append(f"📝 Blog: {blog_url}")
        
        links_text = '\n\n'.join(links_info) if links_info else ''
        
        # Build tags text
        if tags and len(tags) > 0:
            # Convert tags to hashtags
            hashtags = []
            for tag in tags:
                # Clean tag and make it hashtag-friendly
                clean_tag = ''.join(c for c in tag if c.isalnum() or c.isspace()).strip()
                clean_tag = ''.join(clean_tag.split())  # Remove spaces
                if clean_tag:
                    hashtags.append(f"#{clean_tag}")
            
            tags_text = ' '.join(hashtags) if hashtags else ''
        else:
            tags_text = '#SundaiClub #Innovation #TechProject'
        
        # Create an engaging prompt for Gemini
        prompt = f"""Create an engaging and professional LinkedIn post about this innovative project from Sundai Club:

PROJECT TITLE: {title}

PROJECT DESCRIPTION: {description}

TEAM INFORMATION: {team_text}

Make this post:
1. Professional yet exciting and engaging
2. Highlight the innovation and impact of the project
3. Mention the team (give credit where due)
4. Include a call-to-action (like checking out the demo or connecting)
5. Use an enthusiastic but professional tone
6. Keep it concise but informative (ideal LinkedIn post length)
7. Start with an attention-grabbing opening

{f"Include these links naturally in the post: {links_text}" if links_text else ""}

End the post with these hashtags: {tags_text}

Make sure the post sounds authentic and would get good engagement on LinkedIn. Focus on what makes this project special and why people should care about it."""

        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=TEMPERATURE,
                max_output_tokens=MAX_TOKENS
            )
        )
        logger.info("Project post generated successfully")
        return response.text
    except Exception as e:
        logger.exception(f"Error generating project post: {e}")
        return f"Error generating project post: {str(e)}"

@app.route('/', methods=['GET'])
def root():
    """Root endpoint with API status."""
    logger.info("Home page accessed - API is running!")
    return jsonify({
        "status": "API is running",
        "model": MODEL_NAME,
        "gemini_configured": GEMINI_API_KEY is not None,
        "firebase_configured": db is not None,
        "firebase_connection": firebase_connection_method,
        "endpoints": [
            "/",
            "/health",
            "/generate_post",
            "/regenerate_post",
            "/modify_post",
            "/generate_comment",
            "/get_projects",
            "/generate_project_post",
            "/projects_health",
            "/debug_firebase"
        ]
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    logger.info("Health check endpoint accessed")
    
    firebase_status = "not_configured"
    if db:
        try:
            # Test actual database connection
            test_ref = db.collection('sundai_projects').limit(1)
            test_docs = list(test_ref.stream())
            firebase_status = "connected"
        except Exception as e:
            firebase_status = "connection_failed"
    
    return jsonify({
        "status": "ok",
        "gemini_api": "configured" if GEMINI_API_KEY else "not configured",
        "firebase": firebase_status,
        "firebase_connection": firebase_connection_method
    })

@app.route('/debug_firebase', methods=['GET'])
def debug_firebase():
    """Debug endpoint to check Firebase configuration"""
    try:
        debug_info = {
            "firebase_admin_installed": True,
            "firebase_apps_count": len(firebase_admin._apps) if 'firebase_admin' in globals() else 0,
            "db_initialized": db is not None,
            "connection_method": firebase_connection_method,
            "environment_variables": {},
            "test_results": {}
        }
        
        # Check environment variables (safely)
        env_vars = [
            "FIREBASE_PROJECT_ID", "FIREBASE_PRIVATE_KEY", "FIREBASE_CLIENT_EMAIL",
            "FIREBASE_PRIVATE_KEY_ID", "FIREBASE_CLIENT_ID"
        ]
        
        for var in env_vars:
            value = os.getenv(var)
            if value:
                if var == "FIREBASE_PRIVATE_KEY":
                    debug_info["environment_variables"][var] = {
                        "present": True,
                        "length": len(value),
                        "starts_with": value[:50] + "..." if len(value) > 50 else value,
                        "has_begin_marker": "-----BEGIN PRIVATE KEY-----" in value,
                        "has_end_marker": "-----END PRIVATE KEY-----" in value
                    }
                else:
                    debug_info["environment_variables"][var] = {
                        "present": True,
                        "value": value
                    }
            else:
                debug_info["environment_variables"][var] = {"present": False}
        
        # Test database connection if available
        if db:
            try:
                test_ref = db.collection('sundai_projects').limit(1)
                test_docs = list(test_ref.stream())
                debug_info["test_results"]["collection_accessible"] = True
                debug_info["test_results"]["document_count"] = len(test_docs)
                
                if test_docs:
                    sample_doc = test_docs[0]
                    debug_info["test_results"]["sample_document"] = {
                        "id": sample_doc.id,
                        "keys": list(sample_doc.to_dict().keys())
                    }
                
            except Exception as e:
                debug_info["test_results"]["collection_accessible"] = False
                debug_info["test_results"]["error"] = str(e)
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "firebase_admin_installed": 'firebase_admin' in globals()
        }), 500

@app.route('/generate_post', methods=['POST'])
def generate_post_endpoint():
    """Generate a LinkedIn post based on the provided context."""
    if not request.is_json:
        logger.warning("Request is not JSON")
        return jsonify({"error": "Request must be JSON"}), 400
    
    data = request.get_json()
    if 'context' not in data:
        logger.warning("Missing 'context' field in request")
        return jsonify({"error": "Missing 'context' field"}), 400

    logger.info(f"Generating LinkedIn post for context: {data['context'][:50]}...")
    generated_text = generate_post(data['context'])

    if isinstance(generated_text, str) and generated_text.startswith("Error"):
        logger.error(generated_text)
        return jsonify({"error": generated_text}), 500

    return jsonify({"post": generated_text.strip()})

@app.route('/regenerate_post', methods=['POST'])
def regenerate_post_endpoint():
    """Generate a new LinkedIn post with a different approach."""
    if not request.is_json:
        logger.warning("Request is not JSON")
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    if 'context' not in data:
        logger.warning("Missing 'context' field in request")
        return jsonify({"error": "Missing 'context' field"}), 400

    logger.info(f"Regenerating LinkedIn post for context: {data['context'][:50]}...")
    generated_text = regenerate_post(data['context'])

    if isinstance(generated_text, str) and generated_text.startswith("Error"):
        logger.error(generated_text)
        return jsonify({"error": generated_text}), 500

    return jsonify({"post": generated_text.strip()})

@app.route('/modify_post', methods=['POST'])
def modify_post_endpoint():
    """Modify the existing post according to the action (reduce or elaborate)."""
    if not request.is_json:
        logger.warning("Request is not JSON")
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    required_fields = ['context', 'current_post', 'action']
    missing_fields = [field for field in required_fields if field not in data]

    if missing_fields:
        logger.warning(f"Missing fields in request: {missing_fields}")
        return jsonify({"error": f"Missing fields: {', '.join(missing_fields)}"}), 400

    if data['action'] not in ["reduce", "elaborate"]:
        logger.warning(f"Invalid action in request: {data['action']}")
        return jsonify({"error": "Invalid action. Use 'reduce' or 'elaborate'."}), 400

    logger.info(f"Modifying LinkedIn post with action: {data['action']}")
    modified_text = modify_post(data['current_post'], data['action'])

    if isinstance(modified_text, str) and modified_text.startswith("Error"):
        logger.error(modified_text)
        return jsonify({"error": modified_text}), 500

    return jsonify({"post": modified_text.strip()})

@app.route('/generate_comment', methods=['POST'])
def generate_comment_endpoint():
    """Generate a comment for a LinkedIn post."""
    if not request.is_json:
        logger.warning("Request is not JSON")
        return jsonify({"error": "Request must be JSON"}), 400
    
    data = request.get_json()
    required_fields = ['post_text', 'post_author']
    missing_fields = [field for field in required_fields if field not in data]

    if missing_fields:
        logger.warning(f"Missing fields in request: {missing_fields}")
        return jsonify({"error": f"Missing fields: {', '.join(missing_fields)}"}), 400

    # Optional parameters
    refinement = data.get('refinement', '')
    current_comment = data.get('current_comment', '')

    logger.info(f"Generating LinkedIn comment for post by: {data['post_author']}")
    generated_comment = generate_comment(
        data['post_text'], 
        data['post_author'], 
        refinement, 
        current_comment
    )

    if isinstance(generated_comment, str) and generated_comment.startswith("Error"):
        logger.error(generated_comment)
        return jsonify({"error": generated_comment}), 500

    return jsonify({"comment": generated_comment.strip()})

# NEW ROUTES FOR PROJECTS FUNCTIONALITY

@app.route('/get_projects', methods=['GET'])
def get_projects():
    """Fetch all projects from Firebase for the extension"""
    try:
        if not db:
            return jsonify({
                'success': False,
                'error': 'Firebase not configured. Please check Firebase setup in backend.',
                'setup_instructions': 'Add firebase-credentials.json to backend directory or set Firebase environment variables'
            }), 503
        
        logger.info("Fetching projects from Firebase...")
        
        # Get all projects from sundai_projects collection
        projects_ref = db.collection('sundai_projects')
        docs = projects_ref.stream()
        
        projects = []
        for doc in docs:
            try:
                project_data = doc.data()
                
                # Ensure we have required fields
                if not project_data.get('title'):
                    logger.warning(f"Project {doc.id} missing title, skipping")
                    continue
                
                # Structure project info for extension
                project_info = {
                    'id': doc.id,
                    'title': project_data.get('title', 'Untitled Project'),
                    'description': project_data.get('description', ''),
                    'team_lead': project_data.get('team_lead', ''),
                    'team_members': project_data.get('team_members', []),
                    'demo_url': project_data.get('demo_url', ''),
                    'github_url': project_data.get('github_url', ''),
                    'blog_url': project_data.get('blog_url', ''),
                    'tags': project_data.get('tags', []),
                    'last_updated': project_data.get('last_updated', ''),
                    'start_date': project_data.get('start_date', ''),
                    'scraped_at': project_data.get('scraped_at', '')
                }
                
                projects.append(project_info)
                
            except Exception as e:
                logger.error(f"Error processing project {doc.id}: {e}")
                continue
        
        # Sort by last_updated (most recent first)
        projects.sort(key=lambda x: x.get('last_updated', ''), reverse=True)
        
        logger.info(f"Successfully fetched {len(projects)} projects from Firebase")
        
        return jsonify({
            'success': True,
            'projects': projects,
            'count': len(projects),
            'connection_method': firebase_connection_method
        })
        
    except Exception as e:
        logger.exception(f"Error fetching projects from Firebase: {e}")
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}',
            'suggestion': 'Check Firebase configuration and collection name'
        }), 500

@app.route('/generate_project_post', methods=['POST'])
def generate_project_post_endpoint():
    """Generate a LinkedIn post for a specific project"""
    try:
        if not request.is_json:
            logger.warning("Request is not JSON")
            return jsonify({
                'success': False,
                'error': 'Request must be JSON'
            }), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No project data provided'
            }), 400
        
        # Extract and validate project information
        title = data.get('title', '')
        if not title:
            return jsonify({
                'success': False,
                'error': 'Project title is required'
            }), 400
        
        logger.info(f"Generating LinkedIn post for project: {title}")
        
        # Generate the post using the project data
        generated_post = generate_project_post(data)
        
        if isinstance(generated_post, str) and generated_post.startswith("Error"):
            logger.error(generated_post)
            return jsonify({
                'success': False,
                'error': generated_post
            }), 500
        
        logger.info(f"Successfully generated post for project: {title}")
        
        return jsonify({
            'success': True,
            'post': generated_post.strip(),
            'project_title': title
        })
        
    except Exception as e:
        logger.exception(f"Error generating project post: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to generate post: {str(e)}'
        }), 500

@app.route('/projects_health', methods=['GET'])
def projects_health():
    """Detailed health check for projects functionality"""
    try:
        status = {
            'success': True,
            'firebase_connected': False,
            'gemini_connected': False,
            'projects_count': 0,
            'connection_method': firebase_connection_method,
            'timestamp': datetime.now().isoformat() if 'datetime' in globals() else 'N/A'
        }
        
        # Test Firebase connection
        if db:
            try:
                projects_ref = db.collection('sundai_projects')
                
                # Count total projects
                docs = list(projects_ref.stream())
                status['projects_count'] = len(docs)
                status['firebase_connected'] = True
                
                logger.info(f"Firebase health check passed - {len(docs)} projects found")
                
                # Sample a few project titles for verification
                if docs:
                    sample_titles = [doc.data().get('title', 'Untitled')[:50] for doc in docs[:3]]
                    status['sample_projects'] = sample_titles
                
            except Exception as e:
                logger.error(f"Firebase health check failed: {e}")
                status['firebase_error'] = str(e)
        else:
            status['firebase_error'] = "Firebase not initialized"
        
        # Test Gemini API
        if GEMINI_API_KEY:
            try:
                model = genai.GenerativeModel(MODEL_NAME)
                test_response = model.generate_content("Test connection")
                if test_response and test_response.text:
                    status['gemini_connected'] = True
                    logger.info("Gemini API health check passed")
            except Exception as e:
                logger.error(f"Gemini API health check failed: {e}")
                status['gemini_error'] = str(e)
        else:
            status['gemini_error'] = "API key not configured"
        
        return jsonify(status)
        
    except Exception as e:
        logger.exception(f"Error in projects health check: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'firebase_connected': False,
            'gemini_connected': False,
            'timestamp': datetime.now().isoformat() if 'datetime' in globals() else 'N/A'
        }), 500

# Make app available for Render
server = app

# Only run the app directly if this file is being run directly
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting server on port {port}")
    logger.info(f"Gemini API: {'Configured' if GEMINI_API_KEY else 'Not configured'}")
    logger.info(f"Firebase: {'Connected' if db else 'Not connected'}")
    app.run(host="0.0.0.0", port=port)
    logger.info(f"✅ Server deployed successfully and running on port {port}")