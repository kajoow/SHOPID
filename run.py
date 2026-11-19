import os
import sys
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Load .env dari folder be jika ada
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

