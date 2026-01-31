# Deployment Guide: Financial Analysis Agent on Render

This guide outlines the steps to deploy your application to Render.com using the provided Docker configuration.

## Prerequisites
1.  **GitHub Repository**: Ensure your code is pushed to a GitHub repository.
2.  **Render Account**: Sign up at [dashboard.render.com](https://dashboard.render.com/).

## Step 1: Push Code to GitHub
Make sure all your recent changes (Dockerfiles, `render.yaml`, `nginx.conf.template`) are committed and pushed.

```bash
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

## Step 2: Deploy using Blueprint

1.  Log in to the [Render Dashboard](https://dashboard.render.com/).
2.  Click **New +** and select **Blueprint**.
3.  Connect your GitHub repository.
4.  Render will automatically detect the `render.yaml` file.
5.  It will ask you to approve the services:
    *   **financial-agent-backend**: The Django backend (Docker).
    *   **financial-agent-frontend**: The React frontend (Docker).
6.  Click **Apply** or **Create Services**.

## Step 3: Configuration (Environment Variables)

The `render.yaml` sets up most defaults, but for security, some keys were not committed. You need to add them in the Render Dashboard if they are not hardcoded in your app.

1.  Go to the **financial-agent-backend** service in the dashboard.
2.  Click **Environment**.
3.  Add the following keys if they are not already present in your code:
    *   `GROQ_API_KEY`: Your Groq API key.
    *   `QDRANT_API_KEY`: Your Qdrant API Key.
    *   `QDRANT_URL`: Your Qdrant Cluster URL.
    *   `OPENAI_API_KEY`: (If used anywhere else).

## Step 4: Verify Deployment

1.  Wait for the builds to finish. The frontend build might take a few minutes.
2.  Once deployed, Render will provide a URL for the frontend (e.g., `https://financial-agent-frontend.onrender.com`).
3.  Visit the URL.
4.  **Test**: Upload a PDF and ask a question.

### Troubleshooting
*   **WebSocket Errors**: If real-time updates fail, ensure the frontend is correctly pointing to the backend. The `nginx.conf.template` should handle this automatically using the `REACT_APP_API_URL` injected by Render.
*   **Build Failures**: Check the logs in the Render dashboard. Common issues include missing dependencies in `requirements.txt` or Docker context issues (which we fixed).
