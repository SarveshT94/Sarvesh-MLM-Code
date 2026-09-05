from app import create_app
from app.utils.logger import setup_logging  # ✅ ADD THIS

# Initialize logging BEFORE app starts
setup_logging()  # ✅ ADD THIS

app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",  # 🔥 UPDATED: Forces Flask to listen on all IPv4/IPv6 channels
        port=5000,
        debug=True,
        use_reloader=True
    )
