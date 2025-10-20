## Running the Project with Docker

This project provides a Docker setup for streamlined development and deployment. The application is containerized using Python 3.11 (slim) and leverages a virtual environment for dependency management. The default exposed port is **8000**.

### Requirements
- **Python version:** 3.11 (slim)
- **Dependencies:** All Python dependencies are installed from `requirements.txt` inside a virtual environment (`.venv`).
- **Environment Variables:**
  - The application supports multiple environment files: `.env`, `.env.development`, `.env.production`, and `environment.env`. Specify the appropriate file via the `env_file` option in `docker-compose.yml` if needed.

### Build and Run Instructions
1. **Build and start the application:**
   ```bash
   docker compose up --build
   ```
   This will build the image and start the `python-app` service, exposing port **8000**.

2. **Environment Configuration:**
   - By default, no environment file is loaded. To use a specific environment file, uncomment and set the `env_file` option in `docker-compose.yml`:
     ```yaml
     env_file: ./.env
     ```
   - Ensure your environment file contains all required variables for your application.

3. **Ports:**
   - The application is accessible on **localhost:8000**.
   - If you add external services (e.g., PostgreSQL), configure their ports and dependencies in `docker-compose.yml`.

### Special Configuration
- The Dockerfile creates a non-root user (`appuser`) for running the application securely.
- All dependencies are installed in an isolated `.venv` directory.
- If you need to add external services (e.g., a database), refer to the commented sections in `docker-compose.yml` for guidance.

---

*Ensure you have Docker and Docker Compose installed on your system before proceeding. For advanced configuration, review the provided Dockerfile and `docker-compose.yml` for additional options.*
